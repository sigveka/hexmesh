"""
Y-junction block — full-circle bifurcation with seam.

The junction block is built from 12 volumes (6 per branch):
  • 3 primary volumes (E-half of inlet → branch outlet E-half)
  • 3 fill    volumes (W-half of inlet → branch outlet W-half)

The fill volumes share their inlet face with the primary volumes of the
*opposite* branch (conformal shared faces).  This is valid: each shared
inlet patch is adjacent to two volumes — one going left, one going right.

The outlet CrossSection for each branch has **6 surfaces**:
  [rc, lc, NE, NW, SW, SE]
where rc/lc are the E/W half-centre patches and NE/NW/SW/SE are the four
quadrant patches.  Downstream ``Straight`` connectors handle 6-surface
inlets via the ``is_split_core`` path introduced in ``straight.py``.

The seam (N-S split line) extends through the downstream pipe and is an
interior mesh line — all elements remain valid hexahedra.

Rotation requirement
--------------------
``rot = -π/4`` must be used for the outlet OH faces so that the inner
corners land at cardinal positions E/N/W/S, making the N-S split line
align with the V-axis.  This is enforced via ``_ROT`` below.
"""
from __future__ import annotations
import math

import numpy as np
import gmsh

from ..core.cross_section import CrossSection, LayeredCrossSection
from ..core.cursor import Cursor
from ..core.region import RegionSet
from .base import Outlet, JunctionResult
from .fittings import _build_miter_outlet, _extract_geom

_ROT = -math.pi / 4   # required rotation for clean N-S split


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_y_junction_block(
    inlet:      LayeredCrossSection,
    cursor:     Cursor,
    half_angle: float,
    roll:       float,
    n_layers:   int,
) -> JunctionResult:
    """Non-overlapping Y-junction with full-circle branch outlets."""
    geo  = gmsh.model.occ
    mesh = gmsh.model.mesh

    φ        = math.radians(roll)
    rot_axis = math.cos(φ) * cursor.up + math.sin(φ) * cursor.right
    theta_rad = math.radians(abs(half_angle))
    cursor_1  = cursor.rotated(rot_axis, math.radians(+half_angle))
    cursor_2  = cursor.rotated(rot_axis, math.radians(-half_angle))

    # Ensure cursor_1 is the +H branch
    h_check = float(np.dot(
        np.asarray(cursor_1.direction, dtype=float),
        np.asarray(cursor.right, dtype=float),
    ))
    if h_check < 0:
        cursor_1, cursor_2 = cursor_2, cursor_1

    R_outer = inlet.outermost.shape.radius
    L_sep   = R_outer / math.sin(theta_rad) * 1.05

    pos_1 = cursor.position + L_sep * cursor_1.direction
    pos_2 = cursor.position + L_sep * cursor_2.direction

    # Build fresh outlet faces at each branch position.
    # n_outer=8: rot=0 (N/S/E/W corners already at split positions).
    # n_outer=4: rot=-π/4 (inner corners must land at cardinal positions).
    _rot_outlet = 0.0 if inlet.innermost.n_outer == 8 else _ROT
    out1_face = _build_miter_outlet(
        inlet, Cursor(pos_1, cursor_1.direction, cursor_1.up), rot=_rot_outlet
    )
    out2_face = _build_miter_outlet(
        inlet, Cursor(pos_2, cursor_2.direction, cursor_2.up), rot=_rot_outlet
    )

    geo.synchronize()

    # ------------------------------------------------------------------
    # Layer-by-layer junction build
    # ------------------------------------------------------------------
    merged_regions:   dict[str, RegionSet]  = {}
    merged_interfaces: dict[str, list[int]] = {}
    iface_names = inlet.interface_names()

    # Accumulate per-branch outlet CrossSections (6-surface split-centre)
    out1_layers: list[tuple[str, CrossSection]] = []
    out2_layers: list[tuple[str, CrossSection]] = []

    # Track pre-fragment branch volumes per layer for post-fragment surface recovery
    branch_vols: dict[str, tuple[list[int], list[int]]] = {}

    prev_ow1: list[int] | None = None   # 4 outer-wall side surfs, branch_1
    prev_ow2: list[int] | None = None   # 4 outer-wall side surfs, branch_2
    prev_oa1: list[int] | None = None   # 4 outer-corner axials, branch_1
    prev_oa2: list[int] | None = None   # 4 outer-corner axials, branch_2

    for idx, (name, _) in enumerate(inlet.layers):
        ap_cs   = inlet.layers[idx][1]
        out1_cs = out1_face.layers[idx][1]
        out2_cs = out2_face.layers[idx][1]

        (vols_1, vols_2,
         ow1, ow2, oa1, oa2,
         out1_surfs, out2_surfs,
         new_ap_surfs) = _build_layer(
            ap_cs, out1_cs, out2_cs, cursor,
            n_layers,
            prev_ow1, prev_ow2, prev_oa1, prev_oa2,
        )

        # Build 6-surface split-centre CrossSection for each branch outlet
        cs1 = CrossSection(
            surfaces      = out1_surfs,
            center        = out1_cs.center,
            outer_points  = out1_cs.outer_points,
            outer_curves  = out1_cs.outer_curves,
            shape         = out1_cs.shape,
            boundary_type = out1_cs.boundary_type,
            h_axis        = out1_cs.h_axis,
            v_axis        = out1_cs.v_axis,
            cx=out1_cs.cx, cy=out1_cs.cy, cz=out1_cs.cz,
            inner_points  = list(out1_cs.inner_points),
            inner_curves  = list(out1_cs.inner_curves),
            radial_curves = list(out1_cs.radial_curves),
            nrad          = out1_cs.nrad,
            lc            = out1_cs.lc,
        )
        cs2 = CrossSection(
            surfaces      = out2_surfs,
            center        = out2_cs.center,
            outer_points  = out2_cs.outer_points,
            outer_curves  = out2_cs.outer_curves,
            shape         = out2_cs.shape,
            boundary_type = out2_cs.boundary_type,
            h_axis        = out2_cs.h_axis,
            v_axis        = out2_cs.v_axis,
            cx=out2_cs.cx, cy=out2_cs.cy, cz=out2_cs.cz,
            inner_points  = list(out2_cs.inner_points),
            inner_curves  = list(out2_cs.inner_curves),
            radial_curves = list(out2_cs.radial_curves),
            nrad          = out2_cs.nrad,
            lc             = out2_cs.lc,
        )
        out1_layers.append((name, cs1))
        out2_layers.append((name, cs2))
        branch_vols[name] = (list(vols_1), list(vols_2))

        # All original inlet-layer surfaces go to inlets.
        # new_ap_surfs (split half-surfaces at inlet) go to BOTH so they cancel.
        all_ap_surfs = list(ap_cs.surfaces)

        merged_regions[name] = RegionSet(
            volumes = vols_1 + vols_2,
            inlets  = all_ap_surfs + new_ap_surfs,
            outlets = out1_surfs + out2_surfs + new_ap_surfs,
            walls   = ow1 + ow2,
        )

        if idx > 0 and (idx - 1) < len(iface_names):
            merged_interfaces[iface_names[idx - 1]] = (
                (prev_ow1 or []) + (prev_ow2 or [])
            )

        prev_ow1, prev_ow2 = ow1, ow2
        prev_oa1, prev_oa2 = oa1, oa2

    # Re-inject original inlet surfaces → system inlet detection
    for name, cs in inlet.layers:
        if name in merged_regions:
            merged_regions[name].inlets.extend(cs.surfaces)

    # ------------------------------------------------------------------
    # Resolve geometric overlaps with OCC fragment.
    #
    # The fill volumes for each branch cross through the space occupied by
    # primary volumes of the opposite branch, producing genuine geometric
    # overlap.  fragment() resolves this by splitting the overlapping
    # volumes at their intersection surface, producing a conformal non-
    # overlapping decomposition.
    #
    # Surfaces outside the overlap region (inlet faces, branch outlet
    # faces, outer-wall arc surfaces) are NOT on the intersection
    # boundary and their tags are preserved after fragment.  Only
    # volumes may be split; the outDimTagsMap is used to remap them.
    # ------------------------------------------------------------------
    all_vol_tags: list[int] = []
    for rset in merged_regions.values():
        all_vol_tags.extend(rset.volumes)
    all_vol_dimtags = [(3, v) for v in all_vol_tags]

    geo.synchronize()
    geo.healShapes(all_vol_dimtags)
    geo.synchronize()
    out_dimtags, out_map = geo.fragment(all_vol_dimtags, [])
    geo.synchronize()

    # Build old→new volume tag mapping
    vol_remap: dict[int, list[int]] = {}
    for i, (_, old_tag) in enumerate(all_vol_dimtags):
        vol_remap[old_tag] = [dt[1] for dt in out_map[i] if dt[0] == 3]

    # Apply recombine to all new sub-volumes (includes split fragments)
    all_new_vol_tags: set[int] = set()
    for new_tags in vol_remap.values():
        all_new_vol_tags.update(new_tags)
    for v in all_new_vol_tags:
        mesh.setRecombine(3, v)

    # Update regions with remapped volume tags
    for rset in merged_regions.values():
        new_vols: list[int] = []
        for v in rset.volumes:
            new_vols.extend(vol_remap.get(v, [v]))
        rset.volumes = new_vols

    # ------------------------------------------------------------------
    # Re-derive outlet surface tags after fragment.
    #
    # fragment() removes/renumbers surfaces that lie on the intersection
    # boundary between branch volumes.  The outlet CrossSections in
    # out1_layers / out2_layers still hold the pre-fragment tags, so we
    # must re-query getBoundary on the post-fragment volumes and filter
    # by axial position along each branch direction.
    # ------------------------------------------------------------------
    all_inlet_surfs: set[int] = {
        s for _, cs in inlet.layers for s in cs.surfaces
    }
    dir_1 = np.asarray(cursor_1.direction, dtype=float)
    dir_2 = np.asarray(cursor_2.direction, dtype=float)
    proj_1 = float(np.dot(pos_1, dir_1))
    proj_2 = float(np.dot(pos_2, dir_2))

    def _collect_outlet_surfs(
        old_vols: list[int],
        outlet_proj: float,
        outlet_dir: np.ndarray,
    ) -> list[int]:
        new_vols = [nv for v in old_vols for nv in vol_remap.get(v, [v])]
        candidates: set[int] = set()
        for vol in new_vols:
            for d, t in gmsh.model.getBoundary([(3, vol)], oriented=False):
                if d == 2 and t not in all_inlet_surfs:
                    candidates.add(t)
        result = []
        for s in candidates:
            bb = gmsh.model.getBoundingBox(2, s)
            scx = (bb[0] + bb[3]) / 2
            scy = (bb[1] + bb[4]) / 2
            scz = (bb[2] + bb[5]) / 2
            s_proj = float(np.dot([scx, scy, scz], outlet_dir))
            if abs(s_proj - outlet_proj) < 1e-6:
                result.append(s)
        return result

    for i, (name, cs1) in enumerate(out1_layers):
        old_v1, old_v2 = branch_vols[name]
        new_s1 = _collect_outlet_surfs(old_v1, proj_1, dir_1)
        if new_s1:
            out1_layers[i][1].surfaces = new_s1
        new_s2 = _collect_outlet_surfs(old_v2, proj_2, dir_2)
        if new_s2:
            out2_layers[i][1].surfaces = new_s2

    cursor_at_1 = Cursor(pos_1, cursor_1.direction, cursor_1.up)
    cursor_at_2 = Cursor(pos_2, cursor_2.direction, cursor_2.up)

    return JunctionResult(
        outlets=[
            Outlet(LayeredCrossSection(out1_layers), cursor_at_1, "branch_1"),
            Outlet(LayeredCrossSection(out2_layers), cursor_at_2, "branch_2"),
        ],
        regions=merged_regions,
        interfaces=merged_interfaces,
    )


