"""
Shape variants for cross-section geometry.

A Shape carries the *geometric* parameters of a cross-section boundary and
the *mesh* parameters that must be consistent across the entire layer stack.

CircleShape
    Circular boundary.  One angular division count (nang) shared by all
    quadrant arcs.  Used by OHCircle, build_annulus, build_ring.

RectShape
    Rectangular boundary with independent width (nang_w) and height (nang_h)
    division counts.  Used by OHRect.  The special case half_w == half_h,
    nang_w == nang_h reduces to a square.

The union type Shape is used wherever a cross-section builder accepts either.

Outline protocol (decision 0026)
--------------------------------
Every layer of a stack has an outline, and every outline answers the same
questions, so the ring builder and the checks never ask which shape it is
(a contour shape would be one more class):

``corner(k)``            corner *k* (NE, NW, SW, SE) of the shape's own
                         O-H face, in-plane ``(u, v)`` before ``rot``;
``ring_corner(d)``       the corner a ring's corner line ends on, coming
                         from an inner corner in direction *d* (radians):
                         a circle meets it radially, a rectangle at its
                         corner in that quadrant;
``corners_from(ds)``     ``ring_corner`` for each direction: a ring's
                         outer corners (a ``BlendShape`` station has its
                         own, blended);
``side(p0, p1, s)``      point(s) at fraction *s* along the side between
                         two of its corners (an arc about the centre, or a
                         line);
``side_curve``           ``"arc"``, ``"line"`` or ``"spline"`` (a
                         ``BlendShape`` station, through ``side_samples``):
                         what the face builders draw between two corners;
``side_count(k, n)``     divisions of side *k* when there are *n* corners;
``extent(a)``            support function: distance from the centre to the
                         supporting line in direction *a* (a float, or an
                         array for an array of angles);
``max_extent``           the largest distance from the centre;
``distance(u, v)``       distance-like deviation of points from the
                         outline (0 on it);
``grown(dR)``            the outline offset outward by *dR* (a rectangle
                         keeps sharp corners);
``scaled(f)``            all lengths times *f*;
``lerp(other, u)``       the outline *u* of the way to *other* (same
                         class);
``counts``               divisions per side ``(width, height)``;
``period(n)``            smallest roll (radians) mapping it onto itself
                         with *n* corners;
``to_dict()``            JSON form, read back by ``shape_from_dict``.
"""

from __future__ import annotations
import functools
import math
from dataclasses import dataclass
from typing import Union

import numpy as np


@dataclass(frozen=True)
class CircleShape:
    """Circular cross-section specification.

    Parameters
    ----------
    radius : float
        Outer radius of the circle.
    nang : int
        Number of mesh divisions per quadrant arc.  Must be identical for
        every layer in the same pipe stack (conformality requirement).
    """

    radius: float
    nang:   int

    def __post_init__(self) -> None:
        if self.radius <= 0:
            raise ValueError(f"radius must be positive, got {self.radius}")
        if self.nang < 1:
            raise ValueError(f"nang must be >= 1, got {self.nang}")

    @property
    def max_extent(self) -> float:
        """Maximum radial extent from centre (radius)."""
        return self.radius

    # -- outline protocol (decision 0026) ---------------------------------

    side_curve = "arc"

    @property
    def counts(self) -> tuple[int, int]:
        return (self.nang, self.nang)

    def corner(self, k: int) -> np.ndarray:
        a = math.pi / 4 + math.pi / 2 * k
        return self.radius * np.array([math.cos(a), math.sin(a)])

    def ring_corner(self, d: float) -> np.ndarray:
        return self.radius * np.array([math.cos(d), math.sin(d)])

    def corners_from(self, directions) -> list[np.ndarray]:
        return [self.ring_corner(d) for d in directions]

    def side(self, p0, p1, s) -> np.ndarray:
        s = np.asarray(s, dtype=float)
        a0 = math.atan2(p0[1], p0[0])
        a1 = a0 + (math.atan2(p1[1], p1[0]) - a0) % (2 * math.pi)   # counter-clockwise
        a = a0 + (a1 - a0) * s
        return self.radius * np.stack([np.cos(a), np.sin(a)], axis=-1)

    def side_count(self, k: int, n_corners: int) -> int:
        return self.nang // (n_corners // 4)

    def extent(self, angle):
        return self.radius if np.ndim(angle) == 0 else np.full(np.shape(angle), self.radius)

    def period(self, n_corners: int) -> float:
        return 2 * math.pi / n_corners

    def distance(self, u, v):
        return np.abs(np.hypot(u, v) - self.radius)

    def grown(self, dR: float) -> "CircleShape":
        return CircleShape(radius=self.radius + dR, nang=self.nang)

    def scaled(self, f: float) -> "CircleShape":
        return CircleShape(radius=self.radius * f, nang=self.nang)

    def lerp(self, other: "CircleShape", u: float) -> "CircleShape":
        return CircleShape(radius=self.radius + (other.radius - self.radius) * u,
                           nang=self.nang)

    def to_dict(self) -> dict:
        return {"type": "circle", "radius": self.radius, "nang": self.nang}


