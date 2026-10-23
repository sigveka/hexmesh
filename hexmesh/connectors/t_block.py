"""
T-junction block construction.

Stage 1 — Saddle curve parameterisation
----------------------------------------
The saddle curve is the intersection of the branch pipe outer surface
(radius r, axis through origin along branch_dir) with the main pipe
outer surface (radius R, axis through origin along main_dir).

In the orthonormal frame {e1=branch_dir, e2=main_dir×branch_dir, e3=main_dir}
a point on the main pipe outer surface is:

    p(θ, t) = origin + t·e3 + R·cosθ·e1 + R·sinθ·e2

Its distance from the branch axis is √(t² + R²sin²θ).  Setting this
equal to r gives:

    t(θ) = ±√(r² − R²sin²θ),   |θ| ≤ θ_max = arcsin(r/R)

The two signs correspond to the downstream (+t) and upstream (−t) arcs.
The arcs close at θ = ±θ_max where t = 0.

Corner points of the saddle curve
----------------------------------
    tip_downstream  θ=0, t=+r  →  origin + r·e3 + R·e1
    tip_upstream    θ=0, t=−r  →  origin − r·e3 + R·e1
    side_pos        θ=+θ_max   →  origin + R·cos(θ_max)·e1 + R·sin(θ_max)·e2
    side_neg        θ=−θ_max   →  origin + R·cos(θ_max)·e1 − R·sin(θ_max)·e2

Stage 2 — Branch stub block
-----------------------------
The stub block connects the saddle curve opening (on the main pipe outer
surface) to the branch pipe inlet face (an OH circle at distance
branch_length along branch_dir).

Topology: 5 volumes — one centre block + 4 quadrant blocks — matching
the OH butterfly cross-section of the branch pipe.

The saddle "face" at the main pipe end uses:
  • 4 GMSH splines for the outer saddle arc segments (half-arcs)
  • straight lines for the inner edges and radials
  • addSurfaceFilling for each patch

Corner ordering convention (index 0..3 = top / left / bottom / right):
  outer[0]=tip_dn, outer[1]=side_neg, outer[2]=tip_up, outer[3]=side_pos
The branch OH face is built with rot=π/4 so its outer corners also land
at the cardinal positions top/left/bottom/right.

Saddle half-arc segments (each nang+1 nodes):
  arc[0]: tip_dn → side_neg  (downstream, reversed left half)
  arc[1]: side_neg → tip_up  (upstream, left half)
  arc[2]: tip_up → side_pos  (upstream, right half)
  arc[3]: side_pos → tip_dn  (downstream, reversed right half)
"""
from __future__ import annotations
import math

