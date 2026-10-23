"""
Internal GMSH helper utilities shared by all face builders.

These are thin wrappers around the gmsh.model.occ API that
reduce boilerplate and centralise entity creation.
"""

from __future__ import annotations
import gmsh


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
    return geo.addLine(start, end)


def add_arc(start: int, center: int, end: int) -> int:
    return geo.addCircleArc(start, center, end)


def add_line_loop(tags: list[int]) -> int:
    return geo.addCurveLoop(tags)


def add_surface(loop: int) -> int:
    return geo.addPlaneSurface([loop])


def set_transfinite_line(tags: list[int], n: int, progression: float = 1.0) -> None:
    """Apply Transfinite Line with Progression to a list of curve tags."""
    geo.synchronize()   # OCC: entities must exist before mesh constraints
    for t in tags:
        mesh.setTransfiniteCurve(t, n + 1, "Progression", progression)


def set_transfinite_line_bump(tags: list[int], n: int, bump: float = 1.0) -> None:
    """Apply Transfinite Line with Bump to a list of curve tags."""
    geo.synchronize()
    for t in tags:
        mesh.setTransfiniteCurve(t, n + 1, "Bump", bump)


def set_transfinite_surface(tags: list[int]) -> None:
    geo.synchronize()
    for t in tags:
        mesh.setTransfiniteSurface(t)


def set_recombine_surface(tags: list[int]) -> None:
    geo.synchronize()
    for t in tags:
        mesh.setRecombine(2, t)
