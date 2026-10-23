"""
TJunction and YJunction connectors.

TJunction — perpendicular T-junction.

The branch always exits perpendicular to the main pipe axis.  Its
rotational position around the main pipe is specified either as a
global 3-D direction vector (``branch_direction``) or as a ``roll``
angle in degrees relative to the cursor frame.

Usage
-----
::

    net = Network(PIPE)
    n_inlet          = net.add(Straight(length=0.4, n_layers=4))
    n_main, n_branch = net.add(n_inlet,
                                TJunction(approach_length=0.15,
                                          departure_length=0.15,
                                          branch_length=0.15,
                                          branch_direction=[1, 0, 0]))
    net.add(n_main,   Straight(length=0.4, n_layers=4))
    net.add(n_branch, Straight(length=0.4, n_layers=4))
    net.write_physical_groups()
"""

from __future__ import annotations
import math
from dataclasses import dataclass

import numpy as np

from ..core.cross_section import LayeredCrossSection, BoundaryType
from ..core.cursor import Cursor
from ..core.region import RegionSet
from .base import Outlet, JunctionResult, SegmentResult


@dataclass
class TJunction:
    """Perpendicular T-junction connector.

    The branch is always perpendicular to the main pipe axis.  Its
    rotational position around the main pipe is specified with exactly
    one of:

    ``branch_direction`` (preferred for layout-driven workflows)
        A global 3-D vector pointing in the desired branch direction.
        It is automatically projected onto the plane perpendicular to
        the main pipe axis, so it does not need to be exactly
        perpendicular.

    ``roll`` (preferred for programmatic/parametric workflows)
        Rotation in **degrees** around the main pipe axis relative to
        the cursor frame.  ``0`` (default) → ``cursor.right`` side;
        ``90`` → ``cursor.up`` side.

    Parameters
    ----------
    approach_length : float
        Distance from the cursor entry point to the T-point centre.
        Must be ≥ ``branch_r`` (the minimum T-zone step length).  Values
        of 1–2 main pipe diameters are typical for CFD inlet development.
    departure_length : float
        Distance from the T-point centre to the main outlet cursor.
        Must be either ``0.0`` (cursor exits at T-point) or ≥ ``branch_r``
        so the T-zone layer boundary at the downstream saddle tip is included.
        Values of 1–2 main pipe diameters are typical for CFD.
    branch_length : float
        Distance from the T-point to the branch outlet face.  Must be
        strictly greater than the main pipe outer radius so the branch
        face clears the main pipe.
    branch_direction : sequence of 3 floats, optional
        Global branch direction vector.  Mutually exclusive with ``roll``.
    roll : float, optional
        Rotation around the pipe axis in degrees (cursor-relative).
        Mutually exclusive with ``branch_direction``.  Default ``0.0``.
    n_layers : int
        Hex layers in each extrusion direction.  Default 2.
    branch_r : float, optional
        Outer radius of the branch pipe.  When provided (and less than
        the main pipe outer radius), the side-tap stub-block architecture
        is used — producing non-overlapping all-hex geometry.  Must
        satisfy ``0 < branch_r < R_main``.  When ``None`` (default) the
        legacy overlapping-extrusion code is used for backward
        compatibility.
    """

    REQUIRED_BOUNDARY_TYPE = BoundaryType.CIRCULAR

    approach_length:  float
    branch_length:    float
    departure_length: float                 = 0.0
    branch_direction: "list[float] | None" = None
    roll:             "float | None"        = None
    n_layers:         int                   = 2
    branch_r:         "float | None"        = None

    def __post_init__(self) -> None:
        if self.approach_length <= 0:
            raise ValueError(
                f"TJunction.approach_length must be positive, got {self.approach_length!r}"
            )
        if self.departure_length < 0:
            raise ValueError(
                f"TJunction.departure_length must be >= 0, got {self.departure_length!r}"
            )
        if self.branch_length <= 0:
            raise ValueError(
                f"TJunction.branch_length must be positive, got {self.branch_length!r}"
            )
        if self.branch_direction is not None and self.roll is not None:
            raise ValueError(
                "TJunction: specify either branch_direction or roll, not both."
            )
        if self.roll is not None and not math.isfinite(self.roll):
            raise ValueError(
                f"TJunction.roll must be a finite number, got {self.roll!r}"
            )
        if self.branch_direction is not None:
            if len(self.branch_direction) != 3:
                raise ValueError(
                    "TJunction.branch_direction must be a 3-element vector, "
                    f"got length {len(self.branch_direction)}"
                )
        if self.n_layers < 1:
            raise ValueError(
                f"TJunction.n_layers must be >= 1, got {self.n_layers!r}"
            )
        if self.branch_r is not None and self.branch_r <= 0:
            raise ValueError(
                f"TJunction.branch_r must be positive, got {self.branch_r!r}"
            )

    def connect(
        self,
        inlet:  LayeredCrossSection,
        cursor: Cursor,
    ) -> JunctionResult:
        """Build the junction block.

        When ``branch_r`` is set (side-tap architecture)
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        The main leg is a normal straight extrusion along the main pipe axis.
        The branch leg is built as a stub block (5 + 4*n_shells hex volumes)
        connecting the saddle curve on the main pipe outer surface to the
        branch OH inlet face.  No volumes overlap.

        When ``branch_r`` is ``None`` (legacy path)
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        The main leg reuses the inlet face entities directly.  The branch leg
        requires a **fresh** face built at the junction centre and oriented
        perpendicular to the branch direction.  Both extrusions start at
        ``cursor.position`` and partly overlap — acceptable for visualisation
        but incorrect for CFD.

        Returns
        -------
        JunctionResult
            ``outlets[0]`` — ``"main"`` leg (straight-through)
            ``outlets[1]`` — ``"branch"`` leg (lateral offtake)
        """
        from .straight import Straight

        # --- Resolve branch direction ----------------------------------------
        if self.branch_direction is not None:
            d = np.asarray(self.branch_direction, dtype=float)
            pipe_dir = np.asarray(cursor.direction, dtype=float)
            d = d - np.dot(d, pipe_dir) * pipe_dir
            norm = float(np.linalg.norm(d))
            if norm < 1e-10:
                raise ValueError(
                    "TJunction.branch_direction is parallel to the main pipe axis."
                )
            d /= norm
            φ = math.atan2(
                float(np.dot(d, np.asarray(cursor.up,    dtype=float))),
                float(np.dot(d, np.asarray(cursor.right, dtype=float))),
            )
        else:
            φ = math.radians(self.roll if self.roll is not None else 0.0)

        rot_axis      = math.cos(φ) * cursor.up + math.sin(φ) * cursor.right
        branch_cursor = cursor.rotated(rot_axis, math.radians(90.0))
        # branch_cursor.position == cursor.position (rotation preserves position)

        if self.branch_r is not None:
            return self._connect_stub(inlet, cursor, branch_cursor)
        else:
            main_result = Straight(self.approach_length, self.n_layers).connect(
                inlet, cursor
            )
            return self._connect_legacy(inlet, cursor, main_result, branch_cursor)

    # ------------------------------------------------------------------
    # Side-tap stub block path (branch_r is set)
    # ------------------------------------------------------------------

    def _connect_stub(
        self,
        inlet:         LayeredCrossSection,
        cursor:        Cursor,
        branch_cursor: Cursor,
    ) -> JunctionResult:
        """Build branch leg as a stub block (non-overlapping, conformal geometry).

        T-zone steps (length = r_branch on each side of the T-point) are built
        as explicit OCC volumes via ``_build_tzone_step_manual`` so that
        ``occ.fragment()`` can be applied to them + the stub block without
        crashing the structured extrusion mesher.  Pre-step and rest-departure
        use normal ``Straight`` extrusion (excluded from fragment).
        """
        import warnings
        from .straight import Straight
        from .t_block import build_stub_block, saddle_conformality_check
        from ..core.shape import CircleShape
        from ..core.cross_section import LayeredCrossSection as LCS

        # --- Extract main pipe outer radius and mesh params -----------------
        outer_cs = inlet.outermost
        if not isinstance(outer_cs.shape, CircleShape):
            raise ValueError(
                "TJunction with branch_r requires a circular-core inlet "
                "(PipeSpec with CircleShape core)."
            )
        R_outer  = outer_cs.shape.radius
        r_branch = float(self.branch_r)  # type: ignore[arg-type]

        if r_branch >= R_outer:
            raise ValueError(
                f"TJunction.branch_r ({r_branch}) must be strictly less than the "
                f"main pipe outer radius R ({R_outer}).  Equal-diameter "
                "T-junctions are not yet supported by the side-tap approach."
            )

        core_cs = inlet.innermost
        nang = core_cs.shape.nang if isinstance(core_cs.shape, CircleShape) else 5
        nrad = core_cs.nrad
        lc   = core_cs.lc

        branch_dir   = np.asarray(branch_cursor.direction, dtype=float)
        main_dir_arr = np.asarray(cursor.direction, dtype=float)

        # --- Conformality check (warn, don't raise) -------------------------
        m, conformal, suggestions = saddle_conformality_check(r_branch, R_outer, nang)
        if not conformal:
            s_str = (
                ", ".join(f"{v:.4g}" for v in suggestions)
                if suggestions else "none for this nang"
            )
            warnings.warn(
                f"TJunction saddle-arc conformality not satisfied: "
                f"r={r_branch}, R={R_outer}, nang={nang}. "
                f"The mesh at the T-zone boundary will be non-conformal. "
                f"Conforming branch_r values for nang={nang}: [{s_str}].",
                stacklevel=4,
            )

        if self.approach_length < r_branch:
            raise ValueError(
                f"TJunction.approach_length ({self.approach_length}) must be >= "
                f"branch_r ({r_branch}) for the T-zone step split."
            )
        if 0 < self.departure_length < r_branch:
            raise ValueError(
                f"TJunction.departure_length ({self.departure_length}) must be "
                f"either 0 (minimum forced departure of branch_r={r_branch:.4g} is "
                f"always added) or >= branch_r ({r_branch}) for the T-zone step split."
            )

        n_tzone    = max(1, self.n_layers)
        outer_name = inlet.layers[-1][0]
        inner_name = inlet.layers[0][0]

        # --- Pre-step (structured Straight) ---------------------------------
        # The pre-step uses occ.extrude (structured) so the T-zone manual volumes
        # start from cursor-advance to the saddle tip position, not from the
        # TJunction entry.  occ.fragment() is NOT called: the T-zone manual
        # volumes create NEW surfaces (via _build_miter_outlet) that are
        # geometrically coincident with but topologically separate from the
        # pre-step's output surfaces.  removeDuplicateNodes() in Model.mesh()
        # merges the coincident mesh nodes, making the mesh conformal.
        if self.approach_length > r_branch:
            pre_step    = Straight(
                self.approach_length - r_branch, self.n_layers
            ).connect(inlet, cursor)
            tz_inlet    = pre_step.end_face
            tz_cursor   = pre_step.end_cursor
        else:
            pre_step    = None
            tz_inlet    = inlet
            tz_cursor   = cursor

        # --- T-zone approach (manual OCC volumes) ---------------------------
        tzone_approach = _build_tzone_step_manual(tz_inlet, tz_cursor, r_branch, n_tzone)
        junction_origin = tzone_approach.end_cursor.position

        # --- Build stub block at T-point ------------------------------------
        stub = build_stub_block(
            origin        = junction_origin,
            main_dir      = cursor.direction,
            branch_dir    = branch_dir,
            R             = R_outer,
            r             = r_branch,
            branch_length = self.branch_length,
            nang          = nang,
            nrad          = nrad,
            n_axial       = self.n_layers,
            lc            = lc,
        )

        # --- T-zone departure (manual OCC volumes) --------------------------
        # Always build a T-zone departure of length r_branch even when
        # departure_length=0.  The stub block's saddle extends r_branch
        # downstream of junction_origin; without this step the Straight
        # continuation would place an outer wall face right at the branch
        # opening, creating a spurious wall BC visible in GMSH and CFD.
        tzone_depart: "SegmentResult" = _build_tzone_step_manual(
            tzone_approach.end_face, tzone_approach.end_cursor,
            r_branch, n_tzone,
        )

        # --- Rest departure (structured Straight) ---------------------------
        if self.departure_length > r_branch:
            rest_depart: "SegmentResult | None" = Straight(
                self.departure_length - r_branch, self.n_layers
            ).connect(tzone_depart.end_face, tzone_depart.end_cursor)
        else:
            rest_depart = None

        # --- Remove T-zone E outer wall (faces branch opening) ---------------
        # Both T-zone steps have an outer arc wall facing the branch saddle.
        # Remove it from both so no spurious wall BC appears at the opening.
        for seg in [tzone_approach, tzone_depart]:
            if outer_name in seg.regions:
                rs = seg.regions[outer_name]
                e_outer = _find_e_outer_wall_surf(rs.walls, branch_dir, main_dir_arr)
                e_set = set(e_outer)
                rs.walls = [s for s in rs.walls if s not in e_set]

        # --- Assemble main_result by merging segments -----------------------
        if pre_step is not None:
            approach_result = _merge_two_segments(pre_step, tzone_approach)
        else:
            approach_result = tzone_approach

        if rest_depart is not None:
            departure_result = _merge_two_segments(tzone_depart, rest_depart)
        else:
            departure_result = tzone_depart
        main_result = _merge_two_segments(approach_result, departure_result)

        # --- Branch outlet cursor and LCS -----------------------------------
        branch_face_cursor = Cursor(
            position  = junction_origin + self.branch_length * branch_dir,
            direction = branch_dir,
            up        = branch_cursor.up,
        )
        branch_cs  = stub["branch_cs"]
        branch_lcs = LCS(layers=[(inner_name, branch_cs)])

        # --- Classify stub surfaces -----------------------------------------
        new_stub_vols, internal_surfs, stub_wall_surfs = _classify_stub_surfs(
            stub_vols    = list(stub["volumes"]),
            saddle_surfs = stub.get("saddle_surfs", []),
            branch_cs    = branch_cs,
        )

        branch_face_surfs = list(branch_cs.surfaces)
        stub_region = RegionSet(
            volumes = new_stub_vols,
            inlets  = list(internal_surfs),
            outlets = list(internal_surfs) + branch_face_surfs,
            walls   = stub_wall_surfs,
        )

        # --- Build merged regions -------------------------------------------
        merged_regions: dict[str, RegionSet] = {}
        for name, rset in main_result.regions.items():
            merged_regions[name] = RegionSet(
                volumes = list(rset.volumes),
                inlets  = list(rset.inlets),
                outlets = list(rset.outlets),
                walls   = list(rset.walls),
            )

        merged_interfaces: dict[str, list[int]] = {}
        for label, tags in main_result.interfaces.items():
            merged_interfaces[label] = list(tags)

        if inner_name in merged_regions:
            merged_regions[inner_name].merge(stub_region)
        else:
            merged_regions[inner_name] = stub_region

        # --- Collect deferred_mesh ------------------------------------------
        # T-zone manual volumes carry transfinite constraints in their
        # deferred_mesh.  pre_step / rest_depart use Straight extrusion
        # (no deferred mesh).  Stub deferred_mesh from build_stub_block.
        tz_dm_curves:   list = []
        tz_dm_surfaces: list = []
        tz_dm_volumes:  list = []
        for seg in [tzone_approach, tzone_depart]:
            if seg.deferred_mesh:
                tz_dm_curves.extend(seg.deferred_mesh.get("curves", []))
                tz_dm_surfaces.extend(seg.deferred_mesh.get("surfaces", []))
                tz_dm_volumes.extend(seg.deferred_mesh.get("volumes", []))

        return JunctionResult(
            outlets=[
                Outlet(main_result.end_face, main_result.end_cursor, "main"),
                Outlet(branch_lcs, branch_face_cursor, "branch"),
            ],
            regions=merged_regions,
            interfaces=merged_interfaces,
            deferred_mesh={
                "curves":   tz_dm_curves   + stub.get("deferred_curves", []),
                "surfaces": tz_dm_surfaces + stub.get("deferred_surfaces", []),
                "volumes":  tz_dm_volumes  + stub.get("deferred_volumes", list(stub["volumes"])),
            },
        )

    # ------------------------------------------------------------------
    # Legacy overlapping-extrusion path (branch_r is None)
    # ------------------------------------------------------------------

    def _connect_legacy(
        self,
        inlet:         LayeredCrossSection,
        cursor:        Cursor,
        main_result:   "SegmentResult",
        branch_cursor: Cursor,
    ) -> JunctionResult:
        """Legacy path: two overlapping extrusions from cursor.position."""
        from .straight import Straight
        from .fittings import _build_miter_outlet

        branch_inlet  = _build_miter_outlet(inlet, branch_cursor)
        branch_result = Straight(self.branch_length, self.n_layers).connect(
            branch_inlet, branch_cursor
        )

        # Cancel the fresh branch junction face from physical groups
        branch_face_surfs = {
            surf
            for _, cs in branch_inlet.layers
            for surf in cs.surfaces
        }
        for rset in branch_result.regions.values():
            for surf in branch_face_surfs:
                if surf in rset.inlets:
                    rset.outlets.append(surf)

        # Merge regions
        merged_regions: dict[str, RegionSet] = {}
        for name, rset in main_result.regions.items():
            merged_regions[name] = RegionSet(
                volumes=list(rset.volumes),
                inlets=list(rset.inlets),
                outlets=list(rset.outlets),
                walls=list(rset.walls),
            )
        for name, rset in branch_result.regions.items():
            if name in merged_regions:
                merged_regions[name].merge(rset)
            else:
                merged_regions[name] = RegionSet(
                    volumes=list(rset.volumes),
                    inlets=list(rset.inlets),
                    outlets=list(rset.outlets),
                    walls=list(rset.walls),
                )

        # Merge interfaces
        merged_interfaces: dict[str, list[int]] = {}
        for iface in (main_result.interfaces, branch_result.interfaces):
            for label, tags in iface.items():
                merged_interfaces.setdefault(label, []).extend(tags)

        return JunctionResult(
            outlets=[
                Outlet(main_result.end_face, main_result.end_cursor, "main"),
                Outlet(branch_result.end_face, branch_result.end_cursor, "branch"),
            ],
            regions=merged_regions,
            interfaces=merged_interfaces,
        )


