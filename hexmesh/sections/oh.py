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
The O-H section layout, pure (task 0082; DESIGN §6.1 "Sections").

One description of the 5-patch O-H face, used by the GMSH builders
(``sections.oh_gmsh``) and by the block layouts (``assembly.blocks``):
corner positions per level, edges with their division counts and
grading, and patches with their materials.  Plain data only: ``sections``
doesn't import ``assembly`` (DESIGN §3.1).  The 2-D formulas behind it
(the rectangle's ring inset, the inner corners and arcs, the inner
outlines) are here too (task 0083).  ``OH_RATIO`` is read from
``core.shape.LAYOUTS``, which ``first_cell`` also uses (task 0084).

Topology, viewed from the extrusion direction::

            NW ──── NE
           /  ╲  N  /  ╲
          /  W  ╲  /  E  ╲
        SW ───── c ─────  SE
          ╲  W  /  ╲  E  /
           ╲  S  ╲ /  S /
            SW ──── SE

- **Levels.**  Level 0 is the core's inner square (or rectangle); level
  *l* ≥ 1 is the outer boundary of layer *l* − 1.  Each level has
  ``n_outer`` corners.
- **Corner order** (the ``CrossSection`` exports follow it): corner *k*
  is NE, NW, SW, SE for *k* = 0…3, counter-clockwise from ``frame.right``
  toward ``frame.up``, corner 0 at :func:`corner0_angle`.  Side *k* runs
  from corner *k* to *k* + 1; the corner line (radial) *k* runs from
  level *l* − 1 to *l* at corner *k*; ring patch *k* of a layer lies
  between corners *k* and *k* + 1.
- **Ring corners** (decision 0026): a ring's corner line leaves the inner
  corner along the direction from the centre and ends where the outer
  outline says (``ring_corner``): radially on a circle, at the corner in
  that quadrant on a rectangle.  A ``BlendShape`` station brings its own.
- **Vertex keys** of a block layout are ``(prefix, level, k)``; the tee,
  wye and duct tap bind to them.

