"""
Bend, MiterBend, and Elbow connectors.

Industry context
----------------
In piping engineering the terms *bend* and *elbow* have distinct meanings:

Elbow (ASME B16.9 / B16.28)
    Factory-made standard fitting.  Fixed angles (45°, 90°, 180°).
    Two standard radius classes:

    ======  ========================  ========================
    Class   Centreline radius R        Common use
    ======  ========================  ========================
    Short   R = 1D  = 2 × R_pipe      Compact, higher ΔP
    Long    R = 1.5D = 3 × R_pipe     General piping (default)
    ======  ========================  ========================

    *D* is the nominal pipe diameter ≈ 2 × R_pipe (outer radius).
    Long radius is the more common choice in process piping.

Pipe Bend (custom / field-fabricated)
    Any angle.  Centreline radius typically 3D–5D or larger.
    Smoother flow profile, lower pressure drop, more space required.

Miter elbow
    Zero-radius abrupt turn built from flat cuts.  Used in HVAC and
    low-pressure ductwork.

This module
-----------

Bend
    General smooth bend.  Accepts either an absolute ``radius`` (m) or a
    ``radius_factor`` × D convenience shorthand.  Corresponds to the
    industry *pipe bend* or *elbow* depending on the chosen radius.

Elbow
    Convenience wrapper that fixes the angle and picks the centreline
    radius from a ``schedule`` string ("short" → 1D, "long" → 1.5D).
    Corresponds directly to the ASME short- and long-radius elbow.

MiterBend
    Abrupt direction change modelling a mitered pipe joint.

After Bend / Elbow:
  - cursor.position  advances to the new end-face centre
  - cursor.direction rotates by ``angle`` around the bend axis
  - cursor.up        rotates by the same amount (frame preserved)

After MiterBend:
  - cursor.position  unchanged (zero-radius miter)
  - cursor.direction rotates by ``angle``
  - cursor.up        rotates by the same amount (frame preserved)
"""

from __future__ import annotations
from dataclasses import dataclass
import math

import numpy as np
import gmsh

from ..core.cross_section import CrossSection, LayeredCrossSection, BoundaryType
from ..core.cursor import Cursor, _rodrigues
from ..core.region import RegionSet
from .base import Connector, SegmentResult


