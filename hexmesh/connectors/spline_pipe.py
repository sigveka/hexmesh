"""
SplinePipe connector — hex pipe following a cubic spline through 3D waypoints.

Approach (Path A)
-----------------
Rather than extruding along a spline (which GMSH cannot do for structured hex
meshes), we build N+1 planar OH cross-sections at arc-length-uniform stations
along the spline and connect consecutive station pairs with transfinite hex
slabs using the same _connect_layer machinery as Reducer/Expander.

The spline is a SciPy CubicSpline with a clamped boundary condition at the
inlet so that the tangent at station 0 matches cursor.direction exactly.

Cross-section orientations are propagated by a parallel-transport (Bishop)
frame: given tangent T_i at station i, the (h, v) pair is rotated from the
previous frame by the minimal rotation that takes T_{i-1} → T_i.  This
eliminates unnecessary twist along the pipe.

Usage
-----
    net.add(SplinePipe(
        waypoints  = [[0,0,0], [0,0.1,0.05], [0.1,0.2,0]],
        n_stations = 10,   # cross-section planes (not counting inlet)
        n_layers   = 2,    # hex layers per slab
    ))

Notes
-----
- ``waypoints`` must have at least 2 entries.  The first waypoint should
  coincide with the cursor position; if it doesn't, the spline is shifted so
  station 0 starts at cursor.position.
- Equal-nang, equal-spec requirement: all layers must be CircleShape (same as
  MiterBend / Reducer). Square-shell layers are not supported.
- The resulting cross-sections are not re-used for transfinite extrusion; each
  slab is built with _connect_layer (ruled side-surfaces + addVolume).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import gmsh

from ..core.cross_section import CrossSection, LayeredCrossSection
from ..core.cursor import Cursor
from ..core.region import RegionSet
from .base import SegmentResult
from ..faces.oh_circle import build_oh_circle
from ..faces.annulus import build_annulus
from .fittings import _connect_layer

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Internal geometry helpers
# ---------------------------------------------------------------------------


def _rodrigues(v: np.ndarray, axis: np.ndarray, angle: float) -> np.ndarray:
    """Rotate vector *v* around *axis* by *angle* (radians) — Rodrigues formula."""
    c, s = np.cos(angle), np.sin(angle)
    axis = axis / np.linalg.norm(axis)
    return v * c + np.cross(axis, v) * s + axis * np.dot(axis, v) * (1 - c)


def _sample_spline(
    waypoints: list,
    n_stations: int,
    tangent_0: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Fit a cubic spline through *waypoints* and sample arc-length-uniform stations.

    The spline tangent at the first waypoint is clamped to *tangent_0* so that
    the pipe enters the spline smoothly from the current cursor direction.

    Parameters
    ----------
    waypoints : list of array-like, shape (M, 3)
        Control points.  M >= 2.
    n_stations : int
        Number of output stations (not counting the inlet at t=0).
    tangent_0 : ndarray, shape (3,)
        Unit tangent vector at the first waypoint (= cursor.direction).

    Returns
    -------
    positions : ndarray, shape (n_stations+1, 3)
        Station positions along the spline (station 0 = waypoints[0]).
    tangents : ndarray, shape (n_stations+1, 3)
        Unit tangent vectors at each station.
    """
    from scipy.interpolate import CubicSpline

    pts = np.asarray(waypoints, dtype=float)
    if pts.shape[0] < 2:
        raise ValueError("SplinePipe requires at least 2 waypoints.")

    # Parameterise by chord length (good initial guess for arc-length)
    diffs = np.diff(pts, axis=0)
    chord_lens = np.linalg.norm(diffs, axis=1)
    t_knots = np.concatenate([[0.0], np.cumsum(chord_lens)])

    # Clamped BC at start: derivative = tangent_0 scaled to dt/ds at first knot
    # CubicSpline bc_type=((1, dy/dt), ...) — derivative is w.r.t. parameter t,
    # not arc length.  We want ds/dt ≈ chord_lens[0] at the first interior span,
    # so scale the unit tangent by the parameter step.
    dt0 = t_knots[1] - t_knots[0]
    bc_start = (1, tangent_0 * dt0)   # first derivative at t[0]
    bc_end   = (2, np.zeros(3))        # second derivative = 0 (natural end)

    cs = CubicSpline(t_knots, pts, bc_type=(bc_start, bc_end))

    # Dense sampling for arc-length reparameterisation
    n_dense = max(1000, n_stations * 50)
    t_dense = np.linspace(t_knots[0], t_knots[-1], n_dense)
    dp_dt   = cs(t_dense, 1)            # derivative w.r.t. t
    ds_dt   = np.linalg.norm(dp_dt, axis=1)

    # Cumulative arc length via trapezoidal integration
    dt_arr  = np.diff(t_dense)
    ds_arr  = 0.5 * (ds_dt[:-1] + ds_dt[1:]) * dt_arr
    s_dense = np.concatenate([[0.0], np.cumsum(ds_arr)])
    total_s = s_dense[-1]

    # Arc-length-uniform station parameter values
    s_uniform = np.linspace(0.0, total_s, n_stations + 1)
    t_uniform = np.interp(s_uniform, s_dense, t_dense)

    positions = cs(t_uniform)                # shape (n_stations+1, 3)
    deriv_raw = cs(t_uniform, 1)             # shape (n_stations+1, 3)
    norms = np.linalg.norm(deriv_raw, axis=1, keepdims=True)
    tangents = deriv_raw / np.maximum(norms, 1e-12)

    return positions, tangents