@dataclass(frozen=True)
class RectShape:
    """Rectangular cross-section specification.

    Parameters
    ----------
    half_w : float
        Half-width  (first  in-plane axis: X for XY/XZ planes, Y for YZ).
    half_h : float
        Half-height (second in-plane axis: Y for XY, Z for XZ/YZ planes).
    nang_w : int
        Mesh divisions along each width  edge.  Shared across all layers.
    nang_h : int
        Mesh divisions along each height edge.  Shared across all layers.
    """

    half_w: float
    half_h: float
    nang_w: int
    nang_h: int

    def __post_init__(self) -> None:
        if self.half_w <= 0:
            raise ValueError(f"half_w must be positive, got {self.half_w}")
        if self.half_h <= 0:
            raise ValueError(f"half_h must be positive, got {self.half_h}")
        if self.nang_w < 1:
            raise ValueError(f"nang_w must be >= 1, got {self.nang_w}")
        if self.nang_h < 1:
            raise ValueError(f"nang_h must be >= 1, got {self.nang_h}")

    @property
    def max_extent(self) -> float:
        """Maximum radial extent from centre (corner diagonal)."""
        return math.sqrt(self.half_w**2 + self.half_h**2)

    @property
    def is_square(self) -> bool:
        """True when half_w == half_h and nang_w == nang_h."""
        return self.half_w == self.half_h and self.nang_w == self.nang_h

    # -- outline protocol (decision 0026) ---------------------------------

    side_curve = "line"

    @property
    def counts(self) -> tuple[int, int]:
        return (self.nang_w, self.nang_h)

    def corner(self, k: int) -> np.ndarray:
        su, sv = ((1, 1), (-1, 1), (-1, -1), (1, -1))[k % 4]
        return np.array([su * self.half_w, sv * self.half_h])

    def ring_corner(self, d: float) -> np.ndarray:
        return np.array([math.copysign(self.half_w, math.cos(d)),
                         math.copysign(self.half_h, math.sin(d))])

    def corners_from(self, directions) -> list[np.ndarray]:
        return [self.ring_corner(d) for d in directions]

    def side(self, p0, p1, s) -> np.ndarray:
        s = np.asarray(s, dtype=float)[..., None]
        return np.asarray(p0) + (np.asarray(p1) - np.asarray(p0)) * s

    def side_count(self, k: int, n_corners: int) -> int:
        return self.nang_w if k % 2 == 0 else self.nang_h

    def extent(self, angle):
        return self.half_w * np.abs(np.cos(angle)) + self.half_h * np.abs(np.sin(angle))

    def period(self, n_corners: int) -> float:
        return math.pi / 2 if self.is_square else math.pi

    def distance(self, u, v):
        return np.abs(np.maximum(np.abs(u) - self.half_w, np.abs(v) - self.half_h))

    def grown(self, dR: float) -> "RectShape":
        return RectShape(self.half_w + dR, self.half_h + dR, self.nang_w, self.nang_h)

    def scaled(self, f: float) -> "RectShape":
        return RectShape(self.half_w * f, self.half_h * f, self.nang_w, self.nang_h)

    def lerp(self, other: "RectShape", u: float) -> "RectShape":
        return RectShape(self.half_w + (other.half_w - self.half_w) * u,
                         self.half_h + (other.half_h - self.half_h) * u,
                         self.nang_w, self.nang_h)

    def to_dict(self) -> dict:
        return {"type": "rect", "half_w": self.half_w, "half_h": self.half_h,
                "nang_w": self.nang_w, "nang_h": self.nang_h}


Shape = Union[CircleShape, RectShape]