import numpy as np


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def saddle_curve(
    origin:     "np.ndarray | list[float]",
    main_dir:   "np.ndarray | list[float]",
    branch_dir: "np.ndarray | list[float]",
    R:          float,
    r:          float,
    n_points:   int = 21,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample points on the saddle curve.

    Parameters
    ----------
    origin : (3,) array-like
        Junction centre (cursor.position at the T-point).
    main_dir : (3,) array-like
        Unit vector along the main pipe axis (cursor.direction).
    branch_dir : (3,) array-like
        Unit vector along the branch direction (perpendicular to main_dir).
    R : float
        Main pipe outer radius.
    r : float
        Branch pipe outer radius.  Must satisfy 0 < r ≤ R.
    n_points : int
        Number of sample points per arc, including both endpoints.
        Default 21.

    Returns
    -------
    upstream_arc : ndarray, shape (n_points, 3)
        Points on the upstream half of the saddle curve (t < 0 side).
    downstream_arc : ndarray, shape (n_points, 3)
        Points on the downstream half (t > 0 side).

    Notes
    -----
    The two arcs share their endpoints at θ = ±θ_max (the ``side_pos``
    and ``side_neg`` corner points from :func:`saddle_corners`).
    """
    _validate(R, r)

    e1, e2, e3 = _frame(main_dir, branch_dir)
    origin      = np.asarray(origin, dtype=float)

    theta_max = math.asin(r / R)
    thetas    = np.linspace(-theta_max, theta_max, n_points)
    t_vals    = np.sqrt(np.maximum(r**2 - R**2 * np.sin(thetas)**2, 0.0))

    radial = (  R * np.cos(thetas)[:, None] * e1
              + R * np.sin(thetas)[:, None] * e2)

    downstream_arc = origin +  t_vals[:, None] * e3 + radial
    upstream_arc   = origin -  t_vals[:, None] * e3 + radial

    return upstream_arc, downstream_arc


def saddle_corners(
    origin:     "np.ndarray | list[float]",
    main_dir:   "np.ndarray | list[float]",
    branch_dir: "np.ndarray | list[float]",
    R:          float,
    r:          float,
) -> dict[str, np.ndarray]:
    """The four corner points of the saddle curve.

    Returns a dict with keys:

    ``tip_downstream``
        θ=0, t=+r  (downstream end of the hole, closest to branch side)
    ``tip_upstream``
        θ=0, t=−r  (upstream end of the hole)
    ``side_pos``
        θ=+θ_max, t=0  (positive e2 side of the hole)
    ``side_neg``
        θ=−θ_max, t=0  (negative e2 side of the hole)
    """
    _validate(R, r)

    e1, e2, e3 = _frame(main_dir, branch_dir)
    origin      = np.asarray(origin, dtype=float)

    theta_max  = math.asin(r / R)
    cos_tm, sin_tm = math.cos(theta_max), math.sin(theta_max)

    return {
        "tip_downstream": origin + r * e3 + R * e1,
        "tip_upstream":   origin - r * e3 + R * e1,
        "side_pos":       origin + R * cos_tm * e1 + R * sin_tm * e2,
        "side_neg":       origin + R * cos_tm * e1 - R * sin_tm * e2,
    }


# ---------------------------------------------------------------------------
# Conformality check
# ---------------------------------------------------------------------------

def saddle_conformality_check(
    r:    float,
    R:    float,
    nang: int,
) -> "tuple[int | None, bool, list[float]]":
    """Check whether (r, R, nang) satisfy the saddle conformality condition.

    For the side corners of the saddle curve (θ = ±arcsin(r/R)) to land on
    transfinite node positions of the main pipe outer arc, two conditions
    must hold simultaneously:

    1. ``nang`` must be **even** — the branch tip (θ=0°) is a node only when
       nang is even (arc is divided into nang equal segments; θ=0 is the
       midpoint node).
    2. θ_max = arcsin(r/R) must equal ``m × (90° / nang)`` for an integer m
       in the range 1 … nang/2.  (m = nang/2 places side corners at the arc
       endpoints, which are always transfinite corner nodes.)

    Parameters
    ----------
    r : float
        Branch pipe outer radius.
    R : float
        Main pipe outer radius.
    nang : int
        Angular divisions per 90° arc.

    Returns
    -------
    m : int or None
        The integer multiplier such that θ_max = m × (90°/nang), or None if
        no such integer exists.
    is_conformal : bool
        True when both conditions are satisfied.
    conforming_r_values : list of float
        All branch radii that would be conformal for the given (R, nang),
        i.e. R·sin(m × π/(2·nang)) for m = 1 … nang/2.  Empty when
        nang is odd.
    """
    theta_max  = math.asin(r / R)
    arc_step   = math.pi / 2 / nang     # 90°/nang in radians
    nang_even  = (nang % 2 == 0)

    # Conforming r values (always computed for the hint message).
    # m = nang/2 places side corners at the arc endpoints (always nodes) → valid.
    conforming_r: list[float] = []
    if nang_even:
        half = nang // 2
        for m in range(1, half + 1):
            conforming_r.append(R * math.sin(m * arc_step))

    if not nang_even:
        return None, False, conforming_r

    # Check if theta_max is an integer multiple of arc_step
    ratio = theta_max / arc_step
    m_int = round(ratio)
    half  = nang // 2
    if m_int < 1 or m_int > half:
        return None, False, conforming_r

    if abs(ratio - m_int) < 1e-6:
        return m_int, True, conforming_r

    return None, False, conforming_r


# ---------------------------------------------------------------------------
# Stage 2 — Branch stub block geometry
# ---------------------------------------------------------------------------

def build_stub_block(
    origin:           "np.ndarray | list[float]",
    main_dir:         "np.ndarray | list[float]",
    branch_dir:       "np.ndarray | list[float]",
    R:                float,
    r:                float,
    branch_length:    float,
    nang:             int   = 5,
    nrad:             int   = 4,
    n_axial:          int   = 4,
    ratio:            float = 0.6,
    lc:               "float | None" = None,
    outer_point_tags: "list[int | None] | None" = None,
    spec:             "object | None" = None,
) -> "dict":
    """Build the branch stub block in the current GMSH OCC model.

    The stub block connects the saddle curve opening on the main pipe outer
    surface to the branch pipe OH inlet face.  Five hex volumes are created
    (one centre + four quadrants), matching the OH butterfly cross-section.

    Parameters
    ----------
    origin : (3,) array-like
        Centre of the saddle curve (junction point on main pipe axis).
    main_dir : (3,) array-like
        Unit vector along the main pipe axis.
    branch_dir : (3,) array-like
        Unit vector along the branch direction (perpendicular to main_dir).
    R : float
        Main pipe outer radius.
    r : float
        Branch pipe outer radius (≤ R).
    branch_length : float
        Distance from origin to the branch face centre, along branch_dir.
        Must be > R so the branch face clears the main pipe.
    nang : int
        Angular divisions per quadrant arc on the branch face and per
        saddle half-arc.  Default 5.
    nrad : int
        Radial divisions (inner square → outer circle).  Default 4.
    n_axial : int
        Hex layers along the branch axis.  Default 4.
    ratio : float
        OH inner-square scale factor (0 < ratio < 1).  Default 0.6.
    lc : float or None
        GMSH characteristic length.  Defaults to ``r / (nang * 1.5)``.
    outer_point_tags : list of (int or None) or None
        Optional pre-existing GMSH point tags for the 4 saddle outer
        corners, in the order ``[tip_dn, side_neg, tip_up, side_pos]``
        (i.e. indices 0–3).  Pass a pre-existing tag to reuse an
        existing model point (conformality with adjacent blocks);
        pass ``None`` in a slot to create a new point as usual.
        If the entire argument is ``None`` all four corners are new.

    Returns
    -------
    dict with keys:

    ``volumes``
        List of 5 GMSH volume tags.
    ``branch_cs``
        :class:`~hexmesh.core.cross_section.CrossSection` for the branch
        face (the OH circle at the far end of the stub).
    ``saddle_surfs``
        List of 5 GMSH surface tags at the main pipe end
        ([centre, top-left, left-bottom, bottom-right, right-top]).
        When *spec* is provided, includes all layer saddle surfaces
        (5 core + 4 per shell).

    Notes
    -----
    When *spec* is provided the *r*, *nrad*, and *nang* positional
    parameters are **ignored**; the PipeSpec supplies those values.
    """
    if spec is not None:
        return _build_stub_block_ml(
            origin, main_dir, branch_dir, R, branch_length,
            n_axial, ratio, lc, outer_point_tags, spec,
        )

    import gmsh
    from ..faces.oh_circle import build_oh_circle
    from ..core.shape import CircleShape

    _validate(R, r)
    if branch_length <= R:
        raise ValueError(
            f"branch_length ({branch_length}) must be > R ({R}) so the "
            "branch face clears the main pipe outer surface."
        )

    geo  = gmsh.model.occ
    mesh = gmsh.model.mesh

    e1, e2, e3 = _frame(main_dir, branch_dir)
    origin = np.asarray(origin, dtype=float)

    if lc is None:
        lc = r / (nang * 1.5)

    theta_max = math.asin(r / R)
    cos_tm    = math.cos(theta_max)
    sin_tm    = math.sin(theta_max)

    branch_ctr = origin + branch_length * e1
    saddle_ctr = origin + R * e1

    # Corner ordering: index i = 0/1/2/3 = top/left/bottom/right
    # Outer saddle corners (on main pipe outer surface):
    m_outer = [
        origin + r * e3 + R * e1,                           # [0] top    = tip_dn
        origin + R * cos_tm * e1 - R * sin_tm * e2,         # [1] left   = side_neg
        origin - r * e3 + R * e1,                           # [2] bottom = tip_up
        origin + R * cos_tm * e1 + R * sin_tm * e2,         # [3] right  = side_pos
    ]
    # Inner saddle corners (linearly interpolated toward centre):
    # The side corners (i=1 and i=3) can fall slightly inside the main pipe
    # outer cylinder (r < R) because the saddle_ctr→m_outer vector has a
    # transverse component.  Project each inner corner back to r ≥ R so the
    # stub block never volumetrically overlaps the main pipe.
    m_inner = []
    for c in m_outer:
        mi = saddle_ctr + ratio * (c - saddle_ctr)
        # Component perpendicular to main axis (in e1-e2 plane)
        mi_from_origin = mi - origin
        mi_axial   = float(np.dot(mi_from_origin, e3)) * e3
        mi_perp    = mi_from_origin - mi_axial
        dist_perp  = float(np.linalg.norm(mi_perp))
        if dist_perp > 0 and dist_perp < R:
            mi = origin + mi_axial + (R / dist_perp) * mi_perp
        m_inner.append(mi)

    # ------------------------------------------------------------------ #
    # Build branch OH face at branch_ctr                                  #
    # rot=π/4 aligns outer corners at cardinal positions (top/left/…)     #
    # h_axis=e2, v_axis=e3 so top = +e3 (downstream), right = +e2        #
    # ------------------------------------------------------------------ #
    cx, cy, cz = float(branch_ctr[0]), float(branch_ctr[1]), float(branch_ctr[2])
    branch_cs = build_oh_circle(
        cx=cx, cy=cy, cz=cz,
        shape=CircleShape(radius=r, nang=nang),
        h_axis=e2, v_axis=e3,
        lc=lc,
        nrad=nrad,
        rot=math.pi / 4,
    )
    geo.synchronize()

    # Extract branch face tags (with rot=π/4: NE/NW/SW/SE → top/left/bottom/right)
    b_op = branch_cs.outer_points    # [top, left, bottom, right] outer point tags
    b_ip = branch_cs.inner_points    # [top, left, bottom, right] inner point tags
    b_cp = branch_cs.center          # centre point tag
    b_oc = branch_cs.outer_curves    # [top→left, left→bottom, bottom→right, right→top] (unsigned)
    b_ic = branch_cs.inner_curves    # same ordering, signed
    b_rc = branch_cs.radial_curves   # [top, left, bottom, right] inner→outer (unsigned)

    # ------------------------------------------------------------------ #
    # Create saddle-end GMSH points                                       #
    # ------------------------------------------------------------------ #
    def _pt(xyz: "np.ndarray") -> int:
        return geo.addPoint(float(xyz[0]), float(xyz[1]), float(xyz[2]), lc)

    pm_outer = []
    for i, c in enumerate(m_outer):
        if outer_point_tags is not None and outer_point_tags[i] is not None:
            pm_outer.append(outer_point_tags[i])
        else:
            pm_outer.append(_pt(c))
    pm_inner  = [_pt(c) for c in m_inner]
    pm_center = _pt(saddle_ctr)

    # ------------------------------------------------------------------ #
    # Saddle arc splines (one per quadrant boundary)                      #
    # nang+1 nodes per spline; interior points created as GMSH points     #
    # ------------------------------------------------------------------ #
    n_arc   = 2 * nang + 1   # total points for full saddle arc
    up_arc, dn_arc = saddle_curve(origin, main_dir, branch_dir, R, r, n_points=n_arc)
    mid = nang  # index of tip point in full arc (θ=0)

    # Four half-arc segments, each shape (nang+1, 3):
    seg_pts = [
        dn_arc[mid::-1],       # [0] top→left   (dn left  half, reversed)
        up_arc[:mid + 1],      # [1] left→bottom (up left  half)
        up_arc[mid:],          # [2] bottom→right (up right half)
        dn_arc[-1:mid - 1:-1], # [3] right→top  (dn right half, reversed)
    ]

    saddle_arcs: list[int] = []
    for i, seg in enumerate(seg_pts):
        start = pm_outer[i]
        end   = pm_outer[(i + 1) % 4]
        # Create interior points (exclude endpoints which already exist)
        inner_pts = [_pt(seg[k]) for k in range(1, len(seg) - 1)]
        arc = geo.addSpline([start] + inner_pts + [end])
        saddle_arcs.append(arc)

    # ------------------------------------------------------------------ #
    # Main-end inner lines and radials (straight lines for simplicity)    #
    # ------------------------------------------------------------------ #
    # main_inner_lines[i]: pm_inner[i] → pm_inner[(i+1)%4]
    main_inner_lines = [
        geo.addLine(pm_inner[i], pm_inner[(i + 1) % 4]) for i in range(4)
    ]
    # main_radials[i]: pm_inner[i] → pm_outer[i]
    main_radials = [
        geo.addLine(pm_inner[i], pm_outer[i]) for i in range(4)
    ]

    # ------------------------------------------------------------------ #
    # Spine lines (saddle end → branch end)                               #
    # ------------------------------------------------------------------ #
    spines_outer  = [geo.addLine(pm_outer[i],  b_op[i]) for i in range(4)]
    spines_inner  = [geo.addLine(pm_inner[i],  b_ip[i]) for i in range(4)]
    spine_center  = geo.addLine(pm_center, b_cp)
    geo.synchronize()

    # ------------------------------------------------------------------ #
    # Saddle-end surfaces (5 patches at main pipe end)                    #
    # ------------------------------------------------------------------ #
    # Centre patch: inner[0]→inner[1]→inner[2]→inner[3]→inner[0]
    ll = geo.addCurveLoop([
        main_inner_lines[0], main_inner_lines[1],
        main_inner_lines[2], main_inner_lines[3],
    ])
    surf_m0 = geo.addSurfaceFilling(ll)

    # Quadrant patch i: saddle_arc[i] + radial_j reversed + inner_line_i reversed + radial_i
    surf_m_quad: list[int] = []
    for i in range(4):
        j = (i + 1) % 4
        ll = geo.addCurveLoop([
            saddle_arcs[i],       # outer[i] → outer[j]
            -main_radials[j],     # outer[j] → inner[j]
            -main_inner_lines[i], # inner[j] → inner[i]
            main_radials[i],      # inner[i] → outer[i]
        ])
        surf_m_quad.append(geo.addSurfaceFilling(ll))

    geo.synchronize()

    # ------------------------------------------------------------------ #
    # Side surfaces                                                        #
    # ------------------------------------------------------------------ #
    # Outer arc sides: saddle_arcs[i] ↔ b_oc[i]
    oss: list[int] = []
    for i in range(4):
        j = (i + 1) % 4
        ll = geo.addCurveLoop([
            saddle_arcs[i],
            spines_outer[j],
            -b_oc[i],
            -spines_outer[i],
        ])
        oss.append(geo.addSurfaceFilling(ll))

    # Inner arc sides: main_inner_lines[i] ↔ b_ic[i]
    iss: list[int] = []
    for i in range(4):
        j = (i + 1) % 4
        ll = geo.addCurveLoop([
            main_inner_lines[i],
            spines_inner[j],
            -b_ic[i],
            -spines_inner[i],
        ])
        iss.append(geo.addSurfaceFilling(ll))

    # Radial sides: main_radials[i] ↔ b_rc[i]
    rss: list[int] = []
    for i in range(4):
        ll = geo.addCurveLoop([
            main_radials[i],
            spines_outer[i],
            -b_rc[i],
            -spines_inner[i],
        ])
        rss.append(geo.addSurfaceFilling(ll))

    # Centre-spine side: 4 surfaces connecting centre spine to inner sides
    # These share edges with iss[] so we don't need separate surfaces —
    # the centre volume uses iss[0..3] as its lateral faces directly.

    geo.synchronize()

    # ------------------------------------------------------------------ #
    # Volumes                                                              #
    # ------------------------------------------------------------------ #
    vols: list[int] = []

    # Centre block
    sloop = geo.addSurfaceLoop([
        surf_m0, branch_cs.surfaces[0],
        iss[0], iss[1], iss[2], iss[3],
    ])
    vols.append(geo.addVolume([sloop]))

    # Four quadrant blocks
    for i in range(4):
        j = (i + 1) % 4
        sloop = geo.addSurfaceLoop([
            surf_m_quad[i],         # saddle end face
            branch_cs.surfaces[1 + i],  # branch end face
            oss[i],                 # outer arc side
            iss[i],                 # inner arc side (shared with centre)
            rss[i],                 # radial side at corner i
            rss[j],                 # radial side at corner j
        ])
        vols.append(geo.addVolume([sloop]))

    geo.synchronize()

    # ------------------------------------------------------------------ #
    # Transfinite mesh constraints                                         #
    # ------------------------------------------------------------------ #
    # Saddle arc splines: nang+1 nodes
    for arc in saddle_arcs:
        mesh.setTransfiniteCurve(arc, nang + 1)

    # Branch outer arcs: nang+1 nodes (may be already set by build_oh_circle)
    for arc in b_oc:
        mesh.setTransfiniteCurve(abs(arc), nang + 1)

    # Branch inner arcs: nang+1 nodes
    for arc in b_ic:
        mesh.setTransfiniteCurve(abs(arc), nang + 1)

    # Main inner lines: nang+1 nodes
    for L in main_inner_lines:
        mesh.setTransfiniteCurve(L, nang + 1)

    # Branch radials and main radials: nrad+1 nodes
    for L in b_rc:
        mesh.setTransfiniteCurve(abs(L), nrad + 1)
    for L in main_radials:
        mesh.setTransfiniteCurve(L, nrad + 1)

    # All spines: n_axial+1 nodes
    for L in spines_outer + spines_inner + [spine_center]:
        mesh.setTransfiniteCurve(L, n_axial + 1)

    # Transfinite surfaces
    all_surfs = (
        [surf_m0] + surf_m_quad
        + list(branch_cs.surfaces)
        + oss + iss + rss
    )
    for s in all_surfs:
        mesh.setTransfiniteSurface(s)
        mesh.setRecombine(2, s)

    # Transfinite volumes + hex recombination
    for v in vols:
        mesh.setTransfiniteVolume(v)
        mesh.setRecombine(3, v)

    all_deferred_curves = (
        [(arc, nang + 1) for arc in saddle_arcs]
        + [(abs(arc), nang + 1) for arc in b_oc]
        + [(abs(arc), nang + 1) for arc in b_ic]
        + [(L, nang + 1) for L in main_inner_lines]
        + [(abs(L), nrad + 1) for L in b_rc + main_radials]
        + [(L, n_axial + 1) for L in spines_outer + spines_inner + [spine_center]]
    )
    all_deferred_surfaces = (
        [surf_m0] + surf_m_quad
        + list(branch_cs.surfaces)
        + oss + iss + rss
    )

    return {
        "volumes":             vols,
        "branch_cs":           branch_cs,
        "saddle_surfs":        [surf_m0] + surf_m_quad,
        "saddle_arcs":         saddle_arcs,     # 4 spline tags (outermost layer)
        "saddle_outer_points": pm_outer,        # [tip_dn, side_neg, tip_up, side_pos]
        "deferred_curves":     all_deferred_curves,
        "deferred_surfaces":   all_deferred_surfaces,
    }


# ---------------------------------------------------------------------------
# Multi-layer stub block (internal)
# ---------------------------------------------------------------------------

def _build_stub_block_ml(
    origin, main_dir, branch_dir, R, branch_length,
    n_axial, ratio, lc, outer_point_tags, spec
):
    """Multi-layer stub block — called when spec is not None."""
    import gmsh
    from ..faces.oh_circle import build_oh_circle
    from ..faces.annulus import build_annulus
    from ..core.cross_section import LayeredCrossSection
    from ..core.shape import CircleShape
    from ..core.spec import LayerSpec

    geo  = gmsh.model.occ
    mesh = gmsh.model.mesh

    # ------------------------------------------------------------------
    # Validate and extract spec contents
    # ------------------------------------------------------------------
    if spec._core is None:
        raise ValueError("PipeSpec must have a .core() layer set before calling build_stub_block.")
    core_name, core_shape = spec._core
    if not isinstance(core_shape, CircleShape):
        raise ValueError(
            "build_stub_block with spec= requires a circular-core PipeSpec "
            "(PipeSpec(nang=…).core(…, radius=…))."
        )

    shell_layers = []
    r_layers = [core_shape.radius]
    for shell in spec.shells:
        if not isinstance(shell, LayerSpec):
            raise ValueError(
                "build_stub_block with spec= does not support SquareShellSpec shells."
            )
        shell_layers.append(shell)
        r_layers.append(r_layers[-1] + shell.dR)

    r_core  = r_layers[0]
    r_outer = r_layers[-1]
    nang    = spec._nang
    if nang is None:
        raise ValueError("PipeSpec must have nang set (e.g. PipeSpec(nang=5)).")

    _validate(R, r_outer)
    if branch_length <= R:
        raise ValueError(
            f"branch_length ({branch_length}) must be > R ({R}) so the "
            "branch face clears the main pipe outer surface."
        )

    if lc is None:
        lc = r_core / (nang * 1.5)

    e1, e2, e3 = _frame(main_dir, branch_dir)
    origin     = np.asarray(origin, dtype=float)
    branch_ctr = origin + branch_length * e1
    saddle_ctr = origin + R * e1

    cx = float(branch_ctr[0])
    cy = float(branch_ctr[1])
    cz = float(branch_ctr[2])

    # ------------------------------------------------------------------
    # Build all branch face layers (core OH + annular shells)
    # ------------------------------------------------------------------
    branch_core_cs = build_oh_circle(
        cx=cx, cy=cy, cz=cz,
        shape=CircleShape(radius=r_core, nang=nang),
        h_axis=e2, v_axis=e3,
        lc=lc,
        nrad=spec._core_nrad,
        mprg=spec._core_mprg,
        rot=math.pi / 4,
    )
    branch_layers = [(core_name, branch_core_cs)]
    prev_cs = branch_core_cs
    for shell in shell_layers:
        shell_cs = build_annulus(
            inner=prev_cs,
            dR=shell.dR,
            lc=lc,
            nrad=shell.nrad,
            mprg=shell.mprg,
            mbmp=spec._mbmp,
            rot=math.pi / 4,
        )
        branch_layers.append((shell.name, shell_cs))
        prev_cs = shell_cs

    geo.synchronize()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _pt(xyz):
        return geo.addPoint(float(xyz[0]), float(xyz[1]), float(xyz[2]), lc)

    n_arc = 2 * nang + 1
    mid   = nang  # index of tip (θ=0) in full saddle arc

    # ------------------------------------------------------------------
    # Core layer: 5 OH volumes at r_core
    # ------------------------------------------------------------------
    theta_max_c = math.asin(r_core / R)
    cos_tc      = math.cos(theta_max_c)
    sin_tc      = math.sin(theta_max_c)

    m_outer_core = [
        origin + r_core * e3 + R * e1,                     # [0] tip_dn
        origin + R * cos_tc * e1 - R * sin_tc * e2,        # [1] side_neg
        origin - r_core * e3 + R * e1,                     # [2] tip_up
        origin + R * cos_tc * e1 + R * sin_tc * e2,        # [3] side_pos
    ]
    # Project side corners to r ≥ R (same fix as single-layer build_stub_block)
    m_inner_core = []
    for c in m_outer_core:
        mi = saddle_ctr + ratio * (c - saddle_ctr)
        mi_from_origin = mi - origin
        mi_axial  = float(np.dot(mi_from_origin, e3)) * e3
        mi_perp   = mi_from_origin - mi_axial
        dist_perp = float(np.linalg.norm(mi_perp))
        if dist_perp > 0 and dist_perp < R:
            mi = origin + mi_axial + (R / dist_perp) * mi_perp
        m_inner_core.append(mi)

    pm_outer_core = [_pt(c) for c in m_outer_core]
    pm_inner_core = [_pt(c) for c in m_inner_core]
    pm_center     = _pt(saddle_ctr)

    up_arc, dn_arc = saddle_curve(origin, main_dir, branch_dir, R, r_core, n_points=n_arc)
    seg_pts_core = [
        dn_arc[mid::-1],
        up_arc[:mid + 1],
        up_arc[mid:],
        dn_arc[-1:mid - 1:-1],
    ]
    saddle_arcs_core = []
    for i, seg in enumerate(seg_pts_core):
        inner_pts = [_pt(seg[k]) for k in range(1, len(seg) - 1)]
        arc = geo.addSpline(
            [pm_outer_core[i]] + inner_pts + [pm_outer_core[(i + 1) % 4]]
        )
        saddle_arcs_core.append(arc)

    main_inner_lines = [
        geo.addLine(pm_inner_core[i], pm_inner_core[(i + 1) % 4]) for i in range(4)
    ]
    main_radials = [
        geo.addLine(pm_inner_core[i], pm_outer_core[i]) for i in range(4)
    ]

    b_op = branch_core_cs.outer_points
    b_ip = branch_core_cs.inner_points
    b_cp = branch_core_cs.center
    b_oc = branch_core_cs.outer_curves
    b_ic = branch_core_cs.inner_curves
    b_rc = branch_core_cs.radial_curves

    spines_outer_core = [geo.addLine(pm_outer_core[i], b_op[i]) for i in range(4)]
    spines_inner_core = [geo.addLine(pm_inner_core[i], b_ip[i]) for i in range(4)]
    spine_center      = geo.addLine(pm_center, b_cp)

    geo.synchronize()

    ll       = geo.addCurveLoop(main_inner_lines)
    surf_m0  = geo.addSurfaceFilling(ll)
    surf_m_quad = []
    for i in range(4):
        j  = (i + 1) % 4
        ll = geo.addCurveLoop([
            saddle_arcs_core[i], -main_radials[j],
            -main_inner_lines[i], main_radials[i],
        ])
        surf_m_quad.append(geo.addSurfaceFilling(ll))

    geo.synchronize()

    oss_core = []
    for i in range(4):
        j  = (i + 1) % 4
        ll = geo.addCurveLoop([
            saddle_arcs_core[i], spines_outer_core[j],
            -b_oc[i], -spines_outer_core[i],
        ])
        oss_core.append(geo.addSurfaceFilling(ll))

    iss_core = []
    for i in range(4):
        j  = (i + 1) % 4
        ll = geo.addCurveLoop([
            main_inner_lines[i], spines_inner_core[j],
            -b_ic[i], -spines_inner_core[i],
        ])
        iss_core.append(geo.addSurfaceFilling(ll))

    rss_core = []
    for i in range(4):
        ll = geo.addCurveLoop([
            main_radials[i], spines_outer_core[i],
            -b_rc[i], -spines_inner_core[i],
        ])
        rss_core.append(geo.addSurfaceFilling(ll))

    geo.synchronize()

    all_vols = []
    sloop = geo.addSurfaceLoop(
        [surf_m0, branch_core_cs.surfaces[0]] + iss_core
    )
    all_vols.append(geo.addVolume([sloop]))
    for i in range(4):
        j     = (i + 1) % 4
        sloop = geo.addSurfaceLoop([
            surf_m_quad[i], branch_core_cs.surfaces[1 + i],
            oss_core[i], iss_core[i], rss_core[i], rss_core[j],
        ])
        all_vols.append(geo.addVolume([sloop]))

    geo.synchronize()

    all_saddle_surfs = [surf_m0] + surf_m_quad

    # Collect transfinite constraints from core layer
    tf_curves = []   # list of (tag, n_nodes)
    tf_surfs  = []   # list of surf tags (excluding branch faces set by builders)

    for arc in saddle_arcs_core:
        tf_curves.append((arc, nang + 1))
    for arc in b_oc:
        tf_curves.append((abs(arc), nang + 1))
    for arc in b_ic:
        tf_curves.append((abs(arc), nang + 1))
    for L in main_inner_lines:
        tf_curves.append((L, nang + 1))
    for L in main_radials:
        tf_curves.append((L, spec._core_nrad + 1))
    for L in b_rc:
        tf_curves.append((abs(L), spec._core_nrad + 1))
    for L in spines_outer_core + spines_inner_core + [spine_center]:
        tf_curves.append((L, n_axial + 1))

    tf_surfs.extend([surf_m0] + surf_m_quad)
    tf_surfs.extend(list(branch_core_cs.surfaces))
    tf_surfs.extend(oss_core + iss_core + rss_core)

    # ------------------------------------------------------------------
    # Shell layers: 4 annular volumes per shell
    # ------------------------------------------------------------------
    oss_prev         = oss_core
    pm_outer_prev    = pm_outer_core
    saddle_arcs_prev = saddle_arcs_core
    spines_prev      = spines_outer_core

    for shell_idx, shell in enumerate(shell_layers):
        is_outermost   = (shell_idx == len(shell_layers) - 1)
        r_next         = r_layers[shell_idx + 1]
        branch_shell_cs = branch_layers[shell_idx + 1][1]

        theta_max_n = math.asin(r_next / R)
        cos_tn      = math.cos(theta_max_n)
        sin_tn      = math.sin(theta_max_n)

        m_outer_next = [
            origin + r_next * e3 + R * e1,
            origin + R * cos_tn * e1 - R * sin_tn * e2,
            origin - r_next * e3 + R * e1,
            origin + R * cos_tn * e1 + R * sin_tn * e2,
        ]

        apply_tags   = outer_point_tags if is_outermost else None
        pm_outer_next = []
        for q, c in enumerate(m_outer_next):
            if apply_tags is not None and apply_tags[q] is not None:
                pm_outer_next.append(apply_tags[q])
            else:
                pm_outer_next.append(_pt(c))

        # Outer saddle arcs at r_next
        up_n, dn_n = saddle_curve(origin, main_dir, branch_dir, R, r_next, n_points=n_arc)
        seg_pts_next = [
            dn_n[mid::-1],
            up_n[:mid + 1],
            up_n[mid:],
            dn_n[-1:mid - 1:-1],
        ]
        saddle_arcs_next = []
        for q, seg in enumerate(seg_pts_next):
            inner_pts = [_pt(seg[k]) for k in range(1, len(seg) - 1)]
            arc = geo.addSpline(
                [pm_outer_next[q]] + inner_pts + [pm_outer_next[(q + 1) % 4]]
            )
            saddle_arcs_next.append(arc)

        # Saddle radials connecting previous to next layer corners
        saddle_radials = [
            geo.addLine(pm_outer_prev[q], pm_outer_next[q]) for q in range(4)
        ]

        b_op_sh = branch_shell_cs.outer_points
        b_oc_sh = branch_shell_cs.outer_curves
        b_rc_sh = branch_shell_cs.radial_curves

        spines_outer_next = [
            geo.addLine(pm_outer_next[q], b_op_sh[q]) for q in range(4)
        ]

        geo.synchronize()

        # Annular saddle surfaces
        shell_saddle_surfs = []
        for q in range(4):
            j  = (q + 1) % 4
            ll = geo.addCurveLoop([
                saddle_arcs_next[q],
                -saddle_radials[j],
                -saddle_arcs_prev[q],
                saddle_radials[q],
            ])
            shell_saddle_surfs.append(geo.addSurfaceFilling(ll))

        # Outer arc laterals
        outer_oss = []
        for q in range(4):
            j  = (q + 1) % 4
            ll = geo.addCurveLoop([
                saddle_arcs_next[q],
                spines_outer_next[j],
                -b_oc_sh[q],
                -spines_outer_next[q],
            ])
            outer_oss.append(geo.addSurfaceFilling(ll))

        # Radial laterals
        rss_shell = []
        for q in range(4):
            ll = geo.addCurveLoop([
                saddle_radials[q],
                spines_outer_next[q],
                -b_rc_sh[q],
                -spines_prev[q],
            ])
            rss_shell.append(geo.addSurfaceFilling(ll))

        geo.synchronize()

        # 4 annular volumes
        for q in range(4):
            j     = (q + 1) % 4
            sloop = geo.addSurfaceLoop([
                shell_saddle_surfs[q],
                branch_shell_cs.surfaces[q],
                outer_oss[q],
                oss_prev[q],
                rss_shell[q],
                rss_shell[j],
            ])
            all_vols.append(geo.addVolume([sloop]))

        geo.synchronize()

        all_saddle_surfs.extend(shell_saddle_surfs)

        # Transfinite constraints for this shell
        for arc in saddle_arcs_next:
            tf_curves.append((arc, nang + 1))
        for L in saddle_radials:
            tf_curves.append((L, shell.nrad + 1))
        for L in spines_outer_next:
            tf_curves.append((L, n_axial + 1))
        for arc in b_oc_sh:
            tf_curves.append((abs(arc), nang + 1))
        for L in b_rc_sh:
            tf_curves.append((abs(L), shell.nrad + 1))

        tf_surfs.extend(shell_saddle_surfs)
        tf_surfs.extend(outer_oss)
        tf_surfs.extend(rss_shell)
        tf_surfs.extend(list(branch_shell_cs.surfaces))

        # Advance to next shell
        oss_prev         = outer_oss
        pm_outer_prev    = pm_outer_next
        saddle_arcs_prev = saddle_arcs_next
        spines_prev      = spines_outer_next

    # ------------------------------------------------------------------
    # Apply transfinite constraints
    # ------------------------------------------------------------------
    for tag, n in tf_curves:
        mesh.setTransfiniteCurve(tag, n)

    for s in tf_surfs:
        mesh.setTransfiniteSurface(s)
        mesh.setRecombine(2, s)

    for v in all_vols:
        mesh.setTransfiniteVolume(v)
        mesh.setRecombine(3, v)

    branch_lcs = LayeredCrossSection(layers=branch_layers)
    return {
        "volumes":             all_vols,
        "branch_lcs":          branch_lcs,
        "branch_cs":           branch_core_cs,
        "saddle_surfs":        all_saddle_surfs,
        "saddle_arcs":         saddle_arcs_prev,   # 4 spline tags (outermost layer)
        "saddle_outer_points": pm_outer_prev,      # [tip_dn, side_neg, tip_up, side_pos]
        "deferred_curves":     tf_curves,
        "deferred_surfaces":   tf_surfs,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _frame(
    main_dir:   "np.ndarray | list[float]",
    branch_dir: "np.ndarray | list[float]",
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return orthonormal (e1, e2, e3) where e1=branch, e3=main."""
    e1 = np.asarray(branch_dir, dtype=float)
    e3 = np.asarray(main_dir,   dtype=float)
    e1 = e1 / np.linalg.norm(e1)
    e3 = e3 / np.linalg.norm(e3)
    e2 = np.cross(e3, e1)
    norm_e2 = np.linalg.norm(e2)
    if norm_e2 < 1e-10:
        raise ValueError(
            "main_dir and branch_dir are parallel — branch must be "
            "perpendicular to the main pipe axis."
        )
    e2 = e2 / norm_e2
    return e1, e2, e3


def _validate(R: float, r: float) -> None:
    if R <= 0:
        raise ValueError(f"Main pipe radius R must be positive, got {R!r}")
    if r <= 0:
        raise ValueError(f"Branch pipe radius r must be positive, got {r!r}")
    if r > R:
        raise ValueError(
            f"Branch radius r={r} exceeds main pipe outer radius R={R}. "
            "Equal-diameter T-junctions are not yet supported by the "
            "side-tap approach."
        )