def _classify_stub_surfs(
    stub_vols:   "list[int]",
    saddle_surfs: "list[int]",  # from build_stub_block["saddle_surfs"]
    branch_cs:   "object",      # CrossSection for the branch outlet face
) -> "tuple[list[int], list[int], list[int]]":
    """Classify stub block surfaces for physical group assignment.

    The saddle surfaces (from build_stub_block) are the geometric interface
    between the stub block and the main pipe outer surface.  They are listed
    as both inlets and outlets of the stub region so they cancel in physical
    groups.  Mesh-level conformality at the saddle opening is achieved via
    removeDuplicateNodes() in net.mesh().

    Returns
    -------
    stub_vols : list[int]
        Unchanged stub volume tags.
    internal_surfs : list[int]
        Saddle surfaces — cancelled in physical groups.
    stub_wall_surfs : list[int]
        Lateral outer surfaces of the stub block (not saddle, not branch face).
    """
    import gmsh

    # Volume adjacency counting: OH patch interfaces shared between 2 stub
    # volumes have count=2 and must not be classified as outer walls.
    stub_surf_vol_count: dict[int, int] = {}
    for v in stub_vols:
        try:
            for d, t in gmsh.model.getBoundary([(3, v)], oriented=False):
                if d == 2:
                    stub_surf_vol_count[t] = stub_surf_vol_count.get(t, 0) + 1
        except Exception:
            pass
    outer_stub_surfs = {s for s, cnt in stub_surf_vol_count.items() if cnt == 1}

    saddle_set = set(saddle_surfs)
    branch_set = set(branch_cs.surfaces)
    stub_walls = [s for s in outer_stub_surfs
                  if s not in saddle_set and s not in branch_set]

    return list(stub_vols), list(saddle_set & outer_stub_surfs), stub_walls


