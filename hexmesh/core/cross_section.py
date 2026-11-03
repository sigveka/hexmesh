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
CrossSection — the result of building a 2-D face in GMSH.

A CrossSection is the output of every face builder (``hexmesh.sections``).
It captures the GMSH entity tags that subsequent layers and fittings must
reuse for conformality.

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
              Can be extended with a ring (``sections.build_ring``).

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



def interface_group_name(inner: str, outer: str) -> str:
    """Physical-group name of the interface between two materials.

    ``interface_<inner>_<outer>``, materials in inner → outer order of the
    layer stack (decision 0013).  The ``interface_`` prefix keeps the name
    clear of the ``<a>_to_<b>`` patches OpenFOAM's ``splitMeshRegions``
    creates.
    """
    return f"interface_{inner}_{outer}"


class BoundaryType(Enum):
    CIRCULAR = "circular"
    SQUARE   = "square"


@dataclass
class CrossSection:
    """GMSH entity tags for one layer of a pipe cross-section.

    The lists follow the corner order of the section's layout: corner *k*
    of ``outer_points``, curve *k* from corner *k* to *k* + 1.  For the
    O-H layout (``sections.oh``: NE, NW, SW, SE, …) the fields
    ``inner_points``, ``inner_curves``, ``radial_curves``,
    ``corner_angles`` and the order of ``surfaces`` are its anatomy, not
    generic; a generic form is decided with the second layout (task 0082).

    Attributes
    ----------
    surfaces : list[int]
        GMSH surface tags, in the layout's patch order.
    center : int
        GMSH point tag of the pipe-axis centre point.
    outer_points : list[int]
        Corner point tags of the outer boundary.
    outer_curves : list[int]
        Arc, line or spline tags, curve *k* from corner *k* to *k* + 1.
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
    # Inner boundary and corner lines (the O-H layout's, sections.oh);
    # used to match corners between faces (assembly/corners.py).
    # inner_points : inner corner point tags, in corner order
    # inner_curves : signed inner-boundary curve tags, as outer_curves
    # radial_curves: corner-line tags (inner → outer), in corner order
    inner_points:  list[int]   = field(default_factory=list)
    inner_curves:  list[int]   = field(default_factory=list)
    radial_curves: list[int]   = field(default_factory=list)
    # Number of transfinite node layers on radial lines.
    nrad: int   = 4
    # GMSH characteristic mesh length used when this face was built.
    lc:   float = 0.1
    # Angles (radians) of the outer corner points, in the same order as
    # outer_points.  Stored by face builders so annulus layers can position
    # their outer corners at matching angles without re-deriving them.
    # Empty list = not set.
    corner_angles: list[float] = field(default_factory=list)
    # Section layout that built the face (``sections``): "oh" or "h".  An
    # H face has one patch and no inner boundary, corner lines or centre.
    layout: str = "oh"
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
        """Labels for the interfaces between adjacent layers.

        Returns a list of length ``len(layers) - 1``.  For a stack
        ["fluid", "pipe_wall", "insulation"] this yields:
            ["interface_fluid_pipe_wall", "interface_pipe_wall_insulation"]
        """
        names = self.names
        return [interface_group_name(names[i], names[i + 1])
                for i in range(len(names) - 1)]

    def add_layer(self, name: str, cs: CrossSection) -> "LayeredCrossSection":
        """Return a new LayeredCrossSection with *cs* appended."""
        return LayeredCrossSection(self.layers + [(name, cs)])

    def __len__(self) -> int:
        return len(self.layers)

    def __iter__(self):
        return iter(self.layers)
