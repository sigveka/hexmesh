"""
Fittings — cross-section transition connectors.

Reducer / Expander
    Transition between two PipeSpecs with the same shape type and nang
    but different radii.  Each layer is tapered by connecting the inlet
    corner points to new outlet corner points with straight radial lines
    and building ruled surfaces between the inlet and outlet arcs.

    nang must be identical on inlet and outlet (checked at construction).

Transition
    Shape-changing fitting (e.g. circle → rectangle).  Dispatches to the
    appropriate geometry builder based on the (inlet, outlet) shape pair.

    Currently supported:
        CIRCULAR → CIRCULAR  (Reducer/Expander)
        CIRCULAR → SQUARE    (circle-to-square transition)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

import numpy as np
import gmsh

from ..core.cross_section import CrossSection, LayeredCrossSection, BoundaryType
from ..core.cursor import Cursor
from ..core.region import RegionSet
from ..core.spec import PipeSpec
from .base import Connector, SegmentResult
from ..faces.oh_circle import build_oh_circle
from ..faces.annulus   import build_annulus
from ..faces.square_shell import build_square_shell

if TYPE_CHECKING:
    pass


def _check_nang_compatible(inlet: LayeredCrossSection, outlet_spec: PipeSpec) -> None:
    """Raise ValueError if angular divisions differ between inlet and outlet."""
    inlet_nang = _get_nang(inlet.innermost)
    outlet_nang = outlet_spec.nang
    if outlet_nang is not None and inlet_nang != outlet_nang:
        raise ValueError(
            f"Reducer: inlet nang={inlet_nang} but outlet nang={outlet_nang}. "
            "Angular divisions must match for a structured transition."
        )


def _get_nang(cs: CrossSection) -> int | None:
    from ..core.shape import CircleShape
    if isinstance(cs.shape, CircleShape):
        return cs.shape.nang
    return None


@dataclass
class Reducer:
    """Taper from a larger to a smaller cross-section.

    Parameters
    ----------
    outlet : PipeSpec
        Specification for the outlet cross-section.  Must have the same
        number of layers and matching ``nang`` values as the inlet.
    length : float
        Axial length of the taper.
    n_layers : int
        Hex layers along the taper direction.
    """

    REQUIRED_BOUNDARY_TYPE = BoundaryType.CIRCULAR

    outlet:   PipeSpec
    length:   float
    n_layers: int

    def __post_init__(self) -> None:
        if self.length <= 0:
            raise ValueError(f"Reducer.length must be positive, got {self.length!r}")

    def connect(
        self,
        inlet:  LayeredCrossSection,
        cursor: Cursor,
    ) -> SegmentResult:
        _check_nang_compatible(inlet, self.outlet)
        return _taper_connect(inlet, cursor, self.outlet, self.length, self.n_layers)


@dataclass
class Expander:
    """Taper from a smaller to a larger cross-section.

    Identical to Reducer — the distinction is semantic (larger outlet).
    """

    REQUIRED_BOUNDARY_TYPE = BoundaryType.CIRCULAR

    outlet:   PipeSpec
    length:   float
    n_layers: int

    def __post_init__(self) -> None:
        if self.length <= 0:
            raise ValueError(f"Expander.length must be positive, got {self.length!r}")

    def connect(
        self,
        inlet:  LayeredCrossSection,
        cursor: Cursor,
    ) -> SegmentResult:
        _check_nang_compatible(inlet, self.outlet)
        return _taper_connect(inlet, cursor, self.outlet, self.length, self.n_layers)


@dataclass
class Transition:
    """Cross-section shape transition (e.g. circle → rectangle).

    The inlet and outlet may have different BoundaryType values.
    Currently only CIRCULAR → SQUARE is implemented.

    Parameters
    ----------
    outlet : PipeSpec
        Must end in a square_shell layer.
    length : float
        Axial length of the transition.
    n_layers : int
        Hex layers along the transition.
    """

    REQUIRED_BOUNDARY_TYPE = BoundaryType.CIRCULAR

    outlet:   PipeSpec
    length:   float
    n_layers: int

    def connect(
        self,
        inlet:  LayeredCrossSection,
        cursor: Cursor,
    ) -> SegmentResult:
        outermost_in  = inlet.outermost
        outermost_out_type = BoundaryType.SQUARE  # only case supported for now
        if outermost_in.boundary_type is BoundaryType.CIRCULAR \
                and outermost_out_type is BoundaryType.SQUARE:
            return _taper_connect(
                inlet, cursor, self.outlet, self.length, self.n_layers
            )
        raise NotImplementedError(
            f"Transition from {outermost_in.boundary_type} to "
            f"{outermost_out_type} is not yet implemented."
        )


# ---------------------------------------------------------------------------
# Shared taper implementation
# ---------------------------------------------------------------------------

def _taper_connect(
    inlet:       LayeredCrossSection,
    cursor:      Cursor,
    outlet_spec: PipeSpec,
    length:      float,
    n_layers:    int,
) -> SegmentResult:
    """Build the outlet face then connect inlet and outlet with ruled surfaces.

    Processes layers from innermost to outermost.  The outer arc side-surfaces
    of each layer are shared as the inner arc side-surfaces of the next layer
    (stacking protocol), giving a conformal hex mesh across the taper.
    """
    # Synchronize so getBoundary works to query actual inlet face geometry.
    # The inlet CrossSections carry stale inner/outer point/curve tags from the
    # original build (x=0), but their surfaces are the extruded end faces at the
    # current cursor position.  After synchronize we can derive the true tags.
    gmsh.model.occ.synchronize()

    end_cursor = cursor.advanced(length)
    outlet_lcs = _build_outlet(outlet_spec, end_cursor.position, cursor, inlet)

    # Synchronize again so the outlet face entities are in the model alongside
    # the inlet entities.  addCurveLoop cannot mix buffer-only curves with
    # already-synchronized curves, so we must synchronize before building the
    # taper side surfaces.
    gmsh.model.occ.synchronize()

    regions:    dict[str, RegionSet]  = {}
    interfaces: dict[str, list[int]] = {}
    iface_names = inlet.interface_names()

    # Entities shared between adjacent concentric layers
    prev_outer_axial:      list[int] | None = None  # axial lines at inner boundary
    prev_outer_side_surfs: list[int] | None = None  # arc side-surfaces at inner boundary

    # Accumulated mesh constraints (applied once after all geometry is built
    # so that no subsequent geo.synchronize() can reset them).
    all_deferred_curves:   list[int]             = []
    all_deferred_arc_cvs:  list[tuple[int, int]] = []  # (tag, n_nodes) for arcs/radials
    all_deferred_surfaces: list[int]             = []
    all_deferred_volumes:  list[int]             = []

    for idx, ((in_name, in_cs), (out_name, out_cs)) in enumerate(
        zip(inlet.layers, outlet_lcs.layers)
    ):
        assert in_name == out_name, \
            f"Layer name mismatch: inlet '{in_name}' vs outlet '{out_name}'"

        vols, outer_side_surfs, outer_axial, deferred = _connect_layer(
            in_cs, out_cs, n_layers,
            prev_outer_axial=prev_outer_axial,
            prev_outer_side_surfs=prev_outer_side_surfs,
        )
        all_deferred_curves.extend(deferred["curves"])
        all_deferred_arc_cvs.extend(deferred.get("arc_curves", []))
        all_deferred_surfaces.extend(deferred["surfaces"])
        all_deferred_volumes.extend(deferred["volumes"])

        regions[in_name] = RegionSet(
            volumes = vols,
            inlets  = list(in_cs.surfaces),
            outlets = list(out_cs.surfaces),
            walls   = outer_side_surfs,
        )

        if prev_outer_side_surfs is not None and idx - 1 < len(iface_names):
            interfaces[iface_names[idx - 1]] = prev_outer_side_surfs

        prev_outer_axial      = outer_axial
        prev_outer_side_surfs = outer_side_surfs

    # Synchronize once so all OCC volumes are in the GMSH model.
    # Do NOT apply mesh constraints here — Network.mesh() will apply them
    # after its own final synchronize (which could reset them if done here).
    gmsh.model.occ.synchronize()

    # Deduplicate surfaces (some inlet/outlet surfaces appear in multiple layers)
    seen: set[int] = set()
    unique_surfaces: list[int] = []
    for s in all_deferred_surfaces:
        if s not in seen:
            seen.add(s)
            unique_surfaces.append(s)

    # Deduplicate arc/radial curve constraints (tag may appear from multiple layers).
    _arc_seen: set[int] = set()
    unique_arc_cvs: list[tuple[int, int]] = []
    for tag, n in all_deferred_arc_cvs:
        if tag not in _arc_seen:
            _arc_seen.add(tag)
            unique_arc_cvs.append((tag, n))

    return SegmentResult(
        end_face   = outlet_lcs,
        end_cursor = end_cursor,
        regions    = regions,
        interfaces = interfaces,
        deferred_mesh = {
            "curves":   [(L, n_layers + 1) for L in all_deferred_curves]
                        + unique_arc_cvs,
            "surfaces": unique_surfaces,
            "volumes":  all_deferred_volumes,
        },
    )


def _build_outlet(
    spec:   PipeSpec,
    pos:    "np.ndarray",
    cursor: Cursor,
    inlet:  LayeredCrossSection,
) -> LayeredCrossSection:
    """Build the outlet LayeredCrossSection at the given position."""
    from ..faces.oh_circle import build_oh_circle
    from ..faces.annulus   import build_annulus
    from ..faces.square_shell import build_square_shell
    from ..core.shape import CircleShape
    from ..core.spec import SquareShellSpec

    cx, cy, cz = float(pos[0]), float(pos[1]), float(pos[2])
    # Derive face orientation from the cursor frame, not from the (possibly
    # stale) inlet plane.  After a bend the pipe direction changes, so the
    # outlet face must be perpendicular to the new direction.
    h_axis = cursor.right
    v_axis = cursor.up
    lc     = inlet.innermost.lc

    layers: list[tuple[str, CrossSection]] = []
    prev_cs: CrossSection | None = None

    from ..faces.oh_circle import build_oh_circle8

    core_name, core_shape = spec._core
    _builder = build_oh_circle8 if spec._n_outer == 8 else build_oh_circle
    cs = _builder(
        cx=cx, cy=cy, cz=cz,
        shape=core_shape if isinstance(core_shape, CircleShape)
              else core_shape,
        h_axis=h_axis, v_axis=v_axis, lc=lc,
        nrad=spec._core_nrad, mprg=spec._core_mprg,
        mbmp=spec._mbmp, rot=spec._rot,
    )
    layers.append((core_name, cs))
    prev_cs = cs

    for shell in spec.shells:
        if isinstance(shell, SquareShellSpec):
            cs = build_square_shell(prev_cs, shell, lc, spec._mbmp)
        else:
            cs = build_annulus(
                inner=prev_cs, dR=shell.dR, lc=lc,
                nrad=shell.nrad, mprg=shell.mprg, mbmp=spec._mbmp,
                rot=spec._rot,
            )
        layers.append((shell.name, cs))
        prev_cs = cs

    return LayeredCrossSection(layers)


def _curve_endpoints(abs_c: int) -> "tuple[int, int]":
    """Return (start_pt, end_pt) — endpoint tags of curve abs_c.

    Uses the oriented-boundary sign convention: -1 = curve start vertex
    (source), +1 = curve end vertex (sink).  This is kernel-independent
    and works for both geo and OCC circle arcs.
    """
    pts = gmsh.model.getBoundary([(1, abs_c)], oriented=True)
    start_pt = end_pt = None
    for sign, pt in pts:
        if sign < 0:
            start_pt = pt
        else:
            end_pt = pt
    if start_pt is None or end_pt is None:
        # Fallback: assume first returned = start
        start_pt, end_pt = pts[0][1], pts[1][1]
    return (start_pt, end_pt)


def _pt_coincide(pt_a: int, pt_b: int, tol: float = 1e-6) -> bool:
    """True when two point tags resolve to the same coordinate (within tol).

    OCC extrudes surfaces one-by-one and can create duplicate coincident
    corner points (same geometry, different GMSH tag).  This fallback lets
    chain-building work by coordinate equality instead of tag equality.
    """
    if pt_a == pt_b:
        return True
    ca = gmsh.model.getValue(0, pt_a, [])
    cb = gmsh.model.getValue(0, pt_b, [])
    return ((ca[0]-cb[0])**2 + (ca[1]-cb[1])**2 + (ca[2]-cb[2])**2) < tol*tol


def _curve_start(c: int) -> int:
    """Return the START point tag of signed curve c.

    Positive c  → t=0 endpoint.
    Negative c  → t=1 endpoint (traversal is reversed).
    """
    t0, t1 = _curve_endpoints(abs(c))
    return t0 if c > 0 else t1


def _curve_end(c: int) -> int:
    """Return the END point tag of signed curve c."""
    t0, t1 = _curve_endpoints(abs(c))
    return t1 if c > 0 else t0


def _extract_geom(cs: CrossSection) -> "dict":
    """After geo.synchronize(), extract actual GMSH entity tags from surfaces.

    Uses a chain-building approach: the n_outer quadrant surfaces are processed
    in index order and corner ordering is determined by matching shared
    endpoints between adjacent quadrants.  This is orientation-independent
    and works after pipe bends.

    The cross-section center is estimated as the centroid of all arc
    endpoints found on the n_outer quadrant surfaces — no reliance on cs.cx/cy/cz
    or cs.h_axis/cs.v_axis, which can be stale after extrusion connectors.

    Returns dict with keys ip, ic, op, oc, rc  (each a list[int] of length n_outer).

    Convention:
      oc[i] : outer arc  starting at op[i], ending at op[(i+1)%n]
      ic[i] : inner arc  starting at ip[i], ending at ip[(i+1)%n]
      rc[i] : radial     inner→outer at corner i  (ip[i] → op[i])
    """
    n = cs.n_outer
    is_core = (len(cs.surfaces) == n + 1)
    surf_offset = 1 if is_core else 0

    oc: list[int] = [0]*n
    op: list[int] = [0]*n
    rc: list[int] = [0]*n
    ic: list[int] = [0]*n
    ip: list[int] = [0]*n

    # ------------------------------------------------------------------ #
    # Pre-pass: collect all arc endpoints → estimate cross-section centre  #
    # ------------------------------------------------------------------ #
    all_bnd:      list = []
    all_arc_pts:  set  = set()

    for i in range(n):
        bnd = gmsh.model.getBoundary(
            [(2, cs.surfaces[surf_offset + i])], oriented=True
        )
        all_bnd.append(bnd)
        for _, c in bnd:
            if gmsh.model.getType(1, abs(c)) == 'Circle':
                t0, t1 = _curve_endpoints(abs(c))
                all_arc_pts.update([t0, t1])

    cx_est = cy_est = cz_est = 0.0
    for pt in all_arc_pts:
        coord = gmsh.model.getValue(0, pt, [])
        cx_est += coord[0]; cy_est += coord[1]; cz_est += coord[2]
    n_pts = len(all_arc_pts)
    cx_est /= n_pts; cy_est /= n_pts; cz_est /= n_pts

    def _r(pt: int) -> float:
        """3-D distance from pt to the estimated cross-section centre."""
        c = gmsh.model.getValue(0, pt, [])
        return ((c[0]-cx_est)**2 + (c[1]-cy_est)**2 + (c[2]-cz_est)**2) ** 0.5

    # ------------------------------------------------------------------ #
    # Gather per-quadrant data                                            #
    # ------------------------------------------------------------------ #
    q_outer_arc: list[int]  = []
    q_outer_t0:  list[int]  = []
    q_outer_t1:  list[int]  = []
    q_inner_arc: list[int]  = []
    q_inner_t0:  list[int]  = []
    q_inner_t1:  list[int]  = []
    q_radials:   list       = []   # list of (inner_pt, outer_pt, fwd_radial)

    for i in range(n):
        bnd = all_bnd[i]
        arcs:    list[int] = []
        radials: list[int] = []
        for _, c in bnd:
            if gmsh.model.getType(1, abs(c)) == 'Circle':
                arcs.append(c)
            else:
                radials.append(c)

        # Outer arc has larger average distance from centre
        def _avg_r(a: int) -> float:
            return (_r(_curve_start(a)) + _r(_curve_end(a))) / 2

        outer_a, inner_a = (arcs[0], arcs[1]) if _avg_r(arcs[0]) > _avg_r(arcs[1]) \
                           else (arcs[1], arcs[0])

        q_outer_arc.append(outer_a)
        q_outer_t0.append(_curve_start(outer_a))
        q_outer_t1.append(_curve_end(outer_a))
        q_inner_arc.append(inner_a)
        q_inner_t0.append(_curve_start(inner_a))
        q_inner_t1.append(_curve_end(inner_a))

        rad_data = []
        for rad in radials:
            rs = _curve_start(rad); re = _curve_end(rad)
            if _r(rs) < _r(re):
                rad_data.append((rs, re, rad))    # (inner_pt, outer_pt, fwd)
            else:
                rad_data.append((re, rs, -rad))
        q_radials.append(rad_data)

    # ------------------------------------------------------------------ #
    # Build outer arc chain (op/oc)                                       #
    # op[i] = start of oc[i]; oc[i] goes op[i] → op[(i+1)%n]            #
    # Quadrant-0 arc defines the initial direction.                       #
    # ------------------------------------------------------------------ #
    oc[0] = q_outer_arc[0]
    op[0] = q_outer_t0[0]
    op[1] = q_outer_t1[0]
    used: set[int] = {0}

    for i in range(1, n):
        prev_end = op[i]
        next_idx = (i + 1) % n
        found = False
        for j in range(n):
            if j in used:
                continue
            t0, t1 = q_outer_t0[j], q_outer_t1[j]
            if _pt_coincide(t0, prev_end):
                op[next_idx] = t1
                oc[i] = q_outer_arc[j]
                used.add(j)
                found = True
                break
            elif _pt_coincide(t1, prev_end):
                op[next_idx] = t0
                oc[i] = -q_outer_arc[j]
                used.add(j)
                found = True
                break
        if not found:
            raise RuntimeError(
                f"_extract_geom: cannot chain outer arcs at i={i}, "
                f"prev_end={prev_end}, remaining arcs={[q_outer_arc[j] for j in range(n) if j not in used]}"
            )

    # ------------------------------------------------------------------ #
    # Radials (rc/ip): for each quadrant, each radial's outer endpoint    #
    # identifies which corner it belongs to.                              #
    # ------------------------------------------------------------------ #
    for i in range(n):
        for inner_pt, outer_pt, fwd in q_radials[i]:
            if _pt_coincide(outer_pt, op[i]):
                k = i
            elif _pt_coincide(outer_pt, op[(i + 1) % n]):
                k = (i + 1) % n
            else:
                continue   # shouldn't happen
            rc[k] = fwd
            ip[k] = inner_pt
            op[k] = outer_pt   # confirm (already set, just in case)

    # ------------------------------------------------------------------ #
    # Inner arcs (ic/ip): same chain approach                            #
    # ------------------------------------------------------------------ #
    if is_core:
        # Use center-patch boundary (all n inner arcs form a closed loop)
        bnd_c = gmsh.model.getBoundary([(2, cs.surfaces[0])], oriented=True)
        # Match each boundary curve to ic[k] by endpoint matching with ip[]
        for _, c in bnd_c:
            cs_start = _curve_start(c)
            cs_end   = _curve_end(c)
            for k in range(n):
                if _pt_coincide(ip[k], cs_start) and _pt_coincide(ip[(k + 1) % n], cs_end):
                    ic[k] = c
                    break
                elif _pt_coincide(ip[k], cs_end) and _pt_coincide(ip[(k + 1) % n], cs_start):
                    ic[k] = -c
                    break
    else:
        # Annulus inner arcs: same chain approach using ip[]
        for i in range(n):
            t0, t1 = q_inner_t0[i], q_inner_t1[i]
            # Find which ic index this arc belongs to
            for k in range(n):
                if _pt_coincide(t0, ip[k]) and _pt_coincide(t1, ip[(k + 1) % n]):
                    ic[k] = q_inner_arc[i]
                    break
                elif _pt_coincide(t1, ip[k]) and _pt_coincide(t0, ip[(k + 1) % n]):
                    ic[k] = -q_inner_arc[i]
                    break

    return {'ip': ip, 'ic': ic, 'op': op, 'oc': oc, 'rc': rc}


def _build_miter_outlet(
    inlet:      LayeredCrossSection,
    end_cursor: "Cursor",
    rot:        float = 0.0,
) -> LayeredCrossSection:
    """Build outlet face for a miter connector using inlet geometry parameters.

    Rebuilds each layer's cross-section at the same centre position as the
    inlet but in the plane perpendicular to ``end_cursor.direction`` (the
    post-miter pipe direction).  The nrad, shape radius, and nang are taken
    directly from the inlet CrossSections so the resulting mesh node counts
    are compatible with ``_connect_layer``.

    Parameters
    ----------
    inlet : LayeredCrossSection
        Upstream face whose geometry parameters are reused.
    end_cursor : Cursor
        Defines the position and orientation of the new outlet face.
    rot : float
        Rotation offset (radians) passed to ``build_oh_circle`` for the core
        layer.  Use ``rot=-π/4`` to align inner corners with the horizontal
        split plane (e.g. for Y-junction bifurcation blocks).  Default 0.0.
    """
    from ..faces.oh_circle import build_oh_circle, build_oh_circle8
    from ..faces.annulus   import build_annulus
    from ..core.shape import CircleShape

    pos = end_cursor.position
    cx, cy, cz = float(pos[0]), float(pos[1]), float(pos[2])

    h_axis = end_cursor.right
    v_axis = end_cursor.up
    lc     = inlet.innermost.lc
    _core_n_outer = inlet.innermost.n_outer

    layers_out: list[tuple[str, CrossSection]] = []
    prev_cs_out: "CrossSection | None" = None

    for i, (name, cs) in enumerate(inlet.layers):
        if not isinstance(cs.shape, CircleShape):
            raise NotImplementedError(
                f"MiterBend only supports CircleShape layers; "
                f"layer '{name}' has {type(cs.shape).__name__}."
            )
        nrad = cs.nrad

        if i == 0:
            _builder = build_oh_circle8 if _core_n_outer == 8 else build_oh_circle
            cs_out = _builder(
                cx=cx, cy=cy, cz=cz,
                shape=cs.shape,
                h_axis=h_axis, v_axis=v_axis, lc=lc,
                nrad=nrad,
                rot=rot,
            )
        else:
            prev_in = inlet.layers[i - 1][1]
            dR = cs.shape.radius - prev_in.shape.radius
            cs_out = build_annulus(
                inner=prev_cs_out, dR=dR, lc=lc, nrad=nrad, rot=rot,
            )

        layers_out.append((name, cs_out))
        prev_cs_out = cs_out

    return LayeredCrossSection(layers_out)


def _connect_layer(
    in_cs:    CrossSection,
    out_cs:   CrossSection,
    n_layers: int,
    prev_outer_axial:      "list[int] | None" = None,
    prev_outer_side_surfs: "list[int] | None" = None,
    planar_radial: bool = True,
    axial_curve: "Callable[[int, int], int] | None" = None,
) -> "tuple[list[int], list[int], list[int]]":
    """Connect one cross-section layer with a structured hex taper.

    Builds axial lines, ruled side-surfaces, and transfinite hex volumes
    for each patch in the layer.  Side-surfaces at the outer boundary are
    returned so the next concentric layer can reuse them.

    Parameters
    ----------
    in_cs / out_cs
        Inlet and outlet CrossSections for this layer.
    n_layers
        Hex divisions along the taper axis.
    prev_outer_axial
        Axial lines at the inner boundary (from the previous layer).
        ``None`` for the innermost layer (OH core).
    prev_outer_side_surfs
        Arc side-surfaces at the inner boundary (from the previous layer).
        ``None`` for the innermost layer.
    axial_curve
        ``f(pt_in, pt_out) -> curve_tag`` building the axial curve between
        corresponding inlet and outlet corner points.  Default: straight
        line.  Bends pass a circular-arc builder.

    Returns
    -------
    vols               : volumes created in this layer
    outer_side_surfs   : 4 side-surfaces at the outer arc boundary
    outer_axial        : 4 axial lines at the outer boundary corners [NE,NW,SW,SE]
    """
    geo  = gmsh.model.occ
    mesh = gmsh.model.mesh
    if axial_curve is None:
        axial_curve = geo.addLine

    # Derive actual inlet and outlet geometry from the current GMSH model.
    # in_cs.inner_points etc. may be stale (copied from the original face),
    # and GMSH normalizes some circle arcs by reversing their parametrisation
    # (arcs crossing 0°), so we use _extract_geom for both sides.
    _g_in = _extract_geom(in_cs)
    ip_in  = _g_in['ip']   # [NE, NW, SW, SE, …] actual inner corners on inlet face
    op_in  = _g_in['op']
    ic_in  = _g_in['ic']   # signed inner arcs NE→NW, …
    oc_in  = _g_in['oc']
    rc_in  = _g_in['rc']

    _g_out = _extract_geom(out_cs)
    ip_out = _g_out['ip']
    op_out = _g_out['op']
    ic_out = _g_out['ic']
    oc_out = _g_out['oc']
    rc_out = _g_out['rc']
    n = in_cs.n_outer
    is_core = (len(in_cs.surfaces) == n + 1)

    # ------------------------------------------------------------------
    # Align out chain to in chain.
    # _extract_geom starts the chain at whichever corner GMSH happens to
    # return first from getBoundary, which differs between freshly-built
    # and extruded surfaces.  Rotate the out chain by the k ∈ {0…n-1}
    # that minimises sum of squared distances between op_in[i] and
    # op_out[(i+k)%n], so that geometrically corresponding corners connect.
    # ------------------------------------------------------------------
    _best_k, _best_d = 0, float('inf')
    for _k in range(n):
        _d = sum(
            sum((gmsh.model.getValue(0, op_in[_i], [])[_j]
                 - gmsh.model.getValue(0, op_out[(_i+_k)%n], [])[_j])**2
                for _j in range(3))
            for _i in range(n)
        )
        if _d < _best_d:
            _best_d, _best_k = _d, _k
    _surf_off_out = 1 if is_core else 0
    if _best_k:
        def _rn(lst: list) -> list:
            return [lst[(_i + _best_k) % n] for _i in range(n)]
        ip_out = _rn(ip_out)
        op_out = _rn(op_out)
        ic_out = _rn(ic_out)
        oc_out = _rn(oc_out)
        rc_out = _rn(rc_out)
        out_quad_surfs = [
            out_cs.surfaces[_surf_off_out + (_i + _best_k) % n] for _i in range(n)
        ]
    else:
        out_quad_surfs = [
            out_cs.surfaces[_surf_off_out + _i] for _i in range(n)
        ]

    in_quad_surfs = [in_cs.surfaces[_surf_off_out + _i] for _i in range(n)]
    from ..assembly.corners import connect_aligned as _connect_layer_aligned
    return _connect_layer_aligned(
        in_cs, out_cs,
        {'ip': ip_in,  'op': op_in,  'ic': ic_in,  'oc': oc_in,  'rc': rc_in},
        {'ip': ip_out, 'op': op_out, 'ic': ic_out, 'oc': oc_out, 'rc': rc_out},
        in_quad_surfs, out_quad_surfs, n_layers,
        prev_outer_axial=prev_outer_axial,
        prev_outer_side_surfs=prev_outer_side_surfs,
        planar_radial=planar_radial,
        axial_curve=axial_curve,
    )


