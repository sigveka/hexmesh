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
``n_width`` × ``n_height`` cells, graded toward the walls by a two-sided
``Bump`` on every side (``core.grading``; gmsh's two-sided law,
``docs/integrations/gmsh.md``).  It has one level, the core's boundary,
whose corners are the rectangle's corners NE, NW, SW, SE (DESIGN §6.1's
corner table, as the O-H face's outer corners), and no inner boundary,
corner lines or rings.

**Shells** (task 0086, decision 0036 option B).  The first shell's ring
takes the core's four corners as its inner corners, so the corner
diagonals lie in the shell and the fluid stays Cartesian.  Every ring is
an O-H ring (``sections.oh``: corner lines by ``ring_corners``), its
sides graded as the core's side of the same index (the core's wall
``Bump``), so the lines across a thin shell stay straight.

``pillowed`` is the O-H face an H face pillows into: what a junction's
own O-H blocks use on an H port (task 0086).

The pure declaration (``levels``, ``patches``) and the GMSH face
(``build_h_rect``) both come from the functions here.
"""

from __future__ import annotations

import math

import numpy as np

from ..core.cross_section import BoundaryType, CrossSection
from ..core.grading import bump, progression_for_first_cell
from ..core.shape import RectShape
from . import oh
from ._gmsh_helpers import (add_line, add_line_loop, add_point, add_surface, plane,
                            set_recombine_surface, set_transfinite_curve,
                            set_transfinite_surface)
from ..errors import InternalError

NAME = "h"
#: signature layout kind (``assembly.signature``)
CORE_KIND = "h_core"


def corner0_angle(spec) -> float:
    """Angle of corner 0 (NE) from ``frame.right``, ``rot`` included: the
    rectangle's corner, as on the O-H face."""
    shape = spec.core_shape
    return math.atan2(shape.half_h, shape.half_w) + math.radians(spec.rot)


def side_counts(shape, n_outer: int = 4) -> tuple[int, ...]:
    """Divisions of side *k*: ``n_width``, ``n_height``, ``n_width``, ``n_height``."""
    return tuple(shape.side_count(k, 4) for k in range(4))


def side_grading(spec, k: int) -> tuple | None:
    """``("Bump", coef)`` of side *k* (corner k → k + 1), from the spec's
    wall grading (``PipeSpec.wall_grading``), or ``None`` if uniform.
    The coefficients are per side (``wall_bump``, the sides of ``n_width``
    then ``n_height``); ``first_cell=`` and ``radial_grading=`` resolve to them."""
    wall = spec.wall_grading
    if wall is None:
        return None
    coef = wall[1][k % 2]
    return None if coef == 1.0 else ("Bump", coef)


def levels(spec) -> list[oh.Level]:
    """The corner levels: the rectangle's corners, ``rot`` applied, and
    its four sides; then each shell's outer corners, its sides (graded as
    the core's) and its corner lines from the level below."""
    shape, rot = spec.core_shape, math.radians(spec.rot)
    corners = spec.corners()
    out = []
    for lvl, pts in enumerate(corners):
        edges = []
        for k in range(4):
            edges.append(oh.Edge((lvl, k), (lvl, (k + 1) % 4), shape.side_count(k, 4),
                                 side_grading(spec, k)))
            if lvl:
                sh = spec.shells[lvl - 1]
                edges.append(oh.Edge((lvl - 1, k), (lvl, k), sh.n_radial, ("Progression", sh.radial_grading)))
        out.append(oh.Level(tuple(oh.rotated(p, rot) for p in pts), tuple(edges)))
    return out


def patches(spec) -> list[tuple[str, tuple[tuple[int, int], ...]]]:
    """(material, cyclic ``(level, k)`` corners): the core's patch, then
    each shell's ring patches."""
    names = spec.layer_names
    out = [(names[0], tuple((0, k) for k in range(4)))]
    for lvl, name in enumerate(names[1:]):
        for k in range(4):
            j = (k + 1) % 4
            out.append((name, ((lvl, k), (lvl, j), (lvl + 1, j), (lvl + 1, k))))
    return out


def node_grid(spec) -> np.ndarray:
    """The patch's nodes, ``(n_width + 1, n_height + 1, 2)``, unrotated: a
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


def side_fractions(spec, k: int) -> np.ndarray:
    """Node fractions of side *k*, corner k → k + 1: its wall grading's."""
    n = spec.core_shape.side_count(k, 4)
    g = side_grading(spec, k)
    return bump(n, g[1]) if g else np.arange(n + 1) / n


