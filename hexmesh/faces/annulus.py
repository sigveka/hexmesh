"""
Annular shell cross-section builder.

Stacks n_outer patches on top of an existing CircleShape layer, where
n_outer is inherited from the inner CrossSection (4 or 8).  The inner
boundary reuses the previous layer's GMSH entities — the stacking protocol
that guarantees conformal interfaces.

Patch layout (n_outer patches, one per outer arc):

    outer arc k→k+1  ─┐
    radial k+1 (inward)│  patch k
    inner arc k→k+1 ←──┘  (inner.outer_curves[k] reversed)
    radial k (outward)

For n_outer=4: 4 patches at 90° each (NE/NW/SW/SE corners).
For n_outer=8: 8 patches at 45° each (NE/N/NW/W/SW/S/SE/E corners).
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


def build_annulus(
    inner:  CrossSection,
    dR:     float,
    lc:     float,
    nrad:   int,
    mprg:   float = 1.0,
    mbmp:   float = 1.0,
    rot:    float = 0.0,
    stretch: tuple | None = None,
) -> CrossSection:
    """Build an n_outer-patch annular shell on top of *inner*.

    The inner boundary reuses the GMSH entities exported by *inner*
    (``outer_points`` and ``outer_curves``).  No new inner-boundary entities
    are created, guaranteeing a conformal mesh at the interface.

    Works for any ``inner.n_outer`` in {4, 8}: the number of patches, outer
    corner angles, and arc mesh density are all derived from the inner layer.

    Parameters
    ----------
    inner : CrossSection
        The previous layer.  Must have BoundaryType.CIRCULAR.
    dR : float
        Radial thickness of this annular layer.
        New outer radius = inner.shape.radius + dR.
    lc : float
        GMSH characteristic mesh length for new outer-boundary points.
    nrad : int
        Transfinite node layers across the annulus thickness.
    mprg : float
        Radial progression factor (>1 biases nodes toward inner boundary).
    mbmp : float
        Angular bump factor for the outer arcs.
    rot : float
        Additional rotation (radians) applied on top of the inner layer's
        corner angles.  Default 0.0 (outer corners align with inner corners).
    stretch : (ndarray, float), optional
        In-plane stretch ``(b, s)`` of the face; must match the one *inner*
        was built with (see ``build_oh_circle``).

    Returns
    -------
    CrossSection
        New layer with updated outer_points and outer_curves for further
        stacking.  ``n_outer`` matches ``inner.n_outer``.
    """
    if inner.boundary_type is not BoundaryType.CIRCULAR:
        raise TypeError(
            "build_annulus requires a CIRCULAR inner boundary; "
            f"got {inner.boundary_type}."
        )
    if not isinstance(inner.shape, CircleShape):
        raise TypeError("build_annulus requires CircleShape inner layer.")
    if dR <= 0:
        raise ValueError(f"dR must be positive, got {dR!r}")

    n      = inner.n_outer          # 4 or 8
    cx, cy, cz = inner.cx, inner.cy, inner.cz
    center     = inner.center       # reuse — no new centre point
    si         = inner.outer_points # n inner corner tags
    ia         = inner.outer_curves # n inner arc tags (CCW, k → k+1)
    h_axis     = inner.h_axis
    v_axis     = inner.v_axis
    r_out      = inner.shape.radius + dR
    nang       = inner.shape.nang
    # Mesh density per arc: same spacing as inner layer's arcs.
    # For n=4: nang per 90° arc.  For n=8: nang//2 per 45° arc.
    nang_per_arc = nang // (n // 4)

    _centre = np.array([cx, cy, cz])

    def _coords(angle: float, r: float):
        u = math.cos(angle) * r
        v = math.sin(angle) * r
        p = stretched(_centre + u * h_axis + v * v_axis, _centre, stretch)
        return float(p[0]), float(p[1]), float(p[2])

    # Corner angles: when the inner layer recorded its corner angles, outer
    # corners align with them exactly (no additional rotation — the inner
    # angles already include any pipe-spec rot).  Fall back to the default
    # corner layout when corner_angles is absent (CrossSections created without
    # a face builder, e.g. manually in tests), applying rot from scratch.
    if inner.corner_angles:
        angles = list(inner.corner_angles)
    else:
        step = 2 * math.pi / n
        angles = [math.pi / 4 + k * step + rot for k in range(n)]

    # ------------------------------------------------------------------ #
    # Outer circle corner points (one per corner, at r_out)              #
    # ------------------------------------------------------------------ #
    O = [add_point(*_coords(angles[k], r_out), lc) for k in range(n)]

    # ------------------------------------------------------------------ #
    # Radial lines: si[k] → O[k]                                         #
    # ------------------------------------------------------------------ #
    R = [add_line(si[k], O[k]) for k in range(n)]

    # ------------------------------------------------------------------ #
    # Outer arcs: O[k] → O[(k+1)%n]                                      #
    # ------------------------------------------------------------------ #
    A_out = [add_conic_arc(O[k], center, O[(k + 1) % n], (cx, cy, cz), stretch)
             for k in range(n)]

    # ------------------------------------------------------------------ #
    # Surfaces: patch k bounded by A_out[k], -R[k+1], -ia[k], R[k]      #
    # ------------------------------------------------------------------ #
    surfaces = []
    for k in range(n):
        ll = add_line_loop([A_out[k], -R[(k + 1) % n], -ia[k], R[k]])
        surfaces.append(add_surface(ll))

    # ------------------------------------------------------------------ #
    # Mesh constraints (only new entities)                                #
    # Inner arcs already have Transfinite from the previous layer.        #
    # ------------------------------------------------------------------ #
    set_transfinite_line(R,     nrad,        mprg)
    set_transfinite_line_bump(A_out, nang_per_arc, mbmp)
    set_transfinite_surface(surfaces)
    set_recombine_surface(surfaces)

    return CrossSection(
        surfaces      = surfaces,
        center        = center,
        outer_points  = O,
        outer_curves  = A_out,
        shape         = CircleShape(radius=r_out, nang=nang),
        boundary_type = BoundaryType.CIRCULAR,
        h_axis        = h_axis,
        v_axis        = v_axis,
        cx=cx, cy=cy, cz=cz,
        # Taper support: inner boundary is previous layer's outer boundary
        inner_points  = list(si),
        inner_curves  = list(ia),
        radial_curves = R,
        nrad          = nrad,
        lc            = lc,
        corner_angles = angles,
    )