# ---------------------------------------------------------------------------
# Per-layer builder
# ---------------------------------------------------------------------------

def _build_layer(
    ap_cs:    CrossSection,
    out1_cs:  CrossSection,
    out2_cs:  CrossSection,
    cursor:   Cursor,
    n_layers: int,
    prev_ow1: "list[int] | None",
    prev_ow2: "list[int] | None",
    prev_oa1: "list[int] | None",
    prev_oa2: "list[int] | None",
):
    """Build 12 junction volumes for one concentric layer.

    Returns
    -------
    vols_1, vols_2          branch volume tags (6 per branch)
    ow1, ow2                outer-arc side surfaces (4 each, for next layer)
    oa1, oa2                outer-corner axials (4 each: N,E,S,W for branch_1;
                                                         N,W,S,E for branch_2)
    out1_surfs, out2_surfs  6-surface outlet list per branch [rc,lc,NE,NW,SW,SE]
    new_ap_surfs            split-inlet surfaces to cancel in RegionSet
    """
    geo     = gmsh.model.occ
    mesh    = gmsh.model.mesh
    is_core = (len(ap_cs.surfaces) == ap_cs.n_outer + 1)

    if ap_cs.n_outer != 4:
        return _build_layer_8(
            ap_cs, out1_cs, out2_cs, cursor, n_layers,
            prev_ow1, prev_ow2, prev_oa1, prev_oa2,
        )
    nL      = n_layers

    # ------------------------------------------------------------------ #
    # Extract geometry                                                     #
    # ------------------------------------------------------------------ #
    g_ap   = _extract_geom(ap_cs)
    g_out1 = _extract_geom(out1_cs)
    g_out2 = _extract_geom(out2_cs)

    ip_ap = g_ap['ip'];   ic_ap = g_ap['ic']
    op_ap = g_ap['op'];   oc_ap = g_ap['oc'];   rc_ap = g_ap['rc']
    ip_1  = g_out1['ip']; ic_1  = g_out1['ic']
    op_1  = g_out1['op']; oc_1  = g_out1['oc']; rc_1  = g_out1['rc']
    ip_2  = g_out2['ip']; ic_2  = g_out2['ic']
    op_2  = g_out2['op']; oc_2  = g_out2['oc']; rc_2  = g_out2['rc']

    # ------------------------------------------------------------------ #
    # Classify corners (E/N/W/S)                                          #
    # ------------------------------------------------------------------ #
    apos = np.asarray(cursor.position, dtype=float)
    iE_ap, iN_ap, iW_ap, iS_ap = _classify(g_ap,   cursor, apos)
    iE_1,  iN_1,  iW_1,  iS_1  = _classify(g_out1, cursor, apos)
    iE_2,  iN_2,  iW_2,  iS_2  = _classify(g_out2, cursor, apos)

    # ------------------------------------------------------------------ #
    # Mark all face surfaces transfinite                                   #
    # ------------------------------------------------------------------ #
    geo.synchronize()
    for s in ap_cs.surfaces + out1_cs.surfaces + out2_cs.surfaces:
        mesh.setTransfiniteSurface(s)
        mesh.setRecombine(2, s)

    # ------------------------------------------------------------------ #
    # Axial-line helper                                                    #
    # ------------------------------------------------------------------ #
    def al(pa, pb):
        L = geo.addLine(pa, pb)
        geo.synchronize()
        mesh.setTransfiniteCurve(L, nL + 1)
        return L

    # ------------------------------------------------------------------ #
    # Outer-corner axials (all 4 corners per branch)                      #
    # ------------------------------------------------------------------ #
    ax_oN_1 = al(op_ap[iN_ap], op_1[iN_1])
    ax_oE_1 = al(op_ap[iE_ap], op_1[iE_1])
    ax_oS_1 = al(op_ap[iS_ap], op_1[iS_1])
    ax_oW_1 = al(op_ap[iW_ap], op_1[iW_1])   # NEW: W corner for branch_1

    ax_oN_2 = al(op_ap[iN_ap], op_2[iN_2])
    ax_oW_2 = al(op_ap[iW_ap], op_2[iW_2])
    ax_oS_2 = al(op_ap[iS_ap], op_2[iS_2])
    ax_oE_2 = al(op_ap[iE_ap], op_2[iE_2])   # NEW: E corner for branch_2

    # ------------------------------------------------------------------ #
    # Outer-arc signed tags (all 4 quadrant arcs per face)                #
    # ------------------------------------------------------------------ #
    oc_EN_ap = _arc(op_ap, oc_ap, op_ap[iE_ap], op_ap[iN_ap])
    oc_NW_ap = _arc(op_ap, oc_ap, op_ap[iN_ap], op_ap[iW_ap])
    oc_WS_ap = _arc(op_ap, oc_ap, op_ap[iW_ap], op_ap[iS_ap])
    oc_SE_ap = _arc(op_ap, oc_ap, op_ap[iS_ap], op_ap[iE_ap])

    oc_EN_1 = _arc(op_1, oc_1, op_1[iE_1], op_1[iN_1])
    oc_SE_1 = _arc(op_1, oc_1, op_1[iS_1], op_1[iE_1])
    oc_NW_1 = _arc(op_1, oc_1, op_1[iN_1], op_1[iW_1])
    oc_WS_1 = _arc(op_1, oc_1, op_1[iW_1], op_1[iS_1])

    oc_NW_2 = _arc(op_2, oc_2, op_2[iN_2], op_2[iW_2])
    oc_WS_2 = _arc(op_2, oc_2, op_2[iW_2], op_2[iS_2])
    oc_EN_2 = _arc(op_2, oc_2, op_2[iE_2], op_2[iN_2])
    oc_SE_2 = _arc(op_2, oc_2, op_2[iS_2], op_2[iE_2])

    # ------------------------------------------------------------------ #
    # Outer-arc side surfaces (primary)                                    #
    # ------------------------------------------------------------------ #
    s_NE_out1 = _curved([oc_EN_ap, ax_oN_1, -oc_EN_1, -ax_oE_1],
                        [op_ap[iE_ap], op_ap[iN_ap], op_1[iN_1], op_1[iE_1]])
    s_SE_out1 = _curved([oc_SE_ap, ax_oE_1, -oc_SE_1, -ax_oS_1],
                        [op_ap[iS_ap], op_ap[iE_ap], op_1[iE_1], op_1[iS_1]])

    s_NW_out2 = _curved([oc_NW_ap, ax_oW_2, -oc_NW_2, -ax_oN_2],
                        [op_ap[iN_ap], op_ap[iW_ap], op_2[iW_2], op_2[iN_2]])
    s_SW_out2 = _curved([oc_WS_ap, ax_oS_2, -oc_WS_2, -ax_oW_2],
                        [op_ap[iW_ap], op_ap[iS_ap], op_2[iS_2], op_2[iW_2]])

    # ------------------------------------------------------------------ #
    # Outer-arc side surfaces (fill — connect inlet arcs to opposite       #
    # branch outlets)                                                      #
    # ------------------------------------------------------------------ #
    s_NW_out1_fill = _curved([oc_NW_ap, ax_oW_1, -oc_NW_1, -ax_oN_1],
                             [op_ap[iN_ap], op_ap[iW_ap], op_1[iW_1], op_1[iN_1]])
    s_SW_out1_fill = _curved([oc_WS_ap, ax_oS_1, -oc_WS_1, -ax_oW_1],
                             [op_ap[iW_ap], op_ap[iS_ap], op_1[iS_1], op_1[iW_1]])

    s_NE_out2_fill = _curved([oc_EN_ap, ax_oN_2, -oc_EN_2, -ax_oE_2],
                             [op_ap[iE_ap], op_ap[iN_ap], op_2[iN_2], op_2[iE_2]])
    s_SE_out2_fill = _curved([oc_SE_ap, ax_oE_2, -oc_SE_2, -ax_oS_2],
                             [op_ap[iS_ap], op_ap[iE_ap], op_2[iE_2], op_2[iS_2]])

    # ------------------------------------------------------------------ #
    # Quad surface identification                                          #
    # ------------------------------------------------------------------ #
    surf_NE_ap = _surf_by_arc(ap_cs,   oc_EN_ap)
    surf_SE_ap = _surf_by_arc(ap_cs,   oc_SE_ap)
    surf_NW_ap = _surf_by_arc(ap_cs,   oc_NW_ap)
    surf_SW_ap = _surf_by_arc(ap_cs,   oc_WS_ap)

    surf_NE_1  = _surf_by_arc(out1_cs, oc_EN_1)
    surf_SE_1  = _surf_by_arc(out1_cs, oc_SE_1)
    surf_NW_1  = _surf_by_arc(out1_cs, oc_NW_1)
    surf_SW_1  = _surf_by_arc(out1_cs, oc_WS_1)

    surf_NW_2  = _surf_by_arc(out2_cs, oc_NW_2)
    surf_SW_2  = _surf_by_arc(out2_cs, oc_WS_2)
    surf_NE_2  = _surf_by_arc(out2_cs, oc_EN_2)
    surf_SE_2  = _surf_by_arc(out2_cs, oc_SE_2)

    # ------------------------------------------------------------------ #
    # Radial side surfaces                                                 #
    # ------------------------------------------------------------------ #
    new_ap_surfs: list[int] = []

    if is_core:
        # ---------------------------------------------------------------- #
        # Core layer                                                        #
        # ---------------------------------------------------------------- #
        _c_coords = np.mean(
            [np.array(gmsh.model.getValue(0, p, [])) for p in ip_ap], axis=0
        )
        cen_ap = geo.addPoint(
            float(_c_coords[0]), float(_c_coords[1]), float(_c_coords[2]),
            ap_cs.lc,
        )
        cen_1  = out1_cs.center
        cen_2  = out2_cs.center
        nrad   = ap_cs.nrad
        nang_pts = ap_cs.shape.nang + 1

        def sl(pa, pb):
            L = geo.addLine(pa, pb)
            geo.synchronize()
            mesh.setTransfiniteCurve(L, nang_pts)
            return L

        # Split lines at apex and each outlet
        L_NC_ap = sl(ip_ap[iN_ap], cen_ap)
        L_CS_ap = sl(cen_ap,        ip_ap[iS_ap])
        L_NC_1  = sl(ip_1[iN_1],   cen_1)
        L_CS_1  = sl(cen_1,        ip_1[iS_1])
        L_NC_2  = sl(ip_2[iN_2],   cen_2)
        L_CS_2  = sl(cen_2,        ip_2[iS_2])

        # Half-centre surfaces at apex
        ic_NE_ap = _arc(ip_ap, ic_ap, ip_ap[iN_ap], ip_ap[iE_ap])
        ic_ES_ap = _arc(ip_ap, ic_ap, ip_ap[iE_ap], ip_ap[iS_ap])
        ic_SW_ap = _arc(ip_ap, ic_ap, ip_ap[iS_ap], ip_ap[iW_ap])
        ic_WN_ap = _arc(ip_ap, ic_ap, ip_ap[iW_ap], ip_ap[iN_ap])

        surf_rc_ap = _plane(
            [ic_NE_ap, ic_ES_ap, -L_CS_ap, -L_NC_ap],
            [ip_ap[iN_ap], ip_ap[iE_ap], ip_ap[iS_ap], cen_ap],
        )
        surf_lc_ap = _plane(
            [L_NC_ap, L_CS_ap, ic_SW_ap, ic_WN_ap],
            [ip_ap[iN_ap], cen_ap, ip_ap[iS_ap], ip_ap[iW_ap]],
        )
        new_ap_surfs = [surf_rc_ap, surf_lc_ap]

        # Half-centre surfaces at outlet_1 (both halves — full split-centre)
        ic_NE_1 = _arc(ip_1, ic_1, ip_1[iN_1], ip_1[iE_1])
        ic_ES_1 = _arc(ip_1, ic_1, ip_1[iE_1], ip_1[iS_1])
        ic_SW_1 = _arc(ip_1, ic_1, ip_1[iS_1], ip_1[iW_1])
        ic_WN_1 = _arc(ip_1, ic_1, ip_1[iW_1], ip_1[iN_1])

        surf_rc_1 = _plane(
            [ic_NE_1, ic_ES_1, -L_CS_1, -L_NC_1],
            [ip_1[iN_1], ip_1[iE_1], ip_1[iS_1], cen_1],
        )
        surf_lc_1 = _plane(
            [L_NC_1, L_CS_1, ic_SW_1, ic_WN_1],
            [ip_1[iN_1], cen_1, ip_1[iS_1], ip_1[iW_1]],
        )

        # Half-centre surfaces at outlet_2 (both halves)
        ic_NE_2 = _arc(ip_2, ic_2, ip_2[iN_2], ip_2[iE_2])
        ic_ES_2 = _arc(ip_2, ic_2, ip_2[iE_2], ip_2[iS_2])
        ic_SW_2 = _arc(ip_2, ic_2, ip_2[iS_2], ip_2[iW_2])
        ic_WN_2 = _arc(ip_2, ic_2, ip_2[iW_2], ip_2[iN_2])

        surf_lc_2 = _plane(
            [L_NC_2, L_CS_2, ic_SW_2, ic_WN_2],
            [ip_2[iN_2], cen_2, ip_2[iS_2], ip_2[iW_2]],
        )
        surf_rc_2 = _plane(
            [ic_NE_2, ic_ES_2, -L_CS_2, -L_NC_2],
            [ip_2[iN_2], ip_2[iE_2], ip_2[iS_2], cen_2],
        )

        # Centre axials
        ax_cen_1 = al(cen_ap, cen_1)
        ax_cen_2 = al(cen_ap, cen_2)

        # Inner-corner axials: E/N/S for branch_1, W/N/S for branch_2
        ax_iE_1 = al(ip_ap[iE_ap], ip_1[iE_1])
        ax_iN_1 = al(ip_ap[iN_ap], ip_1[iN_1])
        ax_iS_1 = al(ip_ap[iS_ap], ip_1[iS_1])
        ax_iW_1 = al(ip_ap[iW_ap], ip_1[iW_1])   # NEW

        ax_iW_2 = al(ip_ap[iW_ap], ip_2[iW_2])
        ax_iN_2 = al(ip_ap[iN_ap], ip_2[iN_2])
        ax_iS_2 = al(ip_ap[iS_ap], ip_2[iS_2])
        ax_iE_2 = al(ip_ap[iE_ap], ip_2[iE_2])   # NEW

        # Split-plane side surfaces (shared between centre volumes)
        s_spN1 = _flat(
            [L_NC_ap, ax_cen_1, -L_NC_1, -ax_iN_1],
            [ip_ap[iN_ap], cen_ap, cen_1, ip_1[iN_1]],
        )
        s_spS1 = _flat(
            [L_CS_ap, ax_iS_1, -L_CS_1, -ax_cen_1],
            [cen_ap, ip_ap[iS_ap], ip_1[iS_1], cen_1],
        )
        s_spN2 = _flat(
            [L_NC_ap, ax_cen_2, -L_NC_2, -ax_iN_2],
            [ip_ap[iN_ap], cen_ap, cen_2, ip_2[iN_2]],
        )
        s_spS2 = _flat(
            [L_CS_ap, ax_iS_2, -L_CS_2, -ax_cen_2],
            [cen_ap, ip_ap[iS_ap], ip_2[iS_2], cen_2],
        )

        # Radial surfaces (all 4 corners per branch)
        s_rN1 = _flat([rc_ap[iN_ap], ax_oN_1, -rc_1[iN_1], -ax_iN_1],
                      [ip_ap[iN_ap], op_ap[iN_ap], op_1[iN_1], ip_1[iN_1]])
        s_rE1 = _flat([rc_ap[iE_ap], ax_oE_1, -rc_1[iE_1], -ax_iE_1],
                      [ip_ap[iE_ap], op_ap[iE_ap], op_1[iE_1], ip_1[iE_1]])
        s_rS1 = _flat([rc_ap[iS_ap], ax_oS_1, -rc_1[iS_1], -ax_iS_1],
                      [ip_ap[iS_ap], op_ap[iS_ap], op_1[iS_1], ip_1[iS_1]])
        s_rW1 = _flat([rc_ap[iW_ap], ax_oW_1, -rc_1[iW_1], -ax_iW_1],
                      [ip_ap[iW_ap], op_ap[iW_ap], op_1[iW_1], ip_1[iW_1]])

        s_rN2 = _flat([rc_ap[iN_ap], ax_oN_2, -rc_2[iN_2], -ax_iN_2],
                      [ip_ap[iN_ap], op_ap[iN_ap], op_2[iN_2], ip_2[iN_2]])
        s_rW2 = _flat([rc_ap[iW_ap], ax_oW_2, -rc_2[iW_2], -ax_iW_2],
                      [ip_ap[iW_ap], op_ap[iW_ap], op_2[iW_2], ip_2[iW_2]])
        s_rS2 = _flat([rc_ap[iS_ap], ax_oS_2, -rc_2[iS_2], -ax_iS_2],
                      [ip_ap[iS_ap], op_ap[iS_ap], op_2[iS_2], ip_2[iS_2]])
        s_rE2 = _flat([rc_ap[iE_ap], ax_oE_2, -rc_2[iE_2], -ax_iE_2],
                      [ip_ap[iE_ap], op_ap[iE_ap], op_2[iE_2], ip_2[iE_2]])

        # Inner arc side surfaces (from inlet inner arcs)
        ic_NE_ap_ = _arc(ip_ap, ic_ap, ip_ap[iN_ap], ip_ap[iE_ap])
        ic_ES_ap_ = _arc(ip_ap, ic_ap, ip_ap[iE_ap], ip_ap[iS_ap])
        ic_SW_ap_ = _arc(ip_ap, ic_ap, ip_ap[iS_ap], ip_ap[iW_ap])
        ic_WN_ap_ = _arc(ip_ap, ic_ap, ip_ap[iW_ap], ip_ap[iN_ap])

        # Primary inner arc sides (inlet → branch primary outlet)
        s_NE_in1 = _curved([ic_NE_ap_, ax_iE_1, -ic_NE_1, -ax_iN_1],
                           [ip_ap[iN_ap], ip_ap[iE_ap], ip_1[iE_1], ip_1[iN_1]])
        s_ES_in1 = _curved([ic_ES_ap_, ax_iS_1, -ic_ES_1, -ax_iE_1],
                           [ip_ap[iE_ap], ip_ap[iS_ap], ip_1[iS_1], ip_1[iE_1]])
        s_WN_in2 = _curved([ic_WN_ap_, ax_iN_2, -ic_WN_2, -ax_iW_2],
                           [ip_ap[iW_ap], ip_ap[iN_ap], ip_2[iN_2], ip_2[iW_2]])
        s_SW_in2 = _curved([ic_SW_ap_, ax_iW_2, -ic_SW_2, -ax_iS_2],
                           [ip_ap[iS_ap], ip_ap[iW_ap], ip_2[iW_2], ip_2[iS_2]])

        # Fill inner arc sides (inlet → opposite-branch fill outlet)
        s_WN_in1_fill = _curved([ic_WN_ap_, ax_iN_1, -ic_WN_1, -ax_iW_1],
                                [ip_ap[iW_ap], ip_ap[iN_ap], ip_1[iN_1], ip_1[iW_1]])
        s_SW_in1_fill = _curved([ic_SW_ap_, ax_iW_1, -ic_SW_1, -ax_iS_1],
                                [ip_ap[iS_ap], ip_ap[iW_ap], ip_1[iW_1], ip_1[iS_1]])
        s_NE_in2_fill = _curved([ic_NE_ap_, ax_iE_2, -ic_NE_2, -ax_iN_2],
                                [ip_ap[iN_ap], ip_ap[iE_ap], ip_2[iE_2], ip_2[iN_2]])
        s_ES_in2_fill = _curved([ic_ES_ap_, ax_iS_2, -ic_ES_2, -ax_iE_2],
                                [ip_ap[iE_ap], ip_ap[iS_ap], ip_2[iS_2], ip_2[iE_2]])

        # ---------------------------------------------------------------- #
        # Build volumes — primary (6: 3 per branch)                        #
        # ---------------------------------------------------------------- #
        vol_rc1 = _vol(
            [-surf_rc_ap, surf_rc_1,
             s_NE_in1, s_ES_in1, -s_spN1, s_spS1],
            [ip_ap[iN_ap], ip_ap[iE_ap], ip_ap[iS_ap], cen_ap,
             ip_1[iN_1],   ip_1[iE_1],   ip_1[iS_1],   cen_1],
        )
        vol_NE1 = _vol(
            [-surf_NE_ap, surf_NE_1,
             s_NE_out1, -s_NE_in1, -s_rN1, s_rE1],
            [ip_ap[iN_ap], op_ap[iN_ap], op_ap[iE_ap], ip_ap[iE_ap],
             ip_1[iN_1],   op_1[iN_1],   op_1[iE_1],   ip_1[iE_1]],
        )
        vol_SE1 = _vol(
            [-surf_SE_ap, surf_SE_1,
             s_SE_out1, -s_ES_in1, -s_rE1, s_rS1],
            [ip_ap[iE_ap], op_ap[iE_ap], op_ap[iS_ap], ip_ap[iS_ap],
             ip_1[iE_1],   op_1[iE_1],   op_1[iS_1],   ip_1[iS_1]],
        )

        vol_lc2 = _vol(
            [-surf_lc_ap, surf_lc_2,
             -s_WN_in2, s_SW_in2, s_spN2, -s_spS2],
            [ip_ap[iN_ap], cen_ap, ip_ap[iS_ap], ip_ap[iW_ap],
             ip_2[iN_2],   cen_2,  ip_2[iS_2],   ip_2[iW_2]],
        )
        vol_NW2 = _vol(
            [-surf_NW_ap, surf_NW_2,
             s_NW_out2, -s_WN_in2, s_rN2, -s_rW2],
            [ip_ap[iW_ap], ip_ap[iN_ap], op_ap[iN_ap], op_ap[iW_ap],
             ip_2[iW_2],   ip_2[iN_2],   op_2[iN_2],   op_2[iW_2]],
        )
        vol_SW2 = _vol(
            [-surf_SW_ap, surf_SW_2,
             s_SW_out2, -s_SW_in2, s_rW2, -s_rS2],
            [ip_ap[iS_ap], ip_ap[iW_ap], op_ap[iW_ap], op_ap[iS_ap],
             ip_2[iS_2],   ip_2[iW_2],   op_2[iW_2],   op_2[iS_2]],
        )

        # ---------------------------------------------------------------- #
        # Build volumes — fill (6: 3 per branch)                           #
        # ---------------------------------------------------------------- #
        vol_lc1_fill = _vol(
            [-surf_lc_ap, surf_lc_1,
             s_spN1, -s_spS1, s_WN_in1_fill, s_SW_in1_fill],
            [ip_ap[iN_ap], cen_ap, ip_ap[iS_ap], ip_ap[iW_ap],
             ip_1[iN_1],   cen_1,  ip_1[iS_1],   ip_1[iW_1]],
        )
        vol_NW1_fill = _vol(
            [-surf_NW_ap, surf_NW_1,
             s_NW_out1_fill, -s_WN_in1_fill, s_rN1, -s_rW1],
            [ip_ap[iW_ap], ip_ap[iN_ap], op_ap[iN_ap], op_ap[iW_ap],
             ip_1[iW_1],   ip_1[iN_1],   op_1[iN_1],   op_1[iW_1]],
        )
        vol_SW1_fill = _vol(
            [-surf_SW_ap, surf_SW_1,
             s_SW_out1_fill, -s_SW_in1_fill, s_rW1, -s_rS1],
            [ip_ap[iS_ap], ip_ap[iW_ap], op_ap[iW_ap], op_ap[iS_ap],
             ip_1[iS_1],   ip_1[iW_1],   op_1[iW_1],   op_1[iS_1]],
        )

        vol_rc2_fill = _vol(
            [-surf_rc_ap, surf_rc_2,
             -s_spN2, s_spS2, s_NE_in2_fill, s_ES_in2_fill],
            [ip_ap[iN_ap], ip_ap[iE_ap], ip_ap[iS_ap], cen_ap,
             ip_2[iN_2],   ip_2[iE_2],   ip_2[iS_2],   cen_2],
        )
        vol_NE2_fill = _vol(
            [-surf_NE_ap, surf_NE_2,
             s_NE_out2_fill, -s_NE_in2_fill, -s_rN2, s_rE2],
            [ip_ap[iN_ap], op_ap[iN_ap], op_ap[iE_ap], ip_ap[iE_ap],
             ip_2[iN_2],   op_2[iN_2],   op_2[iE_2],   ip_2[iE_2]],
        )
        vol_SE2_fill = _vol(
            [-surf_SE_ap, surf_SE_2,
             s_SE_out2_fill, -s_ES_in2_fill, s_rE2, -s_rS2],
            [ip_ap[iE_ap], op_ap[iE_ap], op_ap[iS_ap], ip_ap[iS_ap],
             ip_2[iE_2],   op_2[iE_2],   op_2[iS_2],   ip_2[iS_2]],
        )

        vols_1 = [vol_rc1, vol_NE1, vol_SE1, vol_lc1_fill, vol_NW1_fill, vol_SW1_fill]
        vols_2 = [vol_lc2, vol_NW2, vol_SW2, vol_rc2_fill, vol_NE2_fill, vol_SE2_fill]

        # 6-surface outlet lists: [rc, lc, NE, NW, SW, SE]
        out1_surfs = [surf_rc_1, surf_lc_1, surf_NE_1, surf_NW_1, surf_SW_1, surf_SE_1]
        out2_surfs = [surf_lc_2, surf_rc_2, surf_NW_2, surf_SW_2, surf_NE_2, surf_SE_2]

        ow1 = [s_NE_out1, s_SE_out1, s_NW_out1_fill, s_SW_out1_fill]
        ow2 = [s_NW_out2, s_SW_out2, s_NE_out2_fill, s_SE_out2_fill]
        oa1 = [ax_oN_1, ax_oE_1, ax_oS_1, ax_oW_1]
        oa2 = [ax_oN_2, ax_oW_2, ax_oS_2, ax_oE_2]

    else:
        # ---------------------------------------------------------------- #
        # Annular shell layer                                               #
        # ---------------------------------------------------------------- #
        # Inner corner axials from previous layer's outer axials
        ax_iN_1, ax_iE_1, ax_iS_1, ax_iW_1 = prev_oa1
        ax_iN_2, ax_iW_2, ax_iS_2, ax_iE_2 = prev_oa2

        # Radial surfaces
        s_rN1 = _flat([rc_ap[iN_ap], ax_oN_1, -rc_1[iN_1], -ax_iN_1],
                      [ip_ap[iN_ap], op_ap[iN_ap], op_1[iN_1], ip_1[iN_1]])
        s_rE1 = _flat([rc_ap[iE_ap], ax_oE_1, -rc_1[iE_1], -ax_iE_1],
                      [ip_ap[iE_ap], op_ap[iE_ap], op_1[iE_1], ip_1[iE_1]])
        s_rS1 = _flat([rc_ap[iS_ap], ax_oS_1, -rc_1[iS_1], -ax_iS_1],
                      [ip_ap[iS_ap], op_ap[iS_ap], op_1[iS_1], ip_1[iS_1]])
        s_rW1 = _flat([rc_ap[iW_ap], ax_oW_1, -rc_1[iW_1], -ax_iW_1],
                      [ip_ap[iW_ap], op_ap[iW_ap], op_1[iW_1], ip_1[iW_1]])

        s_rN2 = _flat([rc_ap[iN_ap], ax_oN_2, -rc_2[iN_2], -ax_iN_2],
                      [ip_ap[iN_ap], op_ap[iN_ap], op_2[iN_2], ip_2[iN_2]])
        s_rW2 = _flat([rc_ap[iW_ap], ax_oW_2, -rc_2[iW_2], -ax_iW_2],
                      [ip_ap[iW_ap], op_ap[iW_ap], op_2[iW_2], ip_2[iW_2]])
        s_rS2 = _flat([rc_ap[iS_ap], ax_oS_2, -rc_2[iS_2], -ax_iS_2],
                      [ip_ap[iS_ap], op_ap[iS_ap], op_2[iS_2], ip_2[iS_2]])
        s_rE2 = _flat([rc_ap[iE_ap], ax_oE_2, -rc_2[iE_2], -ax_iE_2],
                      [ip_ap[iE_ap], op_ap[iE_ap], op_2[iE_2], ip_2[iE_2]])

        # Inner arc side surfaces reused from previous layer's outer sides
        s_NE_in1    = prev_ow1[0]
        s_ES_in1    = prev_ow1[1]
        s_WN_in1_fill = prev_ow1[2]
        s_SW_in1_fill = prev_ow1[3]

        s_WN_in2    = prev_ow2[0]
        s_SW_in2    = prev_ow2[1]
        s_NE_in2_fill = prev_ow2[2]
        s_ES_in2_fill = prev_ow2[3]

        # Primary shell volumes for branch_1 (NE + SE)
        vol_NE_sh1 = _vol(
            [-surf_NE_ap, surf_NE_1,
             s_NE_out1, -s_NE_in1, -s_rN1, s_rE1],
            [ip_ap[iN_ap], op_ap[iN_ap], op_ap[iE_ap], ip_ap[iE_ap],
             ip_1[iN_1],   op_1[iN_1],   op_1[iE_1],   ip_1[iE_1]],
        )
        vol_SE_sh1 = _vol(
            [-surf_SE_ap, surf_SE_1,
             s_SE_out1, -s_ES_in1, -s_rE1, s_rS1],
            [ip_ap[iE_ap], op_ap[iE_ap], op_ap[iS_ap], ip_ap[iS_ap],
             ip_1[iE_1],   op_1[iE_1],   op_1[iS_1],   ip_1[iS_1]],
        )
        # Primary shell volumes for branch_2 (NW + SW)
        vol_NW_sh2 = _vol(
            [-surf_NW_ap, surf_NW_2,
             s_NW_out2, -s_WN_in2, s_rN2, -s_rW2],
            [ip_ap[iW_ap], ip_ap[iN_ap], op_ap[iN_ap], op_ap[iW_ap],
             ip_2[iW_2],   ip_2[iN_2],   op_2[iN_2],   op_2[iW_2]],
        )
        vol_SW_sh2 = _vol(
            [-surf_SW_ap, surf_SW_2,
             s_SW_out2, -s_SW_in2, s_rW2, -s_rS2],
            [ip_ap[iS_ap], ip_ap[iW_ap], op_ap[iW_ap], op_ap[iS_ap],
             ip_2[iS_2],   ip_2[iW_2],   op_2[iW_2],   op_2[iS_2]],
        )

        # Fill shell volumes for branch_1 (NW + SW)
        vol_NW_fill_sh1 = _vol(
            [-surf_NW_ap, surf_NW_1,
             s_NW_out1_fill, -s_WN_in1_fill, s_rN1, -s_rW1],
            [ip_ap[iW_ap], ip_ap[iN_ap], op_ap[iN_ap], op_ap[iW_ap],
             ip_1[iW_1],   ip_1[iN_1],   op_1[iN_1],   op_1[iW_1]],
        )
        vol_SW_fill_sh1 = _vol(
            [-surf_SW_ap, surf_SW_1,
             s_SW_out1_fill, -s_SW_in1_fill, s_rW1, -s_rS1],
            [ip_ap[iS_ap], ip_ap[iW_ap], op_ap[iW_ap], op_ap[iS_ap],
             ip_1[iS_1],   ip_1[iW_1],   op_1[iW_1],   op_1[iS_1]],
        )
        # Fill shell volumes for branch_2 (NE + SE)
        vol_NE_fill_sh2 = _vol(
            [-surf_NE_ap, surf_NE_2,
             s_NE_out2_fill, -s_NE_in2_fill, -s_rN2, s_rE2],
            [ip_ap[iN_ap], op_ap[iN_ap], op_ap[iE_ap], ip_ap[iE_ap],
             ip_2[iN_2],   op_2[iN_2],   op_2[iE_2],   ip_2[iE_2]],
        )
        vol_SE_fill_sh2 = _vol(
            [-surf_SE_ap, surf_SE_2,
             s_SE_out2_fill, -s_ES_in2_fill, s_rE2, -s_rS2],
            [ip_ap[iE_ap], op_ap[iE_ap], op_ap[iS_ap], ip_ap[iS_ap],
             ip_2[iE_2],   op_2[iE_2],   op_2[iS_2],   ip_2[iS_2]],
        )

        vols_1 = [vol_NE_sh1, vol_SE_sh1, vol_NW_fill_sh1, vol_SW_fill_sh1]
        vols_2 = [vol_NW_sh2, vol_SW_sh2, vol_NE_fill_sh2, vol_SE_fill_sh2]

        out1_surfs = [surf_NE_1, surf_SE_1, surf_NW_1, surf_SW_1]
        out2_surfs = [surf_NW_2, surf_SW_2, surf_NE_2, surf_SE_2]

        ow1 = [s_NE_out1, s_SE_out1, s_NW_out1_fill, s_SW_out1_fill]
        ow2 = [s_NW_out2, s_SW_out2, s_NE_out2_fill, s_SE_out2_fill]
        oa1 = [ax_oN_1, ax_oE_1, ax_oS_1, ax_oW_1]
        oa2 = [ax_oN_2, ax_oW_2, ax_oS_2, ax_oE_2]

    return (vols_1, vols_2, ow1, ow2, oa1, oa2,
            out1_surfs, out2_surfs, new_ap_surfs)


