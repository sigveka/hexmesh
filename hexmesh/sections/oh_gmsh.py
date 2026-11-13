#        _.-------._
#    .-''     |     ''-.
#  .'  \      |      /  '.     _                                         _
# /     +-----+-----+     \   | |__   ___  __  __  _ __ ___   ___  ___  | |__
# |     |     |     |     |   | '_ \ / _ \ \ \/ / | '_ ` _ \ / _ \/ __| | '_ \
# |-----+-----+-----+-----|   | | | |  __/  >  <  | | | | | |  __/\__ \ | | | |
# |     |     |     |     |   |_| |_|\___| /_/\_\ |_| |_| |_|\___||___/ |_| |_|
# \     +-----+-----+     /
#  '.  /      |      \  .'    structured all-hex meshes for pipe networks
#    '-..     |     ..-'
#        '---------'
#
"""
The O-H layout's GMSH faces (task 0082): the realisation of
``sections.oh``.  Corner positions, the rectangle's inset, the inner arcs
and the corner directions all come from there (and ``core.shape``), so
the face and the block layouts can't disagree; ``tests/test_sections.py``
checks it.

- :func:`build_oh_circle`: the 5-patch circle (``n_outer = 4``);
- :func:`build_oh_split`: ``n_outer = 8`` on any of them, the 4-corner
  face cut along its middle grid lines (decision 0005, task 0088), with
  :func:`place_partition_nodes` to put its nodes on the 4-corner mesh's;
- :func:`build_oh_rect`: the 5-patch rectangle, lines for arcs;
- :func:`build_oh_blend`: a ``Transition`` station (task 0029), every
  curve a spline through samples of ``shape.outline``;
- :func:`build_ring` / :func:`build_annulus`: a shell on any of them.

Every builder returns a ``CrossSection`` in the corner order of
``sections.oh``.  Coordinates: ``(u, v)`` in the plane, rotated by
``rot`` from ``h_axis`` toward ``v_axis``, then *stretch* ``(b, s)``
(scale by ``s`` along the in-plane unit vector ``b`` about the centre:
the oblique cut face of a miter joint; circles become ellipses).
"""

from __future__ import annotations


import numpy as np

from .._gmsh import gmsh
from .. import _occ
from dataclasses import dataclass, field

from ..core.cross_section import CrossSection, BoundaryType
from ..core.shape import CircleShape, RectShape
from . import oh
from ._gmsh_helpers import (
    add_point, add_arc, add_conic_arc, add_line, add_line_loop, add_surface,
    plane, stretched,
    set_transfinite_curve, set_transfinite_line, set_transfinite_line_bump,
    set_transfinite_surface, set_recombine_surface,
)
from ..errors import InternalError, SpecError

# Interior samples per spline curve; the spline through them stands for the
# station shape (one axial layer per slab, so no surface carries nodes).
_SAMPLES = 24


# --- the core ----------------------------------------------------------------