Which ``CrossSection`` fields are O-H anatomy rather than generic (task
0082, item 4): ``inner_points``, ``inner_curves`` and ``radial_curves``
(the core's inner square and the corner lines), ``corner_angles``, and
``surfaces`` in the order centre patch, then ring patch *k*.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..core.grading import bump, progression
from ..core.shape import LAYOUTS, BlendShape, CircleShape, RectShape
from ..core.shape import outline as outer_outline

#: signature layout kinds (``assembly.signature``)
NAME = "oh"
CORE_KIND = "oh_core"

#: Inner-square corner radius of the circular O-H face, as a fraction of
#: the core radius: ``core.shape.LAYOUTS``' row, which ``first_cell``
#: sizes the wall cells with.  The core's radial curves run from there to
#: the circle, so they are ``(1 - OH_RATIO) * r`` long.
OH_RATIO = LAYOUTS["oh"]["ratio"]
RING_KIND = "annulus"


# ---------------------------------------------------------------------------
# The face's 2-D formulas, each once (tasks 0082, 0083)
# ---------------------------------------------------------------------------

def ring_thickness(half_w: float, half_h: float) -> float:
    """Ring thickness of a rectangle's O-H face, the same on every side:
    ``(1 - OH_RATIO) · min(half_w, half_h)``.  A uniform ring puts each
    corner radial at 45° to both walls, so the corner cells keep a scaled
    Jacobian of about 0.71 at any aspect ratio; scaling the inner rectangle
    instead gives sin(atan(h/w)), 0.45 for a 2:1 duct (task 0028)."""
    return (1.0 - OH_RATIO) * min(half_w, half_h)


def inner_radius(radius: float) -> float:
    """Distance from the centre to a corner of the inner square of a
    circle's O-H face: ``OH_RATIO · radius``."""
    return OH_RATIO * radius


def inner_half_side(radius: float) -> float:
    """Half the side of the inner square of a circle's O-H face: each
    inner corner is this far along both axes of the 45° frame (the
    junction blocks' inner-square corners, task 0086)."""
    return OH_RATIO * radius / math.sqrt(2)


def inner_corner(shape, k: int) -> np.ndarray:
    """Corner *k* (NE, NW, SW, SE) of the inner square (or rectangle) of
    *shape*'s O-H face, in-plane ``(u, v)`` before ``rot``."""
    if isinstance(shape, RectShape):
        t = ring_thickness(shape.half_w, shape.half_h)
        su, sv = ((1, 1), (-1, 1), (-1, -1), (1, -1))[k % 4]
        return np.array([su * (shape.half_w - t), sv * (shape.half_h - t)])
    return OH_RATIO * shape.corner(k)


def inner_arc_centre(radius: float, k: int, rot: float = 0.0) -> np.ndarray:
    """Centre of inner arc *k* (corner k → k + 1) of a circle's O-H face,
    turned by *rot*: the inner-square point opposite the arc's middle
    (S, E, N, W for k = 0…3), so the arcs bulge toward the centre."""
    a = (k + 3) % 4 * math.pi / 2 + rot
    rho = inner_radius(radius)
    return np.array([math.cos(a) * rho, math.sin(a) * rho])


def _circle_inner(shape: CircleShape, k: int, s):
    s = np.asarray(s, dtype=float)
    r = shape.radius
    # inner arc k is centred on the inner-square point opposite its middle
    rho = inner_radius(r)
    c = inner_arc_centre(r, k)
    ends = [rho * np.array([math.cos(math.pi / 4 + math.pi / 2 * j),
                            math.sin(math.pi / 4 + math.pi / 2 * j)]) for j in (k, k + 1)]
    a0, a1 = (math.atan2(*(e - c)[::-1]) for e in ends)
    a1 = a0 + math.remainder(a1 - a0, 2 * math.pi)    # the short way (k = 1 crosses ±π)
    a = a0 + (a1 - a0) * s
    R = np.linalg.norm(ends[0] - c)
    return c + R * np.stack([np.cos(a), np.sin(a)], axis=-1)


def _rect_inner(shape: RectShape, k: int, s):
    s = np.asarray(s, dtype=float)[..., None]
    t = ring_thickness(shape.half_w, shape.half_h)      # uniform ring
    hw, hh = shape.half_w - t, shape.half_h - t
    corners = np.array([[hw, hh], [-hw, hh], [-hw, -hh], [hw, -hh]])
    return corners[k % 4] + (corners[(k + 1) % 4] - corners[k % 4]) * s


def outline(shape, k: int, s, inner: bool = False) -> np.ndarray:
    """Point(s) at arc-length fraction *s* along outer (or *inner*) curve
    *k* of *shape*'s O-H face, in unrotated in-plane coordinates.  The
    outer curves are the shape's (``core.shape.outline``); a
    ``BlendShape`` station's inner curves blend its ends'."""
    if not inner:
        return shape.outline(k, s) if isinstance(shape, BlendShape) else outer_outline(shape, k, s)
    if isinstance(shape, BlendShape):
        a = outline(shape.inlet, k, s, True)
        b = outline(shape.outlet, k, s, True)
        return (1.0 - shape.u) * a + shape.u * b
    if isinstance(shape, CircleShape):
        return _circle_inner(shape, k, s)
    if isinstance(shape, RectShape):
        return _rect_inner(shape, k, s)
    raise TypeError(f"no outline for {type(shape).__name__}")


def corner0_angle(spec) -> float:
    """Angle of corner 0 (NE) from ``frame.right`` for faces built from
    *spec*, ``rot`` included."""
    return core_directions(spec.core_shape, spec.n_outer)[0] + spec.rot_rad


def core_directions(shape, n_outer: int) -> list[float]:
    """Direction (radians, before ``rot``) of each outer corner of the core:
    where the first ring's corner lines start.  A blend station records
    none, so its rings start from the circle's directions."""
    if isinstance(shape, RectShape):
        a0 = math.atan2(shape.half_h, shape.half_w)
        return [a0, math.pi - 2 * a0 + a0, math.pi + a0, 2 * math.pi - 2 * a0 + a0]
    if n_outer == 8:
        return [(k + 1) * math.pi / 4 for k in range(8)]
    return [(2 * k + 1) * math.pi / 4 for k in range(n_outer)]


def rotated(p, rot: float) -> np.ndarray:
    """In-plane point *p* turned by *rot* (radians, ``h_axis`` toward
    ``v_axis``)."""
    c, s = math.cos(rot), math.sin(rot)
    return np.array([c * p[0] - s * p[1], s * p[0] + c * p[1]])


def core_corners(shape, n_outer: int, rot: float) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """(inner, outer) corners of the core, ``(u, v)`` with *rot* applied.
    A circle's are placed at their angles (``rot`` added to the angle),
    the others turned as points."""
    if isinstance(shape, CircleShape):
        d = [a + rot for a in core_directions(shape, n_outer)]
        polar = lambda r, a: np.array([math.cos(a) * r, math.sin(a) * r])
        return ([polar(inner_radius(shape.radius), a) for a in d],
                [polar(shape.radius, a) for a in d])
    if isinstance(shape, BlendShape):
        return ([rotated(outline(shape, k, 0.0, inner=True), rot) for k in range(4)],
                [rotated(shape.outline(k, 0.0), rot) for k in range(4)])
    return ([rotated(inner_corner(shape, k), rot) for k in range(4)],
            [rotated(shape.corner(k), rot) for k in range(4)])


def ring_corners(outline, angles, rot: float) -> tuple[list[np.ndarray], list[float]]:
    """A ring's outer corners on *outline* (``(u, v)`` before ``rot``) from
    the inner corners' *angles* (radians, ``rot`` included, as
    ``CrossSection.corner_angles``), and the angles the next ring starts
    from: the same on a circle, else toward the new corners."""
    corners = outline.corners_from([a - rot for a in angles])
    if type(outline).side_curve == "arc":
        return corners, list(angles)
    return corners, [rot + math.atan2(p[1], p[0]) for p in corners]


def side_counts(shape, n_outer: int) -> tuple[int, ...]:
    """Divisions of side *k* of a face whose outline is *shape*."""
    return tuple(shape.side_count(k, n_outer) for k in range(n_outer))


@dataclass(frozen=True)
class Edge:
    """An edge between two ``(level, k)`` corners: *divisions* and
    *grading* as ``BlockLayout.edge`` takes them."""
    a:         tuple[int, int]
    b:         tuple[int, int]
    divisions: int
    grading:   tuple | None


@dataclass(frozen=True)
class Level:
    """One corner level: its corners ``(u, v)`` with ``rot`` applied, and
    the edges declared with it (sides, then the corner lines from the
    level below), in declaration order.

    On an all-round stack *polar* is the level's ``(radius, angles)``, the
    same corners as ``position + r·(cos a·right + sin a·up)``: the form
    the junction blocks were written against, which keeps their meshes
    bit-identical (task 0082; ``u·right + v·up`` differs by round-off,
    and the oblique tee amplifies that about 10⁵).  ``None`` otherwise."""
    corners: tuple[np.ndarray, ...]
    edges:   tuple[Edge, ...]
    polar:   tuple[float, tuple[float, ...]] | None = None


def levels(spec) -> list[Level]:
    """Every corner level of *spec*'s O-H face, in the plane of the face:
    ``position + u·right + v·up``."""
    n, rot = spec.n_outer, spec.rot_rad
    outlines = spec.outlines
    inner, outer = core_corners(outlines[0], n, rot)
    pts = [inner, outer]
    angles = [d + rot for d in core_directions(outlines[0], n)]
    for o in outlines[1:]:
        corners, angles = ring_corners(o, angles, rot)
        pts.append([rotated(p, rot) for p in corners])
    polar = [None] * len(pts)
    if all(isinstance(o, CircleShape) for o in outlines):
        a0 = corner0_angle(spec)
        ang = tuple(a0 + 2 * math.pi * k / n for k in range(n))
        radii = [inner_radius(outlines[0].radius)] + [o.radius for o in outlines]
        polar = [(r, ang) for r in radii]
    nrads = [spec._core_nrad] + [sh.nrad for sh in spec.shells]
    mprgs = [spec._core_mprg] + [sh.mprg for sh in spec.shells]
    bump = ("Bump", spec.mbmp) if spec.mbmp != 1.0 else None
    # level 0 and the core's boundary share the core's counts; ring sides theirs
    counts = [side_counts(outlines[0], n)] + [side_counts(o, n) for o in outlines]
    out = []
    for lvl, corners in enumerate(pts):
        edges = []
        for k in range(n):
            edges.append(Edge((lvl, k), (lvl, (k + 1) % n), counts[lvl][k], bump))
            if lvl:
                edges.append(Edge((lvl - 1, k), (lvl, k), nrads[lvl - 1],
                                  ("Progression", mprgs[lvl - 1])))
        out.append(Level(tuple(corners), tuple(edges), polar[lvl]))
    return out


def patches(spec) -> list[tuple[str, tuple[tuple[int, int], ...]]]:
    """(material, cyclic ``(level, k)`` corners) of every patch: the core's
    centre patch, then each layer's ring patches."""
    n = spec.n_outer
    names = spec.layer_names
    out = [(names[0], tuple((0, k) for k in range(n)))]
    for lvl, name in enumerate(names):
        for k in range(n):
            j = (k + 1) % n
            out.append((name, ((lvl, k), (lvl, j), (lvl + 1, j), (lvl + 1, k))))
    return out

# ---------------------------------------------------------------------------
# Predicted section nodes (``assembly.section_quality``)
# ---------------------------------------------------------------------------

def _ring(inner: np.ndarray, outer: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Patch nodes (len(inner), len(t), 2): the two boundaries' linear blend."""
    return inner[:, None, :] * (1 - t)[None, :, None] + outer[:, None, :] * t[None, :, None]


def _chord_fractions(p: np.ndarray) -> np.ndarray:
    d = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])
    return d / d[-1]