@dataclass
class Bend:
    """Smooth rotational-extrusion bend — the general pipe *bend* primitive.

    The centreline bend radius can be specified in two ways:

    * Absolute: ``radius=0.15``  (metres; must be > R_pipe)
    * D-multiple: ``radius_factor=3.0``  → R = 3D = 6 × R_pipe

    Industry reference radii
    ------------------------
    ===============  =================  =============================
    radius_factor    Industry name       Typical use
    ===============  =================  =============================
    1.0              Short-radius elbow  Compact spaces (ASME B16.9)
    1.5              Long-radius elbow   General process piping
    3.0–5.0          Pipe bend (3D–5D)   Low-pressure, smooth flow
    ===============  =================  =============================

    For fixed ASME angles (45°, 90°, 180°) with SR/LR the ``Elbow``
    convenience class is more expressive than this one.

    Parameters
    ----------
    radius : float, optional
        Absolute centreline bend radius [m].  Exactly one of *radius* or
        *radius_factor* must be supplied.
    radius_factor : float, optional
        Centreline radius as a multiple of the pipe outer diameter D
        (D = 2 × R_outer).  Computed from the inlet spec at connect time.
    angle : float
        Bend angle in **degrees** (positive = CCW when viewed along
        ``cursor.right``).  Any value; 45, 90, 180 are standard.
    n_layers : int
        Number of hex layers along the arc.
    roll : float
        Rotation of the bend plane around the pipe axis, in **degrees**.
        ``0`` (default) bends in the ``cursor.up`` plane.
    """

    REQUIRED_BOUNDARY_TYPE = BoundaryType.CIRCULAR

    angle:         float
    n_layers:      int
    radius:        float | None = None
    radius_factor: float | None = None
    roll:          float        = 0.0

    def __post_init__(self) -> None:
        if (self.radius is None) == (self.radius_factor is None):
            raise ValueError(
                "Bend: supply exactly one of 'radius' or 'radius_factor'."
            )
        if self.radius is not None and self.radius <= 0:
            raise ValueError(f"Bend.radius must be positive, got {self.radius!r}")
        if self.radius_factor is not None and self.radius_factor <= 0:
            raise ValueError(
                f"Bend.radius_factor must be positive, got {self.radius_factor!r}"
            )
        if self.n_layers < 1:
            raise ValueError(f"Bend.n_layers must be >= 1, got {self.n_layers!r}")

    def _resolve_radius(self, inlet: LayeredCrossSection) -> float:
        """Return the absolute centreline bend radius [m]."""
        if self.radius is not None:
            return self.radius
        R_outer = inlet.outermost.shape.radius
        D = 2.0 * R_outer
        return self.radius_factor * D

    def connect(
        self,
        inlet:  LayeredCrossSection,
        cursor: Cursor,
    ) -> SegmentResult:
        radius    = self._resolve_radius(inlet)
        angle_rad = math.radians(self.angle)

        # Roll rotates the bend plane around the pipe axis.
        # roll=0: bend in cursor.up direction (default, "turns upward").
        # roll=90: bend in cursor.right direction ("turns sideways").
        φ = math.radians(self.roll)
        bend_axis   = math.cos(φ) * cursor.right - math.sin(φ) * cursor.up
        bend_centre = cursor.position + radius * (
            math.cos(φ) * cursor.up + math.sin(φ) * cursor.right
        )

        # GMSH rotational extrusion: Extrude { {ax,ay,az}, {px,py,pz}, angle }
        ax, ay, az = bend_axis.tolist()
        px, py, pz = bend_centre.tolist()

        # Compute end cursor before the layer loop so its frame vectors are
        # available for the end CrossSection axes.
        end_cursor = Cursor(
            position  = _new_position(cursor, bend_centre, bend_axis, angle_rad),
            direction = _rodrigues(cursor.direction, bend_axis, angle_rad),
            up        = _rodrigues(cursor.up,        bend_axis, angle_rad),
        )
        end_h_axis = end_cursor.right
        end_v_axis = end_cursor.up

        regions:    dict[str, RegionSet]  = {}
        interfaces: dict[str, list[int]] = {}
        end_layers: list[tuple[str, CrossSection]] = []
        prev_outer_walls: list[int] | None = None
        iface_names = inlet.interface_names()

        # Revolve ALL patches from ALL layers in a single OCC call so that
        # shared boundary curves (core outer arcs = annulus inner arcs) produce
        # one shared set of outlet corner points — no duplicate coincident entities.
        _bend_c = np.asarray([px, py, pz], dtype=float)
        _bend_a = np.asarray([ax, ay, az], dtype=float)

        all_dimtags: list[tuple[int, int]] = []
        layer_surf_counts: list[int] = []
        for _, cs in inlet:
            all_dimtags.extend((2, s) for s in cs.surfaces)
            layer_surf_counts.append(len(cs.surfaces))

        _out_rev = gmsh.model.occ.revolve(
            all_dimtags,
            px, py, pz, ax, ay, az, angle_rad,
            numElements=[self.n_layers], recombine=True,
        )
        gmsh.model.occ.synchronize()

        all_vols = [tag for dim, tag in _out_rev if dim == 3]
        all_inlet_set = set(s for _, cs in inlet for s in cs.surfaces)

        vol_offset = 0

        for idx, (name, cs) in enumerate(inlet):
            is_core  = (len(cs.surfaces) == cs.n_outer + 1)
            vols, outer_walls, inner_walls, intra_walls, end_surfaces = \
                [], [], [], [], []

            n_surfs   = layer_surf_counts[idx]
            _vols_all = all_vols[vol_offset:vol_offset + n_surfs]
            vol_offset += n_surfs

            _pc = np.array([cs.cx, cs.cy, cs.cz], dtype=float)
            _pa = cursor.direction

            def _mxr(st: int) -> float:
                bb = gmsh.model.getBoundingBox(2, st)
                rm = 0.0
                for _bx in (bb[0], bb[3]):
                    for _by in (bb[1], bb[4]):
                        for _bz in (bb[2], bb[5]):
                            p = np.array([_bx, _by, _bz])
                            t = float(np.dot(p - _pc, _pa))
                            rm = max(rm, float(np.linalg.norm(p - _pc - t * _pa)))
                return rm

            for i, (vol, surf_in) in enumerate(zip(_vols_all, cs.surfaces)):
                bnd_surfs = [
                    t for d, t in
                    gmsh.model.getBoundary([(3, vol)], oriented=False)
                    if d == 2
                ]
                bb_in = gmsh.model.getBoundingBox(2, surf_in)
                in_c  = np.array([
                    (bb_in[0]+bb_in[3])/2,
                    (bb_in[1]+bb_in[4])/2,
                    (bb_in[2]+bb_in[5])/2,
                ])
                exp_c = _bend_c + _rodrigues(in_c - _bend_c, _bend_a, angle_rad)

                end_face = None
                for s in bnd_surfs:
                    if s in all_inlet_set:
                        continue
                    bb_s = gmsh.model.getBoundingBox(2, s)
                    sc = np.array([
                        (bb_s[0]+bb_s[3])/2,
                        (bb_s[1]+bb_s[4])/2,
                        (bb_s[2]+bb_s[5])/2,
                    ])
                    if float(np.dot(sc - exp_c, sc - exp_c)) < 1e-10:
                        end_face = s
                        break
                if end_face is None:
                    raise RuntimeError(
                        f"Bend: cannot identify end-face for vol {vol} patch {i}"
                    )

                end_surfaces.append(end_face)
                vols.append(vol)

                laterals = [
                    s for s in bnd_surfs if s not in all_inlet_set and s != end_face
                ]

                if is_core and i == 0:
                    inner_walls.extend(laterals)
                elif is_core:
                    outer_lat = max(laterals, key=_mxr)
                    outer_walls.append(outer_lat)
                    intra_walls.extend(s for s in laterals if s != outer_lat)
                else:
                    sorted_lats = sorted(laterals, key=_mxr)
                    inner_walls.append(sorted_lats[0])
                    outer_walls.append(sorted_lats[-1])
                    intra_walls.extend(sorted_lats[1:-1])

            regions[name] = RegionSet(
                volumes = vols,
                inlets  = list(cs.surfaces),
                outlets = end_surfaces,
                walls   = outer_walls,
            )

            if prev_outer_walls is not None and idx - 1 < len(iface_names):
                interfaces[iface_names[idx - 1]] = prev_outer_walls
            prev_outer_walls = outer_walls

            end_cs = CrossSection(
                surfaces      = end_surfaces,
                center        = cs.center,
                outer_points  = cs.outer_points,
                outer_curves  = cs.outer_curves,
                shape         = cs.shape,
                boundary_type = cs.boundary_type,
                h_axis        = end_h_axis,
                v_axis        = end_v_axis,
                cx=cs.cx, cy=cs.cy, cz=cs.cz,
                inner_points  = list(cs.inner_points),
                inner_curves  = list(cs.inner_curves),
                radial_curves = list(cs.radial_curves),
                nrad          = cs.nrad,
                lc            = cs.lc,
            )
            end_layers.append((name, end_cs))

        return SegmentResult(
            end_face   = LayeredCrossSection(end_layers),
            end_cursor = end_cursor,
            regions    = regions,
            interfaces = interfaces,
        )