def _bishop_frames(
    positions: np.ndarray,
    tangents:  np.ndarray,
    h0: np.ndarray,
    v0: np.ndarray,
) -> list[dict]:
    """Parallel-transport (Bishop) frame along the spline.

    Starting from (h0, v0) at station 0, each subsequent frame is obtained by
    rotating the previous (h, v) pair by the minimal rotation that takes
    T_{i-1} → T_i (Rodrigues rotation about their cross product axis).

    Parameters
    ----------
    positions, tangents : ndarray, shape (N, 3)
    h0, v0 : ndarray, shape (3,)
        Initial horizontal and vertical unit vectors (= cursor.right, cursor.up).

    Returns
    -------
    list of dict, length N, each with keys:
        'pos' : ndarray(3,)  — position
        'T'   : ndarray(3,)  — unit tangent
        'h'   : ndarray(3,)  — unit horizontal (right) vector
        'v'   : ndarray(3,)  — unit vertical (up) vector
    """
    N = len(positions)
    frames = []
    h, v = h0.copy(), v0.copy()

    for i in range(N):
        T = tangents[i]
        frames.append({'pos': positions[i], 'T': T, 'h': h, 'v': v})

        if i < N - 1:
            T_next = tangents[i + 1]
            axis   = np.cross(T, T_next)
            sin_a  = np.linalg.norm(axis)
            cos_a  = np.dot(T, T_next)
            if sin_a > 1e-10:
                axis  = axis / sin_a
                angle = math.atan2(sin_a, cos_a)
                h = _rodrigues(h, axis, angle)
                v = _rodrigues(v, axis, angle)
            # else: tangents are parallel — no rotation needed
            # Re-orthogonalise h and v against T_next for numerical stability
            T_next_n = T_next / np.linalg.norm(T_next)
            h = h - np.dot(h, T_next_n) * T_next_n
            h_n = np.linalg.norm(h)
            if h_n < 1e-10:
                # Degenerate — pick an arbitrary perpendicular
                candidate = np.array([1.0, 0.0, 0.0])
                if abs(np.dot(T_next_n, candidate)) > 0.9:
                    candidate = np.array([0.0, 1.0, 0.0])
                h = np.cross(T_next_n, candidate)
                h = h / np.linalg.norm(h)
            else:
                h = h / h_n
            v = np.cross(h, T_next_n)
            v = v / np.linalg.norm(v)

    return frames