def _find_e_outer_wall_surf(
    wall_surfs: "list[int]",
    branch_dir: "np.ndarray",
    main_dir:   "np.ndarray",
) -> "list[int]":
    """Return the wall surface most aligned with *branch_dir* (the E outer arc wall).

    After each T-zone Straight step the outermost layer has 4 outer arc wall
    surfaces — one per cardinal direction.  The one facing ``branch_dir`` is the
    E-sector outer wall that overlaps with the stub-block saddle opening.  This
    function identifies it by comparing the cross-section centroid of each surface
    against ``branch_dir``.

    Returns a one-element list containing the identified surface tag, or an empty
    list when *wall_surfs* is empty.
    """
    import gmsh
    geo = gmsh.model.occ

    bd = np.asarray(branch_dir, dtype=float)
    md = np.asarray(main_dir,   dtype=float)

    best_proj = -float("inf")
    best_surf = None
    for surf in wall_surfs:
        try:
            cx, cy, cz = geo.getCenterOfMass(2, surf)
        except Exception:
            continue
        centroid = np.array([cx, cy, cz])
        # Project the centroid onto the cross-section plane (remove main_dir component)
        centroid_perp = centroid - float(np.dot(centroid, md)) * md
        proj = float(np.dot(centroid_perp, bd))
        if proj > best_proj:
            best_proj = proj
            best_surf = surf

    return [] if best_surf is None else [best_surf]


