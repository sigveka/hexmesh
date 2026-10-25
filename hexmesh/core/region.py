"""
Material graph — materials and their conformal interfaces.

MaterialGraph
    Directed graph: nodes are material names, edges are conformal
    interfaces.  Drives Physical group generation and validates that
    fittings don't create unlabelled interfaces.

    For a single insulated pipe the graph is linear:
        fluid → pipe_wall → insulation

    For a bundle of tubes in a shell it fans out:
        fluid_1 → wall_1 ╮
        fluid_2 → wall_2 ├── shell
        fluid_3 → wall_3 ╯

    Interface labels are automatically derived from the edge (a, b) as
    "interface_{a}_{b}" unless an explicit label is supplied.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterator

from .cross_section import interface_group_name


@dataclass
class _Edge:
    a:     str
    b:     str
    label: str   # Physical Surface name for the interface


class MaterialGraph:
    """Directed graph of materials and their conformal interfaces.

    Usage
    -----
    Build the graph by chaining ``add_material`` and ``add_interface``
    calls.  PipeSpec.graph constructs it automatically from the layer
    stack, so manual construction is only needed for bundles or custom
    topologies.

    Examples
    --------
    >>> g = MaterialGraph()
    >>> g.add_material("fluid").add_interface("fluid", "pipe_wall") \\
    ...  .add_material("pipe_wall").add_interface("pipe_wall", "insulation") \\
    ...  .add_material("insulation")
    """

    def __init__(self) -> None:
        self._nodes: list[str]  = []
        self._edges: list[_Edge] = []

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------

    def add_material(self, name: str) -> "MaterialGraph":
        """Register a material node.  No-op if already present."""
        if name not in self._nodes:
            self._nodes.append(name)
        return self

    def add_interface(
        self,
        a:     str,
        b:     str,
        label: str | None = None,
    ) -> "MaterialGraph":
        """Register a conformal interface between materials *a* and *b*.

        Parameters
        ----------
        a, b : str
            Material names.  Both are auto-added if not yet registered.
        label : str, optional
            Physical Surface name.  Defaults to ``"interface_{a}_{b}"``.
        """
        self.add_material(a)
        self.add_material(b)
        resolved_label = label or interface_group_name(a, b)
        self._edges.append(_Edge(a=a, b=b, label=resolved_label))
        return self

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    @property
    def materials(self) -> list[str]:
        """Ordered list of material names."""
        return list(self._nodes)

    @property
    def interfaces(self) -> list[_Edge]:
        """All registered interface edges."""
        return list(self._edges)

    def neighbors(self, name: str) -> list[str]:
        """Materials that share an interface with *name*."""
        return [e.b for e in self._edges if e.a == name] + \
               [e.a for e in self._edges if e.b == name]

    def interface_label(self, a: str, b: str) -> str:
        """Return the Physical Surface label for the (a, b) interface."""
        for e in self._edges:
            if (e.a == a and e.b == b) or (e.a == b and e.b == a):
                return e.label
        raise KeyError(f"No interface registered between '{a}' and '{b}'.")

    def __iter__(self) -> Iterator[str]:
        return iter(self._nodes)

    def __contains__(self, name: str) -> bool:
        return name in self._nodes

    def __repr__(self) -> str:
        edges = ", ".join(f"{e.a}→{e.b}" for e in self._edges)
        return f"MaterialGraph([{', '.join(self._nodes)}], [{edges}])"