def _coons(bottom, top, left, right) -> np.ndarray:
    """Transfinite patch nodes from four boundary node rows; *bottom* and
    *top* run along u (left → right), *left* and *right* along v."""
    u = _chord_fractions(bottom)[:, None, None]
    v = _chord_fractions(left)[None, :, None]
    B, T = bottom[:, None, :], top[:, None, :]
    L, R = left[None, :, :], right[None, :, :]
    return ((1 - v) * B + v * T + (1 - u) * L + u * R
            - ((1 - u) * (1 - v) * bottom[0] + u * (1 - v) * bottom[-1]
               + (1 - u) * v * top[0] + u * v * top[-1]))


def node_grids(spec) -> list[tuple[int, np.ndarray]]:
    """(layer index, node grid) of every patch of *spec*'s face, unrotated:
    the centre patch as a Coons patch of the inner curves, every ring
    the linear blend of its two boundaries at the radial grading."""
    outlines = spec.outlines
    corners = spec.corners()
    core = outlines[0]
    mb = spec.mbmp
    counts = [core.side_count(k, 4) for k in range(4)]
    s = [bump(c, mb) for c in counts]

    # core: centre patch from the inner curves, then the four ring patches
    inner = [outline(core, k, s[k], inner=True) for k in range(4)]
    out = [(0, _coons(bottom=inner[2], top=inner[0][::-1],
                      left=inner[1][::-1], right=inner[3]))]
    t = progression(spec._core_nrad, spec._core_mprg)
    prev = [outline(core, k, s[k]) for k in range(4)]
    out += [(0, _ring(inner[k], prev[k], t)) for k in range(4)]

    for i, (sh, o) in enumerate(zip(spec.shells, outlines[1:]), start=1):
        t = progression(sh.nrad, sh.mprg)
        c = corners[i]
        cur = [o.side(c[k], c[(k + 1) % 4], s[k]) for k in range(4)]
        out += [(i, _ring(prev[k], cur[k], t)) for k in range(4)]
        prev = cur
    return out


def section_cells(spec) -> int:
    """Quads in one O-H cross-section (pure; DESIGN P4).

    With ``c = spec.side_counts`` (divisions per outer curve), the core is
    a ``c[0] × c[1]`` centre patch plus one ring patch of ``c[k] × nrad``
    per side; every shell adds the same ring again with its own ``nrad``.
    A circle has ``c[k] = nang // (n_outer // 4)``; a rectangle
    ``nang_w, nang_h, nang_w, nang_h``.
    """
    c = spec.side_counts
    nrads = [spec._core_nrad] + [sh.nrad for sh in spec.shells]
    return c[0] * c[1] + sum(c) * sum(nrads)
