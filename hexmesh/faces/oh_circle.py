"""
OH (butterfly) circle cross-section builders.

Two variants are provided:

build_oh_circle  — 5-patch OH (n_outer=4)
------------------------------------------
Topology (5 patches, viewed from the extrusion direction):

            NW ──── NE
           /  ╲  N  /  ╲
          /  W  ╲  /  E  ╲
        SW ───── c ─────  SE
          ╲  W  /  ╲  E  /
           ╲  S  ╲ /  S /
            SW ──── SE

Outer circle: 4 quadrant arcs (90° each), corners at NE/NW/SW/SE.
Output: outer_points=[NE,NW,SW,SE], outer_curves=[NE→NW, NW→SW, SW→SE, SE→NE]

build_oh_circle8 — 9-patch OH (n_outer=8)
------------------------------------------
Topology (9 patches, viewed from the extrusion direction):

        NW ── N ── NE
       / ╲   |   / ╲
      /   ╲  |  /   ╲
    W ─────  c  ───── E
      ╲   /  |  ╲   /
       ╲ /   |   ╲ /
        SW ── S ── SE

Outer circle: 8 half-quadrant arcs (45° each), corners at NE/N/NW/W/SW/S/SE/E.
Inner boundary: 8 arcs (45° each), same angular positions.
1 centre patch (bounded by all 8 inner arcs, transfinite corners at NE/NW/SW/SE).
8 outer ring patches (each bounded by 1 outer arc + 2 radials + 1 inner arc).
Output: outer_points=[NE,N,NW,W,SW,S,SE,E], outer_curves=[NE→N, N→NW, …, E→NE]

The N/W/S/E corners (at 0°/90°/180°/270° from h_axis) are structural in n_outer=8
but only arc-centre helpers in n_outer=4.  This makes them available as shared OCC
boundary nodes for T-junction tips (0°/180°) and Y-junction split planes (90°/270°).

Constraint: nang must be even for n_outer=8 (each 45° arc gets nang//2 divisions).
"""

from __future__ import annotations
import math

import gmsh
import numpy as np

from ..core.cross_section import CrossSection, BoundaryType
from ..core.shape import CircleShape
from ._gmsh_helpers import (
    add_point, add_arc, add_conic_arc, add_line, add_line_loop, add_surface,
    stretched,
    set_transfinite_line, set_transfinite_line_bump,
    set_transfinite_surface, set_recombine_surface,
)


