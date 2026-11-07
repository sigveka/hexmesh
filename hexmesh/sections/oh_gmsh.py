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
- :func:`build_oh_circle8`: 9 patches, 8 outer corners (``n_outer = 8``;
  rejected by ``assembly.interface.check_supported``, replaced by task
  0088);
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
from ..errors import SpecError

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

    def corner_entities(self) -> dict[str, list[int]]:
        """The generic roles, and ``ip`` (inner corners), ``ic`` (inner
        sides), ``rc`` (corner lines, inner → outer)."""
        return {**super().corner_entities(), "ip": list(self.inner_points),
                "ic": list(self.inner_curves), "rc": list(self.radial_curves)}

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

    *shape* carries ``radius`` and ``nang`` (divisions per quadrant arc);
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
    set_transfinite_line_bump([a1, a2, a3, a4, a5, a6, a7, a8], shape.nang, mbmp)
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


def build_oh_circle8(
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
) -> CrossSection:
    """Build a 9-patch O-H circle with 8 outer corners (``n_outer = 8``).

    Corners at 45° + k·45° + *rot* (NE, N, NW, W, SW, S, SE, E); every
    arc, inner and outer, is centred on the axis, so the centre patch is
    bounded by a true circle and has 8 sides.  **nang must be even**: each
    45° arc gets ``nang // 2`` divisions.  The N/W/S/E corners make
    0°/90°/180°/270° shared nodes for junctions (DESIGN §7); decision 0005
    replaces this face by a sub-partition of the 4-corner one (task 0088).
    """
    if shape.nang % 2 != 0:
        raise SpecError(
            f"build_oh_circle8 requires nang to be even (each 45° arc needs "
            f"nang//2 divisions); got nang={shape.nang}.",
            code="nang_not_divisible", where={"field": "nang"}, value=shape.nang,
            limit={"multiple_of": 2}, hint=f"nang={shape.nang - 1} or nang={shape.nang + 1}"
        )
    xyz = plane(cx, cy, cz, h_axis, v_axis, None)
    inner, outer = oh.core_corners(shape, 8, rot)

    center = add_point(cx, cy, cz, lc)
    O = [add_point(*xyz(p), lc) for p in outer]
    I = [add_point(*xyz(p), lc) for p in inner]
    A_out = [add_arc(O[k], center, O[(k + 1) % 8]) for k in range(8)]
    A_in = [add_arc(I[k], center, I[(k + 1) % 8]) for k in range(8)]
    R = [add_line(I[k], O[k]) for k in range(8)]

    s_c = add_surface(add_line_loop(list(A_in)))
    s_ring = [add_surface(add_line_loop([A_out[k], -R[(k + 1) % 8], -A_in[k], R[k]]))
              for k in range(8)]
    surfaces = [s_c] + s_ring

    set_transfinite_line(R, nrad, mprg)
    set_transfinite_line_bump(A_out + A_in, shape.side_count(0, 8), mbmp)
    # the centre patch's 8-curve loop: GMSH can't find 4 corners itself
    if not _occ.in_build:
        gmsh.model.occ.synchronize()
        gmsh.model.mesh.setTransfiniteSurface(s_c, "Left", [I[0], I[2], I[4], I[6]])
    set_transfinite_surface(s_ring)
    set_recombine_surface(surfaces)

    return OHCrossSection(
        surfaces      = surfaces,
        center        = center,
        outer_points  = O,
        outer_curves  = A_out,
        shape         = shape,
        boundary_type = BoundaryType.CIRCULAR,
        h_axis        = np.asarray(h_axis, dtype=float),
        v_axis        = np.asarray(v_axis, dtype=float),
        cx=cx, cy=cy, cz=cz,
        inner_points  = I,
        inner_curves  = A_in,           # CCW: I[0]→I[1], I[1]→I[2], …
        radial_curves = R,              # I[k]→O[k]
        nrad          = nrad,
        lc            = lc,
        corner_angles = [a + rot for a in oh.core_directions(shape, 8)],
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

    if type(outer).side_curve == "arc":
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
    if side_grading is not None:
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
    )