# ---------------------------------------------------------------------------
# n_outer=8 per-layer builder
# ---------------------------------------------------------------------------

def _build_layer_8(
    ap_cs:    CrossSection,
    out1_cs:  CrossSection,
    out2_cs:  CrossSection,
    cursor:   Cursor,
    n_layers: int,
    prev_ow1: "list[int] | None",
    prev_ow2: "list[int] | None",
    prev_oa1: "list[int] | None",
    prev_oa2: "list[int] | None",
):
    """Build junction volumes for one concentric layer (n_outer=8).

    Core layer: 4 centre half-volumes + 16 ring sector volumes = 20 total.
    Shell layer: 16 ring sector volumes.

    Returns same tuple as _build_layer.

    Note: inner arc side surfaces for ring sectors are geometrically coincident
    with the combined inner arc sides of adjacent centre volumes.  Conformal
    node matching is handled by Model.mesh() → removeDuplicateNodes().
    """
    geo  = gmsh.model.occ
    mesh = gmsh.model.mesh
    n    = 8
    is_core = (len(ap_cs.surfaces) == n + 1)
    nL   = n_layers

    # ------------------------------------------------------------------ #
    # Extract geometry                                                     #
    # ------------------------------------------------------------------ #
    g_ap   = _extract_geom(ap_cs)
    g_out1 = _extract_geom(out1_cs)
    g_out2 = _extract_geom(out2_cs)

    ip_ap = g_ap['ip'];  ic_ap = g_ap['ic']
    op_ap = g_ap['op'];  oc_ap = g_ap['oc'];  rc_ap = g_ap['rc']
    ip_1  = g_out1['ip']; ic_1  = g_out1['ic']
    op_1  = g_out1['op']; oc_1  = g_out1['oc']; rc_1  = g_out1['rc']
    ip_2  = g_out2['ip']; ic_2  = g_out2['ic']
    op_2  = g_out2['op']; oc_2  = g_out2['oc']; rc_2  = g_out2['rc']

    # ------------------------------------------------------------------ #
    # Classify cardinal corners                                           #
    # ------------------------------------------------------------------ #
    apos = np.asarray(cursor.position, dtype=float)
    iE_ap, iN_ap, iW_ap, iS_ap = _classify(g_ap,   cursor, apos)
    iE_1,  iN_1,  iW_1,  iS_1  = _classify(g_out1, cursor, apos)
    iE_2,  iN_2,  iW_2,  iS_2  = _classify(g_out2, cursor, apos)

    # ------------------------------------------------------------------ #
    # Mark face surfaces transfinite                                       #
    # ------------------------------------------------------------------ #
    geo.synchronize()
    if is_core:
        # Centre patch has 8 boundary arcs; auto-detection would find 8 corners.
        # Specify the 4 diagonal (NE/NW/SW/SE) corners explicitly.
        for cs, ip in [(ap_cs, ip_ap), (out1_cs, ip_1), (out2_cs, ip_2)]:
            mesh.setTransfiniteSurface(
                cs.surfaces[0], "Left", [ip[0], ip[2], ip[4], ip[6]]
            )
            mesh.setRecombine(2, cs.surfaces[0])
            for s in cs.surfaces[1:]:
                mesh.setTransfiniteSurface(s)
                mesh.setRecombine(2, s)
    else:
        for s in ap_cs.surfaces + out1_cs.surfaces + out2_cs.surfaces:
            mesh.setTransfiniteSurface(s)
            mesh.setRecombine(2, s)

    def al(pa, pb):
        L = geo.addLine(pa, pb)
        geo.synchronize()
        mesh.setTransfiniteCurve(L, nL + 1)
        return L

    # ------------------------------------------------------------------ #
    # Outer corner axials: 8 per branch                                   #
    # ------------------------------------------------------------------ #
    ax_o_1 = [al(op_ap[k], op_1[k]) for k in range(n)]
    ax_o_2 = [al(op_ap[k], op_2[k]) for k in range(n)]

    # ------------------------------------------------------------------ #
    # Ring surface lookups                                                 #
    # ------------------------------------------------------------------ #
    surf_ring_ap = [_surf_by_arc(ap_cs,   oc_ap[k]) for k in range(n)]
    surf_ring_1  = [_surf_by_arc(out1_cs, oc_1[k])  for k in range(n)]
    surf_ring_2  = [_surf_by_arc(out2_cs, oc_2[k])  for k in range(n)]

    # ------------------------------------------------------------------ #
    # Outer arc side surfaces: 8 per branch                               #
    # ------------------------------------------------------------------ #
    ow1_surfs: list[int] = []
    for k in range(n):
        k1 = (k + 1) % n
        s  = _curved(
            [oc_ap[k], ax_o_1[k1], -oc_1[k], -ax_o_1[k]],
            [op_ap[k], op_ap[k1], op_1[k1], op_1[k]],
        )
        ow1_surfs.append(s)

    ow2_surfs: list[int] = []
    for k in range(n):
        k1 = (k + 1) % n
        s  = _curved(
            [oc_ap[k], ax_o_2[k1], -oc_2[k], -ax_o_2[k]],
            [op_ap[k], op_ap[k1], op_2[k1], op_2[k]],
        )
        ow2_surfs.append(s)

    new_ap_surfs: list[int] = []

    if is_core:
        # ---------------------------------------------------------------- #
        # Core layer                                                        #
        # ---------------------------------------------------------------- #
        nrad     = ap_cs.nrad
        nang_pts = ap_cs.shape.nang + 1
        _c_coords = np.mean(
            [np.array(gmsh.model.getValue(0, p, [])) for p in ip_ap], axis=0
        )
        cen_ap = geo.addPoint(
            float(_c_coords[0]), float(_c_coords[1]), float(_c_coords[2]),
            ap_cs.lc,
        )
        cen_1 = out1_cs.center
        cen_2 = out2_cs.center

        def sl(pa, pb):
            L = geo.addLine(pa, pb)
            geo.synchronize()
            mesh.setTransfiniteCurve(L, nang_pts)
            return L

        # Split lines
        L_NC_ap = sl(ip_ap[iN_ap], cen_ap)
        L_CS_ap = sl(cen_ap,       ip_ap[iS_ap])
        L_NC_1  = sl(ip_1[iN_1],  cen_1)
        L_CS_1  = sl(cen_1,       ip_1[iS_1])
        L_NC_2  = sl(ip_2[iN_2],  cen_2)
        L_CS_2  = sl(cen_2,       ip_2[iS_2])

        # Inner corner axials: all 8 per branch
        ax_i_1 = [al(ip_ap[k], ip_1[k]) for k in range(n)]
        ax_i_2 = [al(ip_ap[k], ip_2[k]) for k in range(n)]

        # Centre axials
        ax_cen_1 = al(cen_ap, cen_1)
        ax_cen_2 = al(cen_ap, cen_2)

        # --------------------------------------------------------------- #
        # Half-centre surfaces: 6-curve plane surfaces                     #
        # rc = E-half (N→NE→E→SE→S going CW, i.e. reversed inner arcs    #
        # at k=0,7,6,5 then split lines)                                   #
        # lc = W-half (N→NW→W→SW→S going CCW, inner arcs at k=1,2,3,4)   #
        # Corners for transfinite: [N, E/W, S, cen]                        #
        # --------------------------------------------------------------- #
        surf_rc_ap = _plane(
            [-ic_ap[0], -ic_ap[7], -ic_ap[6], -ic_ap[5], -L_CS_ap, -L_NC_ap],
            [ip_ap[iN_ap], ip_ap[iE_ap], ip_ap[iS_ap], cen_ap],
        )
        surf_lc_ap = _plane(
            [ic_ap[1], ic_ap[2], ic_ap[3], ic_ap[4], -L_CS_ap, -L_NC_ap],
            [ip_ap[iN_ap], ip_ap[iW_ap], ip_ap[iS_ap], cen_ap],
        )
        new_ap_surfs = [surf_rc_ap, surf_lc_ap]

        surf_rc_1 = _plane(
            [-ic_1[0], -ic_1[7], -ic_1[6], -ic_1[5], -L_CS_1, -L_NC_1],
            [ip_1[iN_1], ip_1[iE_1], ip_1[iS_1], cen_1],
        )
        surf_lc_1 = _plane(
            [ic_1[1], ic_1[2], ic_1[3], ic_1[4], -L_CS_1, -L_NC_1],
            [ip_1[iN_1], ip_1[iW_1], ip_1[iS_1], cen_1],
        )
        surf_rc_2 = _plane(
            [-ic_2[0], -ic_2[7], -ic_2[6], -ic_2[5], -L_CS_2, -L_NC_2],
            [ip_2[iN_2], ip_2[iE_2], ip_2[iS_2], cen_2],
        )
        surf_lc_2 = _plane(
            [ic_2[1], ic_2[2], ic_2[3], ic_2[4], -L_CS_2, -L_NC_2],
            [ip_2[iN_2], ip_2[iW_2], ip_2[iS_2], cen_2],
        )

        # --------------------------------------------------------------- #
        # Split-plane side surfaces                                         #
        # --------------------------------------------------------------- #
        s_spN1 = _flat(
            [L_NC_ap, ax_cen_1, -L_NC_1, -ax_i_1[iN_ap]],
            [ip_ap[iN_ap], cen_ap, cen_1, ip_1[iN_1]],
        )
        s_spS1 = _flat(
            [L_CS_ap, ax_i_1[iS_ap], -L_CS_1, -ax_cen_1],
            [cen_ap, ip_ap[iS_ap], ip_1[iS_1], cen_1],
        )
        s_spN2 = _flat(
            [L_NC_ap, ax_cen_2, -L_NC_2, -ax_i_2[iN_ap]],
            [ip_ap[iN_ap], cen_ap, cen_2, ip_2[iN_2]],
        )
        s_spS2 = _flat(
            [L_CS_ap, ax_i_2[iS_ap], -L_CS_2, -ax_cen_2],
            [cen_ap, ip_ap[iS_ap], ip_2[iS_2], cen_2],
        )

        # --------------------------------------------------------------- #
        # Combined inner arc side surfaces for centre half-volumes.        #
        # Each covers 90° (2 arcs × 45°) with 6 boundary curves.          #
        # Geometrically coincident with adjacent ring sector inner sides;  #
        # node conformality is resolved by removeDuplicateNodes().         #
        # --------------------------------------------------------------- #
        # E-side primary (branch_1): N→NE→E and E→SE→S going CW
        s_NE_in1 = _curved(
            [-ic_ap[0], -ic_ap[7],
             ax_i_1[iE_ap], ic_1[7], ic_1[0], -ax_i_1[iN_ap]],
            [ip_ap[iN_ap], ip_ap[iE_ap], ip_1[iE_ap], ip_1[iN_ap]],
        )
        s_ES_in1 = _curved(
            [-ic_ap[6], -ic_ap[5],
             ax_i_1[iS_ap], ic_1[5], ic_1[6], -ax_i_1[iE_ap]],
            [ip_ap[iE_ap], ip_ap[iS_ap], ip_1[iS_ap], ip_1[iE_ap]],
        )
        # W-side primary (branch_2): W→NW→N and S→SW→W going CW
        s_WN_in2 = _curved(
            [-ic_ap[2], -ic_ap[1],
             ax_i_2[iN_ap], ic_2[1], ic_2[2], -ax_i_2[iW_ap]],
            [ip_ap[iW_ap], ip_ap[iN_ap], ip_2[iN_ap], ip_2[iW_ap]],
        )
        s_SW_in2 = _curved(
            [-ic_ap[4], -ic_ap[3],
             ax_i_2[iW_ap], ic_2[3], ic_2[4], -ax_i_2[iS_ap]],
            [ip_ap[iS_ap], ip_ap[iW_ap], ip_2[iW_ap], ip_2[iS_ap]],
        )
        # W-side fill (branch_1): W→NW→N and S→SW→W going CW to outlet_1
        s_WN_in1_fill = _curved(
            [-ic_ap[2], -ic_ap[1],
             ax_i_1[iN_ap], ic_1[1], ic_1[2], -ax_i_1[iW_ap]],
            [ip_ap[iW_ap], ip_ap[iN_ap], ip_1[iN_ap], ip_1[iW_ap]],
        )
        s_SW_in1_fill = _curved(
            [-ic_ap[4], -ic_ap[3],
             ax_i_1[iW_ap], ic_1[3], ic_1[4], -ax_i_1[iS_ap]],
            [ip_ap[iS_ap], ip_ap[iW_ap], ip_1[iW_ap], ip_1[iS_ap]],
        )
        # E-side fill (branch_2): N→NE→E and E→SE→S going CW to outlet_2
        s_NE_in2_fill = _curved(
            [-ic_ap[0], -ic_ap[7],
             ax_i_2[iE_ap], ic_2[7], ic_2[0], -ax_i_2[iN_ap]],
            [ip_ap[iN_ap], ip_ap[iE_ap], ip_2[iE_ap], ip_2[iN_ap]],
        )
        s_ES_in2_fill = _curved(
            [-ic_ap[6], -ic_ap[5],
             ax_i_2[iS_ap], ic_2[5], ic_2[6], -ax_i_2[iE_ap]],
            [ip_ap[iE_ap], ip_ap[iS_ap], ip_2[iS_ap], ip_2[iE_ap]],
        )

        # --------------------------------------------------------------- #
        # Radial side surfaces: 8 per branch                               #
        # --------------------------------------------------------------- #
        s_r_1 = [
            _curved([rc_ap[k], ax_o_1[k], -rc_1[k], -ax_i_1[k]],
                    [ip_ap[k], op_ap[k], op_1[k], ip_1[k]])
            for k in range(n)
        ]
        s_r_2 = [
            _curved([rc_ap[k], ax_o_2[k], -rc_2[k], -ax_i_2[k]],
                    [ip_ap[k], op_ap[k], op_2[k], ip_2[k]])
            for k in range(n)
        ]

        # --------------------------------------------------------------- #
        # Individual inner arc side surfaces for ring sector volumes       #
        # (4-curve each; geometrically coincident with portions of the     #
        # combined 6-curve surfaces above — merged by removeDuplicateNodes)#
        # --------------------------------------------------------------- #
        s_in1_ring = [
            _curved(
                [ic_ap[k], ax_i_1[(k + 1) % n], -ic_1[k], -ax_i_1[k]],
                [ip_ap[k], ip_ap[(k + 1) % n], ip_1[(k + 1) % n], ip_1[k]],
            )
            for k in range(n)
        ]
        s_in2_ring = [
            _curved(
                [ic_ap[k], ax_i_2[(k + 1) % n], -ic_2[k], -ax_i_2[k]],
                [ip_ap[k], ip_ap[(k + 1) % n], ip_2[(k + 1) % n], ip_2[k]],
            )
            for k in range(n)
        ]

        # --------------------------------------------------------------- #
        # Centre half-volumes (4 total: primary rc1+lc2, fill lc1+rc2)    #
        # --------------------------------------------------------------- #
        vol_rc1 = _vol(
            [surf_rc_ap, surf_rc_1, s_NE_in1, s_ES_in1, s_spN1, s_spS1],
            [ip_ap[iN_ap], ip_ap[iE_ap], ip_ap[iS_ap], cen_ap,
             ip_1[iN_1],   ip_1[iE_1],   ip_1[iS_1],   cen_1],
        )
        vol_lc2 = _vol(
            [surf_lc_ap, surf_lc_2, s_WN_in2, s_SW_in2, s_spN2, s_spS2],
            [ip_ap[iN_ap], cen_ap, ip_ap[iS_ap], ip_ap[iW_ap],
             ip_2[iN_2],   cen_2,  ip_2[iS_2],   ip_2[iW_2]],
        )
        vol_lc1_fill = _vol(
            [surf_lc_ap, surf_lc_1, s_spN1, s_spS1, s_WN_in1_fill, s_SW_in1_fill],
            [ip_ap[iN_ap], cen_ap, ip_ap[iS_ap], ip_ap[iW_ap],
             ip_1[iN_1],   cen_1,  ip_1[iS_1],   ip_1[iW_1]],
        )
        vol_rc2_fill = _vol(
            [surf_rc_ap, surf_rc_2, s_NE_in2_fill, s_ES_in2_fill, s_spN2, s_spS2],
            [ip_ap[iN_ap], ip_ap[iE_ap], ip_ap[iS_ap], cen_ap,
             ip_2[iN_2],   ip_2[iE_2],   ip_2[iS_2],   cen_2],
        )

        # --------------------------------------------------------------- #
        # Ring sector volumes: 8 per branch (all arcs)                     #
        # --------------------------------------------------------------- #
        vols_ring_1 = []
        for k in range(n):
            k1 = (k + 1) % n
            vols_ring_1.append(_vol(
                [surf_ring_ap[k], surf_ring_1[k],
                 ow1_surfs[k], s_in1_ring[k], s_r_1[k], s_r_1[k1]],
                [ip_ap[k], op_ap[k], op_ap[k1], ip_ap[k1],
                 ip_1[k],  op_1[k],  op_1[k1],  ip_1[k1]],
            ))

        vols_ring_2 = []
        for k in range(n):
            k1 = (k + 1) % n
            vols_ring_2.append(_vol(
                [surf_ring_ap[k], surf_ring_2[k],
                 ow2_surfs[k], s_in2_ring[k], s_r_2[k], s_r_2[k1]],
                [ip_ap[k], op_ap[k], op_ap[k1], ip_ap[k1],
                 ip_2[k],  op_2[k],  op_2[k1],  ip_2[k1]],
            ))

        vols_1 = [vol_rc1, vol_lc1_fill] + vols_ring_1
        vols_2 = [vol_lc2, vol_rc2_fill] + vols_ring_2

        # 10-surface outlet lists: [rc, lc, ring_0..ring_7]
        # is_split_core detects len == n_outer+2 = 10 downstream.
        out1_surfs = [surf_rc_1, surf_lc_1] + surf_ring_1
        out2_surfs = [surf_lc_2, surf_rc_2] + surf_ring_2

        ow1 = ow1_surfs
        ow2 = ow2_surfs
        oa1 = ax_o_1
        oa2 = ax_o_2

    else:
        # ---------------------------------------------------------------- #
        # Shell (annular) layer                                             #
        # ---------------------------------------------------------------- #
        ax_i_1 = list(prev_oa1)   # 8 inner axials from previous layer
        ax_i_2 = list(prev_oa2)

        # Radial side surfaces
        s_r_1 = [
            _curved([rc_ap[k], ax_o_1[k], -rc_1[k], -ax_i_1[k]],
                    [ip_ap[k], op_ap[k], op_1[k], ip_1[k]])
            for k in range(n)
        ]
        s_r_2 = [
            _curved([rc_ap[k], ax_o_2[k], -rc_2[k], -ax_i_2[k]],
                    [ip_ap[k], op_ap[k], op_2[k], ip_2[k]])
            for k in range(n)
        ]

        # Ring sector volumes: 8 per branch (all arcs)
        vols_ring_1 = []
        for k in range(n):
            k1 = (k + 1) % n
            vols_ring_1.append(_vol(
                [surf_ring_ap[k], surf_ring_1[k],
                 ow1_surfs[k], prev_ow1[k], s_r_1[k], s_r_1[k1]],
                [ip_ap[k], op_ap[k], op_ap[k1], ip_ap[k1],
                 ip_1[k],  op_1[k],  op_1[k1],  ip_1[k1]],
            ))

        vols_ring_2 = []
        for k in range(n):
            k1 = (k + 1) % n
            vols_ring_2.append(_vol(
                [surf_ring_ap[k], surf_ring_2[k],
                 ow2_surfs[k], prev_ow2[k], s_r_2[k], s_r_2[k1]],
                [ip_ap[k], op_ap[k], op_ap[k1], ip_ap[k1],
                 ip_2[k],  op_2[k],  op_2[k1],  ip_2[k1]],
            ))

        vols_1 = vols_ring_1
        vols_2 = vols_ring_2

        out1_surfs = surf_ring_1   # 8 surfaces → annular
        out2_surfs = surf_ring_2

        ow1 = ow1_surfs
        ow2 = ow2_surfs
        oa1 = ax_o_1
        oa2 = ax_o_2

    return (vols_1, vols_2, ow1, ow2, oa1, oa2,
            out1_surfs, out2_surfs, new_ap_surfs)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _classify(g: dict, cursor: Cursor, ref_pos: np.ndarray):
    """Return (iE, iN, iW, iS) indices into g['ip'] by h/v projection."""
    ip   = g['ip']
    h_ax = np.asarray(cursor.right, dtype=float)
    v_ax = np.asarray(cursor.up,    dtype=float)

    def _hv(pt):
        c = np.array(gmsh.model.getValue(0, pt, []))
        d = c - ref_pos
        return float(np.dot(d, h_ax)), float(np.dot(d, v_ax))

    hvs = [_hv(p) for p in ip]
    n   = len(ip)
    iE  = max(range(n), key=lambda i: hvs[i][0])
    iW  = min(range(n), key=lambda i: hvs[i][0])
    iN  = max(range(n), key=lambda i: hvs[i][1])
    iS  = min(range(n), key=lambda i: hvs[i][1])
    return iE, iN, iW, iS