def _build_tzone_step_manual(
    inlet:    "LayeredCrossSection",
    cursor:   "Cursor",
    length:   float,
    n_layers: int,
) -> "SegmentResult":
    """Build a T-zone step as explicit OCC volumes (no structured extrusion).

    Geometrically equivalent to ``Straight(length, n_layers).connect(inlet, cursor)``
    but uses ``addVolume`` internally so ``occ.fragment()`` can be applied to
    the resulting volumes without invalidating structured extrusion mesh data.
    """
    import gmsh
    from .fittings import _build_miter_outlet, _connect_layer
    from ..core.region import RegionSet

    gmsh.model.occ.synchronize()
    end_cursor  = cursor.advanced(length)
    outlet_lcs  = _build_miter_outlet(inlet, end_cursor, rot=0.0)
    gmsh.model.occ.synchronize()

    regions:    dict[str, RegionSet]  = {}
    interfaces: dict[str, list[int]] = {}
    iface_names = inlet.interface_names()

    prev_outer_axial:      "list[int] | None" = None
    prev_outer_side_surfs: "list[int] | None" = None
    all_deferred_curves:   list = []
    all_deferred_arc_cvs:  list = []
    all_deferred_surfaces: list = []
    all_deferred_volumes:  list = []

    for idx, ((in_name, in_cs), (out_name, out_cs)) in enumerate(
        zip(inlet.layers, outlet_lcs.layers)
    ):
        vols, outer_side_surfs, outer_axial, deferred = _connect_layer(
            in_cs, out_cs, n_layers,
            prev_outer_axial      = prev_outer_axial,
            prev_outer_side_surfs = prev_outer_side_surfs,
        )
        all_deferred_curves.extend(deferred["curves"])
        all_deferred_arc_cvs.extend(deferred.get("arc_curves", []))
        all_deferred_surfaces.extend(deferred["surfaces"])
        all_deferred_volumes.extend(deferred["volumes"])

        regions[in_name] = RegionSet(
            volumes = list(vols),
            inlets  = list(in_cs.surfaces),
            outlets = list(out_cs.surfaces),
            walls   = list(outer_side_surfs),
        )

        if prev_outer_side_surfs is not None and idx - 1 < len(iface_names):
            interfaces[iface_names[idx - 1]] = list(prev_outer_side_surfs)

        prev_outer_axial      = outer_axial
        prev_outer_side_surfs = outer_side_surfs

    gmsh.model.occ.synchronize()

    seen: set[int] = set()
    unique_surfs: list[int] = []
    for s in all_deferred_surfaces:
        if s not in seen:
            seen.add(s)
            unique_surfs.append(s)

    arc_seen: set[int] = set()
    unique_arc_cvs: list = []
    for tag, n in all_deferred_arc_cvs:
        if tag not in arc_seen:
            arc_seen.add(tag)
            unique_arc_cvs.append((tag, n))

    return SegmentResult(
        end_face   = outlet_lcs,
        end_cursor = end_cursor,
        regions    = regions,
        interfaces = interfaces,
        deferred_mesh = {
            "curves":   [(L, n_layers + 1) for L in all_deferred_curves] + unique_arc_cvs,
            "surfaces": unique_surfs,
            "volumes":  list(all_deferred_volumes),
        },
    )