def build_oh_circle(
    cx:     float,
    cy:     float,
    cz:     float,
    shape:  CircleShape,
    h_axis: np.ndarray,
    v_axis: np.ndarray,
    lc:     float,
    nrad:   int,
    mprg:   float = 1.0,
    mbmp:   float = 1.0,
    ratio:  float = 0.6,
    rot:    float = 0.0,
    stretch: tuple | None = None,
) -> CrossSection:
    """Build a 5-patch OH-circle cross-section in GMSH.

    Parameters
    ----------
    cx, cy, cz : float
        Pipe-axis centre coordinates.
    shape : CircleShape
        Carries ``radius`` and ``nang`` (divisions per quadrant arc).
    h_axis : ndarray, shape (3,)
        Unit vector for the "horizontal" in-plane direction (cursor.right).
    v_axis : ndarray, shape (3,)
        Unit vector for the "vertical"  in-plane direction (cursor.up).
    lc : float
        GMSH characteristic mesh length.
    nrad : int
        Transfinite node layers on radial lines (inner square → outer circle).
    mprg : float
        Radial progression factor.
    mbmp : float
        Angular bump factor for quadrant arcs.
    ratio : float
        Inner-square scale factor relative to the outer corner radius
        (default 0.6, same as the .geo reference implementation).
    rot : float
        Rotation offset added to all corner angles (radians).
        Use ``rot = -π/4`` to align patch boundaries with the horizontal
        axis for half-buried pipes.
    stretch : (ndarray, float), optional
        ``(b, s)``: scale the face by ``s >= 1`` along the in-plane unit
        vector ``b`` about the centre.  Circles become ellipses; used for
        the oblique cut face of a miter joint.

    Returns
    -------
    CrossSection
        Contains the 5 surface tags and the outer boundary entities
        (outer_points, outer_curves) for the stacking protocol.
    """
    r = shape.radius

    # ------------------------------------------------------------------ #
    # Corner angles for outer circle and inner square                     #
    # ------------------------------------------------------------------ #
    #   Outer (o1..o4): NE / NW / SW / SE on the outer circle
    #   Inner (i1..i4): at  ratio * r, axes at 45° to the outer corners
    #   Square (s1..s4): at ratio * r, aligned with the cardinal axes
    #     (used as arc centres for the inner circle arcs)
    # ------------------------------------------------------------------ #

    angles_o = [math.pi / 4 + rot * i_pad
                for i_pad in [1, 1, 1, 1]]  # overridden below
    angles_o = [math.pi / 4 + rot,
                3 * math.pi / 4 + rot,
                5 * math.pi / 4 + rot,
                7 * math.pi / 4 + rot]

    angles_s = [0.0 + rot,
                math.pi / 2 + rot,
                math.pi + rot,
                3 * math.pi / 2 + rot]

    def _pt2(angle: float, radius: float):
        """Return (u, v) offsets in the cross-section plane."""
        return math.cos(angle) * radius, math.sin(angle) * radius

    _centre = np.array([cx, cy, cz])
    _h = np.asarray(h_axis, dtype=float)
    _v = np.asarray(v_axis, dtype=float)

    def _coords_from_uv(u: float, v: float):
        """Map in-plane (u, v) offsets to 3-D (x, y, z) via cursor frame."""
        p = stretched(_centre + u * _h + v * _v, _centre, stretch)
        return float(p[0]), float(p[1]), float(p[2])

    # ------------------------------------------------------------------ #
    # Points                                                              #
    # ------------------------------------------------------------------ #
    center = add_point(cx, cy, cz, lc)

    # Outer circle corners (o1=NE, o2=NW, o3=SW, o4=SE)
    o_pts = []
    for ang in angles_o:
        u, v = _pt2(ang, r)
        o_pts.append(add_point(*_coords_from_uv(u, v), lc))
    o1, o2, o3, o4 = o_pts

    # Inner square corners (i1=NE, i2=NW, i3=SW, i4=SE)
    i_pts = []
    for ang in angles_o:
        u, v = _pt2(ang, ratio * r)
        i_pts.append(add_point(*_coords_from_uv(u, v), lc))
    i1, i2, i3, i4 = i_pts

    # Square arc centres (s1=E, s2=N, s3=W, s4=S)
    s_pts = []
    for ang in angles_s:
        u, v = _pt2(ang, ratio * r)
        s_pts.append(add_point(*_coords_from_uv(u, v), lc))
    s1, s2, s3, s4 = s_pts
    s_xyz = [_coords_from_uv(*_pt2(ang, ratio * r)) for ang in angles_s]

    def arc(start, centre, end, centre_xyz):
        return add_conic_arc(start, centre, end, centre_xyz, stretch)

    # ------------------------------------------------------------------ #
    # Curves                                                              #
    # ------------------------------------------------------------------ #
    # Outer arcs (CCW viewed from extrusion direction)
    c_xyz = (cx, cy, cz)
    a1 = arc(o1, center, o2, c_xyz)   # NE→NW
    a3 = arc(o2, center, o3, c_xyz)   # NW→SW
    a5 = arc(o3, center, o4, c_xyz)   # SW→SE
    a7 = arc(o4, center, o1, c_xyz)   # SE→NE

    # Radial lines: inner corner → outer corner
    r1 = add_line(i2, o2)   # NW
    r2 = add_line(i1, o1)   # NE
    r3 = add_line(i3, o3)   # SW
    r4 = add_line(i4, o4)   # SE

    # Inner arcs (for centre patch boundary and quadrant inner edges)
    a2 = arc(i2, s4, i1, s_xyz[3])   # NW→NE  (top    inner, centre s4=S)
    a4 = arc(i3, s1, i2, s_xyz[0])   # SW→NW  (left   inner, centre s1=E)
    a6 = arc(i4, s2, i3, s_xyz[1])   # SE→SW  (bottom inner, centre s2=N)
    a8 = arc(i1, s3, i4, s_xyz[2])   # NE→SE  (right  inner, centre s3=W)

    # ------------------------------------------------------------------ #
    # Surfaces                                                            #
    # ------------------------------------------------------------------ #
    ll0 = add_line_loop([-a2, -a4, -a6, -a8])    # centre patch (CW inner arcs)
    ll1 = add_line_loop([a1, -r1, a2, r2])        # NE quadrant
    ll2 = add_line_loop([a3, -r3, a4, r1])        # NW quadrant
    ll3 = add_line_loop([a5, -r4, a6, r3])        # SW quadrant
    ll4 = add_line_loop([a7, -r2, a8, r4])        # SE quadrant

    s0 = add_surface(ll0)
    s1 = add_surface(ll1)
    s2 = add_surface(ll2)
    s3 = add_surface(ll3)
    s4 = add_surface(ll4)

    surfaces = [s0, s1, s2, s3, s4]

    # ------------------------------------------------------------------ #
    # Mesh constraints                                                    #
    # ------------------------------------------------------------------ #
    set_transfinite_line([r1, r2, r3, r4],       nrad, mprg)
    set_transfinite_line_bump([a1, a2, a3, a4,
                               a5, a6, a7, a8], shape.nang, mbmp)
    set_transfinite_surface(surfaces)
    set_recombine_surface(surfaces)

    # ------------------------------------------------------------------ #
    # Stacking protocol exports                                           #
    # ------------------------------------------------------------------ #
    return CrossSection(
        surfaces      = surfaces,
        center        = center,
        outer_points  = [o1, o2, o3, o4],
        outer_curves  = [a1, a3, a5, a7],
        shape         = shape,
        boundary_type = BoundaryType.CIRCULAR,
        h_axis        = _h,
        v_axis        = _v,
        cx=cx, cy=cy, cz=cz,
        # Taper support: inner square corners, inner arcs (signed NE→NW…), radials
        inner_points  = [i1, i2, i3, i4],
        inner_curves  = [-a2, -a4, -a6, -a8],   # NE→NW, NW→SW, SW→SE, SE→NE
        radial_curves = [r2, r1, r3, r4],        # NE, NW, SW, SE (inner→outer)
        nrad          = nrad,
        lc            = lc,
        corner_angles = angles_o,
    )


