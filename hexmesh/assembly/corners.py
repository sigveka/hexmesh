"""
Corner identity — corners are named by the frame, never found by distance
(DESIGN.md §6.1).

Face builders record corners in a fixed order: corner ``k`` lies at
``corner_angles[k]`` from ``h_axis``; ``outer_curves[k]`` / ``inner_curves[k]``
run from corner ``k`` to ``k+1``; ``radial_curves[k]`` runs inner → outer at
corner ``k``; quadrant surface ``k`` lies between corners ``k`` and ``k+1``.

``canonical_geom`` reads that order and fixes curve signs by comparing
endpoint *tags* (OCC may store an arc reversed).  ``frame_offset`` gives the
index correspondence between two faces from their frames alone, in pure
numpy, so it is checked during validation and reused unchanged in ``fill``.
"""

from __future__ import annotations
import math
from typing import Callable

import gmsh
import numpy as np

from ..core.cross_section import CrossSection
from ..core.shape import RectShape
from ..core.spec import PipeSpec
from .interface import Frame


def curve_endpoints(curve: int) -> tuple[int, int]:
    """(start, end) point tags of *curve* in its parametric direction.

    With the OCC kernel ``getBoundary`` returns a curve's two end points in
    ascending tag order, not start/end, so the start is read from the
    curve's own parametrisation: the end point at the lower parameter bound.
    This only distinguishes the curve's own two end points; it never
    matches entities of different faces by distance (DESIGN §6.1).
    OCC's ``getBoundary`` lists the two end points in ascending tag order,
    not start → end, so the boundary order alone cannot be trusted.
    """
    pts = [t for _, t in gmsh.model.getBoundary([(1, abs(curve))], oriented=False)]
    if len(pts) != 2:
        raise RuntimeError(f"curve {abs(curve)} has {len(pts)} end points")
    lo = gmsh.model.getParametrizationBounds(1, abs(curve))[0][0]
    x0 = np.asarray(gmsh.model.getValue(1, abs(curve), [lo]))
    d = [np.linalg.norm(np.asarray(gmsh.model.getValue(0, p, [])) - x0) for p in pts]
    return (pts[0], pts[1]) if d[0] <= d[1] else (pts[1], pts[0])


def _point_graph(dim: int, tag: int) -> dict[int, set[int]]:
    """Corner points of entity (*dim*, *tag*) and the curves joining them."""
    if dim == 2:
        curves = [abs(c) for _, c in gmsh.model.getBoundary([(2, tag)], oriented=False)]
    else:
        curves = list(dict.fromkeys(
            abs(c) for _, s in gmsh.model.getBoundary([(3, tag)], oriented=False)
            for _, c in gmsh.model.getBoundary([(2, abs(s))], oriented=False)))
    adj: dict[int, set[int]] = {}
    for c in curves:
        a, b = curve_endpoints(c)
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    return adj


def transfinite_surface_corners(surface: int) -> list[int]:
    """The 4 corners of a quad *surface* in a canonical order, from tags.

    GMSH starts a transfinite grid at a corner it chooses itself, which can
    depend on the geometry, so two variants of the same assembly could
    number their nodes differently (docs/tasks/0007).  Starting at the
    smallest point tag and walking toward its smaller-tag neighbour fixes
    the grid by topology alone.  ``[]`` (GMSH's choice) if not a quad.
    """
    adj = _point_graph(2, surface)
    if len(adj) != 4 or any(len(n) != 2 for n in adj.values()):
        return []
    c0 = min(adj)
    c1, c3 = sorted(adj[c0])
    c2 = (adj[c1] - {c0}).pop()
    return [c0, c1, c2, c3]


def transfinite_volume_corners(volume: int) -> list[int]:
    """The 8 corners of a hex *volume* in a canonical order, from tags.

    Bottom face: the smallest-tag corner and its two smaller-tag
    neighbours; top: each bottom corner's third neighbour.  ``[]`` if the
    volume is not a hex block.
    """
    adj = _point_graph(3, volume)
    if len(adj) != 8 or any(len(n) != 3 for n in adj.values()):
        return []
    p0 = min(adj)
    p1, p3, _ = sorted(adj[p0])
    p2 = ((adj[p1] & adj[p3]) - {p0}).pop()
    bottom = [p0, p1, p2, p3]
    return bottom + [(adj[b] - set(bottom)).pop() for b in bottom]


