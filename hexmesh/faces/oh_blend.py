"""
OH cross-section built from a shape's outlines (task 0029).

The 5-patch layout of ``build_oh_circle`` / ``build_oh_rect`` (same point
and curve order, same exports), with every curve a spline through samples
of ``shape.outline(k, s, inner)``.  Used for the intermediate stations of a
``Transition``, whose shape (``core.shape.BlendShape``) lies between a
circle and a rectangle.
"""

from __future__ import annotations
import math

import gmsh
import numpy as np

from .. import _occ
from ..core.cross_section import CrossSection, BoundaryType
from ._gmsh_helpers import (
    add_point, add_line, add_line_loop, add_surface, stretched,
    set_transfinite_line, set_transfinite_line_bump,
    set_transfinite_surface, set_recombine_surface,
)

# Interior samples per curve; the spline through them stands for the
# station shape (one axial layer per slab, so no surface carries nodes).
_SAMPLES = 24


def build_oh_blend(
    cx:     float,
    cy:     float,
    cz:     float,
    shape,
    h_axis: np.ndarray,
    v_axis: np.ndarray,
    lc:     float,
    nrad:   int,
    mprg:   float = 1.0,
    mbmp:   float = 1.0,
    rot:    float = 0.0,
    stretch: tuple | None = None,
) -> CrossSection:
    """Build a 5-patch OH face whose curves follow ``shape.outline``.

    *shape* needs ``outline(k, s, inner)``, ``nang_w`` and ``nang_h``;
    *rot* turns the outlines in the plane, as in ``build_oh_rect``.
    """
    geo = gmsh.model.occ
    centre = np.array([cx, cy, cz])
    h, v = np.asarray(h_axis, dtype=float), np.asarray(v_axis, dtype=float)
    c, s_ = math.cos(rot), math.sin(rot)

    def xyz(uv):
        u, w = c * uv[0] - s_ * uv[1], s_ * uv[0] + c * uv[1]
        return stretched(centre + u * h + w * v, centre, stretch)

    def pt(uv):
        return add_point(*(float(x) for x in xyz(uv)), lc)

    center = add_point(cx, cy, cz, lc)
    o = [pt(shape.outline(k, 0.0)) for k in range(4)]
    i = [pt(shape.outline(k, 0.0, inner=True)) for k in range(4)]
    mid = np.linspace(0.0, 1.0, _SAMPLES + 2)[1:-1]

    def spline(k, a, b, inner):
        pts = [geo.addPoint(*xyz(p)) for p in shape.outline(k, mid, inner)]
        return _occ.spline([a, *pts, b])

    oc = [spline(k, o[k], o[(k + 1) % 4], False) for k in range(4)]   # NE→NW, …
    ic = [spline(k, i[k], i[(k + 1) % 4], True) for k in range(4)]
    r = [add_line(i[k], o[k]) for k in range(4)]                      # NE, NW, SW, SE

    surfaces = [add_surface(add_line_loop(ic))]
    for k in range(4):
        j = (k + 1) % 4
        surfaces.append(add_surface(add_line_loop([oc[k], -r[j], -ic[k], r[k]])))

    set_transfinite_line(r, nrad, mprg)
    set_transfinite_line_bump([oc[0], ic[0], oc[2], ic[2]], shape.nang_w, mbmp)
    set_transfinite_line_bump([oc[1], ic[1], oc[3], ic[3]], shape.nang_h, mbmp)
    set_transfinite_surface(surfaces)
    set_recombine_surface(surfaces)

    return CrossSection(
        surfaces      = surfaces,
        center        = center,
        outer_points  = o,
        outer_curves  = oc,
        shape         = shape,
        boundary_type = BoundaryType.SQUARE,
        h_axis        = h,
        v_axis        = v,
        cx=cx, cy=cy, cz=cz,
        inner_points  = i,
        inner_curves  = ic,
        radial_curves = r,
        nrad          = nrad,
        lc            = lc,
    )
