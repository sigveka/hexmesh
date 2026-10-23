"""
Square shell cross-section builder.

Wraps a circular cross-section (BoundaryType.CIRCULAR) in a flat square
outer boundary, producing 4 patches that transition from arc inner edges
to straight outer edges.

This is the key primitive for bundle tiling: the square outer boundary
allows adjacent pipe cells to share flat faces, giving a conformal
structured mesh across the entire bundle without any inter-tube meshing.

Outer boundary convention:
    outer_points = [p1(NE), p2(NW), p3(SW), p4(SE)]   square corners
    outer_curves = [a1(top), a3(left), a5(bottom), a7(right)]  straight lines
    boundary_type = SQUARE
"""

from __future__ import annotations
import math

import gmsh
import numpy as np

from ..core.cross_section import CrossSection, BoundaryType
from ..core.shape import CircleShape, RectShape
from ..core.spec import SquareShellSpec
from ._gmsh_helpers import (
    add_point, add_line, add_line_loop, add_surface,
    set_transfinite_line, set_transfinite_line_bump,
    set_transfinite_surface, set_recombine_surface,
)


def build_square_shell(
    inner: CrossSection,
    spec:  SquareShellSpec,
    lc:    float,
    mbmp:  float = 1.0,
) -> CrossSection:
    """Build a 4-patch square shell around *inner*.

    The inner boundary reuses *inner*'s outer_points and outer_curves
    (stacking protocol).  The outer boundary is a flat square with
    corners at (±half_w, ±half_h).

    Parameters
    ----------
    inner : CrossSection
        The previous circular layer.  Must be BoundaryType.CIRCULAR.
    spec : SquareShellSpec
        Carries half_w, half_h, nrad, mprg.
    lc : float
        Characteristic mesh length for new outer-boundary points.
    mbmp : float
        Bump factor for angular (arc) edges on the inner boundary.

    Returns
    -------
    CrossSection
        BoundaryType.SQUARE with outer_curves = 4 straight Lines.
    """
    if inner.boundary_type is not BoundaryType.CIRCULAR:
        raise TypeError(
            "build_square_shell requires a CIRCULAR inner boundary; "
            f"got {inner.boundary_type}."
        )
    if not isinstance(inner.shape, CircleShape):
        raise TypeError("build_square_shell requires CircleShape inner layer.")

    cx, cy, cz = inner.cx, inner.cy, inner.cz
    center     = inner.center
    si1, si2, si3, si4 = inner.outer_points   # NE, NW, SW, SE inner corners
    h_axis     = inner.h_axis
    v_axis     = inner.v_axis
    nang       = inner.shape.nang
    hw, hh     = spec.half_w, spec.half_h
    _centre    = np.array([cx, cy, cz])

    def _coords(du: float, dv: float):
        p = _centre + du * h_axis + dv * v_axis
        return float(p[0]), float(p[1]), float(p[2])

    # ------------------------------------------------------------------ #
    # Outer square corner points                                          #
    # ------------------------------------------------------------------ #
    p1 = add_point(*_coords( hw,  hh), lc)   # NE
    p2 = add_point(*_coords(-hw,  hh), lc)   # NW
    p3 = add_point(*_coords(-hw, -hh), lc)   # SW
    p4 = add_point(*_coords( hw, -hh), lc)   # SE

    # ------------------------------------------------------------------ #
    # Outer square edges                                                  #
    # ------------------------------------------------------------------ #
    sq1 = add_line(p1, p2)   # NE→NW  top
    sq3 = add_line(p2, p3)   # NW→SW  left
    sq5 = add_line(p3, p4)   # SW→SE  bottom
    sq7 = add_line(p4, p1)   # SE→NE  right

    # ------------------------------------------------------------------ #
    # Radial lines: inner arc corner → outer square corner                #
    # ------------------------------------------------------------------ #
    r1 = add_line(si2, p2)   # NW inner → NW outer
    r2 = add_line(si1, p1)   # NE inner → NE outer
    r3 = add_line(si3, p3)   # SW inner → SW outer
    r4 = add_line(si4, p4)   # SE inner → SE outer

    # ------------------------------------------------------------------ #
    # Line Loops & Surfaces                                               #
    # Negated inner arcs reference previous layer's outer_curves.         #
    # ------------------------------------------------------------------ #
    ia = inner.outer_curves   # [NE→NW, NW→SW, SW→SE, SE→NE]

    ll1 = add_line_loop([sq1, -r1, -ia[0],  r2])   # NE patch
    ll2 = add_line_loop([sq3, -r3, -ia[1],  r1])   # NW patch
    ll3 = add_line_loop([sq5, -r4, -ia[2],  r3])   # SW patch
    ll4 = add_line_loop([sq7, -r2, -ia[3],  r4])   # SE patch

    s1 = add_surface(ll1)
    s2 = add_surface(ll2)
    s3 = add_surface(ll3)
    s4 = add_surface(ll4)
    surfaces = [s1, s2, s3, s4]

    # ------------------------------------------------------------------ #
    # Mesh constraints                                                    #
    # ------------------------------------------------------------------ #
    set_transfinite_line([r1, r2, r3, r4],         spec.nrad, spec.mprg)
    set_transfinite_line_bump([sq1, sq3, sq5, sq7], nang,     mbmp)
    # Inner arcs already transfinite from the previous layer.
    set_transfinite_surface(surfaces)
    set_recombine_surface(surfaces)

    return CrossSection(
        surfaces     = surfaces,
        center       = center,
        outer_points = [p1, p2, p3, p4],
        outer_curves = [sq1, sq3, sq5, sq7],
        shape        = RectShape(half_w=hw, half_h=hh,
                                 nang_w=nang, nang_h=nang),
        boundary_type= BoundaryType.SQUARE,
        h_axis       = h_axis,
        v_axis       = v_axis,
        cx=cx, cy=cy, cz=cz,
        lc           = lc,
    )
