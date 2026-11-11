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
from typing import Iterable

import numpy as np

from ..errors import HexmeshNotice
from .errors import AssemblyError, AssemblyTypeError
from ..core.spec import PipeSpec
from . import intent
from ..io.writers import msh_comments
from .sweep import Arc
from .fittings import FillResult, Straight
from .quality import QualityReport
from .interface import Frame, Interface, outer_radius
from . import _graph, _validate, _realise, _checks, _output
from ._graph import Edge
from ._realise import curve_constraints  # noqa: F401  (tests import it from here)


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
    axial_cell : float, optional
        Target axial cell length.  A sweep fitting added with
        ``n_layers=None`` gets ``ceil(L / axial_cell)`` layers (``L`` its
        centreline length), or more if its own checks need more; the
        resolved count is stored in the fitting (decision 0024).
    """

    def __init__(
        self,
        spec:       PipeSpec,
        position=None,
        direction=None,
        up=None,
        lc:         float | None = None,
        inlet_name: str = "inlet",
        axial_cell: float | None = None,
    ) -> None:
        if axial_cell is not None and not axial_cell > 0:
            raise AssemblyError(f"axial_cell must be positive, got {axial_cell!r}",
                                code="size_not_positive", where={"field": "axial_cell"},
                                value=axial_cell, limit={"min_exclusive": 0})
        self.axial_cell = axial_cell
        self._interfaces: list[Interface] = []
        self._edges:      list[Edge]      = []
        self._lc = lc
        self._fill: FillResult | None = None
        self._fitting_volumes: dict[int, list[int]] = {}
        self._checked_volumes: dict[int, list[int]] = {}
        self._fitting_walls:   dict[int, dict[str, list[int]]] = {}
        self._fitting_projections: dict[int, list[tuple[object, list[int]]]] = {}
        # per fitting name: largest projection move and move / local edge
        # length, from the last mesh() (decision 0029)
        self.projection_report: dict[str, dict[str, float]] = {}
        #: per fitting name: what hexmesh changed in gmsh's mesh in the last
        #: mesh() (decision 0046 rule 5, task 0123): :meth:`_record_corrections`
        self.corrections: dict[str, dict] = {}
        self._faces_built = False
        self._nozzle = None          # (drum, nozzle name) for from_nozzle()
        self._group_roles: dict[str, str] = {}
        self._meshed = False
        self.mesh_order = 1             # 2 after mesh(order=2) (task 0076)
        #: Quality warnings from the last ``validate()`` (task 0047):
        #: ``"<interface>: <message>"``, also issued as ``UserWarning``.
        self.warnings: list[str] = []
        #: Notices from the last ``validate()``: not faults, so not warnings
        #: (decision 0046 rule 5): :class:`hexmesh.errors.HexmeshNotice`.
        self.notices: list[HexmeshNotice] = []
        self.inlet = self._new_interface(
            Frame.from_vectors(position, direction, up), spec, inlet_name,
        )
        self._tail = self.inlet

    @classmethod
    def from_nozzle(cls, drum, nozzle: str, lc: float | None = None,
                    axial_cell: float | None = None) -> "Assembly":
        """Start a network at a drum nozzle (decision 0002).

        The drum is validated first.  The inlet is the nozzle face
        (``drum.frame(nozzle)``), with the nozzle's spec, and is named
        ``"{drum.name}_{nozzle}"``, which becomes its patch name (A7).
        """
        drum.validate()
        frame = drum.frame(nozzle)
        asm = cls(drum.nozzle(nozzle).spec, lc=lc, inlet_name=f"{drum.name}_{nozzle}",
                  axial_cell=axial_cell)
        asm.inlet.frame = frame
        asm.inlet.equipment = True
        asm._nozzle = (drum, nozzle)
        return asm

    # ------------------------------------------------------------------
    # 1–2. Intent and placement (pure Python)
    # ------------------------------------------------------------------

    def add(self, source, fitting=None, names: Iterable[str] | dict | None = None,
            label: str | None = None, origin: dict | None = None):
        """Append a fitting.

        ``add(fitting)`` continues from the tail; ``add(interface, fitting)``
        branches from a given interface.  Returns the outlet Interface (or a
        list for multi-outlet fittings, in ``fitting.port_names`` order).
        After a multi-outlet fitting the tail continues on its first port
        (a tee's ``main``, a wye's ``left``).

        *names* names the outlet interfaces: a list in port order, or a dict
        keyed by port name (``{"branch": "tap1"}``; ``Tee``: ``main``,
        ``branch``; ``Wye``: ``left``, ``right``; one-outlet fittings:
        ``outlet``).  *label* names the fitting itself (its wall patch with
        ``walls_by_fitting``; default ``<Type><index>``).  *origin*: where
        an importer read the fitting from, a JSON-safe mapping (``file``,
        ``line``, ``record``, ``record_id``), for its error messages only;
        never saved.

        Input-only fields are resolved here from the inlet frame
        (``fitting.resolve``): ``toward=`` becomes ``roll``, and
        ``n_layers=None`` a count from ``axial_cell``.  The stored fitting
        holds only the resolved values (decision 0024).
        """
        return _graph.add(self, source, fitting, names, label, origin)

    def close(self, source: Interface, target: Interface, fitting,
              label: str | None = None, origin: dict | None = None) -> None:
        """Join two existing open interfaces with *fitting* (DESIGN.md §8).

        *source* must be a downstream end (an outlet of its fitting) and
        *target* an upstream end (the inlet of its fitting), so flow runs
        source → fitting → target.  Any fitting whose ``validate`` accepts
        the two frames can close a loop: ``Closure`` for an arbitrary gap,
        or a ``Straight`` / ``Bend`` that fits exactly.  *origin*: as for
        :meth:`add`.
        """
        return _graph.close(self, source, target, fitting, label, origin)

    def prepend(self, fitting: Straight, label: str | None = None,
                origin: dict | None = None) -> Interface:
        """Place *fitting* upstream of the inlet; return the new inlet.

        The new inlet sits ``fitting.length`` back along the current
        inlet's normal, and the edge ``[new, old]`` is validated like any
        other.  Only a ``Straight`` can be placed backwards.  The inlet's
        name moves to the new inlet, so the inlet patch keeps its name.
        *origin*: as for :meth:`add`.
        """
        return _graph.prepend(self, fitting, label, origin)

    def extend_open_ends(self, upstream: float = 5.0, downstream: float = 10.0,
                         cells_per_diameter: float = 4.0) -> None:
        """Add straight runs at the inlet and at every open outlet.

        Lengths are in diameters of the end's core (the flow passage; the
        hydraulic diameter 4A / P_w of a duct):
        *upstream* before the inlet, *downstream* after each outlet; 0
        skips that side.  An end marked as equipment (a drum nozzle, or a
        PCF equipment connection) is never extended.  Each run gets ``round(length / D ×
        cells_per_diameter)`` axial cells (at least 1).  Extended ends keep
        their patch names.  Must be called before ``build()``.
        """
        return _graph.extend_open_ends(self, upstream, downstream, cells_per_diameter)

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

    @classmethod
    def from_msh(cls, path) -> "Assembly":
        """Rebuild the assembly a ``.msh`` was written from, by the recipe
        in its ``$Comments`` block (decision 0038)."""
        recipe = msh_comments.read_recipe(path)
        if recipe is None:
            raise AssemblyError(f"{path}: no hexmesh recipe (written with provenance=False, "
                                "by another tool, or from an assembly to_dict can't describe)",
                                code="msh_has_no_recipe", where={"source": {"file": str(path)}})
        return cls.from_dict(recipe)

    def refined(self, k: int) -> "Assembly":
        """A new assembly at k× the resolution in every direction.

        Built from the saved description (:meth:`to_dict`, scaled,
        :meth:`from_dict`); this assembly is unchanged.  ``nang``, every
        ``nrad`` and every axial count (``n_layers``; a tee's ``n_run``,
        ``n_branch`` and ``n_turn``; a wye's ``n_run`` and ``n_branch``)
        are multiplied by *k*, and every grading ratio (radial ``mprg``,
        ``axial_grading``) becomes its k-th root, so each coarse cell
        splits into k cells of the same growth.  Geometry, topology and ``mbmp`` are unchanged.

        Exception: a wye's ``n_split`` grows only up to
        ``limits.WYE_N_SPLIT_MAX`` (6), and never shrinks.  More turning
        layers fold the wye under wall projection (a 120° wye at
        ``nang`` 8: ``n_split`` 12 at k = 2 and 24 at k = 4 both fold;
        task 0056), so its knee arcs refine only with ``nang``.

        **Cost:** k³ × the cells (``refined(2)`` has 8×).

        A spec built with ``first_cell=`` stores its resolved ``mprg``, so
        the refined first cell is smaller, not the requested height.

        Use it for grid-convergence studies (decision 0015).  It refines
        the whole network: ``nang`` and every layer's ``nrad`` are the same
        in every pipe of a connected network, so part of one can't be
        refined alone (GUIDE, "One density per network").
        """
        if isinstance(k, bool) or not isinstance(k, (int, np.integer)) or k < 1:
            raise AssemblyError(f"refined(k): k must be an integer >= 1, got {k!r}",
                                code="refine_factor_invalid", where={"field": "k"}, value=k,
                                limit={"min": 1, "integer": True})
        return type(self).from_dict(intent.refined_dict(self.to_dict(), int(k)))

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

    def _twist_for_toward(self, fitting, source: Interface) -> None:
        # kept on the class: called or patched from outside (task 0136)
        return _graph._twist_for_toward(self, fitting, source)

    def _new_interface(self, frame: Frame, spec: PipeSpec, name: str | None) -> Interface:
        # kept on the class: called or patched from outside (task 0136)
        return _graph._new_interface(self, frame, spec, name)

    # ------------------------------------------------------------------
    # 3. Validation (pure Python)
    # ------------------------------------------------------------------

    def validate(self, max_cells: int | None = None) -> None:
        """Check every interface and fitting; raise AssemblyError on failure.

        With *max_cells*, also reject an assembly whose exact cell count
        (``cell_count()``, computed without GMSH) exceeds the budget.
        """
        return _validate.validate(self, max_cells)

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
        return _realise.build(self, order)

    def build_faces(self) -> None:
        """Pipeline steps 3–4: validate, then build every interface face once."""
        return _realise.build_faces(self)

    def fill(self, order: Iterable[int] | None = None) -> None:
        """Pipeline step 5: fill every fitting between its existing faces."""
        return _realise.fill(self, order)

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
        return _output.patch_name(self, iface)

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
        return _output.write_physical_groups(self, walls_by_fitting)

    def group_roles(self) -> dict[str, str]:
        """Physical-group name → role, as last written by
        :meth:`write_physical_groups` (so after :meth:`mesh`)."""
        if not getattr(self, "_group_roles", None):
            raise AssemblyError("no physical groups written yet; call mesh() first",
                                code="no_mesh_yet", hint="call mesh() first")
        return dict(self._group_roles)

    def mesh(self, dim: int = 3, *, order: int = 1, incomplete: bool = False,
             walls_by_fitting: bool = False) -> None:
        """Build, write physical groups, and generate the mesh.

        *order* 2 (task 0076, decision 0034) raises the checked linear mesh
        to second order: Hex27, or Hex20 with *incomplete*.  The high-order
        nodes on projected walls are projected too, gmsh's high-order
        optimisers are never run, and an element whose Jacobian
        determinant is ≤ 0 at a Hex27 node or a Gauss point is an
        ``AssemblyError`` naming the fitting (:meth:`_second_order`).  A
        fitting with a ``second_order_limitation`` (the wye, an equal tee)
        is rejected before meshing.

        *walls_by_fitting*: see :meth:`write_physical_groups`.
        """
        return _realise.mesh(
            self, dim, order=order, incomplete=incomplete, walls_by_fitting=walls_by_fitting)

    def _revolve_high_order(self, e, arc: Arc) -> None:
        # kept on the class: called or patched from outside (task 0136)
        return _realise._revolve_high_order(self, e, arc)

    def _project_walls(self) -> dict[int, tuple[np.ndarray, np.ndarray]]:
        # kept on the class: called or patched from outside (task 0136)
        return _realise._project_walls(self)

    def write(self, path: str, dim: int = 3, *, order: int = 1, incomplete: bool = False,
              walls_by_fitting: bool = False, provenance: bool = True) -> None:
        """Mesh and write *path* in the format its extension names.  A
        ``.msh`` carries the recipe block unless *provenance* is false
        (:meth:`_stamp`).  *order*, *incomplete*: see :meth:`mesh`."""
        return _output.write(
            self, path, dim, order=order, incomplete=incomplete, walls_by_fitting=walls_by_fitting,
            provenance=provenance)

    def write_openfoam(self, path: str, *, interfaces: bool = False,
                       walls_by_fitting: bool = False, provenance: bool = True,
                       order: int = 1) -> None:
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

        The ``.msh`` carries the recipe block unless *provenance* is false;
        ``gmshToFoam`` skips it (docs/integrations/openfoam.md).

        *order* must be 1: ``gmshToFoam`` reads first-order elements only
        (task 0076), so ``order=2`` is an ``AssemblyError``.
        """
        return _output.write_openfoam(
            self, path, interfaces=interfaces, walls_by_fitting=walls_by_fitting,
            provenance=provenance, order=order)

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
        return _checks.check_quality(self, quality_name, threshold, by)