#: ``to_dict()`` type tag → outline class.
SHAPES = {"circle": CircleShape, "rect": RectShape}


def ring_corners(inner_corners, outline) -> list[np.ndarray]:
    """Corners of a ring's outer boundary *outline*: where the corner lines
    from *inner_corners* (``(u, v)``, before ``rot``) end, each leaving its
    inner corner along the direction from the centre (decision 0026)."""
    return [outline.ring_corner(math.atan2(p[1], p[0])) for p in inner_corners]


def longest_radial(inner, inner_corners, outer, outer_corners, samples: int = 65) -> float:
    """Longest line between corresponding points of a ring's two
    boundaries, at equal fractions along each side: where the ring is
    thickest, so where a ``first_cell`` grading is solved (decision 0026,
    item 7)."""
    n = len(inner_corners)
    s = np.linspace(0.0, 1.0, samples)
    return max(float(np.linalg.norm(
        outer.side(outer_corners[k], outer_corners[(k + 1) % n], s)
        - inner.side(inner_corners[k], inner_corners[(k + 1) % n], s), axis=-1).max())
        for k in range(n))


def shape_from_dict(d: dict) -> Shape:
    """Read back ``Shape.to_dict()``."""
    d = dict(d)
    kind = d.pop("type")
    if kind not in SHAPES:
        raise ValueError(f"unknown shape type {kind!r}; known: {', '.join(SHAPES)}")
    return SHAPES[kind](**d)

# Inner-square corner radius of the circular OH face, as a fraction of the
# core radius (``faces.oh_circle.build_oh_circle``).  The core's radial
# curves run from there to the circle, so they are ``(1 - OH_RATIO) * r``
# long.
OH_RATIO = 0.6


def oh_core_wall_span(radius: float, ratio: float = OH_RATIO) -> float:
    """Largest radial span of the 4-corner OH core ring, inner arc to circle.

    The inner arcs are centred on the opposite inner-square point
    ``(-ρ, 0)``, ``ρ = ratio·radius``, through the corner
    ``(ρ/√2, ρ/√2)``, so they bulge toward the centre and the ring is
    thickest at mid-arc: ``radius - (|(-ρ, 0) - corner| - ρ)``, 0.491 R
    for ``ratio = 0.6`` against 0.4 R at the corners.
    """
    rho = ratio * radius
    return radius - (math.hypot(rho + rho / math.sqrt(2), rho / math.sqrt(2)) - rho)


# ---------------------------------------------------------------------------
# Outlines: the O-H face of each shape as pure 2-D curves (task 0029)
# ---------------------------------------------------------------------------
# In-plane (u, v) coordinates, u along ``frame.right``, v along ``up``,
# before ``rot``.  Curve k runs from corner k to k + 1 (NE, NW, SW, SE), and
# *s* in [0, 1] is the fraction of its arc length.  These must match the
# face builders (``faces.oh_circle``, ``faces.oh_rect``): a transition's
# stations blend them, and its end stations are those builders' faces.

def _circle_outline(shape: CircleShape, k: int, s, inner: bool):
    s = np.asarray(s, dtype=float)
    r = shape.radius
    if not inner:
        a = math.pi / 4 + math.pi / 2 * (k + s)
        return np.stack([r * np.cos(a), r * np.sin(a)], axis=-1)
    # inner arc k is centred on the inner-square point opposite its middle
    rho = OH_RATIO * r
    mid = math.pi / 2 * (k + 1)
    c = -rho * np.array([math.cos(mid), math.sin(mid)])
    ends = [rho * np.array([math.cos(math.pi / 4 + math.pi / 2 * j),
                            math.sin(math.pi / 4 + math.pi / 2 * j)]) for j in (k, k + 1)]
    a0, a1 = (math.atan2(*(e - c)[::-1]) for e in ends)
    a1 = a0 + math.remainder(a1 - a0, 2 * math.pi)    # the short way (k = 1 crosses ±π)
    a = a0 + (a1 - a0) * s
    R = np.linalg.norm(ends[0] - c)
    return c + R * np.stack([np.cos(a), np.sin(a)], axis=-1)