def _build_station_lcs(
    pos:    np.ndarray,
    h_axis: np.ndarray,
    v_axis: np.ndarray,
    inlet:  LayeredCrossSection,
) -> LayeredCrossSection:
    """Build a fresh LayeredCrossSection at *pos* matching the inlet spec.

    Geometry parameters (radii, nang, nrad, lc) are read from each inlet
    layer; a new OH cross-section (core + annuli) is built in the plane
    perpendicular to (h_axis × v_axis) = the pipe tangent at this station.
    """
    from ..core.shape import CircleShape

    cx, cy, cz = float(pos[0]), float(pos[1]), float(pos[2])
    lc = inlet.innermost.lc

    layers_out: list[tuple[str, CrossSection]] = []
    prev_cs_out: CrossSection | None = None

    for i, (name, cs) in enumerate(inlet.layers):
        if not isinstance(cs.shape, CircleShape):
            raise NotImplementedError(
                f"SplinePipe only supports CircleShape layers; "
                f"layer '{name}' has {type(cs.shape).__name__}."
            )
        nrad = cs.nrad
        if i == 0:
            cs_out = build_oh_circle(
                cx=cx, cy=cy, cz=cz,
                shape=cs.shape,
                h_axis=h_axis, v_axis=v_axis,
                lc=lc, nrad=nrad,
            )
        else:
            prev_in = inlet.layers[i - 1][1]
            dR = cs.shape.radius - prev_in.shape.radius
            cs_out = build_annulus(
                inner=prev_cs_out, dR=dR, lc=lc, nrad=nrad,
            )
        layers_out.append((name, cs_out))
        prev_cs_out = cs_out

    return LayeredCrossSection(layers_out)


# ---------------------------------------------------------------------------
# SplinePipe connector
# ---------------------------------------------------------------------------


