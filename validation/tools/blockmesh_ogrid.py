"""
Independent ``blockMesh`` O-grid of a circular pipe with radius R(x), for
checking whether an OpenFOAM behaviour comes from hexmesh's mesh or from
the case.  It reproduces hexmesh's single-layer O-H section (a centre
square with corners at ``ratio · r`` on the diagonals, four ring blocks,
uniform counts) at given axial stations, one block per axial cell, so its
cell count equals hexmesh's for the same counts.

    import importlib.util                      # validation/ is not a package
    spec = importlib.util.spec_from_file_location(
        "blockmesh_ogrid", "validation/tools/blockmesh_ogrid.py")
    bm = importlib.util.module_from_spec(spec); spec.loader.exec_module(bm)
    xs = bm.stations_from_case(hexmesh_case)   # axial nodes on the axis
    text = bm.block_mesh_dict(xs, radius=lambda x: 0.01, nang=12, nrad=6)
    (case / "system/blockMeshDict").write_text(header + text)

Patches: ``{prefix}inlet``, ``{prefix}outlet`` (type patch) and
``{prefix}wall`` (type wall), as hexmesh names a single ``fluid`` layer.
Used by the design session on 2026-10-29 (docs/integrations/openfoam.md,
the stenosis SIMPLE check).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

import numpy as np


def stations_from_case(case: Path) -> np.ndarray:
    """Axial node positions of an OpenFOAM case's mesh: the x of points on
    the axis (y = z = 0), sorted."""
    from hexmesh.study import openfoam as of
    pts = of.read_points(Path(case) / "constant/polyMesh/points")
    on_axis = np.hypot(pts[:, 1], pts[:, 2]) < 1e-9
    return np.unique(np.round(pts[on_axis, 0], 12))


def block_mesh_dict(xs, radius: Callable[[float], float], nang: int, nrad: int,
                    ratio: float = 0.6, prefix: str = "fluid_") -> str:
    """The body of a blockMeshDict (no FoamFile header): an O-grid along x
    through the stations *xs*, wall radius ``radius(x)``, ``nang`` cells per
    side and ``nrad`` across the ring."""
    th = [math.radians(45 + 90 * k) for k in range(4)]
    verts, vid = [], {}
    for j, x in enumerate(xs):
        r = float(radius(x))
        for k in range(4):
            for kind, rad in (("S", ratio * r), ("W", r)):
                vid[(kind, j, k)] = len(verts)
                verts.append((x, rad * math.cos(th[k]), rad * math.sin(th[k])))

    def V(kind, j, k):
        return vid[(kind, j, k % 4)]

    blocks, arcs, inlet, outlet, wall = [], [], [], [], []
    for j in range(len(xs) - 1):
        c = [V("S", j, k) for k in range(4)] + [V("S", j + 1, k) for k in range(4)]
        blocks.append(f"hex ({' '.join(map(str, c))}) ({nang} {nang} 1) simpleGrading (1 1 1)")
        for k in range(4):
            b = [V("S", j, k), V("W", j, k), V("W", j, k + 1), V("S", j, k + 1)]
            t = [V("S", j + 1, k), V("W", j + 1, k), V("W", j + 1, k + 1), V("S", j + 1, k + 1)]
            blocks.append(f"hex ({' '.join(map(str, b + t))}) ({nrad} {nang} 1) simpleGrading (1 1 1)")
            wall.append((V("W", j, k), V("W", j, k + 1), V("W", j + 1, k + 1), V("W", j + 1, k)))
    for j, x in enumerate(xs):
        r = float(radius(x))
        for k in range(4):
            a = math.radians(90 + 90 * k)
            arcs.append(f"arc {V('W', j, k)} {V('W', j, k + 1)} "
                        f"({x} {r * math.cos(a)} {r * math.sin(a)})")
    last = len(xs) - 1
    inlet.append((V("S", 0, 0), V("S", 0, 3), V("S", 0, 2), V("S", 0, 1)))
    outlet.append(tuple(V("S", last, k) for k in range(4)))
    for k in range(4):
        inlet.append((V("S", 0, k), V("S", 0, k + 1), V("W", 0, k + 1), V("W", 0, k)))
        outlet.append((V("S", last, k), V("W", last, k), V("W", last, k + 1), V("S", last, k + 1)))

    def patch(name, kind, faces):
        rows = "\n".join(f"            ({' '.join(map(str, q))})" for q in faces)
        return (f"    {prefix}{name}\n    {{\n        type {kind};\n        faces\n"
                f"        (\n{rows}\n        );\n    }}\n")

    return ("scale 1;\nvertices\n(\n"
            + "\n".join(f"    ({x:.12g} {y:.12g} {z:.12g})" for x, y, z in verts)
            + "\n);\nblocks\n(\n" + "\n".join("    " + b for b in blocks)
            + "\n);\nedges\n(\n" + "\n".join("    " + a for a in arcs)
            + "\n);\nboundary\n(\n"
            + patch("inlet", "patch", inlet) + patch("outlet", "patch", outlet)
            + patch("wall", "wall", wall)
            + ");\nmergePatchPairs ();\n")