def _fragment_tzone_stub(
    tzone_approach:  "SegmentResult",
    tzone_depart:    "SegmentResult | None",
    stub_result:     dict,
    main_dir_arr:    "np.ndarray",
    nang:            int,
    nrad:            int,
    n_tzone:         int,
    branch_dir_arr:  "np.ndarray",
    junction_origin: "np.ndarray",
    branch_length:   float,
) -> "tuple[SegmentResult, SegmentResult | None, dict, list[int]]":
    """Fragment T-zone step volumes with stub block for conformal mesh.

    Only tzone step volumes and stub block are fragmented — pre-step and
    rest-departure ``Straight`` extrusion volumes are excluded (they carry
    structured extrusion data that ``fragment()`` would invalidate).

    Returns
    -------
    tzone_approach, tzone_depart, stub_result (all with remapped tags),
    saddle_surfs_new : new conformal surfaces shared between tzone and stub.
    """
    import gmsh

    geo  = gmsh.model.occ
    mesh = gmsh.model.mesh

    # Collect all volumes to fragment
    ta_vols: list[int] = [v for rs in tzone_approach.regions.values() for v in rs.volumes]
    td_vols: list[int] = (
        [v for rs in tzone_depart.regions.values() for v in rs.volumes]
        if tzone_depart is not None else []
    )
    stub_vols_orig = list(stub_result["volumes"])
    all_dimtags = [(3, v) for v in ta_vols + td_vols + stub_vols_orig]

    geo.synchronize()
    out_dt, out_map = geo.fragment(all_dimtags, [])
    geo.synchronize()

    # Build old→new volume remap
    vol_remap: dict[int, list[int]] = {}
    for i, (_, old_v) in enumerate(all_dimtags):
        vol_remap[old_v] = [dt[1] for dt in out_map[i] if dt[0] == 3]

    # setRecombine on all new volumes
    all_new: set[int] = set()
    for nv in vol_remap.values():
        all_new.update(nv)
    for v in all_new:
        mesh.setRecombine(3, v)

    def _remap_seg(seg: "SegmentResult") -> None:
        for rs in seg.regions.values():
            rs.volumes = [nv for v in rs.volumes for nv in vol_remap.get(v, [v])]

    _remap_seg(tzone_approach)
    if tzone_depart is not None:
        _remap_seg(tzone_depart)

    new_stub_vols: list[int] = [nv for v in stub_vols_orig for nv in vol_remap.get(v, [v])]
    stub_result = dict(stub_result)
    stub_result["volumes"] = new_stub_vols

    # Find saddle surfaces: boundary surfaces shared between tzone and stub
    def _bsurfs(vols: "set[int]") -> "set[int]":
        s: set[int] = set()
        for v in vols:
            try:
                for d, t in gmsh.model.getBoundary([(3, v)], oriented=False):
                    if d == 2:
                        s.add(t)
            except Exception:
                pass
        return s

    tzone_new_vols: set[int] = set()
    for rs in tzone_approach.regions.values():
        tzone_new_vols.update(rs.volumes)
    if tzone_depart is not None:
        for rs in tzone_depart.regions.values():
            tzone_new_vols.update(rs.volumes)

    saddle_surfs_new = sorted(_bsurfs(tzone_new_vols) & _bsurfs(set(new_stub_vols)))
    stub_result["saddle_surfs"] = saddle_surfs_new

    # Rebuild deferred_mesh for tzone volumes (post-fragment tags)
    md = main_dir_arr / (np.linalg.norm(main_dir_arr) + 1e-30)

    # _two_face_projs is defined here so ta_in_proj can be computed before
    # _rebuild_deferred (needed to exclude pre_step output face surfaces).
    def _two_face_projs(vols: "list[int]") -> "tuple[float, float]":
        """Return (min_proj, max_proj) of all flat face centroids in vols."""
        projs: set[float] = set()
        seen_s: set[int] = set()
        for v in vols:
            try:
                for d, t in gmsh.model.getBoundary([(3, v)], oriented=False):
                    if d != 2 or t in seen_s:
                        continue
                    seen_s.add(t)
                    try:
                        bb = gmsh.model.getBoundingBox(2, t)
                        cx, cy, cz = (bb[0]+bb[3])/2, (bb[1]+bb[4])/2, (bb[2]+bb[5])/2
                        projs.add(round(float(np.dot([cx, cy, cz], md)), 8))
                    except Exception:
                        pass
            except Exception:
                pass
        if len(projs) < 2:
            return (0.0, 0.0)
        return (min(projs), max(projs))

    # Compute ta_in_proj before _rebuild_deferred so inlet faces of tzone_approach
    # can be excluded.  These faces are the OUTPUT faces of the upstream Straight
    # extrusion (pre_step).  Calling setTransfiniteSurface on them after the fact
    # conflicts with GMSH's structured-extrusion mesh data → "Could not find
    # extruded node" crash.
    ta_vols_new = [v for rs in tzone_approach.regions.values() for v in rs.volumes]
    ta_in_proj, _ = _two_face_projs(ta_vols_new)

    def _rebuild_deferred(
        seg: "SegmentResult",
        exclude_inlet_proj: "float | None" = None,
    ) -> None:
        new_vols_list = [v for rs in seg.regions.values() for v in rs.volumes]
        surf_seen:  set[int] = set()
        curve_seen: set[int] = set()
        surfs_out:  list[int] = []
        vols_ok:    list[int] = []   # volumes whose surfaces are all 3-or-4-cornered
        curves_out: list = []

        for vol in new_vols_list:
            try:
                bs = gmsh.model.getBoundary([(3, vol)], oriented=False)
            except Exception:
                continue
            vol_ok = True
            for d, s in bs:
                if d != 2:
                    continue
                try:
                    nc = len(gmsh.model.getBoundary([(2, s)], oriented=False))
                except Exception:
                    nc = 4
                if nc < 3 or nc > 4:
                    vol_ok = False
                    break
            if vol_ok:
                vols_ok.append(vol)
            for d, s in bs:
                if d != 2 or s in surf_seen:
                    continue
                # Skip surfaces at the inlet projection — these are output faces
                # of the upstream structured extrusion and must not be marked
                # transfinite (conflicts with structured-extrusion mesh data).
                if exclude_inlet_proj is not None:
                    try:
                        bb = gmsh.model.getBoundingBox(2, s)
                        cx = (bb[0] + bb[3]) / 2
                        cy = (bb[1] + bb[4]) / 2
                        cz = (bb[2] + bb[5]) / 2
                        if abs(float(np.dot([cx, cy, cz], md)) - exclude_inlet_proj) < 1e-4:
                            surf_seen.add(s)
                            continue
                    except Exception:
                        pass
                try:
                    bc = gmsh.model.getBoundary([(2, s)], oriented=False)
                except Exception:
                    continue
                nc = len(bc)
                if nc < 3 or nc > 4:
                    surf_seen.add(s)   # skip but record as seen
                    continue
                surf_seen.add(s)
                surfs_out.append(s)
                for dc, c in bc:
                    if dc != 1 or c in curve_seen:
                        continue
                    curve_seen.add(c)
                    ctype = gmsh.model.getType(1, c)
                    if ctype in ('Circle', 'Ellipse', 'BSpline', 'Spline'):
                        n = nang + 1
                    else:
                        try:
                            pts = gmsh.model.getBoundary([(1, c)], oriented=False)
                            p1 = np.asarray(gmsh.model.getValue(0, pts[0][1], []))
                            p2 = np.asarray(gmsh.model.getValue(0, pts[1][1], []))
                            vec = p2 - p1
                            ln = float(np.linalg.norm(vec))
                            dot = abs(float(np.dot(vec / max(ln, 1e-30), md)))
                            n = n_tzone + 1 if dot > 0.5 else nrad + 1
                        except Exception:
                            n = n_tzone + 1
                    curves_out.append((c, n))

        seg.deferred_mesh = {
            "curves":   curves_out,
            "surfaces": surfs_out,
            "volumes":  vols_ok,
        }

    _rebuild_deferred(tzone_approach, exclude_inlet_proj=ta_in_proj)
    if tzone_depart is not None:
        _rebuild_deferred(tzone_depart)

    # Re-derive inlet/outlet face surface tags after fragment.
    # occ.fragment() renumbers ALL bounding surfaces of the fragmented volumes,
    # even those not at the geometric intersection.  The pre-fragment surface
    # tags stored in RegionSet.inlets/outlets and end_face.layers[*].surfaces
    # are stale and must be replaced with the post-fragment tags, otherwise
    # Straight.connect() fails with "Unknown OpenCASCADE entity".
    def _surfs_at_proj(vols: "list[int]", target_proj: float, axis: "np.ndarray",
                       tol: float = 1e-4):
        """Return (radius, tag) pairs for volume boundary surfaces at target_proj."""
        seen: set[int] = set()
        result = []
        for v in vols:
            try:
                for d, t in gmsh.model.getBoundary([(3, v)], oriented=False):
                    if d != 2 or t in seen:
                        continue
                    seen.add(t)
                    try:
                        bb = gmsh.model.getBoundingBox(2, t)
                        cx = (bb[0] + bb[3]) / 2
                        cy = (bb[1] + bb[4]) / 2
                        cz = (bb[2] + bb[5]) / 2
                        c    = np.array([cx, cy, cz])
                        proj = float(np.dot(c, axis))
                        if abs(proj - target_proj) < tol:
                            r = float(np.linalg.norm(c - proj * axis))
                            result.append((r, t))
                    except Exception:
                        pass
            except Exception:
                pass
        result.sort(key=lambda x: x[0])
        return result

    def _rederive_faces(seg: "SegmentResult", in_proj: float, out_proj: float) -> None:
        """Update inlets, outlets, and end_face surfaces for *seg* post-fragment."""
        new_vols = [v for rs in seg.regions.values() for v in rs.volumes]
        in_surfs  = [t for _, t in _surfs_at_proj(new_vols, in_proj,  axis=md)]
        out_surfs = [t for _, t in _surfs_at_proj(new_vols, out_proj, axis=md)]

        # Update RegionSet.inlets (sorted by radius: innermost layer first)
        total_in = sum(len(rs.inlets) for rs in seg.regions.values())
        if len(in_surfs) == total_in:
            offset = 0
            for rs in seg.regions.values():
                n = len(rs.inlets)
                rs.inlets = in_surfs[offset:offset + n]
                offset += n

        # Update RegionSet.outlets and end_face surface tags
        total_out = sum(len(rs.outlets) for rs in seg.regions.values())
        total_ef  = sum(len(cs.surfaces) for _, cs in seg.end_face.layers)
        if len(out_surfs) == total_out:
            offset = 0
            for rs in seg.regions.values():
                n = len(rs.outlets)
                rs.outlets = out_surfs[offset:offset + n]
                offset += n
        if len(out_surfs) == total_ef:
            offset = 0
            for _name, cs in seg.end_face.layers:
                n = len(cs.surfaces)
                cs.surfaces = out_surfs[offset:offset + n]
                offset += n

    # Compute axial projections for each segment's inlet and outlet faces
    ta_out_pos  = np.asarray(tzone_approach.end_cursor.position, dtype=float)
    ta_out_proj = float(np.dot(ta_out_pos, md))
    # ta_vols_new and ta_in_proj are already computed above (before _rebuild_deferred).
    # _two_face_projs is also already defined above.
    _rederive_faces(tzone_approach, ta_in_proj, ta_out_proj)

    if tzone_depart is not None:
        td_vols_new = [v for rs in tzone_depart.regions.values() for v in rs.volumes]
        _, td_out_proj = _two_face_projs(td_vols_new)
        td_in_proj = ta_out_proj   # inlet of depart = outlet of approach
        _rederive_faces(tzone_depart, td_in_proj, td_out_proj)

    # Rederive stub block branch outlet face surfaces after fragment.
    # The branch face is at (junction_origin + branch_length * branch_dir),
    # projected onto branch_dir_arr.
    bd = branch_dir_arr / (np.linalg.norm(branch_dir_arr) + 1e-30)
    jo = np.asarray(junction_origin, dtype=float)
    branch_face_proj = float(np.dot(jo + branch_length * bd, bd))
    b_surfs = _surfs_at_proj(new_stub_vols, branch_face_proj, axis=bd)
    branch_cs = stub_result.get("branch_cs")
    if branch_cs is not None and b_surfs:
        expected = len(branch_cs.surfaces)
        if len(b_surfs) == expected:
            branch_cs.surfaces = [t for _, t in b_surfs]
        # For multi-layer: also update branch_lcs if present
        branch_lcs = stub_result.get("branch_lcs")
        if branch_lcs is not None:
            total_lcs = sum(len(cs.surfaces) for _, cs in branch_lcs.layers)
            if len(b_surfs) == total_lcs:
                offset = 0
                for _name, cs in branch_lcs.layers:
                    n = len(cs.surfaces)
                    cs.surfaces = [t for _, t in b_surfs[offset:offset + n]]
                    offset += n

    # Rebuild stub deferred_mesh after fragment (all pre-fragment tags are stale).
    # Use branch_dir (bd) for axial vs radial line classification within the stub.
    stub_surf_seen:  set[int] = set()
    stub_curve_seen: set[int] = set()
    stub_surfs_out:  list[int] = []
    stub_vols_ok:    list[int] = []
    stub_curves_out: list = []
    for vol in new_stub_vols:
        try:
            bs = gmsh.model.getBoundary([(3, vol)], oriented=False)
        except Exception:
            continue
        v_ok = True
        for d, s in bs:
            if d != 2:
                continue
            try:
                nc = len(gmsh.model.getBoundary([(2, s)], oriented=False))
            except Exception:
                nc = 4
            if nc < 3 or nc > 4:
                v_ok = False
                break
        if v_ok:
            stub_vols_ok.append(vol)
        for d, s in bs:
            if d != 2 or s in stub_surf_seen:
                continue
            try:
                bc = gmsh.model.getBoundary([(2, s)], oriented=False)
            except Exception:
                continue
            nc = len(bc)
            if nc < 3 or nc > 4:
                stub_surf_seen.add(s)
                continue
            stub_surf_seen.add(s)
            stub_surfs_out.append(s)
            for dc, c in bc:
                if dc != 1 or c in stub_curve_seen:
                    continue
                stub_curve_seen.add(c)
                ctype = gmsh.model.getType(1, c)
                if ctype in ('Circle', 'Ellipse', 'BSpline', 'Spline'):
                    cn = nang + 1
                else:
                    try:
                        pts = gmsh.model.getBoundary([(1, c)], oriented=False)
                        p1 = np.asarray(gmsh.model.getValue(0, pts[0][1], []))
                        p2 = np.asarray(gmsh.model.getValue(0, pts[1][1], []))
                        vec = p2 - p1
                        ln  = float(np.linalg.norm(vec))
                        dot_b = abs(float(np.dot(vec / max(ln, 1e-30), bd)))
                        cn = n_tzone + 1 if dot_b > 0.5 else nrad + 1
                    except Exception:
                        cn = n_tzone + 1
                stub_curves_out.append((c, cn))

    stub_result["deferred_curves"]   = stub_curves_out
    stub_result["deferred_surfaces"] = stub_surfs_out
    stub_result["deferred_volumes"]  = stub_vols_ok

    return tzone_approach, tzone_depart, stub_result, saddle_surfs_new


