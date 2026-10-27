"""
Internal GMSH helper utilities shared by all face builders.

These are thin wrappers around the gmsh.model.occ API that
reduce boilerplate and centralise entity creation.
"""

from __future__ import annotations
import math

import gmsh
import numpy as np

from .. import _occ


geo  = gmsh.model.occ
mesh = gmsh.model.mesh


def add_physical_group(dim: int, tags: list[int], name: str) -> int:
    """Add a Physical group and assign its name (compatible with gmsh 4.3+)."""
    tag = gmsh.model.addPhysicalGroup(dim, tags)
    gmsh.model.setPhysicalName(dim, tag, name)
    return tag


def add_point(x: float, y: float, z: float, lc: float) -> int:
    return geo.addPoint(x, y, z, lc)


def add_line(start: int, end: int) -> int:
    return _occ.line(start, end)


def add_arc(start: int, center: int, end: int) -> int:
    return _occ.circle_arc(start, center, end)


def add_conic_arc(start: int, center: int, end: int, center_xyz,
                  stretch=None) -> int:
    """Circular arc about *center*, or its image under *stretch*.

    *stretch* ``(b, s)`` scales the plane by ``s`` along the unit vector
    ``b`` about the face centre; *center_xyz* is the (stretched) arc
    centre.  The stretched arc is the circle arc's exact rational quadratic
    B-spline with stretched control points (NURBS are affine invariant), so
    it is the exact ellipse arc and reuses the end-point tags.  OCC's
    ``addEllipseArc`` cannot be used: it rejects arcs whose end points are
    symmetric about the major axis.
    """
    if stretch is None or stretch[1] == 1.0:
        return _occ.circle_arc(start, center, end)
    b, s = np.asarray(stretch[0], dtype=float), float(stretch[1])

    def unstretch(p):
        return p - (1.0 - 1.0 / s) * b * float((p - c) @ b)

    c = np.asarray(center_xyz, dtype=float)
    def coords(t):   # OCC pads boxes by its tolerance; the centre is exact
        bb = np.asarray(geo.getBoundingBox(0, t))
        return 0.5 * (bb[:3] + bb[3:])

    p0, p2 = coords(start), coords(end)
    u0, u2 = unstretch(p0) - c, unstretch(p2) - c
    cos_d = float(u0 @ u2) / float(np.linalg.norm(u0) * np.linalg.norm(u2))
    m = c + (u0 + u2) / (1.0 + cos_d)                 # tangent intersection
    m = m + (s - 1.0) * b * float((m - c) @ b)        # stretch it back
    mid = geo.addPoint(*m)
    tag = _occ.bspline([start, mid, end], degree=2,
                         weights=[1.0, math.sqrt((1.0 + cos_d) / 2.0), 1.0],
                         knots=[0.0, 1.0], multiplicities=[3, 3])
    _occ.discard(mid)
    return tag


def stretched(p, centre, stretch):
    """Image of point *p* under *stretch* ``(b, s)`` about *centre*."""
    if stretch is None:
        return p
    b, s = stretch
    return p + (s - 1.0) * b * float((p - centre) @ b)


def add_line_loop(tags: list[int]) -> int:
    return geo.addCurveLoop(tags)


def add_surface(loop: int) -> int:
    return geo.addPlaneSurface([loop])


def set_transfinite_line(tags: list[int], n: int, progression: float = 1.0) -> None:
    """Apply Transfinite Line with Progression to a list of curve tags.

    These four helpers do nothing inside ``_occ.building()``.
    """
    if _occ.in_build:
        return
    geo.synchronize()   # OCC: entities must exist before mesh constraints
    for t in tags:
        mesh.setTransfiniteCurve(t, n + 1, "Progression", progression)


def set_transfinite_line_bump(tags: list[int], n: int, bump: float = 1.0) -> None:
    """Apply Transfinite Line with Bump to a list of curve tags."""
    if _occ.in_build:
        return
    geo.synchronize()
    for t in tags:
        mesh.setTransfiniteCurve(t, n + 1, "Bump", bump)


def set_transfinite_surface(tags: list[int]) -> None:
    if _occ.in_build:
        return
    geo.synchronize()
    for t in tags:
        mesh.setTransfiniteSurface(t)


def set_recombine_surface(tags: list[int]) -> None:
    if _occ.in_build:
        return
    geo.synchronize()
    for t in tags:
        mesh.setRecombine(2, t)
