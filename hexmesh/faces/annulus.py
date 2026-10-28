"""
Ring (shell) cross-section builder: the layer between two outlines
(decision 0026).

Stacks n_outer patches on top of an existing layer, where n_outer is
inherited from the inner CrossSection (4 or 8).  The inner boundary reuses
the previous layer's GMSH entities — the stacking protocol that guarantees
conformal interfaces.  The outer boundary is any outline (``CircleShape``
or ``RectShape``): whatever the two shapes, the ring is one patch per side,
so its connectivity is that of a circular annulus with the same counts.

Patch layout (n_outer patches, one per side):

    outer side k→k+1  ─┐
    radial k+1 (inward) │  patch k
    inner side k→k+1 ←──┘  (inner.outer_curves[k] reversed)
    radial k (outward)

The corner lines (radials) leave the inner corners along the direction from
the centre and end where the outer outline says (``ring_corner``): on a
circle radially, on a rectangle at its corner in that quadrant.  So a
circle inside a square has straight radial corner lines, inside a flat
rectangle skewed ones; a rectangle inside a circle splits the circle into
unequal arcs.
"""

from __future__ import annotations
import math

import gmsh
import numpy as np

from ..core.cross_section import CrossSection, BoundaryType
from ._gmsh_helpers import (
    add_point, add_conic_arc, add_line, add_line_loop, add_surface,
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
    """Build a shell of thickness *dR* on top of *inner*: its outline grown
    by *dR* (a circle's radius + dR; a rectangle's half-sizes + dR).  See
    ``build_ring``."""
    if dR <= 0:
        raise ValueError(f"dR must be positive, got {dR!r}")
    return build_ring(inner, inner.shape.grown(dR), lc, nrad, mprg, mbmp, rot, stretch)


def build_ring(
    inner:  CrossSection,
    outer,
    lc:     float,
    nrad:   int,
    mprg:   float = 1.0,
    mbmp:   float = 1.0,
    rot:    float = 0.0,
    stretch: tuple | None = None,
) -> CrossSection:
    """Build an n_outer-patch ring between *inner* and the outline *outer*.

    The inner boundary reuses the GMSH entities exported by *inner*
    (``outer_points`` and ``outer_curves``).  No new inner-boundary entities
    are created, guaranteeing a conformal mesh at the interface.

    Parameters
    ----------
    inner : CrossSection
        The previous layer (any outline).
    outer : CircleShape or RectShape
        This layer's outline, centred on the inner one's centre.  Must
        enclose it (checked by the assembly's validation).
    lc : float
        GMSH characteristic mesh length for new outer-boundary points.
    nrad : int
        Transfinite node layers across the ring.
    mprg : float
        Radial progression factor (>1 biases nodes toward inner boundary).
    mbmp : float
        Bump factor for the outer sides.
    rot : float
        Rotation of the section (radians), as the core was built with; the
        outer outline is rotated with it.
    stretch : (ndarray, float), optional
        In-plane stretch ``(b, s)`` of the face; must match the one *inner*
        was built with (see ``build_oh_circle``).

    Returns
    -------
    CrossSection
        New layer with updated outer_points and outer_curves for further
        stacking.  ``n_outer`` matches ``inner.n_outer``.
    """
    n      = inner.n_outer          # 4 or 8
    cx, cy, cz = inner.cx, inner.cy, inner.cz
    center     = inner.center       # reuse — no new centre point
    si         = inner.outer_points # n inner corner tags
    ia         = inner.outer_curves # n inner side tags (CCW, k → k+1)
    h_axis     = inner.h_axis
    v_axis     = inner.v_axis
    _centre = np.array([cx, cy, cz])
    c, s = math.cos(rot), math.sin(rot)

    def _coords(p):
        """In-plane point *p* (before rot) → 3-D, rotated and stretched."""
        u, v = c * p[0] - s * p[1], s * p[0] + c * p[1]
        q = stretched(_centre + u * h_axis + v * v_axis, _centre, stretch)
        return float(q[0]), float(q[1]), float(q[2])

    # Inner corner directions: the corner angles the inner layer recorded
    # (they include rot).  Fall back to the default corner layout when they
    # are absent (CrossSections made by hand in tests).
    if inner.corner_angles:
        angles = list(inner.corner_angles)
    else:
        step = 2 * math.pi / n
        angles = [math.pi / 4 + k * step + rot for k in range(n)]
    corners = [outer.ring_corner(a - rot) for a in angles]
    angles_out = [a if type(outer).side_curve == "arc"    # radial: same angle
                  else rot + math.atan2(p[1], p[0]) for a, p in zip(angles, corners)]

    # ------------------------------------------------------------------ #
    # Outer corner points                                                #
    # ------------------------------------------------------------------ #
    O = [add_point(*_coords(corners[k]), lc) for k in range(n)]

    # ------------------------------------------------------------------ #
    # Corner lines: si[k] → O[k]                                         #
    # ------------------------------------------------------------------ #
    R = [add_line(si[k], O[k]) for k in range(n)]

    # ------------------------------------------------------------------ #
    # Outer sides: O[k] → O[(k+1)%n], arcs about the centre or lines      #
    # ------------------------------------------------------------------ #
    if type(outer).side_curve == "arc":
        A_out = [add_conic_arc(O[k], center, O[(k + 1) % n], (cx, cy, cz), stretch)
                 for k in range(n)]
    else:
        A_out = [add_line(O[k], O[(k + 1) % n]) for k in range(n)]

    # ------------------------------------------------------------------ #
    # Surfaces: patch k bounded by A_out[k], -R[k+1], -ia[k], R[k]      #
    # ------------------------------------------------------------------ #
    surfaces = []
    for k in range(n):
        ll = add_line_loop([A_out[k], -R[(k + 1) % n], -ia[k], R[k]])
        surfaces.append(add_surface(ll))

    # ------------------------------------------------------------------ #
    # Mesh constraints (only new entities)                                #
    # Inner sides already have Transfinite from the previous layer.       #
    # ------------------------------------------------------------------ #
    set_transfinite_line(R, nrad, mprg)
    by_count: dict[int, list[int]] = {}
    for k, a in enumerate(A_out):
        by_count.setdefault(outer.side_count(k, n), []).append(a)
    for count, curves in by_count.items():
        set_transfinite_line_bump(curves, count, mbmp)
    set_transfinite_surface(surfaces)
    set_recombine_surface(surfaces)

    return CrossSection(
        surfaces      = surfaces,
        center        = center,
        outer_points  = O,
        outer_curves  = A_out,
        shape         = outer,
        boundary_type = (BoundaryType.CIRCULAR if type(outer).side_curve == "arc"
                         else BoundaryType.SQUARE),
        h_axis        = h_axis,
        v_axis        = v_axis,
        cx=cx, cy=cy, cz=cz,
        # Taper support: inner boundary is previous layer's outer boundary
        inner_points  = list(si),
        inner_curves  = list(ia),
        radial_curves = R,
        nrad          = nrad,
        lc            = lc,
        corner_angles = angles_out,
    )
