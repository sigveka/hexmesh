"""
CrossSection — the result of building a 2-D face in GMSH.

A CrossSection is the output of every face builder (build_oh_circle,
build_oh_rect, build_annulus, build_square_shell).  It captures the GMSH
entity tags that subsequent layers or connectors must reuse for conformality.

Stacking protocol
-----------------
Conformality between concentric layers is guaranteed by sharing GMSH entity
tags rather than creating geometrically coincident duplicates.  When layer B
is stacked on layer A:

    layer B inner boundary  ==  layer A outer boundary
                             (same GMSH tags, not new coincident ones)

CrossSection exposes ``outer_points`` and ``outer_curves`` for exactly this
purpose.  The face builder for layer B receives the CrossSection of layer A
and aliases those tags as its own inner boundary.

BoundaryType
------------
Determines the curve type of the outer boundary and what may stack on top:

    CIRCULAR  outer_curves are Circle arcs.
              Can be extended with build_annulus or build_square_shell.

    SQUARE    outer_curves are Lines.
              Can tile with adjacent cells in a bundle.
              No further concentric circular layers may be added.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .shape import Shape


class BoundaryType(Enum):
    CIRCULAR = "circular"
    SQUARE   = "square"


@dataclass
class CrossSection:
    """GMSH entity tags for one layer of a pipe cross-section.

    All list attributes follow the same NE / NW / SW / SE ordering that the
    .geo function library uses:

        outer_points[0]  NE corner   (angle  π/4 + rot for circles,
        outer_points[1]  NW corner           3π/4 + rot, …)
        outer_points[2]  SW corner
        outer_points[3]  SE corner

        outer_curves[0]  NE→NW  (top    arc or line)
        outer_curves[1]  NW→SW  (left   arc or line)
        outer_curves[2]  SW→SE  (bottom arc or line)
        outer_curves[3]  SE→NE  (right  arc or line)

    Attributes
    ----------
    surfaces : list[int]
        GMSH surface tags.  5 tags for an OH core (centre + 4 quadrants),
        4 tags for an annular or square shell.
    center : int
        GMSH point tag of the pipe-axis centre point.
    outer_points : list[int]
        Four corner point tags [NE, NW, SW, SE].
    outer_curves : list[int]
        Four arc or line tags following NE→NW / NW→SW / SW→SE / SE→NE.
    shape : Shape
        Geometric and mesh parameters of *this* layer's outer boundary.
        Used for conformality checks when stacking.
    boundary_type : BoundaryType
        CIRCULAR if outer_curves are arcs, SQUARE if they are lines.
    h_axis : ndarray, shape (3,)
        Unit vector spanning the "horizontal" (right) direction of the
        cross-section plane.  Equal to ``cursor.right`` at build time.
    v_axis : ndarray, shape (3,)
        Unit vector spanning the "vertical" (up) direction of the
        cross-section plane.  Equal to ``cursor.up`` at build time.
    cx, cy, cz : float
        Centre coordinates.  Required by shell builders to position the
        outer boundary of the next layer.
    """

    surfaces:      list[int]
    center:        int
    outer_points:  list[int]
    outer_curves:  list[int]
    shape:         "Shape"
    boundary_type: BoundaryType
    h_axis:        np.ndarray
    v_axis:        np.ndarray
    cx:            float
    cy:            float
    cz:            float
    # Inner boundary — populated by face builders for taper connectors.
    # inner_points : [NE, NW, SW, SE] inner corner point tags
    # inner_curves : signed curve tags for the inner boundary loop in
    #                NE→NW, NW→SW, SW→SE, SE→NE order (same as outer_curves)
    # radial_curves: [NE, NW, SW, SE] radial line tags (inner→outer direction)
    inner_points:  list[int]   = field(default_factory=list)
    inner_curves:  list[int]   = field(default_factory=list)
    radial_curves: list[int]   = field(default_factory=list)
    # Number of transfinite node layers on radial lines; preserved through
    # extrusion connectors so MiterBend can rebuild the face with matching params.
    nrad: int   = 4
    # GMSH characteristic mesh length used when this face was built.  Preserved
    # so that junction connectors can rebuild a fresh face with the same lc
    # without it being hardcoded.
    lc:   float = 0.1
    # Angles (radians) of the outer corner points, in the same order as
    # outer_points.  Stored by face builders so annulus layers can position
    # their outer corners at matching angles without re-deriving them.
    # Empty list = not set (legacy CrossSection).
    corner_angles: list[float] = field(default_factory=list)
    # Number of outer structural corners.  Automatically derived from
    # outer_points in __post_init__; do not pass explicitly.
    n_outer: int = field(default=0)

    def __post_init__(self) -> None:
        if len(self.outer_points) not in (4, 8):
            raise ValueError(
                f"outer_points must have 4 or 8 entries, got {len(self.outer_points)}."
            )
        if len(self.outer_curves) != len(self.outer_points):
            raise ValueError(
                f"outer_curves length ({len(self.outer_curves)}) must match "
                f"outer_points length ({len(self.outer_points)})."
            )
        self.n_outer = len(self.outer_points)


@dataclass
class LayeredCrossSection:
    """An ordered stack of concentric CrossSection layers.

    layers
        List of (material_name, CrossSection) pairs, innermost first.
        The stacking invariant holds: layers[i+1] inner boundary ==
        layers[i].outer_points / outer_curves.

    Provides helpers used by connector implementations to iterate layers
    and derive interface names.
    """

    layers: list[tuple[str, CrossSection]] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def outermost(self) -> CrossSection:
        """CrossSection of the outermost layer."""
        return self.layers[-1][1]

    @property
    def innermost(self) -> CrossSection:
        """CrossSection of the innermost layer."""
        return self.layers[0][1]

    @property
    def names(self) -> list[str]:
        return [n for n, _ in self.layers]

    def get(self, name: str) -> CrossSection:
        """Retrieve a layer by material name."""
        for n, cs in self.layers:
            if n == name:
                return cs
        raise KeyError(f"No layer named '{name}'.")

    def interface_names(self) -> list[str]:
        """Auto-generated labels for interfaces between adjacent layers.

        Returns a list of length ``len(layers) - 1``.  For a stack
        ["fluid", "pipe_wall", "insulation"] this yields:
            ["fluid_to_pipe_wall", "pipe_wall_to_insulation"]
        """
        names = self.names
        return [f"{names[i]}_to_{names[i + 1]}" for i in range(len(names) - 1)]

    def add_layer(self, name: str, cs: CrossSection) -> "LayeredCrossSection":
        """Return a new LayeredCrossSection with *cs* appended."""
        return LayeredCrossSection(self.layers + [(name, cs)])

    def __len__(self) -> int:
        return len(self.layers)

    def __iter__(self):
        return iter(self.layers)
