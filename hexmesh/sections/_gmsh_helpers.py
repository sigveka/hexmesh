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
Internal GMSH helpers shared by the section builders (``sections.oh_gmsh``).

These are thin wrappers around the gmsh.model.occ API that
reduce boilerplate and centralise entity creation.
"""

from __future__ import annotations

import numpy as np

from .._gmsh import gmsh
from .. import _occ
from .._occ import conic_arc as add_conic_arc     # noqa: F401  (oh_gmsh's name)


def add_physical_group(dim: int, tags: list[int], name: str) -> int:
    """Add a Physical group and assign its name (compatible with gmsh 4.3+)."""
    tag = gmsh.model.addPhysicalGroup(dim, tags)
    gmsh.model.setPhysicalName(dim, tag, name)
    return tag


def add_point(x: float, y: float, z: float, lc: float) -> int:
    return gmsh.model.occ.addPoint(x, y, z, lc)


def add_line(start: int, end: int) -> int:
    return _occ.line(start, end)


def add_arc(start: int, center: int, end: int) -> int:
    return _occ.circle_arc(start, center, end)


def stretched(p, centre, stretch):
    """Image of point *p* under *stretch* ``(b, s)`` about *centre*."""
    if stretch is None:
        return p
    b, s = stretch
    return p + (s - 1.0) * b * float((p - centre) @ b)


def plane(cx, cy, cz, h_axis, v_axis, stretch):
    """In-plane ``(u, v)``, ``rot`` applied (``sections.oh``, ``sections.h``) → 3-D tuple."""
    centre = np.array([cx, cy, cz])
    h, v = np.asarray(h_axis, dtype=float), np.asarray(v_axis, dtype=float)

    def xyz(p):
        q = stretched(centre + p[0] * h + p[1] * v, centre, stretch)
        return float(q[0]), float(q[1]), float(q[2])
    return xyz


def add_line_loop(tags: list[int]) -> int:
    return gmsh.model.occ.addCurveLoop(tags)


def add_surface(loop: int) -> int:
    return gmsh.model.occ.addPlaneSurface([loop])


def set_transfinite_line(tags: list[int], n: int, progression: float = 1.0) -> None:
    """Apply Transfinite Line with Progression to a list of curve tags.

    These four helpers do nothing inside ``_occ.building()``.
    """
    if _occ.in_build:
        return
    gmsh.model.occ.synchronize()   # OCC: entities must exist before mesh constraints
    for t in tags:
        gmsh.model.mesh.setTransfiniteCurve(t, n + 1, "Progression", progression)


def set_transfinite_line_bump(tags: list[int], n: int, bump: float = 1.0) -> None:
    """Apply Transfinite Line with Bump to a list of curve tags."""
    if _occ.in_build:
        return
    gmsh.model.occ.synchronize()
    for t in tags:
        gmsh.model.mesh.setTransfiniteCurve(t, n + 1, "Bump", bump)


def set_transfinite_curve(tag: int, n: int, kind: str = "Progression",
                          coef: float = 1.0) -> None:
    """Transfinite curve *tag* of *n* divisions, any gmsh law."""
    if _occ.in_build:
        return
    gmsh.model.occ.synchronize()
    gmsh.model.mesh.setTransfiniteCurve(tag, n + 1, kind, coef)


def set_transfinite_surface(tags: list[int]) -> None:
    if _occ.in_build:
        return
    gmsh.model.occ.synchronize()
    for t in tags:
        gmsh.model.mesh.setTransfiniteSurface(t)


def set_recombine_surface(tags: list[int]) -> None:
    if _occ.in_build:
        return
    gmsh.model.occ.synchronize()
    for t in tags:
        gmsh.model.mesh.setRecombine(2, t)