@dataclass
class MiterBend:
    """Instantaneous direction change — models a mitered pipe joint.

    Uses rotational extrusion (gmsh revolve) with ``n_layers=1`` around the
    current cursor position to produce valid non-degenerate hex cells at the
    joint.  This is equivalent to a zero-radius Bend with a single layer —
    the cells are arc-swept rather than flat-cut, but are topologically and
    geometrically valid for any angle including 90°.

    For multi-cut miters (N equal cuts approximating a smooth elbow), chain
    Straight + MiterBend N times as usual.

    Parameters
    ----------
    angle : float
        Change of direction in **degrees**.  Positive rotates the pipe
        in the bend plane (cursor.direction × cursor.up).
    roll : float
        Rotation of the bend plane around the pipe axis, in **degrees**.
        ``0`` (default) bends left/right in the horizontal plane (around
        ``cursor.up``).  ``90`` bends up/down (around ``cursor.right``).
        Any intermediate angle is supported.
    n_layers : int
        Revolution layers in the corner cell block (default 1).

    Examples
    --------
    Single 90° miter::

        net.add(Straight(1.0, n_layers=10))
        net.add(MiterBend(angle=90))
        net.add(Straight(1.0, n_layers=10))

    3-cut miter approximating a 90° elbow::

        for _ in range(3):
            net.add(Straight(0.2, n_layers=3))
            net.add(MiterBend(angle=30))
        net.add(Straight(0.2, n_layers=3))
    """

    REQUIRED_BOUNDARY_TYPE = BoundaryType.CIRCULAR

    angle:    float
    roll:     float = 0.0
    n_layers: int   = 1

    def __post_init__(self) -> None:
        if not math.isfinite(self.roll):
            raise ValueError(
                f"MiterBend.roll must be a finite number, got {self.roll!r}."
            )
        if self.n_layers < 1:
            raise ValueError(
                f"MiterBend.n_layers must be >= 1, got {self.n_layers!r}."
            )

    # Maximum single-cut angle that gives zero bad cells for an OH-circle
    # cross-section with the 0.15 × r_pipe lateral axis offset.
    _MAX_SINGLE_CUT_DEG: float = 30.0

    def connect(
        self,
        inlet:  LayeredCrossSection,
        cursor: Cursor,
    ) -> SegmentResult:
        """Rotational extrusion modelling a mitered pipe joint.

        For ``|angle| > 30°`` the bend is automatically subdivided into
        equal sub-cuts of ≤ 30° so that every revolve produces valid,
        non-inverted hex cells regardless of the total bend angle.

        Uses ``gmsh.model.geo.revolve`` with a small lateral axis offset
        (0.15 × r_pipe) so the rotation axis does not pass through the
        inlet face centre — this avoids the degenerate (zero-volume) hex
        cells that a true zero-radius revolve would produce.
        """
        n_sub = max(1, math.ceil(abs(self.angle) / self._MAX_SINGLE_CUT_DEG))
        if n_sub == 1:
            return self._single_cut(inlet, cursor)

        sub_angle = self.angle / n_sub
        sub_bend  = MiterBend(angle=sub_angle, roll=self.roll,
                              n_layers=self.n_layers)

        results: list[SegmentResult] = []
        cur_inlet  = inlet
        cur_cursor = cursor
        for _ in range(n_sub):
            r = sub_bend._single_cut(cur_inlet, cur_cursor)
            results.append(r)
            cur_inlet  = r.end_face
            cur_cursor = r.end_cursor

        return _merge_segment_results(results)

    def _single_cut(
        self,
        inlet:  LayeredCrossSection,
        cursor: Cursor,
    ) -> SegmentResult:
        """One revolve sub-step — |angle| must be ≤ 30° for good quality."""
        angle_rad = math.radians(self.angle)

        # Lateral axis offset of 1.01 × max_extent empirically gives zero bad
        # cells for |angle| ≤ 30°.  The axis is placed just outside the outer
        # pipe boundary; the nearest inlet face point sits only 0.01 × extent
        # from the axis, giving a small but non-zero arc sweep.
        outer_cs = inlet.outermost
        radius   = outer_cs.shape.max_extent * 1.01

        φ = math.radians(self.roll)
        bend_axis   = math.cos(φ) * cursor.up   + math.sin(φ) * cursor.right
        bend_centre = cursor.position - radius * (math.cos(φ) * cursor.right
                                                   - math.sin(φ) * cursor.up)

        ax, ay, az = bend_axis.tolist()
        px, py, pz = bend_centre.tolist()

        end_cursor = Cursor(
            position  = _new_position(cursor, bend_centre, bend_axis, angle_rad),
            direction = _rodrigues(cursor.direction, bend_axis, angle_rad),
            up        = _rodrigues(cursor.up,        bend_axis, angle_rad),
        )
        end_h_axis = end_cursor.right
        end_v_axis = end_cursor.up

        regions:    dict[str, RegionSet]  = {}
        interfaces: dict[str, list[int]] = {}
        end_layers: list[tuple[str, CrossSection]] = []
        prev_outer_walls: list[int] | None = None
        iface_names = inlet.interface_names()

        # Revolve ALL patches from ALL layers in a single OCC call so that
        # shared boundary curves (core outer arcs = annulus inner arcs) produce
        # one shared set of outlet corner points — no duplicate coincident entities.
        _bend_c = np.asarray([px, py, pz], dtype=float)
        _bend_a = np.asarray([ax, ay, az], dtype=float)

        all_dimtags: list[tuple[int, int]] = []
        layer_surf_counts: list[int] = []
        for _, cs in inlet:
            all_dimtags.extend((2, s) for s in cs.surfaces)
            layer_surf_counts.append(len(cs.surfaces))

        _out_rev = gmsh.model.occ.revolve(
            all_dimtags,
            px, py, pz, ax, ay, az, angle_rad,
            numElements=[self.n_layers], recombine=True,
        )
        gmsh.model.occ.synchronize()

        all_vols = [tag for dim, tag in _out_rev if dim == 3]
        all_inlet_set = set(s for _, cs in inlet for s in cs.surfaces)

        vol_offset = 0

        for idx, (name, cs) in enumerate(inlet):
            is_core  = (len(cs.surfaces) == cs.n_outer + 1)
            vols, outer_walls, inner_walls, intra_walls, end_surfaces = \
                [], [], [], [], []

            n_surfs   = layer_surf_counts[idx]
            _vols_all = all_vols[vol_offset:vol_offset + n_surfs]
            vol_offset += n_surfs

            _pc = np.array([cs.cx, cs.cy, cs.cz], dtype=float)
            _pa = cursor.direction

            def _mxr(st: int) -> float:
                bb = gmsh.model.getBoundingBox(2, st)
                rm = 0.0
                for _bx in (bb[0], bb[3]):
                    for _by in (bb[1], bb[4]):
                        for _bz in (bb[2], bb[5]):
                            p = np.array([_bx, _by, _bz])
                            t = float(np.dot(p - _pc, _pa))
                            rm = max(rm, float(np.linalg.norm(p - _pc - t * _pa)))
                return rm

            for i, (vol, surf_in) in enumerate(zip(_vols_all, cs.surfaces)):
                bnd_surfs = [
                    t for d, t in
                    gmsh.model.getBoundary([(3, vol)], oriented=False)
                    if d == 2
                ]
                bb_in = gmsh.model.getBoundingBox(2, surf_in)
                in_c  = np.array([
                    (bb_in[0]+bb_in[3])/2,
                    (bb_in[1]+bb_in[4])/2,
                    (bb_in[2]+bb_in[5])/2,
                ])
                exp_c = _bend_c + _rodrigues(in_c - _bend_c, _bend_a, angle_rad)

                end_face = None
                for s in bnd_surfs:
                    if s in all_inlet_set:
                        continue
                    bb_s = gmsh.model.getBoundingBox(2, s)
                    sc = np.array([
                        (bb_s[0]+bb_s[3])/2,
                        (bb_s[1]+bb_s[4])/2,
                        (bb_s[2]+bb_s[5])/2,
                    ])
                    if float(np.dot(sc - exp_c, sc - exp_c)) < 1e-10:
                        end_face = s
                        break
                if end_face is None:
                    raise RuntimeError(
                        f"Bend: cannot identify end-face for vol {vol} patch {i}"
                    )

                end_surfaces.append(end_face)
                vols.append(vol)

                laterals = [
                    s for s in bnd_surfs if s not in all_inlet_set and s != end_face
                ]

                if is_core and i == 0:
                    inner_walls.extend(laterals)
                elif is_core:
                    outer_lat = max(laterals, key=_mxr)
                    outer_walls.append(outer_lat)
                    intra_walls.extend(s for s in laterals if s != outer_lat)
                else:
                    sorted_lats = sorted(laterals, key=_mxr)
                    inner_walls.append(sorted_lats[0])
                    outer_walls.append(sorted_lats[-1])
                    intra_walls.extend(sorted_lats[1:-1])

            regions[name] = RegionSet(
                volumes = vols,
                inlets  = list(cs.surfaces),
                outlets = end_surfaces,
                walls   = outer_walls,
            )

            if prev_outer_walls is not None and idx - 1 < len(iface_names):
                interfaces[iface_names[idx - 1]] = prev_outer_walls
            prev_outer_walls = outer_walls

            end_cs = CrossSection(
                surfaces      = end_surfaces,
                center        = cs.center,
                outer_points  = cs.outer_points,
                outer_curves  = cs.outer_curves,
                shape         = cs.shape,
                boundary_type = cs.boundary_type,
                h_axis        = end_h_axis,
                v_axis        = end_v_axis,
                cx=cs.cx, cy=cs.cy, cz=cs.cz,
                inner_points  = list(cs.inner_points),
                inner_curves  = list(cs.inner_curves),
                radial_curves = list(cs.radial_curves),
                nrad          = cs.nrad,
                lc            = cs.lc,
            )
            end_layers.append((name, end_cs))

        return SegmentResult(
            end_face   = LayeredCrossSection(end_layers),
            end_cursor = end_cursor,
            regions    = regions,
            interfaces = interfaces,
        )