@dataclass
class OHCrossSection(CrossSection):
    """An O-H face's tags (``sections.oh``): the generic ones, and its
    anatomy, the inner boundary, the corner lines and the centre point."""

    layout:        str = "oh"
    # GMSH point tag of the pipe-axis centre point.
    center:        int = 0
    # inner_points : inner corner point tags, in corner order
    # inner_curves : signed inner-boundary curve tags, as outer_curves
    # radial_curves: corner-line tags (inner → outer), in corner order
    inner_points:  list[int] = field(default_factory=list)
    inner_curves:  list[int] = field(default_factory=list)
    radial_curves: list[int] = field(default_factory=list)
    # Number of transfinite node layers on radial lines.
    nrad: int = 4
    # Angles (radians) of the outer corner points, in the same order as
    # outer_points.  Stored by face builders so annulus layers can position
    # their outer corners at matching angles without re-deriving them.
    # Empty list = not set.
    corner_angles: list[float] = field(default_factory=list)
    # A partitioned face (n_outer = 8, task 0088): the 4-corner face's side
    # curves (corner 2j → 2j + 2), built for their nodes only and in no
    # surface; the core's too; their divisions; the core cuts (centre →
    # odd inner corner 1, 3, 5, 7).  Empty on a 4-corner face.
    full_outer:    list[int] = field(default_factory=list)
    full_inner:    list[int] = field(default_factory=list)
    full_counts:   list[int] = field(default_factory=list)
    cuts:          list[int] = field(default_factory=list)

    def corner_entities(self) -> dict[str, list[int]]:
        """The generic roles, and ``ip`` (inner corners), ``ic`` (inner
        sides), ``rc`` (corner lines, inner → outer)."""
        out = {**super().corner_entities(), "ip": list(self.inner_points),
               "ic": list(self.inner_curves), "rc": list(self.radial_curves)}
        if self.cuts:       # a partitioned core: the cut at each odd corner (task 0088)
            out["cut"] = [self.cuts[k // 2] if k % 2 else 0 for k in range(self.n_outer)]
        return out

    def point_tags(self) -> list[int]:
        return list(self.inner_points) + list(self.outer_points)


def build_oh_circle(
    cx:     float,
    cy:     float,
    cz:     float,
    shape:  CircleShape,
    h_axis: np.ndarray,
    v_axis: np.ndarray,
    lc:     float,
    nrad:   int,
    mprg:   float = 1.0,
    mbmp:   float = 1.0,
    rot:    float = 0.0,
    stretch: tuple | None = None,
) -> CrossSection:
    """Build a 5-patch O-H circle in GMSH.

    *shape* carries ``radius`` and ``nang`` (divisions per quadrant arc),
    or ``arcs`` (each arc's);
    *h_axis*, *v_axis* are the in-plane unit vectors (``cursor.right``,
    ``cursor.up``); *nrad* and *mprg* the radial divisions and progression;
    *mbmp* the arcs' bump.  ``rot = -π/4`` aligns patch boundaries with the
    horizontal axis (half-buried pipes).
    """
    xyz = plane(cx, cy, cz, h_axis, v_axis, stretch)
    inner, outer = oh.core_corners(shape, 4, rot)
    centre_uv = [oh.inner_arc_centre(shape.radius, k, rot) for k in range(4)]   # of inner arc k

    center = add_point(cx, cy, cz, lc)
    o1, o2, o3, o4 = (add_point(*xyz(p), lc) for p in outer)          # NE, NW, SW, SE
    i1, i2, i3, i4 = (add_point(*xyz(p), lc) for p in inner)
    # inner-arc centres, made in the order E, N, W, S (arcs 1, 2, 3, 0)
    s_xyz = {k: xyz(centre_uv[k]) for k in (1, 2, 3, 0)}
    s_tag = {k: add_point(*s_xyz[k], lc) for k in (1, 2, 3, 0)}

    def arc(start, centre, end, centre_xyz):
        return add_conic_arc(start, centre, end, centre_xyz, stretch)

    c_xyz = (cx, cy, cz)
    a1 = arc(o1, center, o2, c_xyz)   # NE→NW
    a3 = arc(o2, center, o3, c_xyz)   # NW→SW
    a5 = arc(o3, center, o4, c_xyz)   # SW→SE
    a7 = arc(o4, center, o1, c_xyz)   # SE→NE

    r1 = add_line(i2, o2)   # NW
    r2 = add_line(i1, o1)   # NE
    r3 = add_line(i3, o3)   # SW
    r4 = add_line(i4, o4)   # SE

    a2 = arc(i2, s_tag[0], i1, s_xyz[0])   # NW→NE: inner arc 0 reversed
    a4 = arc(i3, s_tag[1], i2, s_xyz[1])   # SW→NW: arc 1
    a6 = arc(i4, s_tag[2], i3, s_xyz[2])   # SE→SW: arc 2
    a8 = arc(i1, s_tag[3], i4, s_xyz[3])   # NE→SE: arc 3

    surfaces = [add_surface(add_line_loop(loop)) for loop in (
        [-a2, -a4, -a6, -a8],              # centre patch
        [a1, -r1, a2, r2],                 # ring patch 0 (NE → NW)
        [a3, -r3, a4, r1],
        [a5, -r4, a6, r3],
        [a7, -r2, a8, r4])]

    set_transfinite_line([r1, r2, r3, r4], nrad, mprg)
    if shape.arcs is None:
        set_transfinite_line_bump([a1, a2, a3, a4, a5, a6, a7, a8], shape.nang, mbmp)
    else:                                  # each arc its own count (task 0147)
        for k, pair in enumerate(([a1, a2], [a3, a4], [a5, a6], [a7, a8])):
            set_transfinite_line_bump(pair, shape.side_count(k, 4), mbmp)
    set_transfinite_surface(surfaces)
    set_recombine_surface(surfaces)

    return OHCrossSection(
        surfaces      = surfaces,
        center        = center,
        outer_points  = [o1, o2, o3, o4],
        outer_curves  = [a1, a3, a5, a7],
        shape         = shape,
        boundary_type = BoundaryType.CIRCULAR,
        h_axis        = np.asarray(h_axis, dtype=float),
        v_axis        = np.asarray(v_axis, dtype=float),
        cx=cx, cy=cy, cz=cz,
        inner_points  = [i1, i2, i3, i4],
        inner_curves  = [-a2, -a4, -a6, -a8],   # NE→NW, NW→SW, SW→SE, SE→NE
        radial_curves = [r2, r1, r3, r4],        # NE, NW, SW, SE (inner→outer)
        nrad          = nrad,
        lc            = lc,
        corner_angles = [a + rot for a in oh.core_directions(shape, 4)],
    )


def _sides(xyz, shape, kind: str, corners: list[int], centres, rot: float, stretch,
           inner: bool, fractions=None) -> list[int]:
    """Curves between consecutive *corners* of *shape*'s O-H face, the
    4-corner builders' own way: an arc about *centres*[j] (``(tag, xyz)``),
    a line, or a spline through ``outline`` samples.  With *fractions*
    ``(s0, s1)`` per curve, the pieces of side j between those outline
    fractions (a partitioned face's halves, task 0088)."""
    n = len(corners)
    m = n // 4
    out = []
    for k in range(n):
        j = k // m
        a, b = corners[k], corners[(k + 1) % n]
        if kind == "arc":
            tag, cxyz = centres[j]
            out.append(add_conic_arc(a, tag, b, cxyz, stretch))
        elif kind == "line":
            out.append(add_line(a, b))
        else:
            s0, s1 = fractions[k] if fractions else (0.0, 1.0)
            mid = s0 + (s1 - s0) * np.linspace(0.0, 1.0, _SAMPLES + 2)[1:-1]
            pts = [gmsh.model.occ.addPoint(*xyz(oh.rotated(q, rot)))
                   for q in oh.outline(shape, j, mid, inner)]
            out.append(_occ.spline([a, *pts, b]))
    return out


def build_oh_split(
    cx:     float,
    cy:     float,
    cz:     float,
    shape,
    h_axis: np.ndarray,
    v_axis: np.ndarray,
    lc:     float,
    nrad:   int,
    mprg:   float = 1.0,
    mbmp:   float = 1.0,
    rot:    float = 0.0,
    stretch: tuple | None = None,
) -> CrossSection:
    """An ``n_outer = 8`` O-H face (decision 0005, task 0088): the 4-corner
    face of *shape* (a circle, rectangle or ``Transition`` station) cut
    along its middle grid lines into four core sub-patches around the
    centre and eight ring patches.  Corner 2j is the 4-corner face's
    corner j, corner 2j + 1 the middle of its side j (``sections.oh``).

    The 4-corner side curves are built too, sharing the corners and in no
    surface, meshed as the 4-corner face's; after ``generate(1)`` and
    ``generate(2)``, :func:`place_partition_nodes` sets every node of this
    face to the 4-corner mesh's (gmsh's fill alone misses by 1e-4 R:
    ``docs/integrations/gmsh.md``).  Each side's divisions must be even.
    """
    kind = type(shape).side_curve
    counts = [shape.side_count(j, 4) for j in range(4)]
    if any(c % 2 for c in counts):
        raise SpecError(f"n_outer = 8 needs an even number of divisions on every side, got "
                        f"{counts}", code="nang_not_divisible", where={"field": "nang"},
                        value=counts, limit={"multiple_of": 2})
    xyz = plane(cx, cy, cz, h_axis, v_axis, stretch)
    inner, outer = oh.split_corners(shape, rot)
    center = add_point(cx, cy, cz, lc)
    O = [add_point(*xyz(p), lc) for p in outer]
    I = [add_point(*xyz(p), lc) for p in inner]
    if kind == "arc":
        c_xyz = (cx, cy, cz)
        out_c = [(center, c_xyz)] * 4
        s_xyz = [xyz(oh.inner_arc_centre(shape.radius, j, rot)) for j in range(4)]
        in_c = [(add_point(*s_xyz[j], lc), s_xyz[j]) for j in range(4)]
    else:
        out_c = in_c = None
    halves = [(0.0, 0.5), (0.5, 1.0)] * 4
    Ao = _sides(xyz, shape, kind, O, out_c, rot, stretch, False, halves)
    Ai = _sides(xyz, shape, kind, I, in_c, rot, stretch, True, halves)
    full_o = _sides(xyz, shape, kind, O[::2], out_c, rot, stretch, False)
    full_i = _sides(xyz, shape, kind, I[::2], in_c, rot, stretch, True)
    R = [add_line(I[k], O[k]) for k in range(8)]
    cuts = [add_line(center, I[k]) for k in (1, 3, 5, 7)]
    cut = dict(zip((1, 3, 5, 7), cuts))
    # core sub-patch around even corner c: halves c - 1 and c, cuts c + 1 and c - 1
    core = [add_surface(add_line_loop([Ai[(c - 1) % 8], Ai[c], -cut[c + 1], cut[(c - 1) % 8]]))
            for c in (0, 2, 4, 6)]
    ring = [add_surface(add_line_loop([Ao[k], -R[(k + 1) % 8], -Ai[k], R[k]])) for k in range(8)]
    surfaces = core + ring

    # every node is set by place_partition_nodes; these only fix the counts
    set_transfinite_line(R, nrad, mprg)
    for k in range(8):
        set_transfinite_line([Ao[k], Ai[k]], counts[k // 2] // 2)
    for k, c in cut.items():
        set_transfinite_line([c], counts[(k // 2 + 1) % 4] // 2)
    for j in range(4):
        set_transfinite_line_bump([full_o[j], full_i[j]], counts[j], mbmp)
    set_transfinite_surface(surfaces)
    set_recombine_surface(surfaces)

    return OHCrossSection(
        surfaces      = surfaces,
        center        = center,
        outer_points  = O,
        outer_curves  = Ao,
        shape         = shape,
        boundary_type = BoundaryType.CIRCULAR if kind == "arc" else BoundaryType.SQUARE,
        h_axis        = np.asarray(h_axis, dtype=float),
        v_axis        = np.asarray(v_axis, dtype=float),
        cx=cx, cy=cy, cz=cz,
        inner_points  = I,
        inner_curves  = Ai,
        radial_curves = R,
        nrad          = nrad,
        lc            = lc,
        corner_angles = [a + rot for a in oh.core_directions(shape, 8)],
        full_outer    = full_o,
        full_inner    = full_i,
        full_counts   = counts,
        cuts          = cuts,
    )


def build_oh_rect(
    cx:     float,
    cy:     float,
    cz:     float,
    shape:  RectShape,
    h_axis: np.ndarray,
    v_axis: np.ndarray,
    lc:     float,
    nrad:   int,
    mprg:   float = 1.0,
    mbmp:   float = 1.0,
    rot:    float = 0.0,
    stretch: tuple | None = None,
) -> CrossSection:
    """Build a 5-patch O-H rectangle in GMSH: the circle's layout with
    lines for arcs, the inner rectangle inset by a uniform ring
    (``sections.oh.ring_thickness``).  *shape* carries ``half_w``,
    ``half_h``, ``nang_w`` (width sides) and ``nang_h`` (height sides);
    the other arguments are ``build_oh_circle``'s.  The stretch is
    affine, so the edges stay straight lines."""
    xyz = plane(cx, cy, cz, h_axis, v_axis, stretch)
    inner, outer = oh.core_corners(shape, 4, rot)

    o1, o2, o3, o4 = (add_point(*xyz(p), lc) for p in outer)          # NE, NW, SW, SE
    i1, i2, i3, i4 = (add_point(*xyz(p), lc) for p in inner)
    center = add_point(cx, cy, cz, lc)

    a1 = add_line(o1, o2)   # NE→NW  top    (width  edge)
    a3 = add_line(o2, o3)   # NW→SW  left   (height edge)
    a5 = add_line(o3, o4)   # SW→SE  bottom (width  edge)
    a7 = add_line(o4, o1)   # SE→NE  right  (height edge)

    a2 = add_line(i2, i1)   # NW→NE  top    inner
    a4 = add_line(i3, i2)   # SW→NW  left   inner
    a6 = add_line(i4, i3)   # SE→SW  bottom inner
    a8 = add_line(i1, i4)   # NE→SE  right  inner

    r1 = add_line(i2, o2)   # NW
    r2 = add_line(i1, o1)   # NE
    r3 = add_line(i3, o3)   # SW
    r4 = add_line(i4, o4)   # SE

    surfaces = [add_surface(add_line_loop(loop)) for loop in (
        [-a2, -a4, -a6, -a8],
        [a1, -r1, a2, r2],
        [a3, -r3, a4, r1],
        [a5, -r4, a6, r3],
        [a7, -r2, a8, r4])]

    set_transfinite_line_bump([a1, a2, a5, a6], shape.nang_w, mbmp)
    set_transfinite_line_bump([a3, a4, a7, a8], shape.nang_h, mbmp)
    set_transfinite_line([r1, r2, r3, r4], nrad, mprg)
    set_transfinite_surface(surfaces)
    set_recombine_surface(surfaces)

    return OHCrossSection(
        surfaces     = surfaces,
        center       = center,
        outer_points = [o1, o2, o3, o4],
        outer_curves = [a1, a3, a5, a7],
        shape        = shape,
        boundary_type= BoundaryType.SQUARE,
        h_axis       = np.asarray(h_axis, dtype=float),
        v_axis       = np.asarray(v_axis, dtype=float),
        cx=cx, cy=cy, cz=cz,
        inner_points  = [i1, i2, i3, i4],
        inner_curves  = [-a2, -a4, -a6, -a8],   # NE→NW, NW→SW, SW→SE, SE→NE
        radial_curves = [r2, r1, r3, r4],        # NE, NW, SW, SE (inner→outer)
        nrad          = nrad,
        lc            = lc,
        corner_angles = [a + rot for a in oh.core_directions(shape, 4)],
    )


def build_oh_blend(
    cx:     float,
    cy:     float,
    cz:     float,
    shape,
    h_axis: np.ndarray,
    v_axis: np.ndarray,
    lc:     float,
    nrad:   int,
    mprg:   float = 1.0,
    mbmp:   float = 1.0,
    rot:    float = 0.0,
    stretch: tuple | None = None,
) -> CrossSection:
    """Build a 5-patch O-H face whose curves follow ``shape.outline``: a
    ``Transition`` station (task 0029), whose shape (``core.shape.BlendShape``)
    lies between a circle and a rectangle.  *shape* needs
    ``outline(k, s, inner)``, ``nang_w`` and ``nang_h``."""
    geo = gmsh.model.occ
    xyz = plane(cx, cy, cz, h_axis, v_axis, stretch)
    inner, outer = oh.core_corners(shape, 4, rot)

    center = add_point(cx, cy, cz, lc)
    o = [add_point(*xyz(p), lc) for p in outer]
    i = [add_point(*xyz(p), lc) for p in inner]
    mid = np.linspace(0.0, 1.0, _SAMPLES + 2)[1:-1]

    def spline(k, a, b, inner):
        pts = [geo.addPoint(*xyz(oh.rotated(p, rot))) for p in oh.outline(shape, k, mid, inner)]
        return _occ.spline([a, *pts, b])

    oc = [spline(k, o[k], o[(k + 1) % 4], False) for k in range(4)]   # NE→NW, …
    ic = [spline(k, i[k], i[(k + 1) % 4], True) for k in range(4)]
    r = [add_line(i[k], o[k]) for k in range(4)]                      # NE, NW, SW, SE

    surfaces = [add_surface(add_line_loop(ic))]
    for k in range(4):
        j = (k + 1) % 4
        surfaces.append(add_surface(add_line_loop([oc[k], -r[j], -ic[k], r[k]])))

    set_transfinite_line(r, nrad, mprg)
    set_transfinite_line_bump([oc[0], ic[0], oc[2], ic[2]], shape.nang_w, mbmp)
    set_transfinite_line_bump([oc[1], ic[1], oc[3], ic[3]], shape.nang_h, mbmp)
    set_transfinite_surface(surfaces)
    set_recombine_surface(surfaces)

    return OHCrossSection(
        surfaces      = surfaces,
        center        = center,
        outer_points  = o,
        outer_curves  = oc,
        shape         = shape,
        boundary_type = BoundaryType.SQUARE,
        h_axis        = np.asarray(h_axis, dtype=float),
        v_axis        = np.asarray(v_axis, dtype=float),
        cx=cx, cy=cy, cz=cz,
        inner_points  = i,
        inner_curves  = ic,
        radial_curves = r,
        nrad          = nrad,
        lc            = lc,
        corner_angles = [a + rot for a in oh.core_directions(shape, 4)],
    )


# --- rings ---------------------------------------------------------------------

def build_annulus(
    inner:  CrossSection,
    dR:     float,
    lc:     float,
    nrad:   int,
    mprg:   float = 1.0,
    mbmp:   float = 1.0,
    rot:    float = 0.0,
    stretch: tuple | None = None,
) -> CrossSection:
    """Build a shell of thickness *dR* on top of *inner*: its outline grown
    by *dR* (a circle's radius + dR; a rectangle's half-sizes + dR).  See
    ``build_ring``."""
    if dR <= 0:
        raise SpecError(f"dR must be positive, got {dR!r}", code="size_not_positive",
                        where={"field": "dR"}, value=dR, limit={"min_exclusive": 0})
    return build_ring(inner, inner.shape.grown(dR), lc, nrad, mprg, mbmp, rot, stretch)


def _ring_sides(outer, corners: list[int], center: int, xyz, rot: float, stretch,
                fractions=None) -> list[int]:
    """A ring's outer curves between consecutive *corners* on the outline
    *outer*, as ``build_ring`` makes them; with *fractions* ``(s0, s1)``
    per curve, the pieces of side j between those fractions (task 0088)."""
    n = len(corners)
    m = n // 4
    cx, cy, cz = (float(c) for c in xyz((0.0, 0.0)))
    out = []
    for k in range(n):
        j = k // m
        a, b = corners[k], corners[(k + 1) % n]
        if type(outer).side_curve == "arc":
            out.append(add_conic_arc(a, center, b, (cx, cy, cz), stretch))
        elif type(outer).side_curve == "spline":
            s0, s1 = fractions[k] if fractions else (0.0, 1.0)
            mid = s0 + (s1 - s0) * np.linspace(0.0, 1.0, _SAMPLES + 2)[1:-1]
            out.append(_occ.spline([a, *(gmsh.model.occ.addPoint(*xyz(oh.rotated(q, rot)))
                                         for q in outer.side_samples(j, mid)), b]))
        else:
            out.append(add_line(a, b))
    return out


def build_ring(
    inner:  CrossSection,
    outer,
    lc:     float,
    nrad:   int,
    mprg:   float = 1.0,
    mbmp:   float = 1.0,
    rot:    float = 0.0,
    stretch: tuple | None = None,
    center: int | None = None,
    side_grading: list | None = None,
) -> CrossSection:
    """Build an n_outer-patch ring between *inner* and the outline *outer*
    (decision 0026).

    *center* is the centre point when *inner* has none (an H core, task
    0086); *side_grading* ``[(law, coef) or None, …]`` per side k, instead
    of ``mbmp`` on every side (an H core's wall grading).

    The inner boundary reuses *inner*'s ``outer_points`` and
    ``outer_curves``: no new entities there, so the interface is conformal
    (the stacking protocol, ``core.cross_section``).  *outer* is a
    ``CircleShape``, ``RectShape`` or ``BlendShape`` centred on the inner
    one's centre and enclosing it (checked by the assembly's validation).
    The corner lines follow ``sections.oh.ring_corners``.  Patch *k* is
    bounded by outer side *k*, corner line *k* + 1, inner side *k* and
    corner line *k*.  *rot* and *stretch* must be those *inner* was built
    with.
    """
    n = inner.n_outer          # 4 or 8
    cx, cy, cz = inner.cx, inner.cy, inner.cz
    center = getattr(inner, "center", 0) or center     # reuse — no new centre point
    si = inner.outer_points     # n inner corner tags
    ia = inner.outer_curves     # n inner side tags (CCW, k → k+1)
    xyz = plane(cx, cy, cz, inner.h_axis, inner.v_axis, stretch)

    # The inner corners' directions, as the inner layer recorded them (rot
    # included); the default layout for CrossSections made by hand in tests.
    if getattr(inner, "corner_angles", None):
        angles = list(inner.corner_angles)
    else:
        angles = [d + rot for d in oh.core_directions(CircleShape(1.0, 4), n)]
    corners, angles_out = oh.ring_corners(outer, angles, rot)
    corners = [oh.rotated(p, rot) for p in corners]

    O = [add_point(*xyz(corners[k]), lc) for k in range(n)]
    R = [add_line(si[k], O[k]) for k in range(n)]

    full, full_counts = [], []
    if n == 8:      # partitioned (task 0088): halves, and the full sides for their nodes
        A_out = _ring_sides(outer, O, center, xyz, rot, stretch, [(0.0, 0.5), (0.5, 1.0)] * 4)
        full = _ring_sides(outer, O[::2], center, xyz, rot, stretch)
        full_counts = [outer.side_count(j, 4) for j in range(4)]
    elif type(outer).side_curve == "arc":
        A_out = [add_conic_arc(O[k], center, O[(k + 1) % n], (cx, cy, cz), stretch)
                 for k in range(n)]
    elif type(outer).side_curve == "spline":    # a station: through blended samples
        mid = np.linspace(0.0, 1.0, _SAMPLES + 2)[1:-1]
        A_out = [_occ.spline([O[k], *(gmsh.model.occ.addPoint(*xyz(oh.rotated(q, rot)))
                                      for q in outer.side_samples(k, mid)),
                              O[(k + 1) % n]]) for k in range(n)]
    else:
        A_out = [add_line(O[k], O[(k + 1) % n]) for k in range(n)]

    surfaces = [add_surface(add_line_loop([A_out[k], -R[(k + 1) % n], -ia[k], R[k]]))
                for k in range(n)]

    # only the new entities: the inner sides are the previous layer's
    set_transfinite_line(R, nrad, mprg)
    if n == 8:      # place_partition_nodes sets the halves' nodes from the full sides'
        for k, a in enumerate(A_out):
            set_transfinite_line([a], full_counts[k // 2] // 2)
        for j, a in enumerate(full):
            set_transfinite_line_bump([a], full_counts[j], mbmp)
    elif side_grading is not None:
        for k, a in enumerate(A_out):
            set_transfinite_curve(a, outer.side_count(k, n),
                                  *(side_grading[k] or ("Progression", 1.0)))
    else:
        by_count: dict[int, list[int]] = {}
        for k, a in enumerate(A_out):
            by_count.setdefault(outer.side_count(k, n), []).append(a)
        for count, curves in by_count.items():
            set_transfinite_line_bump(curves, count, mbmp)
    set_transfinite_surface(surfaces)
    set_recombine_surface(surfaces)

    return OHCrossSection(
        surfaces      = surfaces,
        center        = center,
        outer_points  = O,
        outer_curves  = A_out,
        shape         = outer,
        boundary_type = (BoundaryType.CIRCULAR if type(outer).side_curve == "arc"
                         else BoundaryType.SQUARE),   # lines or splines
        h_axis        = inner.h_axis,
        v_axis        = inner.v_axis,
        cx=cx, cy=cy, cz=cz,
        inner_points  = list(si),
        inner_curves  = list(ia),
        radial_curves = R,
        nrad          = nrad,
        lc            = lc,
        corner_angles = angles_out,
        full_outer    = full,
        full_counts   = full_counts,
    )


# --- a partitioned face's nodes (task 0088) -------------------------------------

def _row(curve: int, first: int):
    """(node tags, xyz) of a meshed *curve* from its end point *first* to
    its other end, both included.  Ordered by the curve's parameter: on an
    OCC line ``getBoundary`` doesn't give the ends in that order (gmsh
    4.12.1, task 0088)."""
    msh = gmsh.model.mesh
    c = abs(curve)
    tags, x, u = msh.getNodes(1, c, includeBoundary=False)
    ends = []
    for _, q in gmsh.model.getBoundary([(1, c)], oriented=False):
        (tq,), xq, _ = msh.getNodes(0, abs(q))
        ends.append((gmsh.model.getParametrization(1, c, list(xq))[0], abs(q), tq, xq))
    (_, pa, ta, xa), (_, _, tb, xb) = sorted(ends)
    order = np.argsort(u)
    tags = np.concatenate([[ta], tags[order], [tb]])
    x = np.vstack([xa, x.reshape(-1, 3)[order], xb])
    return (tags, x) if pa == first else (tags[::-1], x[::-1])


def _core_grid(core: OHCrossSection) -> np.ndarray:
    """The 4-corner core patch's nodes, ``(i, j, 3)`` from SW along the
    bottom (i) and the left (j), from the full inner sides'."""
    P = core.inner_points
    s = [_row(c, P[2 * j])[1] for j, c in enumerate(core.full_inner)]   # corner 2j → 2j + 2
    return oh.coons(bottom=s[2], right=s[3], top=s[0][::-1], left=s[1][::-1])


def _ring_grid(cs: OHCrossSection, inner_full: int, inner_pts: list[int], j: int) -> np.ndarray:
    """Layer *cs*'s 4-corner ring patch j, ``(i, k, 3)``: i along its inner
    side (corner 2j → 2j + 2), k along the corner lines (inner → outer)."""
    a, b = 2 * j, (2 * j + 2) % 8
    return oh.coons(bottom=_row(inner_full, inner_pts[a])[1],
                    right=_row(cs.radial_curves[b], inner_pts[b])[1],
                    top=_row(cs.full_outer[j], cs.outer_points[a])[1],
                    left=_row(cs.radial_curves[a], inner_pts[a])[1])


def _layers(face) -> list[tuple[list[int], list[int], OHCrossSection]]:
    """Per layer of a partitioned face: its inner full sides, its inner
    corner points, the layer."""
    out, inner, pts = [], None, None
    for _, cs in face.layers:
        out.append((cs.full_inner, cs.inner_points, cs) if inner is None else (inner, pts, cs))
        inner, pts = cs.full_outer, cs.outer_points
    return out


def _sides_and_halves(face) -> list[tuple[list[int], list[int]]]:
    """(4-corner sides, their halves) of every boundary of a partitioned
    face: the core's inner curves, then each layer's outer."""
    core = face.layers[0][1]
    return ([(core.full_inner, core.inner_curves)]
            + [(cs.full_outer, cs.outer_curves) for _, cs in face.layers])


def _line3(curve: int):
    """A second-order meshed curve's mid-edge nodes ``(tag, xyz)`` and,
    per element, its two end nodes' midpoint (to match elements by) and
    its length."""
    msh = gmsh.model.mesh
    mids, keys, lengths = [], [], []
    for t, _, n in zip(*msh.getElements(1, abs(curve))):
        for a, b, m in n.reshape(-1, 3).astype(int):
            xa, xb, xm = (np.asarray(msh.getNode(int(k))[0]) for k in (a, b, m))
            mids.append((m, xm))
            keys.append(0.5 * (xa + xb))
            lengths.append(float(np.linalg.norm(xb - xa)))
    return mids, np.array(keys), lengths


def place_partition_nodes(faces, stage: int) -> list[tuple[object, np.ndarray, np.ndarray]]:
    """Set every node of each partitioned face in *faces* (``n_outer =
    8``, :func:`build_oh_split`) to the 4-corner face's (decision 0005,
    task 0088).  *stage* 1, after ``generate(1)``: the halves and their
    middle points from the full sides, the ring and core cuts and the
    centre from the full patches' grids (``sections.oh.coons``).  *stage*
    2, after ``generate(2)``: the sub-patch interiors from those grids,
    each node to the nearest grid node (gmsh's own fill puts it within
    1e-3 of a cell).  *stage* 3, after ``setOrder(2)``: the halves'
    mid-edge nodes from the full sides' (gmsh puts them at the parameter
    midpoint of the curve, and a half spline isn't parametrised as the
    whole).  Returns ``(face, moves, spacing)`` per face: how far each
    node moved and the shortest grid edge it moved in."""
    msh = gmsh.model.mesh
    out = []
    for face in faces:
        if face.layers[0][1].n_outer != 8:
            continue
        moves, spacing = [], []
        if stage == 3:
            for full, halves in _sides_and_halves(face):
                for j in range(4):
                    m, h, _ = _line3(full[j])
                    for piece in halves[2 * j:2 * j + 2]:
                        pm, ph, lengths = _line3(piece)
                        d = np.linalg.norm(ph[:, None, :] - h[None, :, :], axis=2)
                        near = d.argmin(axis=1)
                        for (tag, old), i, length in zip(pm, near, lengths):
                            p = m[i][1]
                            par = gmsh.model.getParametrization(1, abs(piece), list(p))
                            msh.setNode(int(tag), list(map(float, p)), list(par))
                            moves.append(float(np.linalg.norm(old - p)))
                            spacing.append(length)
            out.append((face, np.array(moves), np.array(spacing)))
            continue

        def put(tag, p, dim, ent, h):
            old = msh.getNode(int(tag))[0]
            par = [] if dim == 0 else list(gmsh.model.getParametrization(dim, ent, list(p)))
            msh.setNode(int(tag), list(map(float, p)), par)
            moves.append(float(np.linalg.norm(np.asarray(old) - p)))
            spacing.append(h)

        def edge_len(g):
            return float(min(np.linalg.norm(np.diff(g, axis=0), axis=-1).min(),
                             np.linalg.norm(np.diff(g, axis=1), axis=-1).min()))

        core = face.layers[0][1]
        grids = []                  # (patch surfaces, grid) per 4-corner patch
        if stage == 1:
            # the halves and the side middles, from the full sides
            for full, _, cs in _layers(face):
                if cs is core:
                    pairs = [(core.full_inner, core.inner_curves, core.inner_points)]
                else:
                    pairs = []
                pairs.append((cs.full_outer, cs.outer_curves, cs.outer_points))
                for F, H, P in pairs:
                    for j in range(4):
                        tags, x = _row(F[j], P[2 * j])
                        n = len(tags) - 1
                        h = n // 2
                        d = float(np.linalg.norm(np.diff(x, axis=0), axis=1).min())
                        put(msh.getNodes(0, P[2 * j + 1])[0][0], x[h], 0, 0, d)
                        for k, seg in ((2 * j, x[1:h]), (2 * j + 1, x[h + 1:n])):
                            piece = H[k]
                            for tag, p in zip(_row(piece, P[k])[0][1:-1], seg):
                                put(tag, p, 1, abs(piece), d)
        # the 4-corner patches' grids
        G = _core_grid(core)
        grids.append((core.surfaces[:4], G))
        for full, pts, cs in _layers(face):
            rings = cs.surfaces[4:] if cs is core else cs.surfaces
            for j in range(4):
                g = _ring_grid(cs, full[j], pts, j)
                grids.append((rings[2 * j:2 * j + 2], g))
                if stage == 1:          # the ring cut: the grid's middle line
                    h = (g.shape[0] - 1) // 2
                    rc = cs.radial_curves[2 * j + 1]
                    for tag, p in zip(_row(rc, pts[2 * j + 1])[0][1:-1], g[h, 1:-1]):
                        put(tag, p, 1, abs(rc), edge_len(g))
        if stage == 1:                  # the core cuts and the centre
            hu, hv = (G.shape[0] - 1) // 2, (G.shape[1] - 1) // 2
            lines = (G[hu, hv + 1:-1], G[hu - 1:0:-1, hv], G[hu, hv - 1:0:-1], G[hu + 1:-1, hv])
            for c, seg in zip(core.cuts, lines):
                for tag, p in zip(_row(c, core.center)[0][1:-1], seg):
                    put(tag, p, 1, abs(c), edge_len(G))
            put(msh.getNodes(0, core.center)[0][0], G[hu, hv], 0, 0, edge_len(G))
        else:                           # the sub-patch interiors
            for surfs, g in grids:
                pts = g[1:-1, 1:-1].reshape(-1, 3)
                h = edge_len(g)
                for s in surfs:
                    tags, x, _ = msh.getNodes(2, s, includeBoundary=False)
                    x = x.reshape(-1, 3)
                    if not len(x):          # one cell across: no interior nodes
                        continue
                    d = np.linalg.norm(x[:, None, :] - pts[None, :, :], axis=2)
                    near = d.argmin(axis=1)
                    if d[np.arange(len(x)), near].max() > 0.25 * h:
                        raise InternalError(f"partitioned face: surface {s}'s nodes are not "
                                            f"on the 4-corner grid (task 0088)")
                    for tag, i in zip(tags, near):
                        put(tag, pts[i], 2, s, h)
        out.append((face, np.array(moves), np.array(spacing)))
    return out
