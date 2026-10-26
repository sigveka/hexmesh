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
import json
import math
import re
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import gmsh

from ..core.spec import PipeSpec
from ..faces._gmsh_helpers import add_physical_group
from ..quality_hex import METRICS, hex_vertices
from . import intent
from ..io.writers.openfoam_boundary import roles_path, write_roles
from .signature import check_port_pairs, classify, signature
from .corners import transfinite_surface_corners, transfinite_volume_corners
from .fittings import FillResult, Straight
from .quality import QualityReport, RegionQuality
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
    kind:    str = "add"     # "add", "close" or "prepend": how it entered the graph
    label:   str | None = None

    @property
    def name(self) -> str:
        """``label``, or ``<Type><index>`` (``Bend3``): used in wall patch names."""
        return self.label or f"{type(self.fitting).__name__}{self.index}"

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
        self._fitting_volumes: dict[int, list[int]] = {}
        self._fitting_walls:   dict[int, dict[str, list[int]]] = {}
        self._faces_built = False
        self._nozzle = None          # (drum, nozzle name) for from_nozzle()
        self._group_roles: dict[str, str] = {}
        self.inlet = self._new_interface(
            Frame.from_vectors(position, direction, up), spec, inlet_name,
        )
        self._tail = self.inlet

    @classmethod
    def from_nozzle(cls, drum, nozzle: str, lc: float | None = None) -> "Assembly":
        """Start a network at a drum nozzle (decision 0002).

        The drum is validated first.  The inlet is the nozzle face
        (``drum.frame(nozzle)``), with the nozzle's spec, and is named
        ``"{drum.name}_{nozzle}"``, which becomes its patch name (A7).
        """
        drum.validate()
        frame = drum.frame(nozzle)
        asm = cls(drum.nozzle(nozzle).spec, lc=lc, inlet_name=f"{drum.name}_{nozzle}")
        asm.inlet.frame = frame
        asm._nozzle = (drum, nozzle)
        return asm

    # ------------------------------------------------------------------
    # 1–2. Intent and placement (pure Python)
    # ------------------------------------------------------------------

    def add(self, source, fitting=None, names: Iterable[str] | None = None,
            label: str | None = None):
        """Append a fitting.

        ``add(fitting)`` continues from the tail; ``add(interface, fitting)``
        branches from a given interface.  Returns the outlet Interface (or a
        list for multi-outlet fittings).  *names* names the outlet
        interfaces; *label* names the fitting itself (its wall patch with
        ``walls_by_fitting``; default ``<Type><index>``).
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
        self._check_label(label)
        edge = Edge(len(self._edges), fitting, [source, *outlets], label=label)
        self._edges.append(edge)
        for iface in edge.ports:
            iface.edges.append(edge)

        if update_tail:
            self._tail = outlets[0]
        return outlets[0] if len(outlets) == 1 else outlets

    def close(self, source: Interface, target: Interface, fitting,
              label: str | None = None) -> None:
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

        self._check_label(label)
        edge = Edge(len(self._edges), fitting, [source, target], kind="close", label=label)
        self._edges.append(edge)
        source.edges.append(edge)
        target.edges.append(edge)
        if self._tail is source:
            self._tail = None

    def prepend(self, fitting: Straight, label: str | None = None) -> Interface:
        """Place *fitting* upstream of the inlet; return the new inlet.

        The new inlet sits ``fitting.length`` back along the current
        inlet's normal, and the edge ``[new, old]`` is validated like any
        other.  Only a ``Straight`` can be placed backwards.  The inlet's
        name moves to the new inlet, so the inlet patch keeps its name.
        """
        if self._faces_built:
            raise AssemblyError("cannot add fittings after the assembly is built")
        if type(fitting) is not Straight:
            raise TypeError(
                f"prepend places a Straight only, got {type(fitting).__name__}")
        old = self.inlet
        if not old.is_open:
            raise AssemblyError(f"the inlet {old} is not an open end")
        if self._nozzle is not None and old is self._interfaces[0]:
            raise AssemblyError(f"the inlet {old} is a drum nozzle; nothing can be "
                                "placed upstream of it")
        f = old.frame
        frame = Frame(f.position - fitting.length * f.normal, f.normal, f.up)
        new = self._new_interface(frame, old.spec, old.name)
        old.name = None
        self._check_label(label)
        edge = Edge(len(self._edges), fitting, [new, old], kind="prepend", label=label)
        self._edges.append(edge)
        new.edges.append(edge)
        old.edges.append(edge)
        self.inlet = new
        return new

    def extend_open_ends(self, upstream: float = 5.0, downstream: float = 10.0,
                         cells_per_diameter: float = 4.0) -> None:
        """Add straight runs at the inlet and at every open outlet.

        Lengths are in diameters of the end's core (the flow passage):
        *upstream* before the inlet, *downstream* after each outlet; 0
        skips that side.  An inlet at a drum nozzle is never extended.  Each run gets ``round(length / D ×
        cells_per_diameter)`` axial cells (at least 1).  Extended ends keep
        their patch names.  Must be called before ``build()``.
        """
        if self._faces_built:
            raise AssemblyError("cannot add fittings after the assembly is built")
        if upstream < 0 or downstream < 0 or cells_per_diameter <= 0:
            raise ValueError("upstream and downstream must be >= 0, "
                             "and cells_per_diameter > 0")

        def run(iface, diameters):
            d = 2.0 * iface.spec.core_shape.radius
            n = max(1, round(diameters * cells_per_diameter))
            return Straight(diameters * d, n_layers=n)

        outlets = [i for i in self.open_interfaces() if i is not self.inlet]
        names = {i.index: self.patch_name(i) for i in outlets}
        if downstream > 0:
            for iface in outlets:
                out = self.add(iface, run(iface, downstream))
                out.name, iface.name = names[iface.index], None
                if self._tail is iface:
                    self._tail = out
        at_nozzle = self._nozzle is not None and self.inlet is self._interfaces[0]
        if upstream > 0 and self.inlet.is_open and not at_nozzle:
            self.prepend(run(self.inlet, upstream))

    # ------------------------------------------------------------------
    # Intent serialisation (docs/tasks/0006)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """The Intent layer as plain JSON-serialisable data.

        Inlet pose and spec, then every ``add`` / ``close`` in order with
        its fitting's type and fields.  Lengths are in the user's unit,
        unconverted.  See ``hexmesh.assembly.intent``.
        """
        return intent.to_dict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Assembly":
        """Rebuild an assembly from :meth:`to_dict` output."""
        return intent.from_dict(cls, d)

    def save(self, path) -> None:
        """Write :meth:`to_dict` as indented JSON with sorted keys."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(intent.dumps(self))

    @classmethod
    def load(cls, path) -> "Assembly":
        """Read an assembly written by :meth:`save`."""
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    @property
    def interfaces(self) -> list[Interface]:
        return list(self._interfaces)

    @property
    def edges(self) -> list[Edge]:
        return list(self._edges)

    def _check_label(self, label: str | None) -> None:
        if label is None:
            return
        if not isinstance(label, str) or not re.fullmatch(r"[A-Za-z0-9_]+", label):
            raise AssemblyError(
                f"fitting label {label!r} must be letters, digits and _ only "
                "(it becomes part of a patch name)")
        if any(e.name == label for e in self._edges):
            raise AssemblyError(f"fitting label {label!r} is already used")

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
            # The fitting's own checks first: they give the most specific
            # reason (e.g. "Tee prototype supports single-layer specs only").
            try:
                edge.fitting.validate(
                    [p.frame for p in edge.ports], edge.ports[0].spec
                )
            except ValueError as e:
                raise AssemblyError(f"{edge}: {e}") from None
            # A4: each port pair, as connected, must be in a switch class the
            # fitting declares (decision 0011).  Before the exact type check
            # below, so the error names what differs.
            try:
                check_port_pairs(edge.fitting, [p.spec for p in edge.ports])
            except ValueError as e:
                raise AssemblyError(f"{edge}: {e}") from None
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
                    diff = classify(signature(want), signature(iface.spec)).differences
                    raise AssemblyError(
                        f"{edge}: port type at {iface} differs from the type "
                        f"the fitting declares"
                        + (f" ({'; '.join(map(str, diff))})" if diff else " (radii)")
                    )
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
            part = edge.fitting.fill(
                [p.face for p in edge.ports],
                [p.frame for p in edge.ports],
                edge.ports[0].spec, self.lc,
            )
            self._fitting_volumes[edge.index] = [v for vs in part.volumes.values() for v in vs]
            # Wall group per surface; a fill that names none has its
            # inlet's stack throughout (DESIGN A7, decision 0006).
            default = f"{edge.ports[0].spec.layer_names[-1]}_wall"
            walls: dict[str, list[int]] = {}
            for w in part.walls:
                walls.setdefault(part.wall_groups.get(w, default), []).append(w)
            self._fitting_walls[edge.index] = walls
            fill.merge(part)
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

    def write_physical_groups(self, walls_by_fitting: bool = False) -> None:
        """Physical groups derived from the graph (rule A7).

        Walls are named after the layer that is outermost where they are:
        ``{layer}_wall``, plus ``{layer}_end`` for the end annuli of a layer
        that stops or starts inside a fitting (decision 0006).  With
        *walls_by_fitting* each is split into one group per fitting,
        ``{group}_{name}`` (``Edge.name``: its label, or ``<Type><index>``).
        Each wall surface is still in exactly one group.

        Each group's role (``volume``, ``open_end``, ``wall`` or
        ``interface``) is recorded as it is added, from the graph and never
        from the name; :meth:`group_roles` returns them (decision 0013).
        """
        self.build()
        fill = self._fill
        self._group_roles = {}

        def group(dim, tags, name, role):
            add_physical_group(dim, tags, name)
            self._group_roles[name] = role

        for name, vols in fill.volumes.items():
            group(3, vols, name, "volume")
        for iface in self.open_interfaces():
            patch = self.patch_name(iface)
            for name, cs in iface.face.layers:
                group(2, list(cs.surfaces), f"{name}_{patch}", "open_end")
        if walls_by_fitting:
            names = [e.name for e in self._edges]
            if len(set(names)) != len(names):
                raise AssemblyError(f"fitting names are not unique: {names}")
            for e in self._edges:
                for base, tags in self._fitting_walls[e.index].items():
                    group(2, tags, f"{base}_{e.name}", "wall")
        else:
            merged: dict[str, list[int]] = {}
            for e in self._edges:
                for base, tags in self._fitting_walls[e.index].items():
                    merged.setdefault(base, []).extend(tags)
            for base, tags in merged.items():
                group(2, tags, base, "wall")
        for label, tags in fill.interfaces.items():
            group(2, tags, label, "interface")

    def group_roles(self) -> dict[str, str]:
        """Physical-group name → role, as last written by
        :meth:`write_physical_groups` (so after :meth:`mesh`)."""
        if not getattr(self, "_group_roles", None):
            raise AssemblyError("no physical groups written yet; call mesh() first")
        return dict(self._group_roles)

    def mesh(self, dim: int = 3, *, walls_by_fitting: bool = False) -> None:
        """Build, write physical groups, and generate the mesh.

        *walls_by_fitting*: see :meth:`write_physical_groups`.
        """
        self.build()
        gmsh.model.occ.synchronize()
        self.write_physical_groups(walls_by_fitting)
        msh = gmsh.model.mesh
        for c in curve_constraints(self._fill.curves).values():
            msh.setTransfiniteCurve(c.tag, c.nodes, c.kind, c.coef)
        # Corners from tags, not GMSH's geometric choice, so geometry
        # variants of one assembly get identical node numbering (task 0007).
        for tag in dict.fromkeys(self._fill.surfaces):
            msh.setTransfiniteSurface(tag, cornerTags=transfinite_surface_corners(tag))
            msh.setRecombine(2, tag)
        for tag in self._fill.mesh_vols:
            msh.setTransfiniteVolume(tag, cornerTags=transfinite_volume_corners(tag))
            msh.setRecombine(3, tag)
        msh.generate(dim)

    def write(self, path: str, dim: int = 3, *, walls_by_fitting: bool = False) -> None:
        self.mesh(dim, walls_by_fitting=walls_by_fitting)
        gmsh.write(path)

    def write_openfoam(self, path: str, *, interfaces: bool = False,
                       walls_by_fitting: bool = False) -> None:
        """Mesh and write a ``.msh`` file for OpenFOAM's ``gmshToFoam``.

        Writes MSH 2.2 ASCII (``Mesh.MshFileVersion = 2.2``,
        ``Mesh.Binary = 0``), restoring the previous option values
        afterwards.  OpenFOAM v1912 ``gmshToFoam`` reads both 2.2 and 4.1
        and gives the same mesh (docs/integrations/openfoam.md); 2.2 is the
        version every OpenFOAM line reads.

        Physical volumes become cellZones named by material, so a
        multi-material mesh splits with ``splitMeshRegions -cellZones
        -overwrite``.  Material-interface groups
        (``interface_fluid_steel``, …) are left out unless *interfaces* is
        true: the split rebuilds every interface as a ``mappedWall`` pair
        itself, and ``gmshToFoam`` would only turn the groups into empty
        patches plus faceZones.  With *interfaces*, those faceZones are
        kept and the split is unaffected.  The groups stay in the GMSH
        model.

        Also writes the boundary-role manifest ``<stem>.roles.json`` next to
        the file (``pipe.msh`` → ``pipe.roles.json``), which
        ``hexmesh.io.writers.openfoam_boundary.apply_boundary_roles`` uses
        to retype the walls of the converted case.
        """
        if not str(path).endswith(".msh"):
            raise ValueError(f"write_openfoam writes a .msh file, got {path!r}")
        self.mesh(walls_by_fitting=walls_by_fitting)
        dropped = []
        if not interfaces:
            labels = set(self._fill.interfaces)
            for d, t in gmsh.model.getPhysicalGroups(2):
                name = gmsh.model.getPhysicalName(d, t)
                if name in labels:
                    dropped.append((d, t, name,
                                    list(gmsh.model.getEntitiesForPhysicalGroup(d, t))))
            if dropped:   # an empty list would remove every group
                gmsh.model.removePhysicalGroups([(d, t) for d, t, _, _ in dropped])
        write_roles(roles_path(path), self.group_roles(),
                    not_written=[name for _, _, name, _ in dropped])
        options = {k: gmsh.option.getNumber(k) for k in ("Mesh.MshFileVersion", "Mesh.Binary")}
        try:
            gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
            gmsh.option.setNumber("Mesh.Binary", 0)
            gmsh.write(str(path))
        finally:
            for k, v in options.items():
                gmsh.option.setNumber(k, v)
            for d, t, name, ents in dropped:
                gmsh.model.addPhysicalGroup(d, ents, t)
                gmsh.model.setPhysicalName(d, t, name)

    # ------------------------------------------------------------------
    # Quality
    # ------------------------------------------------------------------

    @property
    def volumes(self) -> dict[str, list[int]]:
        """Volume tags per material (after build)."""
        self.build()
        return {k: list(v) for k, v in self._fill.volumes.items()}

    def fitting_volumes(self) -> dict[int, list[int]]:
        """Volume tags per fitting, keyed by edge index (after build)."""
        self.build()
        return {k: list(v) for k, v in self._fitting_volumes.items()}

    def check_quality(self, quality_name: str = "minSICN",
                      threshold: float | None = None,
                      by: str = "material") -> QualityReport:
        """Quality report of the generated mesh.

        *quality_name* is a GMSH element quality ("minSICN", "minSIGE",
        "gamma", …) or a hex metric from ``quality_hex.METRICS``
        ("scaled_jacobian", "nes", …).  *by* groups the rows per
        "material" or per "fitting" (index and type, rule A2: a failure
        names its fitting).  *threshold* defaults to 0 for GMSH qualities
        and to the metric's own limit otherwise; an element is bad when it
        is at or beyond it, on the metric's worse side.
        """
        if by == "material":
            groups = [(name, None, vols) for name, vols in self.volumes.items()]
        elif by == "fitting":
            self.build()
            groups = [(f"#{e.index} {type(e.fitting).__name__}", e.index,
                       self._fitting_volumes[e.index]) for e in self._edges]
        else:
            raise ValueError(f'by must be "material" or "fitting", got {by!r}')

        metric = METRICS.get(quality_name)
        higher = metric.higher_is_better if metric else True
        if threshold is None:
            threshold = metric.default_threshold if metric else 0.0
        report = QualityReport(quality_name=quality_name, threshold=threshold,
                               higher_is_better=higher)
        for name, index, vols in groups:
            q = self._element_qualities(vols, quality_name, metric)
            if not q.size:
                continue
            bad = (q <= threshold) if higher else (q >= threshold)
            report.regions.append(RegionQuality(
                name=name, n_elements=len(q), n_bad=int(bad.sum()),
                min_quality=float(q.min()), max_quality=float(q.max()),
                mean_quality=float(q.mean()),
                quality_name=quality_name, threshold=threshold,
                higher_is_better=higher, fitting=index,
            ))
        return report

    @staticmethod
    def _element_qualities(vols: list[int], quality_name: str, metric) -> np.ndarray:
        if metric is not None:
            _, verts = hex_vertices(vols)
            return np.array([metric.fn(v) for v in verts])
        tags: list[int] = []
        for v in vols:
            _, etags, _ = gmsh.model.mesh.getElements(3, v)
            for arr in etags:
                tags.extend(arr.tolist())
        if not tags:
            return np.empty(0)
        return np.array(gmsh.model.mesh.getElementQualities(tags, quality_name))