def _rebuild_walls_after_fragment(
    seg:           "SegmentResult",
    exclude_surfs: "set[int]",
) -> None:
    """Rebuild wall surface lists for each region after ``occ.fragment()``.

    Queries the actual volume boundary surfaces, strips inlet/outlet faces
    and the shared saddle surfaces, and uses the remainder as walls.
    """
    import gmsh

    for rs in seg.regions.values():
        inlet_set  = set(rs.inlets)
        outlet_set = set(rs.outlets)
        surf_count: dict[int, int] = {}
        for v in rs.volumes:
            try:
                for d, t in gmsh.model.getBoundary([(3, v)], oriented=False):
                    if d == 2:
                        surf_count[t] = surf_count.get(t, 0) + 1
            except Exception:
                pass
        outer = {s for s, c in surf_count.items() if c == 1}
        rs.walls = [
            s for s in outer
            if s not in inlet_set and s not in outlet_set and s not in exclude_surfs
        ]


def _merge_two_segments(a: SegmentResult, b: SegmentResult) -> SegmentResult:
    """Merge two sequential SegmentResults (a upstream, b downstream).

    Volumes and walls from both are combined.  Inlets come from *a* only;
    outlets come from *b* only.  Interfaces from both are merged.
    """
    merged_regions: dict[str, RegionSet] = {}
    for name in set(a.regions) | set(b.regions):
        ra = a.regions.get(name)
        rb = b.regions.get(name)
        if ra is None:
            merged_regions[name] = RegionSet(
                volumes=list(rb.volumes),
                inlets=list(rb.inlets),
                outlets=list(rb.outlets),
                walls=list(rb.walls),
            )
        elif rb is None:
            merged_regions[name] = RegionSet(
                volumes=list(ra.volumes),
                inlets=list(ra.inlets),
                outlets=list(ra.outlets),
                walls=list(ra.walls),
            )
        else:
            merged_regions[name] = RegionSet(
                volumes=list(ra.volumes) + list(rb.volumes),
                inlets=list(ra.inlets),    # inlet face is from the upstream segment
                outlets=list(rb.outlets),  # outlet face is from the downstream segment
                walls=list(ra.walls) + list(rb.walls),
            )

    merged_interfaces: dict[str, list[int]] = {}
    for iface in (a.interfaces, b.interfaces):
        for label, tags in iface.items():
            merged_interfaces.setdefault(label, []).extend(tags)

    return SegmentResult(
        end_face=b.end_face,
        end_cursor=b.end_cursor,
        regions=merged_regions,
        interfaces=merged_interfaces,
    )