def _merge_segment_results(results: list[SegmentResult]) -> SegmentResult:
    """Combine a sequence of sub-bend SegmentResults into one."""
    # Volumes and walls accumulate; inlets come from first, outlets from last.
    all_names = list(results[0].regions.keys())
    merged_regions: dict[str, RegionSet] = {}
    for name in all_names:
        all_vols:  list[int] = []
        all_walls: list[int] = []
        for r in results:
            rs = r.regions[name]
            all_vols.extend(rs.volumes)
            all_walls.extend(rs.walls)
        merged_regions[name] = RegionSet(
            volumes = all_vols,
            inlets  = results[0].regions[name].inlets,
            outlets = results[-1].regions[name].outlets,
            walls   = all_walls,
        )

    merged_interfaces: dict[str, list[int]] = {}
    for r in results:
        for iface_name, surf_list in r.interfaces.items():
            merged_interfaces.setdefault(iface_name, []).extend(surf_list)

    return SegmentResult(
        end_face   = results[-1].end_face,
        end_cursor = results[-1].end_cursor,
        regions    = merged_regions,
        interfaces = merged_interfaces,
    )


# ---------------------------------------------------------------------------
# Elbow — ASME short / long radius convenience class
# ---------------------------------------------------------------------------

#: Centreline radius as a multiple of the pipe outer diameter D = 2·R_pipe.
_SCHEDULE_FACTORS: dict[str, float] = {
    "short": 1.0,    # R = 1D  (ASME B16.9 short radius)
    "long":  1.5,    # R = 1.5D (ASME B16.9 long radius — most common)
}


