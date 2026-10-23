"""
Network — DAG-based pipe network assembly.

Network is the main user-facing class for building a pipe system in GMSH.
It maintains a directed acyclic graph (DAG) of Nodes connected by
Connectors, accumulates GMSH entity tags for each material, and exposes
methods for writing Physical groups.

Node
----
Each call to ``Network.add()`` returns a ``Node`` — a lightweight handle
carrying the ``LayeredCrossSection`` (outlet face) and ``Cursor`` at that
position.  Nodes can be passed back to ``add()`` to branch the network.

Linear pipe (backward-compatible)::

    net = Network(pipe, cursor=CURSOR, lc=0.08)
    net.add(Straight(0.5, n_layers=5))
    net.add(Bend(radius=0.3, angle=90, n_layers=8))
    net.add(Straight(0.5, n_layers=5))
    net.write_physical_groups()

T-junction (DAG form)::

    net = Network(pipe, cursor=CURSOR, lc=0.08)
    n0 = net.add(Straight(0.4, n_layers=4))          # inlet run
    n_main, n_branch = net.add(                      # junction block
        n0, TJunction(approach_length=0.15, branch_length=0.15),
    )
    net.add(n_main,   Straight(0.4, n_layers=4))     # main outlet run
    net.add(n_branch, Straight(0.4, n_layers=4))     # branch outlet run
    net.write_physical_groups()

Inlet / outlet detection
------------------------
A surface tag is a **system inlet** if it appears only in accumulated
``RegionSet.inlets`` and never in ``RegionSet.outlets``.  A surface is a
**system outlet** if the converse holds.  Intermediate faces (shared
between two segments) appear in both and are therefore excluded from
Physical groups.  This works correctly for linear chains, junctions, and
any DAG topology.
"""

from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Union

import gmsh
import numpy as np

from .faces._gmsh_helpers import add_physical_group
from .core.cross_section import LayeredCrossSection, CrossSection, BoundaryType
from .core.cursor import Cursor, Plane
from .core.region import RegionSet, MaterialGraph
from .core.spec import PipeSpec, BundleSpec, SquareShellSpec
from .connectors.base import Connector, SegmentResult, JunctionResult
from .faces.oh_circle import build_oh_circle
from .faces.oh_rect   import build_oh_rect
from .faces.annulus   import build_annulus
from .faces.square_shell import build_square_shell


@dataclass
class Node:
    """A node in the Network DAG.

    Represents a cross-section face at a specific location in the pipe
    network.  Returned by ``Network.add()`` and accepted as the *source*
    argument to explicitly route the next connector.

    Attributes
    ----------
    face : LayeredCrossSection
        Cross-section (GMSH surface entities) at this node.
    cursor : Cursor
        Position and orientation at this node.
    label : str
        Optional descriptive label (e.g. ``"main"``, ``"branch"``).
    """

    face:   LayeredCrossSection
    cursor: Cursor
    label:  str = ""


@dataclass
class RegionQuality:
    """Mesh quality statistics for one named region (physical volume group).

    Attributes
    ----------
    name : str
        Region (material) name.
    n_elements : int
        Total number of 3-D elements in this region.
    n_bad : int
        Elements with quality < ``threshold`` (default 0 — inverted cells).
    min_quality : float
        Worst (lowest) quality value among all elements.
    max_quality : float
        Best (highest) quality value.
    mean_quality : float
        Average quality across all elements.
    quality_name : str
        Name of the quality measure used (e.g. ``"minSICN"``).
    threshold : float
        The threshold below which an element is considered bad.
    """

    name:         str
    n_elements:   int
    n_bad:        int
    min_quality:  float
    max_quality:  float
    mean_quality: float
    quality_name: str
    threshold:    float

    @property
    def ok(self) -> bool:
        """True when no elements fall below the quality threshold."""
        return self.n_bad == 0

    def __str__(self) -> str:
        status = "OK" if self.ok else f"WARN ({self.n_bad} bad)"
        return (
            f"{self.name:<20s}  {self.n_elements:>6d} el  "
            f"min={self.min_quality:+.4f}  mean={self.mean_quality:+.4f}  "
            f"max={self.max_quality:+.4f}  [{status}]"
        )