@dataclass
class YJunction:
    """Symmetric Y-junction: both legs branch away from the inlet direction.

    Unlike TJunction, neither outlet leg reuses the original inlet face —
    both legs deflect, so both require a fresh face built perpendicular to
    the respective branch direction.  The original inlet surfaces are
    re-injected into the merged region inlets so that the physical-group
    ``fluid_inlet`` filter still resolves to exactly the upstream face.

    Parameters
    ----------
    length : float
        Axial length of each branch leg.  Use a value ≥ the pipe outer
        radius for good cell quality at the split.
    half_angle : float
        Half-opening angle in degrees.  Branch 1 deflects by
        ``+half_angle`` and branch 2 by ``−half_angle``.  A 90° Y-split
        uses ``half_angle=45``.  Default 45.
    roll : float
        Rotation of the split plane around the pipe axis, in **degrees**.
        ``0`` (default) splits horizontally (around ``cursor.up``).
        ``90`` splits vertically (around ``cursor.right``).
        Any intermediate angle is supported.
    n_layers : int
        Hex layers in each branch extrusion.  Default 2.

    Returns
    -------
    JunctionResult
        ``outlets[0]`` — ``"branch_1"`` leg (deflected by ``+half_angle``)
        ``outlets[1]`` — ``"branch_2"`` leg (deflected by ``−half_angle``)

    Usage
    -----
    ::

        net   = Network(PIPE, cursor=CURSOR, lc=0.08)
        n_in  = net.add(Straight(0.4, n_layers=4))
        n1, n2 = net.add(n_in, YJunction(length=0.15, half_angle=45))
        net.add(n1, Straight(0.4, n_layers=4))
        net.add(n2, Straight(0.4, n_layers=4))
    """

    REQUIRED_BOUNDARY_TYPE = BoundaryType.CIRCULAR

    length:     float
    half_angle: float = 45.0
    roll:       float = 0.0
    n_layers:   int   = 2

    def __post_init__(self) -> None:
        if self.length <= 0:
            raise ValueError(
                f"YJunction.length must be positive, got {self.length!r}"
            )
        if not (0 < abs(self.half_angle) < 90):
            raise ValueError(
                f"YJunction.half_angle must be in (0, 90) degrees, "
                f"got {self.half_angle!r}"
            )
        if not math.isfinite(self.roll):
            raise ValueError(
                f"YJunction.roll must be a finite number, got {self.roll!r}"
            )
        if self.n_layers < 1:
            raise ValueError(
                f"YJunction.n_layers must be >= 1, got {self.n_layers!r}"
            )

    def connect(
        self,
        inlet:  LayeredCrossSection,
        cursor: Cursor,
    ) -> JunctionResult:
        """Build the Y-junction block.

        For single-layer circular pipes, uses a non-overlapping bifurcation
        block (``build_y_junction_block`` from ``y_block.py``) that splits the
        adapter center patch so no two neck volumes share a face.

        For multi-layer pipes, falls back to the legacy approach (two full
        extrusions from the apex) with a RuntimeWarning.

        The original inlet surfaces are always added to the merged region
        inlets so that ``write_physical_groups`` resolves the correct system
        inlet.  The downstream ``Straight`` segments provide the outlets.
        """
        from .y_block import build_y_junction_block
        from .straight import Straight

        junction_result = build_y_junction_block(
            inlet=inlet,
            cursor=cursor,
            half_angle=self.half_angle,
            roll=self.roll,
            n_layers=self.n_layers,
        )

        # Extend each branch with the requested straight length
        branch_results = []
        for outlet in junction_result.outlets:
            seg = Straight(self.length, self.n_layers).connect(
                outlet.face, outlet.cursor
            )
            branch_results.append((outlet, seg))

        # --- Merge regions ---------------------------------------------------
        merged_regions: dict[str, RegionSet] = {}

        # Start with the junction block regions
        for name, rset in junction_result.regions.items():
            merged_regions[name] = RegionSet(
                volumes=list(rset.volumes),
                inlets=list(rset.inlets),
                outlets=list(rset.outlets),
                walls=list(rset.walls),
            )

        # Merge in the straight-segment regions
        for outlet, seg_result in branch_results:
            for name, rset in seg_result.regions.items():
                if name in merged_regions:
                    merged_regions[name].merge(rset)
                else:
                    merged_regions[name] = RegionSet(
                        volumes=list(rset.volumes),
                        inlets=list(rset.inlets),
                        outlets=list(rset.outlets),
                        walls=list(rset.walls),
                    )

        # Cancel branch-face surfaces: they are outlets of the junction block
        # and inlets of the straight segments — they must cancel in both
        # so that only the true system inlet and the final pipe outlets survive.
        for outlet in junction_result.outlets:
            branch_face_surfs = {
                surf
                for _, cs in outlet.face.layers
                for surf in cs.surfaces
            }
            for rset in merged_regions.values():
                for surf in branch_face_surfs:
                    if surf in rset.inlets and surf not in rset.outlets:
                        rset.outlets.append(surf)
                    if surf in rset.outlets and surf not in rset.inlets:
                        rset.inlets.append(surf)

        # --- Merge interfaces ------------------------------------------------
        merged_interfaces: dict[str, list[int]] = {}
        for iface_dict in [junction_result.interfaces] + [
            seg.interfaces for _, seg in branch_results
        ]:
            for label, tags in iface_dict.items():
                merged_interfaces.setdefault(label, []).extend(tags)

        return JunctionResult(
            outlets=[
                Outlet(seg.end_face, seg.end_cursor, outlet.label)
                for outlet, seg in branch_results
            ],
            regions=merged_regions,
            interfaces=merged_interfaces,
        )
