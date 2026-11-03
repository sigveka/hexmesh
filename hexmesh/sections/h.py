#        _.-------._
#    .-''     |     ''-.
#  .'  \      |      /  '.     _                                         _
# /     +-----+-----+     \   | |__   ___  __  __  _ __ ___   ___  ___  | |__
# |     |     |     |     |   | '_ \ / _ \ \ \/ / | '_ ` _ \ / _ \/ __| | '_ \
# |-----+-----+-----+-----|   | | | |  __/  >  <  | | | | | |  __/\__ \ | | | |
# |     |     |     |     |   |_| |_|\___| /_/\_\ |_| |_| |_|\___||___/ |_| |_|
# \     +-----+-----+     /
#  '.  /      |      \  .'    structured all-hex meshes for pipe networks
#    '-..     |     ..-'
#        '---------'
#
"""
The H section layout (decision 0036; task 0084): one Cartesian patch.

A rectangular core meshed as a single transfinite patch of
``nang_w`` × ``nang_h`` cells, graded toward the walls by a two-sided
``Bump`` on every side (``core.grading``; gmsh's two-sided law,
``docs/integrations/gmsh.md``).  It has one level, the core's boundary,
whose corners are the rectangle's corners NE, NW, SW, SE (DESIGN §6.1's
corner table, as the O-H face's outer corners), and no inner boundary,
corner lines or rings.  Shells around it come with task 0086.

The pure declaration (``levels``, ``patches``) and the GMSH face
(``build_h_rect``) both come from the functions here.
"""

from __future__ import annotations

import math

import numpy as np

from ..core.cross_section import BoundaryType, CrossSection
from ..core.grading import bump, bump_for_ratio
from ..core.shape import RectShape
from . import oh
from ._gmsh_helpers import (add_line, add_line_loop, add_point, add_surface, plane,
                            set_recombine_surface, set_transfinite_curve,
                            set_transfinite_surface)

NAME = "h"
#: signature layout kind (``assembly.signature``)
CORE_KIND = "h_core"


def corner0_angle(spec) -> float:
    """Angle of corner 0 (NE) from ``frame.right``, ``rot`` included: the
    rectangle's corner, as on the O-H face."""
    shape = spec.core_shape
    return math.atan2(shape.half_h, shape.half_w) + spec.rot_rad


def side_counts(shape, n_outer: int = 4) -> tuple[int, ...]:
    """Divisions of side *k*: ``nang_w``, ``nang_h``, ``nang_w``, ``nang_h``."""
    return tuple(shape.side_count(k, 4) for k in range(4))


def side_grading(spec, k: int) -> tuple | None:
    """``("Bump", coef)`` of side *k* (corner k → k + 1), from the spec's
    wall grading (``PipeSpec.wall_grading``), or ``None`` if uniform.
    Stored coefficients are per side (``wall_bump``, the sides of
    ``nang_w`` then ``nang_h``); a ratio solves its coefficient here."""
    wall = spec.wall_grading
    if wall is None:
        return None
    if wall[0] == "bump":
        coef = wall[1][k % 2]
    else:
        coef = bump_for_ratio(spec.core_shape.side_count(k, 4), wall[1])
    return None if coef == 1.0 else ("Bump", coef)


def levels(spec) -> list[oh.Level]:
    """The one corner level: the rectangle's corners, ``rot`` applied, and
    its four sides."""
    shape, rot = spec.core_shape, spec.rot_rad
    corners = tuple(oh.rotated(shape.corner(k), rot) for k in range(4))
    edges = tuple(oh.Edge((0, k), (0, (k + 1) % 4), shape.side_count(k, 4), side_grading(spec, k))
                  for k in range(4))
    return [oh.Level(corners, edges)]


def patches(spec) -> list[tuple[str, tuple[tuple[int, int], ...]]]:
    """(material, cyclic ``(level, k)`` corners): the one patch."""
    return [(spec.layer_names[0], tuple((0, k) for k in range(4)))]


def node_grid(spec) -> np.ndarray:
    """The patch's nodes, ``(nang_w + 1, nang_h + 1, 2)``, unrotated: a
    tensor grid, each side's nodes at its wall grading's fractions (what
    the transfinite patch gives on a rectangle)."""
    shape = spec.core_shape
    f = []
    for k, half in ((0, shape.half_w), (1, shape.half_h)):
        n = shape.side_count(k, 4)
        g = side_grading(spec, k)
        f.append(half * (2 * (bump(n, g[1]) if g else np.arange(n + 1) / n) - 1))
    x, y = np.meshgrid(f[0], f[1], indexing="ij")
    return np.stack([x, y], axis=-1)


def node_grids(spec) -> list[tuple[int, np.ndarray]]:
    """(layer index, node grid) of every patch: the one patch."""
    return [(0, node_grid(spec))]


def section_cells(spec) -> int:
    """Quads in the section: ``nang_w · nang_h``."""
    c = side_counts(spec.core_shape)
    return c[0] * c[1]


# ---------------------------------------------------------------------------
# The GMSH face
# ---------------------------------------------------------------------------

def build_h_rect(spec, position, h_axis, v_axis, lc: float,
                 stretch: tuple | None = None) -> CrossSection:
    """Build *spec*'s H face in GMSH: four corners, four lines and one
    transfinite patch, centred at *position* in the plane of *h_axis* and
    *v_axis*.  Outside an assembly build the sides get their counts and
    wall grading here (inside one, the sweep sets them)."""
    shape = spec.core_shape
    if not isinstance(shape, RectShape):
        raise TypeError(f"the H face needs a rectangle, got {shape.label}")
    cx, cy, cz = (float(c) for c in position)
    xyz = plane(cx, cy, cz, h_axis, v_axis, stretch)
    lvl = levels(spec)[0]
    P = [add_point(*xyz(p), lc) for p in lvl.corners]                  # NE, NW, SW, SE
    C = [add_line(P[k], P[(k + 1) % 4]) for k in range(4)]              # corner k → k + 1
    surface = add_surface(add_line_loop(C))

    for c, e in zip(C, lvl.edges):
        set_transfinite_curve(c, e.divisions, *(e.grading or ("Progression", 1.0)))
    set_transfinite_surface([surface])
    set_recombine_surface([surface])

    return CrossSection(
        surfaces      = [surface],
        outer_points  = P,
        outer_curves  = C,
        shape         = shape,
        boundary_type = BoundaryType.SQUARE,
        h_axis        = np.asarray(h_axis, dtype=float),
        v_axis        = np.asarray(v_axis, dtype=float),
        cx=cx, cy=cy, cz=cz,
        lc            = lc,
        layout        = "h",
    )