def _oriented(curve: int, start: int, end: int) -> int:
    """Signed *curve* tag running from point *start* to point *end*."""
    t0, t1 = curve_endpoints(abs(curve))
    if (t0, t1) == (start, end):
        return abs(curve)
    if (t0, t1) == (end, start):
        return -abs(curve)
    raise RuntimeError(
        f"curve {abs(curve)} does not join points {start} and {end} "
        f"(endpoints {t0}, {t1}): face topology is inconsistent"
    )


def canonical_geom(cs: CrossSection) -> dict:
    """Signed entity tags of *cs* indexed by corner (keys ip, op, ic, oc, rc)."""
    n = cs.n_outer
    op, ip = list(cs.outer_points), list(cs.inner_points)
    return {
        'op': op,
        'ip': ip,
        'oc': [_oriented(c, op[k], op[(k + 1) % n]) for k, c in enumerate(cs.outer_curves)],
        'ic': [_oriented(c, ip[k], ip[(k + 1) % n]) for k, c in enumerate(cs.inner_curves)],
        'rc': [_oriented(c, ip[k], op[k]) for k, c in enumerate(cs.radial_curves)],
    }


def corner0_angle(spec: PipeSpec) -> float:
    """Angle of corner 0 (NE) from ``frame.right`` for faces built from *spec*."""
    shape = spec.core_shape
    if isinstance(shape, RectShape):
        return math.atan2(shape.half_h, shape.half_w) + spec.rot
    return math.pi / 4 + spec.rot


