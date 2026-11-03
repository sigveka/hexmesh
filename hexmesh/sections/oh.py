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
(``OH_RATIO``, the rectangle's ring inset, the inner arcs) are in
``core.shape``, which ``core`` uses too.

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

from ..core.shape import BlendShape, CircleShape, OH_RATIO, RectShape, oh_inner_corner

#: signature layout kinds (``assembly.signature``)
CORE_KIND = "oh_core"
RING_KIND = "annulus"


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
        return ([polar(OH_RATIO * shape.radius, a) for a in d],
                [polar(shape.radius, a) for a in d])
    if isinstance(shape, BlendShape):
        return ([rotated(shape.outline(k, 0.0, inner=True), rot) for k in range(4)],
                [rotated(shape.outline(k, 0.0), rot) for k in range(4)])
    return ([rotated(oh_inner_corner(shape, k), rot) for k in range(4)],
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
    level below), in declaration order."""
    corners: tuple[np.ndarray, ...]
    edges:   tuple[Edge, ...]


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
        out.append(Level(tuple(corners), tuple(edges)))
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
