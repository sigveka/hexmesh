"""
Shape variants for cross-section geometry.

A Shape carries the *geometric* parameters of a cross-section boundary and
the *mesh* parameters that must be consistent across the entire layer stack.

CircleShape
    Circular boundary.  One angular division count (nang) shared by all
    quadrant arcs.  Used by OHCircle, build_annulus, build_square_shell.

RectShape
    Rectangular boundary with independent width (nang_w) and height (nang_h)
    division counts.  Used by OHRect.  The special case half_w == half_h,
    nang_w == nang_h reduces to a square.

The union type Shape is used wherever a cross-section builder accepts either.
"""

from __future__ import annotations
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


Shape = Union[CircleShape, RectShape]

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
    """

    inlet:  object
    outlet: object
    u:      float

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

    def outline(self, k: int, s, inner: bool = False) -> np.ndarray:
        a = outline(self.inlet, k, s, inner)
        b = outline(self.outlet, k, s, inner)
        return (1.0 - self.u) * a + self.u * b