@dataclass
class QualityReport:
    """Quality report for a meshed Network.

    Returned by :meth:`Network.check_quality`.  Contains per-region
    statistics and a summary flag.

    Attributes
    ----------
    regions : list[RegionQuality]
        One entry per named physical volume group.
    quality_name : str
        Quality measure used.
    threshold : float
        Bad-element threshold.
    """

    regions:      list[RegionQuality] = field(default_factory=list)
    quality_name: str   = "minSICN"
    threshold:    float = 0.0

    @property
    def total_elements(self) -> int:
        return sum(r.n_elements for r in self.regions)

    @property
    def total_bad(self) -> int:
        return sum(r.n_bad for r in self.regions)

    @property
    def ok(self) -> bool:
        return self.total_bad == 0

    @property
    def min_quality(self) -> float:
        return min((r.min_quality for r in self.regions), default=float("nan"))

    def __str__(self) -> str:
        lines = [
            f"Quality report  ({self.quality_name}, threshold={self.threshold})",
            "-" * 70,
        ]
        for r in self.regions:
            lines.append(str(r))
        lines.append("-" * 70)
        lines.append(
            f"{'TOTAL':<20s}  {self.total_elements:>6d} el  "
            f"min={self.min_quality:+.4f}  "
            f"{'OK' if self.ok else f'WARN ({self.total_bad} bad elements)'}"
        )
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"QualityReport(regions={len(self.regions)}, "
            f"total={self.total_elements}, bad={self.total_bad}, "
            f"min={self.min_quality:.4f})"
        )


# ---------------------------------------------------------------------------
# Post-mesh repair helper
# ---------------------------------------------------------------------------

def _repair_gap_wall_faces(
    all_regions: "dict[str, RegionSet]",
    outer_wall_classifier: "Callable[[int], str] | None" = None,
) -> None:
    """Find boundary mesh faces of volumes not covered by surface physical
    groups and add them to the appropriate wall group.

    This repairs T-junction gap faces: ``_find_e_outer_wall_surf`` removes the
    entire T-zone E outer wall arc (θ = -45° … +45°) from physical groups
    because the inner portion (θ < θ_max) is coincident with the stub saddle.
    After ``removeDuplicateNodes()`` the inner part is truly interior (shared
    between T-zone and stub hexes) while the gap (θ_max < |θ| < 45°) is a
    true boundary face with no physical group assignment.

    Algorithm
    ---------
    1. Build a face→(count, region) map from all hex8 volume elements.
       Faces with count=1 are boundary faces.
    2. Find surface entities not in any physical group.
    3. For each mesh element on those unassigned surfaces, if its nodes form a
       boundary face (count=1), add it to the appropriate wall group.
    """
    from collections import defaultdict

    mesh = gmsh.model.mesh

    # ── 1. face → (count, first adjacent region) ─────────────────────────
    _HEX8_FACES = (
        (0, 1, 2, 3),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (3, 2, 6, 7),
        (1, 2, 6, 5),
        (0, 4, 7, 3),
    )

    face_count: dict  = {}
    face_region: dict = {}

    for region_name, rset in all_regions.items():
        for vol_tag in rset.volumes:
            try:
                etypes, etags_list, enodes_list = mesh.getElements(3, vol_tag)
            except Exception:
                continue
            for etype, etags, enodes in zip(etypes, etags_list, enodes_list):
                if etype != 5:          # hex8 only
                    continue
                for i in range(len(etags)):
                    hn = enodes[i * 8 : i * 8 + 8]
                    for fi in _HEX8_FACES:
                        key = frozenset(int(hn[j]) for j in fi)
                        face_count[key] = face_count.get(key, 0) + 1
                        if key not in face_region:
                            face_region[key] = region_name

    bnd_region = {k: v for k, v in face_region.items() if face_count[k] == 1}
    if not bnd_region:
        return

    # ── 2. surface entities not in any physical group ─────────────────────
    assigned_surfs: set[int] = set()
    for _, pg_tag in gmsh.model.getPhysicalGroups(2):
        for ent in gmsh.model.getEntitiesForPhysicalGroup(2, pg_tag):
            assigned_surfs.add(ent)

    unassigned_surfs = {t for _, t in gmsh.model.getEntities(2)} - assigned_surfs
    if not unassigned_surfs:
        return

    # ── 3. collect gap mesh elements from unassigned surfaces ─────────────
    # wall_name → {etype: ([elem_tags], [elem_nodes_flat])}
    gap: dict[str, dict[int, tuple[list, list]]] = defaultdict(
        lambda: defaultdict(lambda: ([], []))
    )

    for surf in unassigned_surfs:
        try:
            etypes, etags_list, enodes_list = mesh.getElements(2, surf)
        except Exception:
            continue
        wname_surf = outer_wall_classifier(surf) if outer_wall_classifier else None
        for etype, etags, enodes in zip(etypes, etags_list, enodes_list):
            n_per = len(enodes) // max(len(etags), 1)
            for i, etag in enumerate(etags):
                face_nodes = enodes[i * n_per : i * n_per + n_per]
                key = frozenset(int(x) for x in face_nodes)
                region = bnd_region.get(key)
                if region is None:
                    continue
                wname = wname_surf if wname_surf is not None else f"{region}_wall"
                tags_l, nodes_l = gap[wname][etype]
                tags_l.append(int(etag))
                nodes_l.extend(int(x) for x in face_nodes)

    if not gap:
        return

    # ── 4. add gap elements to wall physical groups ───────────────────────
    # Build name→(tag, entity list) map for existing surface physical groups.
    pg_name_to_info: dict[str, tuple[int, list[int]]] = {}
    for _, pg_tag in gmsh.model.getPhysicalGroups(2):
        name = gmsh.model.getPhysicalName(2, pg_tag)
        ents = list(gmsh.model.getEntitiesForPhysicalGroup(2, pg_tag))
        pg_name_to_info[name] = (pg_tag, ents)

    for wname, by_etype in gap.items():
        disc = gmsh.model.addDiscreteEntity(2)
        for etype, (etags, enodes) in by_etype.items():
            mesh.addElements(2, disc, [etype], [etags], [enodes])

        if wname in pg_name_to_info:
            # Remove existing group and re-create with the gap entity appended.
            old_tag, old_ents = pg_name_to_info[wname]
            gmsh.model.removePhysicalGroups([(2, old_tag)])
            new_tag = gmsh.model.addPhysicalGroup(2, old_ents + [disc])
            gmsh.model.setPhysicalName(2, new_tag, wname)
        else:
            new_tag = gmsh.model.addPhysicalGroup(2, [disc])
            gmsh.model.setPhysicalName(2, new_tag, wname)


