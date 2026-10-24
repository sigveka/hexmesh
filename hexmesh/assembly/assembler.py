"""
Assembly — interface-first network assembly (DESIGN.md §5).

Pipeline
--------
1. Intent     ``add()`` records interfaces and fitting edges (no GMSH)
2. Place      interface poses are computed by ``fitting.ports()`` (no GMSH)
3. Validate   port types and fitting geometry are checked (no GMSH)
4. Faces      every interface face is built once
5. Fill       every fitting is filled between its port faces, any order
6. Groups     physical groups derived from the graph
7. Mesh       transfinite meshing; no node merging

Usage::

    asm = Assembly(pipe, direction=[0, 1, 0], up=[0, 0, 1])
    asm.add(Straight(0.2, n_layers=2))
    asm.add(Bend(radius=0.3, angle=90, n_layers=6))
    asm.add(Straight(0.2, n_layers=2))
    asm.mesh()
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import gmsh

from ..core.spec import PipeSpec
from ..faces._gmsh_helpers import add_physical_group
from ..network import QualityReport, RegionQuality
from .fittings import FillResult
from .interface import (
    Frame, Interface, build_face, check_supported, outer_radius, port_type,
)


class AssemblyError(ValueError):
    """Raised during validation; names the offending fitting or interface."""


def curve_constraints(records) -> dict:
    """One transfinite constraint per curve tag; disagreeing records raise.

    A curve shared by two fittings (an interface face curve) is reported by
    both; their records must agree.
    """
    out: dict = {}
    for c in records:
        prev = out.setdefault(c.tag, c)
        if (prev.nodes != c.nodes or prev.kind != c.kind
                or not math.isclose(prev.coef, c.coef, rel_tol=1e-12)):
            raise AssemblyError(
                f"curve {c.tag}: conflicting transfinite constraints {prev} and {c}"
            )
    return out


@dataclass(eq=False)
class Edge:
    """A fitting placed between its port interfaces (ports[0] = inlet)."""

    index:   int
    fitting: object
    ports:   list[Interface]

    def __repr__(self) -> str:
        return f"fitting #{self.index} {self.fitting!r}"


class Assembly:
    """Interface-first pipe network.

    Parameters
    ----------
    spec : PipeSpec
        Cross-section of the inlet interface.
    position, direction, up : array-like, optional
        Absolute pose of the inlet interface.  Defaults: origin, +X, +Z.
    lc : float, optional
        GMSH characteristic length; defaults to outer radius / 4.
    inlet_name : str
        Name of the inlet interface (used for its boundary patch).
    """

    def __init__(
        self,
        spec:       PipeSpec,
        position=None,
        direction=None,
        up=None,
        lc:         float | None = None,
        inlet_name: str = "inlet",
    ) -> None:
        self._interfaces: list[Interface] = []
        self._edges:      list[Edge]      = []
        self._lc = lc
        self._fill: FillResult | None = None
        self._faces_built = False
        self.inlet = self._new_interface(
            Frame.from_vectors(position, direction, up), spec, inlet_name,
        )
        self._tail = self.inlet

    # ------------------------------------------------------------------
    # 1–2. Intent and placement (pure Python)
    # ------------------------------------------------------------------

    def add(self, source, fitting=None, names: Iterable[str] | None = None):
        """Append a fitting.

        ``add(fitting)`` continues from the tail; ``add(interface, fitting)``
        branches from a given interface.  Returns the outlet Interface (or a
        list for multi-outlet fittings).
        """
        if self._faces_built:
            raise AssemblyError("cannot add fittings after the assembly is built")
        if fitting is None:
            source, fitting, update_tail = self._tail, source, True
        else:
            update_tail = False
        if source is None:
            raise AssemblyError("the tail was closed; pass the interface to add from")
        if not isinstance(source, Interface):
            raise TypeError(f"source must be an Interface, got {type(source).__name__}")

        port_list = fitting.ports(source.frame, source.spec)
        names = list(names) if names is not None else [None] * len(port_list)
        outlets = [
            self._new_interface(frame, spec, name)
            for (frame, spec), name in zip(port_list, names)
        ]
        edge = Edge(len(self._edges), fitting, [source, *outlets])
        self._edges.append(edge)
        for iface in edge.ports:
            iface.edges.append(edge)

        if update_tail:
            self._tail = outlets[0]
        return outlets[0] if len(outlets) == 1 else outlets

    def close(self, source: Interface, target: Interface, fitting) -> None:
        """Join two existing open interfaces with *fitting* (DESIGN.md §8).

        *source* must be a downstream end (an outlet of its fitting) and
        *target* an upstream end (the inlet of its fitting), so flow runs
        source → fitting → target.  Any fitting whose ``validate`` accepts
        the two frames can close a loop: ``Closure`` for an arbitrary gap,
        or a ``Straight`` / ``Bend`` that fits exactly.
        """
        if self._faces_built:
            raise AssemblyError("cannot add fittings after the assembly is built")
        for iface in (source, target):
            if not any(iface is i for i in self._interfaces):
                raise AssemblyError(f"{iface} does not belong to this assembly")
            if not iface.is_open:
                raise AssemblyError(f"{iface} is not an open interface")
        if source is target:
            raise AssemblyError("cannot close an interface onto itself")
        if source.edges[0].ports[0] is source:
            raise AssemblyError(f"source {source} is an upstream end, not an outlet")
        if target.edges[0].ports[0] is not target:
            raise AssemblyError(f"target {target} is a downstream end, not an inlet")

        edge = Edge(len(self._edges), fitting, [source, target])
        self._edges.append(edge)
        source.edges.append(edge)
        target.edges.append(edge)
        if self._tail is source:
            self._tail = None

    @property
    def interfaces(self) -> list[Interface]:
        return list(self._interfaces)

    @property
    def edges(self) -> list[Edge]:
        return list(self._edges)

    def _new_interface(self, frame: Frame, spec: PipeSpec, name: str | None) -> Interface:
        iface = Interface(len(self._interfaces), frame, spec, name)
        self._interfaces.append(iface)
        return iface

    # ------------------------------------------------------------------
    # 3. Validation (pure Python)
    # ------------------------------------------------------------------

    def validate(self, max_cells: int | None = None) -> None:
        """Check every interface and fitting; raise AssemblyError on failure.

        With *max_cells*, also reject an assembly whose exact cell count
        (``cell_count()``, computed without GMSH) exceeds the budget.
        """
        if not self._edges:
            raise AssemblyError("assembly has no fittings")
        for iface in self._interfaces:
            try:
                check_supported(iface.spec)
            except NotImplementedError as e:
                raise AssemblyError(f"{iface}: {e}") from None
        for edge in self._edges:
            # A4 — every port type must match the type the fitting declares
            # for it; a fitting that only joins existing interfaces keeps
            # its inlet type throughout.
            inlet = edge.ports[0]
            if getattr(edge.fitting, "places_outlet", True):
                declared = [s for _, s in edge.fitting.ports(inlet.frame, inlet.spec)]
            else:
                declared = [inlet.spec] * (len(edge.ports) - 1)
            for iface, want in zip(edge.ports[1:], declared):
                if port_type(iface.spec) != port_type(want):
                    raise AssemblyError(
                        f"{edge}: port type at {iface} differs from the type "
                        f"the fitting declares"
                    )
            try:
                edge.fitting.validate(
                    [p.frame for p in edge.ports], edge.ports[0].spec
                )
            except ValueError as e:
                raise AssemblyError(f"{edge}: {e}") from None
        if max_cells is not None:
            counts = self.cell_counts()
            total = sum(counts.values())
            if total > max_cells:
                worst = max(self._edges, key=lambda e: counts[e.index])
                raise AssemblyError(
                    f"assembly has {total} cells, over the budget of {max_cells}; "
                    f"largest is {worst} with {counts[worst.index]}"
                )

    def cell_counts(self) -> dict[int, int]:
        """Exact hex count per fitting (edge index), without GMSH (DESIGN P4)."""
        return {e.index: e.fitting.cell_count([p.frame for p in e.ports], e.ports[0].spec)
                for e in self._edges}

    def cell_count(self) -> int:
        """Exact hex count of the whole assembly, without GMSH (DESIGN P4)."""
        return sum(self.cell_counts().values())

    # ------------------------------------------------------------------
    # 4–5. Realisation
    # ------------------------------------------------------------------

    def build(self, order: Iterable[int] | None = None) -> None:
        """Validate, build interface faces, then fill fittings.

        Equivalent to ``build_faces()`` followed by ``fill(order)``.

        Parameters
        ----------
        order : iterable of int, optional
            Fitting fill order (edge indices).  Any permutation must give
            the same mesh (rule A6).  Default: insertion order.
        """
        if self._fill is not None:
            return
        self.build_faces()
        self.fill(order)

    def build_faces(self) -> None:
        """Pipeline steps 3–4: validate, then build every interface face once."""
        if self._faces_built:
            return
        self.validate()
        for iface in self._interfaces:
            iface.face = build_face(iface.spec, iface.frame, self.lc)
        gmsh.model.occ.synchronize()
        self._faces_built = True

    def fill(self, order: Iterable[int] | None = None) -> None:
        """Pipeline step 5: fill every fitting between its existing faces."""
        if self._fill is not None:
            return
        self.build_faces()
        edges = (self._edges if order is None
                 else [self._edges[i] for i in order])
        if sorted(e.index for e in edges) != list(range(len(self._edges))):
            raise AssemblyError("order must be a permutation of all fittings")

        fill = FillResult()
        for edge in edges:
            fill.merge(edge.fitting.fill(
                [p.face for p in edge.ports],
                [p.frame for p in edge.ports],
                edge.ports[0].spec, self.lc,
            ))
        gmsh.model.occ.synchronize()

        # Face builders leave construction points (arc centres, helpers)
        # that bound nothing; drop them so they do not become stray nodes.
        debris = [(0, p) for _, p in gmsh.model.getEntities(0)
                  if not gmsh.model.getAdjacencies(0, p)[0].size]
        if debris:
            gmsh.model.occ.remove(debris)
            gmsh.model.occ.synchronize()
        self._fill = fill

    @property
    def lc(self) -> float:
        """Characteristic length used for all faces."""
        return self._lc or outer_radius(self.inlet.spec) / 4

    # ------------------------------------------------------------------
    # 6–7. Groups and mesh
    # ------------------------------------------------------------------

    def open_interfaces(self) -> list[Interface]:
        """Interfaces touched by a single fitting — the network boundary."""
        return [i for i in self._interfaces if i.is_open]

    def patch_name(self, iface: Interface) -> str:
        """Boundary patch name of an open interface (rule A7)."""
        if iface.name:
            return iface.name
        ends = [i for i in self.open_interfaces() if i is not self.inlet]
        if len(ends) == 1 and iface is ends[0]:
            return "outlet"
        return f"port{iface.index}"

    def write_physical_groups(self) -> None:
        """Physical groups derived from the graph (rule A7)."""
        self.build()
        fill = self._fill
        for name, vols in fill.volumes.items():
            add_physical_group(3, vols, name)
        for iface in self.open_interfaces():
            patch = self.patch_name(iface)
            for name, cs in iface.face.layers:
                add_physical_group(2, list(cs.surfaces), f"{name}_{patch}")
        outer = self.inlet.spec.layer_names[-1]
        add_physical_group(2, fill.walls, f"{outer}_wall")
        for label, tags in fill.interfaces.items():
            add_physical_group(2, tags, label)

    def mesh(self, dim: int = 3) -> None:
        """Build, write physical groups, and generate the mesh."""
        self.build()
        gmsh.model.occ.synchronize()
        self.write_physical_groups()
        msh = gmsh.model.mesh
        for c in curve_constraints(self._fill.curves).values():
            msh.setTransfiniteCurve(c.tag, c.nodes, c.kind, c.coef)
        for tag in dict.fromkeys(self._fill.surfaces):
            msh.setTransfiniteSurface(tag)
            msh.setRecombine(2, tag)
        for tag in self._fill.mesh_vols:
            msh.setTransfiniteVolume(tag)
            msh.setRecombine(3, tag)
        msh.generate(dim)

    def write(self, path: str, dim: int = 3) -> None:
        self.mesh(dim)
        gmsh.write(path)

    # ------------------------------------------------------------------
    # Quality
    # ------------------------------------------------------------------

    @property
    def volumes(self) -> dict[str, list[int]]:
        """Volume tags per material (after build)."""
        self.build()
        return {k: list(v) for k, v in self._fill.volumes.items()}

    def check_quality(self, quality_name: str = "minSICN",
                      threshold: float = 0.0) -> QualityReport:
        """Per-material GMSH quality report of the generated mesh."""
        report = QualityReport(quality_name=quality_name, threshold=threshold)
        for name, vols in self.volumes.items():
            tags: list[int] = []
            for v in vols:
                _, etags, _ = gmsh.model.mesh.getElements(3, v)
                for arr in etags:
                    tags.extend(arr.tolist())
            if not tags:
                continue
            q = np.array(gmsh.model.mesh.getElementQualities(tags, quality_name))
            report.regions.append(RegionQuality(
                name=name, n_elements=len(q), n_bad=int((q <= threshold).sum()),
                min_quality=float(q.min()), max_quality=float(q.max()),
                mean_quality=float(q.mean()),
                quality_name=quality_name, threshold=threshold,
            ))
        return report
