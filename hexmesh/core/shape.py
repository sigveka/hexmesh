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


@dataclass(frozen=True)
class SquareShape:
    """Single-patch square/rectangular cross-section (direct topology).

    This is the Python equivalent of the ``square.geo`` Function: four
    corner points, four edge lines, one quad surface — no inner OH square,
    no butterfly patches.

    .. warning::
        **Incompatible with OH (butterfly) topology.**
        ``CircleShape`` and ``RectShape`` both use a 5-patch OH structure
        (inner square + 4 surrounding quadrants).  ``SquareShape`` produces
        a single patch and therefore **cannot** be stacked with any OH-based
        layer.  Calling ``PipeSpec.shell()`` or ``PipeSpec.square_shell()``
        on a ``SquareShape`` core will raise ``TypeError``.

    Parameters
    ----------
    half_w : float
        Half-width (first in-plane axis).
    half_h : float
        Half-height (second in-plane axis).
    nang_w : int
        Mesh divisions along each width edge.
    nang_h : int
        Mesh divisions along each height edge.
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
        return math.sqrt(self.half_w ** 2 + self.half_h ** 2)

    @property
    def is_square(self) -> bool:
        return self.half_w == self.half_h and self.nang_w == self.nang_h


Shape = Union[CircleShape, RectShape, SquareShape]