def build_oh_circle8(
    cx:     float,
    cy:     float,
    cz:     float,
    shape:  "CircleShape",
    h_axis: np.ndarray,
    v_axis: np.ndarray,
    lc:     float,
    nrad:   int,
    mprg:   float = 1.0,
    mbmp:   float = 1.0,
    ratio:  float = 0.6,
    rot:    float = 0.0,
) -> CrossSection:
    """Build a 9-patch OH-circle cross-section with 8 outer corners (n_outer=8).

    Parameters
    ----------
    cx, cy, cz : float
        Pipe-axis centre coordinates.
    shape : CircleShape
        Carries ``radius`` and ``nang``.  **nang must be even** — each 45° arc
        gets ``nang // 2`` divisions.
    h_axis : ndarray, shape (3,)
        Unit vector for the "horizontal" in-plane direction (cursor.right).
    v_axis : ndarray, shape (3,)
        Unit vector for the "vertical"   in-plane direction (cursor.up).
    lc : float
        GMSH characteristic mesh length.
    nrad : int
        Transfinite node layers on radial lines (inner ring → outer circle).
    mprg : float
        Radial progression factor.
    mbmp : float
        Angular bump factor for the 45° arcs.
    ratio : float
        Inner-ring scale factor relative to the outer radius (default 0.6).
    rot : float
        Rotation offset added to all corner angles (radians).

    Returns
    -------
    CrossSection
        9 surface tags.  ``n_outer == 8``.
        ``outer_points`` = [NE, N, NW, W, SW, S, SE, E] (8 tags).
        ``outer_curves`` = [NE→N, N→NW, NW→W, W→SW, SW→S, S→SE, SE→E, E→NE].
        ``inner_points`` / ``inner_curves`` / ``radial_curves`` — 8 entries each.

    Notes
    -----
    Corner order convention (CCW from h_axis = 0°):
        index 0 = NE  (45° + rot)
        index 1 = N   (90° + rot)
        index 2 = NW  (135° + rot)
        index 3 = W   (180° + rot)
        index 4 = SW  (225° + rot)
        index 5 = S   (270° + rot)
        index 6 = SE  (315° + rot)
        index 7 = E   (0°  + rot)

    The N/W/S/E corners (indices 1/3/5/7) are structural outer boundary nodes.
    This makes 0°/180° (E/W positions) available as shared OCC nodes for T-junction
    tip conformality and 90°/270° (N/S) for Y-junction split-plane conformality.

    All arcs — outer and inner — are arcs of their respective circles centred at
    the pipe axis point ``center``.  Inner arcs therefore differ from the offset-
    centre arcs used in ``build_oh_circle``; the centre patch boundary is a true
    circle rather than a rounded square.
    """
    if shape.nang % 2 != 0:
        raise ValueError(
            f"build_oh_circle8 requires nang to be even (each 45° arc needs "
            f"nang//2 divisions); got nang={shape.nang}."
        )

    r      = shape.radius
    nang_h = shape.nang // 2   # divisions per 45° arc

    # Corner angles: NE(45°), N(90°), NW(135°), W(180°), SW(225°), S(270°), SE(315°), E(360°)
    angles = [(k + 1) * math.pi / 4 + rot for k in range(8)]

    _centre = np.array([cx, cy, cz])
    _h = np.asarray(h_axis, dtype=float)
    _v = np.asarray(v_axis, dtype=float)

    def _coords(angle: float, radius: float):
        u = math.cos(angle) * radius
        v = math.sin(angle) * radius
        p = _centre + u * _h + v * _v
        return float(p[0]), float(p[1]), float(p[2])

    # ------------------------------------------------------------------ #
    # Points                                                              #
    # ------------------------------------------------------------------ #
    center = add_point(cx, cy, cz, lc)

    # 8 outer corners on circle of radius r
    O = [add_point(*_coords(a, r), lc) for a in angles]

    # 8 inner corners on circle of radius ratio*r (same angular positions)
    I = [add_point(*_coords(a, ratio * r), lc) for a in angles]

    # ------------------------------------------------------------------ #
    # Curves                                                              #
    # ------------------------------------------------------------------ #
    # Outer arcs (CCW): O[k] → O[(k+1)%8], all centred at pipe axis
    A_out = [add_arc(O[k], center, O[(k + 1) % 8]) for k in range(8)]

    # Inner arcs (CCW): I[k] → I[(k+1)%8], all centred at pipe axis
    A_in  = [add_arc(I[k], center, I[(k + 1) % 8]) for k in range(8)]

    # Radials: I[k] → O[k] (inner → outer, same angular position)
    R = [add_line(I[k], O[k]) for k in range(8)]

    # ------------------------------------------------------------------ #
    # Surfaces                                                            #
    # ------------------------------------------------------------------ #
    # Centre patch: CCW loop around all 8 inner arcs; 4 transfinite corners
    # at the diagonal positions NE/NW/SW/SE (indices 0/2/4/6).
    ll_c   = add_line_loop(list(A_in))
    s_c    = add_surface(ll_c)

    # Outer ring: 8 patches, each covering one 45° sector
    s_ring = []
    for k in range(8):
        ll = add_line_loop([A_out[k], -R[(k + 1) % 8], -A_in[k], R[k]])
        s_ring.append(add_surface(ll))

    surfaces = [s_c] + s_ring

    # ------------------------------------------------------------------ #
    # Mesh constraints                                                    #
    # ------------------------------------------------------------------ #
    set_transfinite_line(R, nrad, mprg)
    set_transfinite_line_bump(A_out + A_in, nang_h, mbmp)

    # Centre patch: must specify the 4 diagonal corners explicitly because
    # the loop has 8 curves and GMSH cannot auto-detect 4 corners.
    import gmsh as _gmsh
    _gmsh.model.occ.synchronize()
    _gmsh.model.mesh.setTransfiniteSurface(s_c, "Left", [I[0], I[2], I[4], I[6]])

    # Outer ring patches: each has exactly 4 curves → GMSH detects corners.
    set_transfinite_surface(s_ring)
    set_recombine_surface(surfaces)

    # ------------------------------------------------------------------ #
    # Stacking protocol exports                                           #
    # ------------------------------------------------------------------ #
    return CrossSection(
        surfaces      = surfaces,
        center        = center,
        outer_points  = O,
        outer_curves  = A_out,
        shape         = shape,
        boundary_type = BoundaryType.CIRCULAR,
        h_axis        = _h,
        v_axis        = _v,
        cx=cx, cy=cy, cz=cz,
        # Inner boundary (8 entries each)
        inner_points  = I,
        inner_curves  = A_in,           # CCW: I[0]→I[1], I[1]→I[2], …
        radial_curves = R,              # I[k]→O[k] for k=0..7
        nrad          = nrad,
        lc            = lc,
        corner_angles = angles,
    )