def side_counts(cs: CrossSection) -> tuple[int, ...]:
    """Divisions of outer (and inner) curve *k* of a face, as
    ``PipeSpec.side_counts``."""
    n, shape = cs.n_outer, cs.shape
    if isinstance(shape, RectShape):
        return (shape.nang_w, shape.nang_h) * 2
    return (shape.nang // (n // 4),) * n


def frame_offset(a: Frame, b: Frame, spec: PipeSpec) -> int:
    """Index *j* such that corner 0 of the face at *a* is corner *j* at *b*.

    Pure numpy (runs in validation).  Frame *a* is carried onto plane *b*
    by the minimal rotation between the normals; the roll between the
    carried frame and *b*, rounded to a multiple of the section period P
    (``PipeSpec.period``, decision 0010), gives the corner steps.  P is
    π for a rectangle, so a 2:1 duct only ever matches itself turned by
    half a turn, never a quarter.
    """
    n, P = spec.n_outer, spec.period
    d = a.right

    axis = np.cross(a.normal, b.normal)
    s, c = float(np.linalg.norm(axis)), float(np.dot(a.normal, b.normal))
    if c < -1 + 1e-9:
        raise ValueError("faces are antiparallel: corner correspondence undefined")
    if s > 1e-14:
        k = axis / s
        d = d * c + np.cross(k, d) * s + k * np.dot(k, d) * (1 - c)

    roll = math.atan2(np.dot(d, b.up), np.dot(d, b.right))
    steps = roll / P
    m = round(steps)
    if abs(steps - m) > 0.5 - 1e-9:
        raise ValueError(
            "corner correspondence is ambiguous: the slab twists by half the "
            "cross-section symmetry angle; use more axial layers"
        )
    return (m * round(P * n / (2 * math.pi))) % n


def connect_layer(in_cs: CrossSection, out_cs: CrossSection, n_layers: int,
                  offset: int, **kwargs):
    """``connect_aligned`` with correspondence from frames (*offset*)."""
    n = in_cs.n_outer
    g_in, g_out = canonical_geom(in_cs), canonical_geom(out_cs)
    g_out = {key: [v[(i + offset) % n] for i in range(n)] for key, v in g_out.items()}
    off = 1 if len(in_cs.surfaces) == n + 1 else 0
    in_quads = [in_cs.surfaces[off + i] for i in range(n)]
    out_quads = [out_cs.surfaces[off + (i + offset) % n] for i in range(n)]
    return connect_aligned(
        in_cs, out_cs, g_in, g_out, in_quads, out_quads, n_layers, **kwargs,
    )


def connect_aligned(
    in_cs:    CrossSection,
    out_cs:   CrossSection,
    g_in:     dict,
    g_out:    dict,
    in_quad_surfs:  "list[int]",
    out_quad_surfs: "list[int]",
    n_layers: int,
    prev_outer_axial:      "list[int] | None" = None,
    prev_outer_side_surfs: "list[int] | None" = None,
    planar_radial: bool = True,
    axial_curve: "Callable[[int, int], int] | None" = None,
    side_surface: "Callable[[int], int] | None" = None,
) -> "tuple[list[int], list[int], list[int]]":
    """Build one layer's hex slab once corner correspondence is fixed.

    ``g_in`` / ``g_out`` hold signed entity tags ``ip, op, ic, oc, rc``
    (see ``canonical_geom``) indexed so that entry ``i`` of the inlet
    corresponds to entry ``i`` of the outlet; ``in_quad_surfs[i]`` and
    ``out_quad_surfs[i]`` are the quadrant patches between corners ``i``
    and ``i+1``.  How the correspondence is found is the caller's concern.
    *side_surface* builds the non-planar side faces from a curve loop
    (default: OCC plate filling, ``addSurfaceFilling``).
    Returns ``(volumes, outer_side_surfs, outer_axial, deferred)``; the
    outer side surfaces and axial curves seed the next layer
    (*prev_outer_side_surfs*, *prev_outer_axial*).  *deferred* holds the
    transfinite constraints for the caller to apply after the last
    synchronize.
    """
    geo  = gmsh.model.occ
    mesh = gmsh.model.mesh
    if axial_curve is None:
        axial_curve = geo.addLine
    if side_surface is None:
        side_surface = geo.addSurfaceFilling
    ip_in, op_in, ic_in, oc_in, rc_in = (g_in[k] for k in ('ip', 'op', 'ic', 'oc', 'rc'))
    ip_out, op_out, ic_out, oc_out, rc_out = (g_out[k] for k in ('ip', 'op', 'ic', 'oc', 'rc'))
    n = in_cs.n_outer
    is_core = (len(in_cs.surfaces) == n + 1)

    # ------------------------------------------------------------------
    # Axial lines for inner corners
    # ------------------------------------------------------------------
    new_inner_axial: list[int] = []   # only populated when we create new lines
    if prev_outer_axial is None:
        inner_axial = []
        for pt_in, pt_out in zip(ip_in, ip_out):
            L = axial_curve(pt_in, pt_out)
            inner_axial.append(L)
            new_inner_axial.append(L)
        geo.synchronize()   # needed before addCurveLoop references these lines
    else:
        inner_axial = prev_outer_axial
        geo.synchronize()   # still needed so OCC buffer is clean

    # ------------------------------------------------------------------
    # Axial lines for outer corners
    # ------------------------------------------------------------------
    outer_axial_lines: list[int] = []
    for pt_in, pt_out in zip(op_in, op_out):
        outer_axial_lines.append(axial_curve(pt_in, pt_out))
    outer_axial = outer_axial_lines
    geo.synchronize()   # needed before addCurveLoop references these lines
    # outer_axial = [NE, NW, SW, SE]

    # ------------------------------------------------------------------
    # Outer arc side-surfaces  (one per patch, shared with next layer)
    # Each connects oc_in[i] to oc_out[i] via outer_axial[i] and [j]
    # Loop: op_in[i] →(oc_in[i])→ op_in[j] →(oa[j])→ op_out[j]
    #         →(-oc_out[i])→ op_out[i] →(-oa[i])→ op_in[i]
    # Use addSurfaceFilling: the boundary curves are arcs in different
    # planes (inlet vs outlet), so the surface is non-planar.
    # ------------------------------------------------------------------
    outer_side_surfs: list[int] = []
    for i in range(n):
        j = (i + 1) % n
        loop = geo.addCurveLoop([oc_in[i], outer_axial[j], -oc_out[i], -outer_axial[i]])
        surf = side_surface(loop)
        outer_side_surfs.append(surf)
    geo.synchronize()

    # ------------------------------------------------------------------
    # Inner arc side-surfaces
    # For the innermost layer (OH core) build them fresh;
    # for outer layers reuse the previous layer's outer_side_surfs.
    # ------------------------------------------------------------------
    new_inner_side_surfs: list[int] = []   # only populated when we create new ones
    if prev_outer_side_surfs is None:
        inner_side_surfs: list[int] = []
        for i in range(n):
            j = (i + 1) % n
            loop = geo.addCurveLoop([
                ic_in[i], inner_axial[j], -ic_out[i], -inner_axial[i],
            ])
            surf = side_surface(loop)
            inner_side_surfs.append(surf)
            new_inner_side_surfs.append(surf)
        geo.synchronize()
    else:
        inner_side_surfs = prev_outer_side_surfs

    # ------------------------------------------------------------------
    # Radial side-surfaces  (one per corner)
    # Each connects rc_in[i] (ip→op on inlet) to rc_out[i] (ip→op on outlet)
    # via outer_axial[i] and inner_axial[i].
    # Loop: ip_in[i] →(rc_in[i])→ op_in[i] →(oa[i])→ op_out[i]
    #         →(-rc_out[i])→ ip_out[i] →(-ia[i])→ ip_in[i]
    # ------------------------------------------------------------------
    radial_side_surfs: list[int] = []
    for i in range(n):
        loop = geo.addCurveLoop([
            rc_in[i], outer_axial[i], -rc_out[i], -inner_axial[i],
        ])
        if planar_radial:
            surf = geo.addPlaneSurface([loop])
        else:
            surf = side_surface(loop)
        radial_side_surfs.append(surf)
    geo.synchronize()

    # ------------------------------------------------------------------
    # Volumes
    # ------------------------------------------------------------------
    vols: list[int] = []

    if is_core:
        # Center patch: in + out + all n inner arc sides
        # OCC addSurfaceLoop: orientation not used, all tags positive
        sloop = geo.addSurfaceLoop([
            in_cs.surfaces[0], out_cs.surfaces[0],
            *inner_side_surfs,
        ])
        vol = geo.addVolume([sloop])
        vols.append(vol)
        surf_offset = 1
    else:
        surf_offset = 0

    for i in range(n):
        j = (i + 1) % n
        in_surf  = in_quad_surfs[i]
        out_surf = out_quad_surfs[i]

        sloop = geo.addSurfaceLoop([
            in_surf,               out_surf,
            outer_side_surfs[i],   inner_side_surfs[i],
            radial_side_surfs[i],  radial_side_surfs[j],
        ])
        vol = geo.addVolume([sloop])
        vols.append(vol)

    # ------------------------------------------------------------------
    # Collect deferred mesh constraints.
    # Do NOT apply them here — the caller accumulates constraints from all
    # concentric layers and applies them in a single final synchronize pass
    # so that no subsequent geo.synchronize() can reset them.
    #
    # Arc and radial curves need matching node counts on the inlet and
    # outlet faces so that the taper side-surfaces are transfinite-
    # compatible (opposite edges of a surface must have equal node counts).
    # The axial lines (new_inner_axial + outer_axial) are stored as bare
    # tags; the caller wraps them as (tag, n_layers+1).  Arc and radial
    # curves carry their own node counts stored as (tag, n_nodes) pairs in
    # "arc_curves".
    # ------------------------------------------------------------------
    # Divisions of curve k (corner k → k+1): nang per 90° arc of a circle,
    # nang_w / nang_h alternating on a rectangle.  The offset maps sides
    # onto sides of the same count (a rectangle only turns by P = π).
    counts = side_counts(in_cs)
    nrad = in_cs.nrad

    # Deduplicated (tag, n_nodes) pairs for arc and radial curves.
    _arc_seen: set[int] = set()
    arc_curve_constraints: list[tuple[int, int]] = []

    def _add_arcs(signed_tags: list[int], n_nodes: int) -> None:
        for t in signed_tags:
            tag = abs(t)
            if tag and tag not in _arc_seen:
                _arc_seen.add(tag)
                arc_curve_constraints.append((tag, n_nodes))

    # Angular curves: count+1 nodes on both inlet and outlet faces so that
    # the outer/inner side-surfaces have matching opposing edge counts.
    for k in range(n):
        for tags in (oc_in, oc_out, ic_in, ic_out):
            _add_arcs([tags[k]], counts[k] + 1)

    # Radial curves: nrad+1 nodes on both faces so the radial side-
    # surfaces have matching opposing edge counts.
    _add_arcs(rc_in,  nrad + 1)
    _add_arcs(rc_out, nrad + 1)

    deferred: dict = {
        "curves":      new_inner_axial + outer_axial,
        "arc_curves":  arc_curve_constraints,
        "surfaces": (
            new_inner_side_surfs
            + outer_side_surfs
            + radial_side_surfs
            + list(in_cs.surfaces)
            + list(out_cs.surfaces)
        ),
        "volumes": vols,
    }

    return vols, outer_side_surfs, outer_axial, deferred
