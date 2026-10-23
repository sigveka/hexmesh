"""
OH (butterfly) rectangular cross-section builder.

Generalisation of build_oh_circle to arbitrary aspect ratios.
Lines replace arcs; variable names and Line Loop structure are
intentionally identical to the circle variant for uniformity.

Interface-compatible with build_oh_circle:
    outer_points = [o1(NE), o2(NW), o3(SW), o4(SE)]
    outer_curves = [a1(top), a3(left), a5(bottom), a7(right)]

The special case half_w == half_h, nang_w == nang_h is a square.
"""

from __future__ import annotations

import gmsh
import numpy as np

from ..core.cross_section import CrossSection, BoundaryType
from ..core.shape import RectShape
from ._gmsh_helpers import (
    add_point, add_line, add_line_loop, add_surface,
    set_transfinite_line, set_transfinite_line_bump,
    set_transfinite_surface, set_recombine_surface,
)


def build_oh_rect(
    cx:     float,
    cy:     float,
    cz:     float,
    shape:  RectShape,
    h_axis: np.ndarray,
    v_axis: np.ndarray,
    lc:     float,
    nrad:   int,
    mprg:   float = 1.0,
    mbmp:   float = 1.0,
    ratio:  float = 0.6,
) -> CrossSection:
    """Build a 5-patch OH-rectangle cross-section in GMSH.

    Parameters
    ----------
    cx, cy, cz : float
        Pipe-axis centre coordinates.
    shape : RectShape
        Carries ``half_w``, ``half_h``, ``nang_w``, ``nang_h``.
    h_axis : ndarray, shape (3,)
        Unit vector for the "horizontal" in-plane direction (cursor.right).
    v_axis : ndarray, shape (3,)
        Unit vector for the "vertical"  in-plane direction (cursor.up).
    lc : float
        GMSH characteristic mesh length.
    nrad : int
        Transfinite node layers on radial lines.
    mprg : float
        Radial progression factor.
    mbmp : float
        Edge bump factor (applied to all edges uniformly).
    ratio : float
        Inner-rectangle scale factor (default 0.6).

    Returns
    -------
    CrossSection
        BoundaryType.SQUARE (outer_curves are Lines).
    """
    hw, hh = shape.half_w, shape.half_h
    _centre = np.array([cx, cy, cz])
    _h = np.asarray(h_axis, dtype=float)
    _v = np.asarray(v_axis, dtype=float)

    def _coords(du: float, dv: float):
        """Map in-plane (u, v) offsets to 3-D (x, y, z) via cursor frame."""
        p = _centre + du * _h + dv * _v
        return float(p[0]), float(p[1]), float(p[2])

    # ------------------------------------------------------------------ #
    # Outer corners                                                       #
    # ------------------------------------------------------------------ #
    # NE=(+hw,+hh), NW=(-hw,+hh), SW=(-hw,-hh), SE=(+hw,-hh)
    o1 = add_point(*_coords( hw,  hh), lc)   # NE
    o2 = add_point(*_coords(-hw,  hh), lc)   # NW
    o3 = add_point(*_coords(-hw, -hh), lc)   # SW
    o4 = add_point(*_coords( hw, -hh), lc)   # SE

    # Inner corners (scaled by ratio)
    i1 = add_point(*_coords( ratio * hw,  ratio * hh), lc)   # NE
    i2 = add_point(*_coords(-ratio * hw,  ratio * hh), lc)   # NW
    i3 = add_point(*_coords(-ratio * hw, -ratio * hh), lc)   # SW
    i4 = add_point(*_coords( ratio * hw, -ratio * hh), lc)   # SE

    center = add_point(cx, cy, cz, lc)

    # ------------------------------------------------------------------ #
    # Outer edges (CCW)                                                   #
    # ------------------------------------------------------------------ #
    a1 = add_line(o1, o2)   # NE→NW  top    (width  edge)
    a3 = add_line(o2, o3)   # NW→SW  left   (height edge)
    a5 = add_line(o3, o4)   # SW→SE  bottom (width  edge)
    a7 = add_line(o4, o1)   # SE→NE  right  (height edge)

    # Inner edges
    a2 = add_line(i2, i1)   # NW→NE  top    inner
    a4 = add_line(i3, i2)   # SW→NW  left   inner
    a6 = add_line(i4, i3)   # SE→SW  bottom inner
    a8 = add_line(i1, i4)   # NE→SE  right  inner

    # Radial lines
    r1 = add_line(i2, o2)   # NW
    r2 = add_line(i1, o1)   # NE
    r3 = add_line(i3, o3)   # SW
    r4 = add_line(i4, o4)   # SE

    # ------------------------------------------------------------------ #
    # Surfaces (identical Line Loop structure to oh_circle)               #
    # ------------------------------------------------------------------ #
    ll0 = add_line_loop([-a2, -a4, -a6, -a8])
    ll1 = add_line_loop([a1, -r1, a2, r2])
    ll2 = add_line_loop([a3, -r3, a4, r1])
    ll3 = add_line_loop([a5, -r4, a6, r3])
    ll4 = add_line_loop([a7, -r2, a8, r4])

    s0 = add_surface(ll0)
    s1 = add_surface(ll1)
    s2 = add_surface(ll2)
    s3 = add_surface(ll3)
    s4 = add_surface(ll4)
    surfaces = [s0, s1, s2, s3, s4]

    # ------------------------------------------------------------------ #
    # Mesh constraints                                                    #
    # Width  edges: a1,a2,a5,a6  (nang_w)                               #
    # Height edges: a3,a4,a7,a8  (nang_h)                               #
    # Radial lines: r1..r4       (nrad)                                  #
    # ------------------------------------------------------------------ #
    set_transfinite_line_bump([a1, a2, a5, a6], shape.nang_w, mbmp)
    set_transfinite_line_bump([a3, a4, a7, a8], shape.nang_h, mbmp)
    set_transfinite_line([r1, r2, r3, r4],       nrad, mprg)
    set_transfinite_surface(surfaces)
    set_recombine_surface(surfaces)

    return CrossSection(
        surfaces     = surfaces,
        center       = center,
        outer_points = [o1, o2, o3, o4],
        outer_curves = [a1, a3, a5, a7],
        shape        = shape,
        boundary_type= BoundaryType.SQUARE,
        h_axis       = _h,
        v_axis       = _v,
        cx=cx, cy=cy, cz=cz,
        lc           = lc,
    )