@dataclass
class SplinePipe:
    """Hex pipe following a cubic spline through 3D waypoints.

    Parameters
    ----------
    waypoints : list of array-like, shape (M, 3)
        Points the pipe must pass through.  The first waypoint should be at
        (or near) the current cursor position; the spline is clamped to
        ``cursor.direction`` at the entry point.
    n_stations : int
        Number of cross-section planes along the spline (not counting the inlet
        at station 0).  More stations → smoother bends but more hex cells.
    n_layers : int
        Hex layers per slab (between consecutive station pairs).
    """

    waypoints:  list
    n_stations: int = 20
    n_layers:   int = 1

    def __post_init__(self) -> None:
        if len(self.waypoints) < 2:
            raise ValueError("SplinePipe requires at least 2 waypoints.")
        if self.n_stations < 1:
            raise ValueError("SplinePipe.n_stations must be >= 1.")
        if self.n_layers < 1:
            raise ValueError("SplinePipe.n_layers must be >= 1.")

    def connect(
        self,
        inlet:  LayeredCrossSection,
        cursor: Cursor,
    ) -> SegmentResult:
        """Build all hex slabs along the spline and return a SegmentResult."""

        # ------------------------------------------------------------------
        # 1. Fit spline and compute stations
        # ------------------------------------------------------------------
        waypoints = [np.asarray(w, dtype=float) for w in self.waypoints]

        # Shift waypoints so the first one aligns with cursor.position
        offset = cursor.position - waypoints[0]
        if np.linalg.norm(offset) > 1e-10:
            waypoints = [w + offset for w in waypoints]

        positions, tangents = _sample_spline(
            waypoints, self.n_stations, cursor.direction
        )

        # ------------------------------------------------------------------
        # 2. Compute Bishop frames (parallel-transport)
        # ------------------------------------------------------------------
        frames = _bishop_frames(positions, tangents, cursor.right, cursor.up)

        # ------------------------------------------------------------------
        # 3. Build outlet cross-sections at stations 1..n_stations
        #    Station 0 = inlet (already exists)
        # ------------------------------------------------------------------
        # Synchronize first so inlet surfaces are queryable
        gmsh.model.occ.synchronize()

        station_lcs: list[LayeredCrossSection] = [inlet]
        for i in range(1, self.n_stations + 1):
            fr = frames[i]
            lcs = _build_station_lcs(fr['pos'], fr['h'], fr['v'], inlet)
            station_lcs.append(lcs)

        # Synchronize once so all station cross-sections are in the model
        # before _connect_layer (which calls _extract_geom via getBoundary)
        gmsh.model.occ.synchronize()

        # ------------------------------------------------------------------
        # 4. Connect consecutive stations with transfinite hex slabs
        # ------------------------------------------------------------------
        regions:    dict[str, RegionSet]   = {}
        interfaces: dict[str, list[int]]  = {}
        iface_names = inlet.interface_names()

        all_deferred_curves:  list[int]             = []
        all_deferred_arc_cvs: list[tuple[int, int]] = []
        all_deferred_surfaces: list[int]            = []
        all_deferred_volumes:  list[int]            = []

        for slab_idx in range(self.n_stations):
            in_lcs  = station_lcs[slab_idx]
            out_lcs = station_lcs[slab_idx + 1]

            prev_outer_axial:      list[int] | None = None
            prev_outer_side_surfs: list[int] | None = None

            for layer_idx, ((in_name, in_cs), (out_name, out_cs)) in enumerate(
                zip(in_lcs.layers, out_lcs.layers)
            ):
                vols, outer_side_surfs, outer_axial, deferred = _connect_layer(
                    in_cs, out_cs, self.n_layers,
                    prev_outer_axial=prev_outer_axial,
                    prev_outer_side_surfs=prev_outer_side_surfs,
                    planar_radial=False,
                )
                all_deferred_curves.extend(deferred["curves"])
                all_deferred_arc_cvs.extend(deferred.get("arc_curves", []))
                all_deferred_surfaces.extend(deferred["surfaces"])
                all_deferred_volumes.extend(deferred["volumes"])

                # Accumulate per-material regions
                if in_name not in regions:
                    regions[in_name] = RegionSet(
                        inlets = list(in_cs.surfaces) if slab_idx == 0 else [],
                    )
                regions[in_name].volumes.extend(vols)
                regions[in_name].walls.extend(outer_side_surfs)
                if slab_idx == self.n_stations - 1:
                    regions[in_name].outlets.extend(list(out_cs.surfaces))

                # Interfaces (inner-layer shared surfaces) — only from first slab
                if slab_idx == 0 and prev_outer_side_surfs is not None:
                    iface_idx = layer_idx - 1
                    if iface_idx < len(iface_names):
                        iname = iface_names[iface_idx]
                        interfaces.setdefault(iname, []).extend(prev_outer_side_surfs)

                prev_outer_axial      = outer_axial
                prev_outer_side_surfs = outer_side_surfs

        # ------------------------------------------------------------------
        # 5. Final synchronize
        # ------------------------------------------------------------------
        gmsh.model.occ.synchronize()

        # ------------------------------------------------------------------
        # 6. Deduplicate deferred mesh constraints
        # ------------------------------------------------------------------
        seen_s: set[int] = set()
        unique_surfaces: list[int] = []
        for s in all_deferred_surfaces:
            if s not in seen_s:
                seen_s.add(s)
                unique_surfaces.append(s)

        seen_a: set[int] = set()
        unique_arc_cvs: list[tuple[int, int]] = []
        for tag, n in all_deferred_arc_cvs:
            if tag not in seen_a:
                seen_a.add(tag)
                unique_arc_cvs.append((tag, n))

        # ------------------------------------------------------------------
        # 7. Build end cursor from last Bishop frame
        # ------------------------------------------------------------------
        last_fr = frames[self.n_stations]
        end_cursor = Cursor(
            position  = last_fr['pos'],
            direction = last_fr['T'],
            up        = last_fr['v'],
        )

        return SegmentResult(
            end_face   = station_lcs[-1],
            end_cursor = end_cursor,
            regions    = regions,
            interfaces = interfaces,
            deferred_mesh = {
                "curves":   [(L, self.n_layers + 1) for L in all_deferred_curves]
                            + unique_arc_cvs,
                "surfaces": unique_surfaces,
                "volumes":  all_deferred_volumes,
            },
        )
