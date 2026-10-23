"""
Connector protocol, SegmentResult, and JunctionResult.

Every 3-D operation (Straight, Bend, Reducer, …) implements the
Connector protocol: it accepts a LayeredCrossSection and a Cursor,
performs GMSH extrusion operations, and returns a SegmentResult.

Junction connectors (TJunction, …) instead return a JunctionResult,
which carries multiple Outlet objects — one per branch.

SegmentResult
    The output of a single-outlet connector.  Carries:

    end_face    LayeredCrossSection at the outlet end (for chaining).
    end_cursor  Updated Cursor pointing along the new pipe axis direction.
    regions     dict mapping material name → RegionSet (accumulated GMSH
                volume/surface tags for that material in this segment).
    interfaces  dict mapping interface label → list of GMSH surface tags
                for the conformal faces between adjacent materials.

JunctionResult
    The output of a multi-outlet connector.  Carries:

    outlets     list[Outlet] — one per branch (first is "main").
    regions     same as SegmentResult.
    interfaces  same as SegmentResult.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..core.cross_section import LayeredCrossSection
from ..core.cursor import Cursor
from ..core.region import RegionSet


@dataclass
class SegmentResult:
    """Output of a single-outlet connector call.

    Attributes
    ----------
    end_face : LayeredCrossSection
        The outlet cross-section, ready to feed the next connector.
    end_cursor : Cursor
        Updated cursor at the outlet face centre.
    regions : dict[str, RegionSet]
        Per-material accumulated entity tags for this segment only.
        Network merges these across all segments.
    interfaces : dict[str, list[int]]
        Conformal interface surfaces, keyed by auto-generated label
        "{mat_a}_to_{mat_b}".  These are the shared lateral surfaces
        produced by the stacking protocol.
    deferred_mesh : dict | None
        Optional mesh constraints that cannot be applied immediately because
        occ.synchronize() resets setTransfiniteSurface / setTransfiniteVolume
        attributes.  Connectors that build volumes manually (Reducer, Expander)
        populate this so Network can re-apply the constraints right before
        mesh.generate(), after all occ.synchronize() calls are done.

        Keys:
          "curves"   – list of (tag, n_nodes) tuples for setTransfiniteCurve
          "surfaces" – list of surface tags for setTransfiniteSurface + recombine
          "volumes"  – list of volume tags for setTransfiniteVolume + recombine
    """

    end_face:      LayeredCrossSection
    end_cursor:    Cursor
    regions:       dict[str, RegionSet]  = field(default_factory=dict)
    interfaces:    dict[str, list[int]] = field(default_factory=dict)
    deferred_mesh: "dict | None"         = field(default=None)


@dataclass
class Outlet:
    """One outlet of a junction connector.

    Attributes
    ----------
    face : LayeredCrossSection
        Outlet cross-section for the next connector on this branch.
    cursor : Cursor
        Updated cursor at the outlet face centre.
    label : str
        Branch label — ``"main"`` for the straight-through leg,
        ``"branch"`` (or ``"branch_0"``, ``"branch_1"``, …) for lateral
        offtakes.
    """

    face:   LayeredCrossSection
    cursor: Cursor
    label:  str = "main"


@dataclass
class JunctionResult:
    """Output of a multi-outlet (junction) connector.

    Attributes
    ----------
    outlets : list[Outlet]
        Two or more outlets.  Conventionally ``outlets[0]`` is ``"main"``
        (straight-through) and the rest are lateral branches.
    regions : dict[str, RegionSet]
        Per-material entity tags for the junction block only.
        Network merges these with the rest of the network.
    interfaces : dict[str, list[int]]
        Conformal interface surfaces within the junction block.
    deferred_mesh : dict | None
        Optional mesh constraints, same format as SegmentResult.deferred_mesh.
        Junction connectors that build volumes manually (TJunction stub block)
        populate this so Network can re-apply the constraints right before
        mesh.generate(), after all occ.synchronize() calls are done.
    """

    outlets:      list[Outlet]
    regions:      dict[str, RegionSet]  = field(default_factory=dict)
    interfaces:   dict[str, list[int]] = field(default_factory=dict)
    deferred_mesh: "dict | None"        = field(default=None)


@runtime_checkable
class Connector(Protocol):
    """Protocol satisfied by all connector types (Straight, Bend, …).

    ``connect`` is called by Network.add() with the current end-face and
    cursor.  It must return a SegmentResult (or JunctionResult for
    junction connectors) without mutating its inputs.
    """

    def connect(
        self,
        inlet:  LayeredCrossSection,
        cursor: Cursor,
    ) -> "SegmentResult | JunctionResult":
        ...