class Network:
    """DAG-based pipe network builder.

    Parameters
    ----------
    spec : PipeSpec
        Cross-section specification for the initial pipe.
    cursor : Cursor, optional
        Starting position and orientation.  Mutually exclusive with
        ``direction`` / ``up`` / ``position``.  When nothing is given the
        pipe starts at the origin heading along **+X** with up = **+Z**.
    lc : float, optional
        GMSH characteristic length — the mesh-size hint attached to every
        point when the cross-section geometry is created.  For fully
        structured (transfinite) pipes this has **no effect** on element
        count; the actual resolution is controlled by ``n_layers``,
        ``nrad``, and ``nang``.  It only matters for any unstructured
        fallback regions.  When omitted, a sensible value is derived
        automatically from the core shape's outer radius (``max_extent /
        4``), so you rarely need to set this explicitly.
    direction : array-like, shape (3,), optional
        Axis along which the first segment will grow.  An ``up`` vector is
        inferred automatically if not provided (see note below).  Mutually
        exclusive with ``cursor``.
    up : array-like, shape (3,), optional
        "Up" vector for the starting cross-section.  Only used together
        with ``direction``; ignored if ``cursor`` is supplied.  Determines
        the bend plane for the first ``Bend`` or ``MiterBend``.  When
        omitted an arbitrary perpendicular is chosen — fine for straight
        pipes, but specify explicitly if you care about bend orientation.
    position : array-like, shape (3,), optional
        Centre of the inlet face.  Defaults to the origin.  Only used
        together with ``direction``; ignored if ``cursor`` is supplied.

    Examples
    --------
    Zero-argument start (pipe along +X, origin, up = +Z)::

        net = Network(pipe)

    Specify direction only (up inferred)::

        net = Network(pipe, direction=[0, 0, 1])

    Specify direction and up (full in-plane orientation)::

        net = Network(pipe, direction=[0, 1, 0], up=[0, 0, 1])

    Non-origin start::

        net = Network(pipe, direction=[1, 0, 0], position=[2, 0, 0])

    Full control via Cursor (complex 3-D routing)::

        net = Network(pipe, cursor=Cursor(position=..., direction=..., up=...))

    Override lc for unstructured fallback regions::

        net = Network(pipe, lc=0.05)
    """

    def __init__(
        self,
        spec:       PipeSpec | BundleSpec,
        cursor:     Cursor | None = None,
        lc:         float | None = None,
        *,
        direction:  np.ndarray | list[float] | None = None,
        up:         np.ndarray | list[float] | None = None,
        position:   np.ndarray | list[float] | None = None,
        refinement: int = 1,
    ) -> None:
        if not isinstance(refinement, int) or refinement < 1:
            raise ValueError(
                f"Network refinement must be a positive integer, got {refinement!r}."
            )
        self._refinement = refinement
        self._spec = spec
        if lc is None:
            # Derive a sensible fallback from the core shape's outer radius.
            # For fully transfinite networks this value is never used, but it
            # prevents GMSH from defaulting to its own (often too large) size.
            if isinstance(spec, BundleSpec):
                _shape = spec.pipe.core_shape
            else:
                _shape = spec.core_shape
            self._lc = _shape.max_extent / 4.0
        else:
            self._lc = lc

        # Resolve starting cursor
        geo_kwargs = direction is not None or up is not None or position is not None
        if cursor is not None and geo_kwargs:
            raise TypeError(
                "Network(): pass either cursor= or direction/up/position kwargs, "
                "not both."
            )
        if geo_kwargs:
            if direction is None:
                raise TypeError(
                    "Network(): direction= is required when up= or position= are given."
                )
            _dir = np.asarray(direction, dtype=float)
            _pos = np.zeros(3) if position is None else np.asarray(position, dtype=float)
            if up is not None:
                _up = np.asarray(up, dtype=float)
            else:
                # Infer an arbitrary perpendicular — deterministic for cardinal axes.
                # +X → +Z,  +Y → -Z (odd but consistent),  +Z → +Y
                from .core.cursor import _perpendicular
                _up = _perpendicular(_dir)
            init_cursor = Cursor(position=_pos, direction=_dir, up=_up)
        elif cursor is not None:
            init_cursor = cursor
        else:
            # Default: pipe along +X at origin, up = +Z
            init_cursor = Cursor(
                position  = np.zeros(3),
                direction = np.array([1.0, 0.0, 0.0]),
                up        = np.array([0.0, 0.0, 1.0]),
            )

        # Accumulated across all segments
        self._all_regions:    dict[str, RegionSet]  = defaultdict(RegionSet)
        self._all_interfaces: dict[str, list[int]]  = defaultdict(list)

        # Deferred mesh constraints from connectors that manually build
        # surfaces/volumes (e.g. Reducer, Expander).  occ.synchronize() resets
        # setTransfiniteSurface / setTransfiniteVolume attributes, so these are
        # applied in mesh() AFTER the final synchronize.
        self._deferred_curves:   list[tuple[int, int]] = []  # (tag, n_nodes)
        self._deferred_surfaces: list[int]             = []
        self._deferred_volumes:  list[int]             = []

        # Root node (inlet of the whole network)
        init_face  = self._build_initial_face(spec, init_cursor)
        self._root = Node(face=init_face, cursor=init_cursor, label="root")
        self._tail = self._root   # tail of the current linear chain

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def cursor(self) -> Cursor:
        """Cursor at the tail node (last node on the main chain)."""
        return self._tail.cursor

    @property
    def current_face(self) -> LayeredCrossSection:
        """Face at the tail node (backward-compatible)."""
        return self._tail.face

    def add(
        self,
        connector_or_node: "Union[Connector, Node]",
        connector: "Connector | None" = None,
    ) -> "Node | list[Node]":
        """Apply a connector and return the resulting Node(s).

        Two calling conventions:

        ``net.add(connector)``
            Apply *connector* starting from the tail node (last node on
            the main chain).  Updates the tail.  Returns a single
            ``Node``.  Backward-compatible with the old linear API.

        ``net.add(source_node, connector)``
            Apply *connector* starting from *source_node*.  Does **not**
            update the tail.  Returns a ``Node`` for single-outlet
            connectors, or a ``list[Node]`` for junction connectors.

        Parameters
        ----------
        connector_or_node : Connector | Node
            Either the connector to apply (first form), or the source
            Node (second form).
        connector : Connector, optional
            The connector to apply when a source Node is given as the
            first argument.

        Returns
        -------
        Node
            Single outlet (for Straight, Bend, MiterBend, …).
        list[Node]
            Multiple outlets (for TJunction and other junction connectors).
        """
        if connector is None:
            # add(connector) — use tail as source
            source      = self._tail
            conn        = connector_or_node
            update_tail = True
        else:
            # add(source_node, connector) — explicit source
            if not isinstance(connector_or_node, Node):
                raise TypeError(
                    "When two arguments are given, the first must be a Node; "
                    f"got {type(connector_or_node).__name__}."
                )
            source      = connector_or_node
            conn        = connector
            update_tail = False

        # Scale n_layers by refinement if > 1.
        if self._refinement > 1 and hasattr(conn, 'n_layers'):
            import dataclasses as _dc
            if _dc.is_dataclass(conn):
                conn = _dc.replace(conn, n_layers=conn.n_layers * self._refinement)

        req = getattr(conn, 'REQUIRED_BOUNDARY_TYPE', None)
        if req is not None:
            actual = source.face.outermost.boundary_type
            if actual is not req:
                label_hint = f" (node '{source.label}')" if source.label else ""
                raise TypeError(
                    f"{type(conn).__name__} requires a {req.value!r} inlet face"
                    f"{label_hint}, but got {actual.value!r}. "
                    "Insert an appropriate transition connector to change face type."
                )

        result = conn.connect(source.face, source.cursor)

        if isinstance(result, JunctionResult):
            self._validate_junction_outlets(result, source.face)
            nodes = [Node(o.face, o.cursor, o.label) for o in result.outlets]
            self._merge(result.regions, result.interfaces)
            if result.deferred_mesh is not None:
                dm = result.deferred_mesh
                self._deferred_curves.extend(dm.get("curves", []))
                seen = set(self._deferred_surfaces)
                for s in dm.get("surfaces", []):
                    if s not in seen:
                        seen.add(s)
                        self._deferred_surfaces.append(s)
                self._deferred_volumes.extend(dm.get("volumes", []))
            if update_tail and nodes:
                self._tail = nodes[0]   # "main" outlet continues the chain
            return nodes

        # SegmentResult (single outlet)
        node = Node(result.end_face, result.end_cursor)
        self._merge(result.regions, result.interfaces)
        if result.deferred_mesh is not None:
            dm = result.deferred_mesh
            self._deferred_curves.extend(dm.get("curves", []))
            # Accumulate surfaces, deduplicating as we go
            seen = set(self._deferred_surfaces)
            for s in dm.get("surfaces", []):
                if s not in seen:
                    seen.add(s)
                    self._deferred_surfaces.append(s)
            self._deferred_volumes.extend(dm.get("volumes", []))
        if update_tail:
            self._tail = node
        return node

    def write_physical_groups(
        self,
        outer_wall_classifier: Callable[[int], str] | None = None,
        inlet_classifier:      Callable[[int], str] | None = None,
        outlet_classifier:     Callable[[int], str] | None = None,
    ) -> None:
        """Emit Physical Volume and Physical Surface declarations to GMSH.

        Synchronises the GMSH model before writing.

        Inlet / outlet detection uses set-difference: a surface that
        appears only in accumulated ``inlets`` (never in ``outlets``) is
        the system inlet; a surface only in ``outlets`` is a system
        outlet.  Intermediate faces that appear in both are excluded.
        This correctly handles linear chains, T-junctions, and arbitrary
        DAG topologies.

        Parameters
        ----------
        outer_wall_classifier : callable, optional
            ``f(surface_tag) -> str`` — assigns outer wall surfaces to
            named Physical Surface groups.  Default: ``"{material}_wall"``.
        inlet_classifier : callable, optional
            As above for inlet faces.  Default: ``"{material}_inlet"``.
        outlet_classifier : callable, optional
            As above for outlet faces.  Default: ``"{material}_outlet"``.
        """
        gmsh.model.occ.synchronize()

        # --- Volumes --------------------------------------------------------
        for name, rset in self._all_regions.items():
            if rset.volumes:
                add_physical_group(3, rset.volumes, name)

        # --- Inlet / outlet faces -------------------------------------------
        # Exclude intermediate cross-section faces (appear in both sets).
        for name, rset in self._all_regions.items():
            inlet_only  = sorted(set(rset.inlets)  - set(rset.outlets))
            outlet_only = sorted(set(rset.outlets) - set(rset.inlets))
            _write_classified(2, inlet_only,  inlet_classifier,
                              default_name=f"{name}_inlet")
            _write_classified(2, outlet_only, outlet_classifier,
                              default_name=f"{name}_outlet")

        # --- Outer walls ----------------------------------------------------
        for name, rset in self._all_regions.items():
            _write_classified(2, rset.walls, outer_wall_classifier,
                              default_name=f"{name}_wall")

        # --- Conformal interfaces -------------------------------------------
        for label, tags in self._all_interfaces.items():
            if tags:
                add_physical_group(2, tags, label)

    def mesh(
        self,
        dim:                   int = 3,
        outer_wall_classifier: "Callable[[int], str] | None" = None,
        inlet_classifier:      "Callable[[int], str] | None" = None,
        outlet_classifier:     "Callable[[int], str] | None" = None,
    ) -> None:
        """Generate the mesh up to *dim* dimensions.

        Calls ``write_physical_groups`` (synchronize + physical groups) then
        ``gmsh.model.mesh.generate``.  Idempotent — safe to call multiple
        times; each call re-generates the mesh.

        Parameters
        ----------
        dim : int
            Mesh dimension.  3 for full volumetric hex mesh (default).
        outer_wall_classifier : callable, optional
            ``f(surface_tag) -> str`` — assigns outer wall surfaces to named
            Physical Surface groups.  Forwarded to ``write_physical_groups``.
            Use ``gmsh.model.getBoundingBox(2, tag)`` inside the callable to
            classify by geometry (returns xmin,ymin,zmin,xmax,ymax,zmax).
            Default: ``"{material}_wall"``.
        inlet_classifier : callable, optional
            As above for inlet faces.  Default: ``"{material}_inlet"``.
        outlet_classifier : callable, optional
            As above for outlet faces.  Default: ``"{material}_outlet"``.
        """
        self.write_physical_groups(
            outer_wall_classifier=outer_wall_classifier,
            inlet_classifier=inlet_classifier,
            outlet_classifier=outlet_classifier,
        )
        # Re-apply deferred transfinite mesh constraints.
        # write_physical_groups() calls occ.synchronize() which resets any
        # setTransfiniteSurface / setTransfiniteVolume attributes set during
        # connect().  Connectors that build volumes manually (Reducer, Expander,
        # TJunction stub block) store their constraints in _deferred_* so we can
        # re-apply them here, after the final synchronize and before mesh.generate().
        self._apply_deferred_mesh_constraints()
        gmsh.model.mesh.generate(dim)
        # Merge geometrically coincident mesh nodes (e.g. at the T-junction saddle
        # opening where stub block and main pipe surfaces share the same geometry
        # but different GMSH surface tags).  This makes the mesh conformal for CFD
        # even without topologically shared surfaces.
        try:
            gmsh.model.mesh.removeDuplicateNodes()
        except AttributeError:
            pass
        # Repair unassigned boundary faces: T-junction T-zone steps have their E
        # outer wall removed from physical groups entirely, but the gap portion
        # (theta_max < |theta| < 45°) is a true boundary face.  Scan all hex
        # boundary faces not in any surface group and add them to the appropriate
        # wall group.
        _repair_gap_wall_faces(self._all_regions, outer_wall_classifier)

    def write(
        self,
        path:                  str,
        dim:                   int = 3,
        outer_wall_classifier: "Callable[[int], str] | None" = None,
        inlet_classifier:      "Callable[[int], str] | None" = None,
        outlet_classifier:     "Callable[[int], str] | None" = None,
    ) -> None:
        """Mesh and write to *path* in one call.

        Equivalent to ``net.mesh(dim)`` followed by ``gmsh.write(path)``.
        Use this for the common case where you do not need to inspect the
        model between meshing and saving.  For interactive inspection keep
        the two steps separate and call ``m.show()`` in between::

            with Model("my_pipe", verbose=True) as m:
                net = Network(...)
                ...
                net.mesh(dim=3)
                m.show()          # inspect before saving
                m.write("my_pipe.msh")

        Parameters
        ----------
        path : str
            Output file path.  Format is determined by the extension
            (e.g. ``.msh``, ``.vtk``, ``.cgns``).
        dim : int
            Mesh dimension passed to ``mesh()``.  Default 3.
        outer_wall_classifier : callable, optional
            Forwarded to ``write_physical_groups``.  See ``mesh()`` for details.
        inlet_classifier : callable, optional
            Forwarded to ``write_physical_groups``.
        outlet_classifier : callable, optional
            Forwarded to ``write_physical_groups``.
        """
        self.mesh(
            dim,
            outer_wall_classifier=outer_wall_classifier,
            inlet_classifier=inlet_classifier,
            outlet_classifier=outlet_classifier,
        )
        gmsh.write(path)

    def _apply_deferred_mesh_constraints(self) -> None:
        """Re-apply transfinite / recombine constraints reset by synchronize."""
        mesh = gmsh.model.mesh
        for tag, n_nodes in self._deferred_curves:
            mesh.setTransfiniteCurve(tag, n_nodes)
        for tag in self._deferred_surfaces:
            mesh.setTransfiniteSurface(tag)
            mesh.setRecombine(2, tag)
        for tag in self._deferred_volumes:
            mesh.setTransfiniteVolume(tag)
            mesh.setRecombine(3, tag)

    def check_quality(
        self,
        quality_name: str   = "minSICN",
        threshold:    float = 0.0,
        mesh:         bool  = True,
        print_report: bool  = True,
    ) -> QualityReport:
        """Mesh the model and report element quality statistics per region.

        Parameters
        ----------
        quality_name : str
            GMSH quality measure name.  Supported values include:

            ``"minSICN"`` (default)
                Minimum signed inverted condition number.  Range [−1, 1];
                perfect hex = 1, inverted element < 0.
            ``"minSJ"``
                Minimum sampled scaled Jacobian.
            ``"gamma"``
                Inscribed / circumscribed sphere ratio.
            ``"volume"``
                Element volume (useful for spotting collapsed cells).

        threshold : float
            Quality value at or below which an element is flagged as "bad".
            Default 0 — flags inverted (< 0) *and* degenerate zero-volume
            elements (== 0) whose Jacobian determinant is exactly zero.
        mesh : bool
            If True (default), calls :meth:`mesh` first.  Set to False
            if the mesh is already generated.
        print_report : bool
            If True (default), print the formatted report to stdout.

        Returns
        -------
        QualityReport
            Per-region statistics.  Access ``report.ok`` for a pass/fail
            flag and ``report.total_bad`` for the total bad element count.

        Examples
        --------
        ::

            net = Network(pipe, lc=0.08)
            net.add(Straight(1.0, n_layers=10))
            net.add(MiterBend(angle=90))
            net.add(Straight(1.0, n_layers=10))
            report = net.check_quality()
            assert report.ok, f"Mesh has {report.total_bad} bad elements"
        """
        if mesh:
            self.mesh()
        else:
            gmsh.model.occ.synchronize()

        report = QualityReport(quality_name=quality_name, threshold=threshold)

        for name, rset in self._all_regions.items():
            if not rset.volumes:
                continue

            # Collect all 3-D element tags in this region's volumes.
            # getElements(dim=3, tag=vol_tag) returns elements inside one
            # volume; we gather across all volumes in the region.
            all_tags: list[int] = []
            for vol in rset.volumes:
                elem_types, elem_tags, _ = gmsh.model.mesh.getElements(3, vol)
                for tag_array in elem_tags:
                    all_tags.extend(tag_array.tolist())

            if not all_tags:
                continue

            qualities = np.array(
                gmsh.model.mesh.getElementQualities(all_tags, quality_name)
            )

            n_bad = int(np.sum(qualities <= threshold))
            report.regions.append(RegionQuality(
                name         = name,
                n_elements   = len(qualities),
                n_bad        = n_bad,
                min_quality  = float(qualities.min()),
                max_quality  = float(qualities.max()),
                mean_quality = float(qualities.mean()),
                quality_name = quality_name,
                threshold    = threshold,
            ))

        if print_report:
            print(report)

        return report

    def check_hex_quality(
        self,
        mesh: bool = True,
        print_report: bool = True,
    ) -> "list[HexVolumeQuality]":
        """Compute all Table-2 hex quality metrics (Sorgente et al. 2023).

        Evaluates ten indicators per element across every named physical
        volume in the network:

        Face-aggregated (max over 6 faces unless noted)
            ``warping``             φ₂ per face — 0 = flat faces
            ``aspect_ratio``        ε₁ per face — 1 = square faces
            ``skewness``            ϑ  per face — 0 = orthogonal axes
            ``taper``               τ  per face — 0 = parallel sides
            ``interp_quality_min``  min 2/κ(A_i) per face — 1 = ideal
            ``interp_quality_avg``  36/Σκ² per face — 1 = ideal

        Jacobian-based (over 8 hex vertices)
            ``mean_ratio_min``         min 3/κ(A_k) — 1 = ideal
            ``mean_ratio_avg``         72/Σκ² — 1 = ideal
            ``shape_regularity_ratio`` min J / max J — 1 = uniform Jacobian
            ``shape_regularity_knupp`` 24/Σ(‖A_k‖_F²/J_k^{2/3}) — 1 = ideal

        Parameters
        ----------
        mesh : bool
            If True (default), mesh the model first.
        print_report : bool
            If True (default), print a per-region summary table.

        Returns
        -------
        list[HexVolumeQuality]
            One entry per physical volume containing hex elements.
        """
        from .quality_hex import HexVolumeQuality, evaluate_hex_quality

        if mesh:
            self.mesh()
        else:
            gmsh.model.occ.synchronize()

        results: list[HexVolumeQuality] = []
        for name, rset in self._all_regions.items():
            if not rset.volumes:
                continue
            vq = evaluate_hex_quality(list(rset.volumes), name=name)
            if vq is None:
                continue
            results.append(vq)
            if print_report:
                print(vq)
                print()

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_junction_outlets(
        self,
        result:     "JunctionResult",
        inlet_face: "LayeredCrossSection",
    ) -> None:
        """Warn when a junction outlet face is nearly tangential to its cursor.

        At a bifurcation point every outlet face must be perpendicular to the
        direction the next connector will extrude along.  A tangential
        extrusion produces zero-volume (degenerate) hexahedra.

        The check is performed per outlet using that outlet's own face axes
        (not the original inlet face normal), so a junction connector that
        builds a fresh face for angled branches will correctly suppress the
        warning once the fix is in place.

        Emits a ``RuntimeWarning`` for each outlet where
        ``|dot(outlet_face_normal, outlet_direction)| < 0.1``.
        """
        import warnings

        for outlet in result.outlets:
            _, cs0   = outlet.face.layers[0]
            face_n   = np.cross(cs0.h_axis, cs0.v_axis)
            norm     = float(np.linalg.norm(face_n))
            if norm < 1e-10:
                continue
            face_n  /= norm
            out_dir  = np.asarray(outlet.cursor.direction, dtype=float)
            dot      = abs(float(np.dot(face_n, out_dir)))
            if dot < 0.1:
                label = outlet.label or "(unlabelled)"
                warnings.warn(
                    f"Junction outlet '{label}': outlet face normal "
                    f"{np.round(face_n, 4).tolist()} is nearly tangential to "
                    f"the extrusion direction "
                    f"{np.round(out_dir, 4).tolist()} "
                    f"(|dot| = {dot:.4f}). "
                    "This will produce zero-volume hexahedra. "
                    "Build a fresh cross-section face perpendicular to the "
                    "branch direction before extruding.",
                    RuntimeWarning,
                    stacklevel=4,
                )

    def _merge(
        self,
        regions:    dict[str, RegionSet],
        interfaces: dict[str, list[int]],
    ) -> None:
        for name, rset in regions.items():
            self._all_regions[name].merge(rset)
        for label, tags in interfaces.items():
            self._all_interfaces[label].extend(tags)

    def _build_initial_face(
        self,
        spec:   PipeSpec,
        cursor: Cursor,
    ) -> LayeredCrossSection:
        """Build the inlet LayeredCrossSection from *spec* and *cursor*."""
        from .core.shape import CircleShape, RectShape, SquareShape
        from .faces.oh_circle import build_oh_circle8

        pos        = cursor.position
        cx, cy, cz = float(pos[0]), float(pos[1]), float(pos[2])
        h_axis     = cursor.right
        v_axis     = cursor.up
        lc         = self._lc
        r          = self._refinement

        layers:  list[tuple[str, CrossSection]] = []
        prev_cs: CrossSection | None = None

        core_name, core_shape = spec._core
        if isinstance(core_shape, CircleShape):
            scaled_shape = CircleShape(radius=core_shape.radius, nang=core_shape.nang * r)
            _builder = build_oh_circle8 if spec._n_outer == 8 else build_oh_circle
            cs = _builder(
                cx=cx, cy=cy, cz=cz,
                shape=scaled_shape, h_axis=h_axis, v_axis=v_axis, lc=lc,
                nrad=spec._core_nrad * r, mprg=spec._core_mprg,
                mbmp=spec._mbmp, rot=spec._rot,
            )
        elif isinstance(core_shape, RectShape):
            cs = build_oh_rect(
                cx=cx, cy=cy, cz=cz,
                shape=core_shape, h_axis=h_axis, v_axis=v_axis, lc=lc,
                nrad=spec._core_nrad * r, mprg=spec._core_mprg,
                mbmp=spec._mbmp,
            )
        elif isinstance(core_shape, SquareShape):
            from .faces.square import build_square
            cs = build_square(
                cx=cx, cy=cy, cz=cz,
                shape=core_shape, h_axis=h_axis, v_axis=v_axis, lc=lc,
                mbmp=spec._mbmp,
            )
        else:
            raise TypeError(f"Unsupported core shape: {type(core_shape)}")

        layers.append((core_name, cs))
        prev_cs = cs

        for shell in spec.shells:
            if isinstance(shell, SquareShellSpec):
                cs = build_square_shell(prev_cs, shell, lc, spec._mbmp)
            else:
                cs = build_annulus(
                    inner=prev_cs, dR=shell.dR, lc=lc,
                    nrad=shell.nrad * r, mprg=shell.mprg, mbmp=spec._mbmp,
                    rot=spec._rot,
                )
            layers.append((shell.name, cs))
            prev_cs = cs

        return LayeredCrossSection(layers)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _write_classified(
    dim:          int,
    tags:         list[int],
    classifier:   Callable[[int], str] | None,
    default_name: str,
) -> None:
    """Group *tags* by classifier result and write Physical groups."""
    if not tags:
        return
    if classifier is None:
        add_physical_group(dim, tags, default_name)
        return
    groups: dict[str, list[int]] = defaultdict(list)
    for tag in tags:
        groups[classifier(tag)].append(tag)
    for label, group_tags in groups.items():
        add_physical_group(dim, group_tags, label)