@dataclass
class Elbow:
    """Standard ASME short- or long-radius elbow.

    Corresponds to ASME B16.9 (butt-weld) and B16.28 (short-radius) factory
    fittings.  The centreline radius is derived automatically from the inlet
    pipe outer diameter:

    =========  =================  ======================================
    schedule   Centreline radius  Industry name
    =========  =================  ======================================
    ``"long"`` R = 1.5D           Long-radius elbow  (default, most common)
    ``"short"`` R = 1D            Short-radius elbow (compact installations)
    =========  =================  ======================================

    D = 2 × R_outer_pipe (outer diameter of the pipe cross-section).

    Parameters
    ----------
    angle : float
        Deflection angle in **degrees**.  Standard values: 45, 90, 180.
        Any angle is accepted.
    schedule : str
        ``"long"`` (default) or ``"short"``.
    n_layers : int
        Hex layers along the arc.  A higher value improves cell aspect
        ratio.  Suggested: 6–10 for 90° elbows.
    roll : float
        Rotation of the bend plane around the pipe axis in **degrees**.
        ``0`` (default) bends in the ``cursor.up`` plane.

    Examples
    --------
    Standard long-radius 90° elbow::

        net.add(Elbow(90))

    Short-radius 45° elbow turning sideways::

        net.add(Elbow(45, schedule="short", roll=90))

    Relationship to ``Bend``
    ------------------------
    ``Elbow(angle=90, schedule="long")`` is exactly equivalent to::

        Bend(radius_factor=1.5, angle=90, n_layers=...)

    Use ``Bend`` when you need a custom radius factor (e.g. 3D pipe bend).
    """

    REQUIRED_BOUNDARY_TYPE = BoundaryType.CIRCULAR

    angle:    float
    schedule: str   = "long"
    n_layers: int   = 8
    roll:     float = 0.0

    def __post_init__(self) -> None:
        if self.schedule not in _SCHEDULE_FACTORS:
            raise ValueError(
                f"Elbow.schedule must be 'short' or 'long', got {self.schedule!r}."
            )
        if self.n_layers < 1:
            raise ValueError(
                f"Elbow.n_layers must be >= 1, got {self.n_layers!r}."
            )

    def connect(
        self,
        inlet:  LayeredCrossSection,
        cursor: Cursor,
    ) -> SegmentResult:
        factor = _SCHEDULE_FACTORS[self.schedule]
        return Bend(
            radius_factor = factor,
            angle         = self.angle,
            n_layers      = self.n_layers,
            roll          = self.roll,
        ).connect(inlet, cursor)


def _new_position(
    cursor:      Cursor,
    bend_centre: np.ndarray,
    axis:        np.ndarray,
    angle:       float,
) -> np.ndarray:
    """Compute the end-face centre after a rotational extrusion."""
    # Vector from bend centre to current cursor position
    r_vec = cursor.position - bend_centre
    return bend_centre + _rodrigues(r_vec, axis, angle)