def _arc(pts: list, arcs: list, from_pt: int, to_pt: int) -> int:
    """Signed arc tag going from_pt → to_pt in the given chain."""
    n = len(arcs)
    for k in range(n):
        if pts[k] == from_pt and pts[(k + 1) % n] == to_pt:
            return arcs[k]
        if pts[k] == to_pt and pts[(k + 1) % n] == from_pt:
            return -arcs[k]
    raise RuntimeError(
        f"No arc/line connecting {from_pt} ↔ {to_pt}  "
        f"(pts={pts}, arcs={arcs})"
    )


def _surf_by_arc(cs: CrossSection, arc_tag: int) -> int:
    """Surface in cs whose boundary contains abs(arc_tag)."""
    off = 1 if len(cs.surfaces) == cs.n_outer + 1 else 0
    tgt = abs(arc_tag)
    for i in range(cs.n_outer):
        bnd = gmsh.model.getBoundary(
            [(2, cs.surfaces[off + i])], oriented=True
        )
        if any(abs(c) == tgt for _, c in bnd):
            return cs.surfaces[off + i]
    raise RuntimeError(
        f"No surface found containing arc {tgt}  (cs.surfaces={cs.surfaces})"
    )


def _plane(curves: list[int], corners: list[int]) -> int:
    geo  = gmsh.model.occ
    mesh = gmsh.model.mesh
    ll   = geo.addCurveLoop(curves)
    s    = geo.addPlaneSurface([ll])
    geo.synchronize()
    mesh.setTransfiniteSurface(s, "Left", corners)
    mesh.setRecombine(2, s)
    return s


def _curved(curves: list[int], corners: list[int]) -> int:
    geo  = gmsh.model.occ
    mesh = gmsh.model.mesh
    ll   = geo.addCurveLoop(curves)
    s    = geo.addSurfaceFilling(ll)
    geo.synchronize()
    mesh.setTransfiniteSurface(s, "Left", corners)
    mesh.setRecombine(2, s)
    return s


def _flat(curves: list[int], corners: list[int]) -> int:
    return _plane(curves, corners)


def _vol(faces: list[int], corners: list[int]) -> int:
    geo  = gmsh.model.occ
    mesh = gmsh.model.mesh
    sl   = geo.addSurfaceLoop([abs(f) for f in faces])
    vol  = geo.addVolume([sl])
    geo.synchronize()
    mesh.setTransfiniteVolume(vol, corners)
    mesh.setRecombine(3, vol)
    return vol