def _rect_outline(shape: RectShape, k: int, s, inner: bool):
    s = np.asarray(s, dtype=float)[..., None]
    hw, hh = shape.half_w, shape.half_h
    if inner:                       # uniform ring, as faces.oh_rect
        t = (1.0 - OH_RATIO) * min(hw, hh)
        hw, hh = hw - t, hh - t
    corners = np.array([[hw, hh], [-hw, hh], [-hw, -hh], [hw, -hh]])
    return corners[k % 4] + (corners[(k + 1) % 4] - corners[k % 4]) * s


def outline(shape, k: int, s, inner: bool = False) -> np.ndarray:
    """Point(s) at arc-length fraction *s* along outer (or *inner*) curve
    *k* of *shape*'s O-H face, in unrotated in-plane coordinates."""
    if isinstance(shape, CircleShape):
        return _circle_outline(shape, k, s, inner)
    if isinstance(shape, RectShape):
        return _rect_outline(shape, k, s, inner)
    raise TypeError(f"no outline for {type(shape).__name__}")


@dataclass(frozen=True)
class BlendShape:
    """Station shape of a ``Transition`` (task 0029): the fraction *u* of
    the way from *inlet* to *outlet* (circle or rectangle, equal counts per
    side).  Every point is the linear blend of the two outlines' points at
    the same arc-length fraction (a "node blend").  A superellipse
    |x/a|^p + |y/b|^p = 1 with interpolated a, b, p was measured against it
    and gave the same min SICN and lower scaled Jacobians (task 0029).

    A shell's station (task 0046) also carries the corners its ring has at
    each end (*corners_in*, *corners_out*, ``PipeSpec.corners()``): its
    sides blend the end rings' sides between those corners, so the corner
    lines of every station blend too and the layers stay nested.  A core
    station has none and blends the O-H outlines (``outline``).
    """

    inlet:  object
    outlet: object
    u:      float
    corners_in:  tuple | None = None
    corners_out: tuple | None = None

    side_curve = "spline"

    @property
    def nang_w(self) -> int:
        return getattr(self.inlet, "nang_w", None) or self.inlet.nang

    @property
    def nang_h(self) -> int:
        return getattr(self.inlet, "nang_h", None) or self.inlet.nang

    @property
    def max_extent(self) -> float:
        return max(self.inlet.max_extent, self.outlet.max_extent)

    @property
    def is_square(self) -> bool:
        def sq(s):
            return isinstance(s, CircleShape) or s.half_w == s.half_h
        return sq(self.inlet) and sq(self.outlet) and self.nang_w == self.nang_h

    # -- outline protocol, as far as a station needs it -------------------

    @property
    def counts(self) -> tuple[int, int]:
        return (self.nang_w, self.nang_h)

    def period(self, n_corners: int) -> float:
        return math.pi / 2 if self.is_square else math.pi

    def outline(self, k: int, s, inner: bool = False) -> np.ndarray:
        a = outline(self.inlet, k, s, inner)
        b = outline(self.outlet, k, s, inner)
        return (1.0 - self.u) * a + self.u * b

    def side_samples(self, k: int, s) -> np.ndarray:
        """Point(s) at fraction *s* along outer side *k* (corner k → k+1)."""
        if self.corners_in is None:
            return self.outline(k, s)
        ci, co = self.corners_in, self.corners_out
        j = (k + 1) % len(ci)
        a = self.inlet.side(np.asarray(ci[k]), np.asarray(ci[j]), s)
        b = self.outlet.side(np.asarray(co[k]), np.asarray(co[j]), s)
        return (1.0 - self.u) * a + self.u * b

    def corner(self, k: int) -> np.ndarray:
        return self.side_samples(k, 0.0)

    def side_count(self, k: int, n_corners: int) -> int:
        return self.nang_w if k % 2 == 0 else self.nang_h

    def corners_from(self, directions) -> list[np.ndarray]:
        """The blended corners; a station's corner lines join the blended
        corners of its two boundaries, whatever the directions."""
        return [self.corner(k) for k in range(len(directions))]

    @functools.cached_property
    def boundary(self) -> np.ndarray:
        """Points along the whole outline, side 0 first (256 per side: an
        arc of 150° and radius R is then under-read by about 1e-5·R)."""
        s = np.linspace(0.0, 1.0, 256, endpoint=False)
        return np.vstack([self.side_samples(k, s) for k in range(4)])

    def extent(self, angle):
        """Support function of the sampled outline (exact at the samples)."""
        d = np.stack([np.cos(angle), np.sin(angle)])
        return (self.boundary @ d).max(axis=0)
