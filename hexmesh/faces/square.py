"""
Single-patch square cross-section builder.

Python equivalent of the ``square.geo`` / ``SquareLinearExtrusion`` function
library.  Produces exactly **one** quad surface — four corner points, four
edge lines, one ``Plane Surface`` — with no inner OH square and no butterfly
patches.

.. warning::
    **Incompatible with OH (butterfly) topology.**
    ``build_oh_circle`` and ``build_oh_rect`` create a 5-patch cross-section
    (inner square + 4 surrounding quadrants).  ``build_square`` creates a
    single patch.  These two topologies **cannot share conformal boundaries**:
    the inner/outer point and curve counts differ, so you cannot stack an
    annulus or square_shell layer on top of a square face.  Mixing them in
    the same ``PipeSpec`` will raise ``TypeError``.

Usage
-----
This builder is wired into the framework when a ``SquareShape`` is passed as
the core of a ``PipeSpec``.  Direct use::

    from hexmesh.faces.square import build_square
    from hexmesh.core.shape   import SquareShape

    cs = build_square(
        cx=0.0, cy=0.0, cz=0.0,
        shape=SquareShape(half_w=0.5, half_h=0.5, nang_w=4, nang_h=4),
        h_axis=np.array([1, 0, 0]),
        v_axis=np.array([0, 0, 1]),
        lc=0.1,
    )
"""

from __future__ import annotations

import numpy as np
import gmsh

from ..core.cross_section import CrossSection, BoundaryType
from ..core.shape import SquareShape
from ._gmsh_helpers import (
    add_point, add_line, add_line_loop, add_surface,
    set_transfinite_line, set_transfinite_surface, set_recombine_surface,
    set_transfinite_line_bump,
)


def build_square(
    cx:     float,
    cy:     float,
    cz:     float,
    shape:  SquareShape,
    h_axis: np.ndarray,
    v_axis: np.ndarray,
    lc:     float,
    mbmp:   float = 1.0,
) -> CrossSection:
    """Build a single-patch square cross-section in GMSH.

    Directly mirrors the ``square.geo`` Function:

    * Four corner points: NE, NW, SW, SE
    * Four lines forming a closed loop (CCW when viewed from outside)
    * One ``Plane Surface``
    * ``Transfinite`` + ``Recombine`` constraints → structured quad mesh

    The returned ``CrossSection`` has one surface (``surfaces[0]``), which
    the ``Straight`` connector will correctly classify as a standalone block
    with all four lateral surfaces treated as outer walls.

    Parameters
    ----------
    cx, cy, cz : float
        Pipe-axis centre coordinates.
    shape : SquareShape
        Carries ``half_w``, ``half_h``, ``nang_w``, ``nang_h``.
    h_axis : ndarray, shape (3,)
        Unit vector for the "horizontal" in-plane direction (cursor.right).
    v_axis : ndarray, shape (3,)
        Unit vector for the "vertical"  in-plane direction (cursor.up).
    lc : float
        GMSH characteristic mesh length.
    mbmp : float
        Bump factor for Transfinite Line (default 1.0 = uniform spacing).

    Returns
    -------
    CrossSection
        Single-surface, ``BoundaryType.SQUARE``.
        ``outer_points`` and ``outer_curves`` follow the NE/NW/SW/SE
        convention shared with ``build_oh_rect``.
    """
    hw, hh = shape.half_w, shape.half_h
    centre = np.array([cx, cy, cz])
    _h     = np.asarray(h_axis, dtype=float)
    _v     = np.asarray(v_axis, dtype=float)

    def _pt(du: float, dv: float) -> tuple[float, float, float]:
        p = centre + du * _h + dv * _v
        return float(p[0]), float(p[1]), float(p[2])

    # ------------------------------------------------------------------ #
    # Corner points — same compass ordering as square.geo / oh_rect.py   #
    # NE = (+hw, +hh),  NW = (-hw, +hh)                                 #
    # SW = (-hw, -hh),  SE = (+hw, -hh)                                 #
    # ------------------------------------------------------------------ #
    o_ne = add_point(*_pt( hw,  hh), lc)   # NE
    o_nw = add_point(*_pt(-hw,  hh), lc)   # NW
    o_sw = add_point(*_pt(-hw, -hh), lc)   # SW
    o_se = add_point(*_pt( hw, -hh), lc)   # SE

    # Centre point (required by CrossSection; no geometry role here)
    centre_pt = add_point(cx, cy, cz, lc)

    # ------------------------------------------------------------------ #
    # Edges — CCW loop when viewed from outside (same convention as       #
    # oh_rect: top=NE→NW, left=NW→SW, bottom=SW→SE, right=SE→NE)        #
    # Matches outer_curves[0..3] of CrossSection.                        #
    # ------------------------------------------------------------------ #
    top    = add_line(o_ne, o_nw)   # NE → NW  (width  edge, +v side)
    left   = add_line(o_nw, o_sw)   # NW → SW  (height edge, -h side)
    bottom = add_line(o_sw, o_se)   # SW → SE  (width  edge, -v side)
    right  = add_line(o_se, o_ne)   # SE → NE  (height edge, +h side)

    # ------------------------------------------------------------------ #
    # Single surface                                                      #
    # ------------------------------------------------------------------ #
    ll = add_line_loop([top, left, bottom, right])
    surf = add_surface(ll)

    # ------------------------------------------------------------------ #
    # Transfinite + recombine constraints                                 #
    # Width  edges (top, bottom) → nang_w divisions                      #
    # Height edges (left, right) → nang_h divisions                      #
    # ------------------------------------------------------------------ #
    set_transfinite_line_bump([top, bottom], shape.nang_w, mbmp)
    set_transfinite_line_bump([left, right], shape.nang_h, mbmp)
    set_transfinite_surface([surf])
    set_recombine_surface([surf])

    return CrossSection(
        surfaces      = [surf],
        center        = centre_pt,
        outer_points  = [o_ne, o_nw, o_sw, o_se],
        outer_curves  = [top, left, bottom, right],
        shape         = shape,
        boundary_type = BoundaryType.SQUARE,
        h_axis        = _h,
        v_axis        = _v,
        cx=cx, cy=cy, cz=cz,
        lc=lc,
    )