def node_grids(spec) -> list[tuple[int, np.ndarray]]:
    """(layer index, node grid) of every patch, unrotated: the core's
    tensor grid, then each shell's ring patches, the linear blend of their
    two boundaries at the radial grading (as ``sections.oh.node_grids``)."""
    out = [(0, node_grid(spec))]
    corners = spec.corners()
    s = [side_fractions(spec, k) for k in range(4)]
    prev = [spec.core_shape.side(corners[0][k], corners[0][(k + 1) % 4], s[k]) for k in range(4)]
    for i, (sh, o) in enumerate(zip(spec.shells, spec.outlines[1:]), start=1):
        t = oh.progression(sh.n_radial, sh.radial_grading)
        c = corners[i]
        cur = [o.side(c[k], c[(k + 1) % 4], s[k]) for k in range(4)]
        out += [(i, oh._ring(prev[k], cur[k], t)) for k in range(4)]
        prev = cur
    return out


def section_cells(spec) -> int:
    """Quads in the section: ``n_width · n_height``, and per shell its ring,
    ``2 (n_width + n_height) · n_radial``."""
    c = side_counts(spec.core_shape)
    return c[0] * c[1] + sum(c) * sum(sh.n_radial for sh in spec.shells)


# ---------------------------------------------------------------------------
# The O-H face an H face pillows into (task 0086, design answer to Q1)
# ---------------------------------------------------------------------------

def wall_distances(spec) -> tuple[np.ndarray, float]:
    """(node distances from the wall, half-extent) along the H face's
    smaller side: its nodes at the wall grading's fractions, from one wall
    to the middle and on.  On a square the ``n_height`` side."""
    shape = spec.core_shape
    k = 0 if shape.half_w < shape.half_h else 1
    half = shape.half_w if k == 0 else shape.half_h
    n = shape.side_count(k, 4)
    g = side_grading(spec, k)
    return 2 * half * (bump(n, g[1]) if g else np.arange(n + 1) / n), half


def pillow_ring(spec, n_radial: int | None = None) -> tuple[int, float]:
    """(n_radial, radial_grading) of the O-H ring an H face pillows into: n_radial (unless
    given) is the number of H cells within one ring thickness t of the
    wall on the smaller side (a cell counts when its midpoint is within
    t; at least 1), and ``radial_grading`` puts the ring's wall cell at the H face's
    wall cell.  A spec's ``radial_grading`` grows from the inner square to the wall,
    so it is the inverse of the progression grown from the wall."""
    d, _ = wall_distances(spec)
    shape = spec.core_shape
    t = oh.ring_thickness(shape.half_w, shape.half_h)
    mids = 0.5 * (d[:-1] + d[1:])
    if n_radial is None:
        n_radial = max(1, int(np.count_nonzero(mids <= t * (1 + 1e-12))))
    if n_radial == 1:
        return 1, 1.0
    return n_radial, 1.0 / progression_for_first_cell(t, n_radial, float(d[1] - d[0]))


def pillowed(spec, n_radial: int | None = None, radial_grading: float | None = None):
    """The O-H spec of the H spec's rectangle: the same name, counts,
    ``arc_bump`` and ``rot``, with *n_radial* and *radial_grading* (``pillow_ring``'s when
    not given).  What a junction's own O-H blocks and its embedded switch
    legs use on an H port (decision 0036 item 5)."""
    from ..core.spec import PipeSpec
    if n_radial is None or radial_grading is None:
        n_radial, dm = pillow_ring(spec, n_radial)
        radial_grading = dm if radial_grading is None else radial_grading
    shape = spec.core_shape
    return PipeSpec(n_width=shape.n_width, n_height=shape.n_height, arc_bump=spec.arc_bump,
                    rot=spec.rot).core(spec.layer_names[0], shape=shape, n_radial=n_radial, radial_grading=radial_grading,
                                       layout="oh")


# ---------------------------------------------------------------------------
# The GMSH face
# ---------------------------------------------------------------------------

def build_h_rect(spec, position, h_axis, v_axis,
                 stretch: tuple | None = None) -> CrossSection:
    """Build *spec*'s H face in GMSH: four corners, four lines and one
    transfinite patch, centred at *position* in the plane of *h_axis* and
    *v_axis*.  Outside an assembly build the sides get their counts and
    wall grading here (inside one, the sweep sets them)."""
    shape = spec.core_shape
    if not isinstance(shape, RectShape):
        raise InternalError(f"the H face needs a rectangle, got {shape.label}")
    cx, cy, cz = (float(c) for c in position)
    xyz = plane(cx, cy, cz, h_axis, v_axis, stretch)
    lvl = levels(spec)[0]
    P = [add_point(*xyz(p)) for p in lvl.corners]                  # NE, NW, SW, SE
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
        layout        = "h",
    )
