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
"""B1 (task 0116): can a sub-partitioned port face share its mesh with a
neighbour whose face isn't cut?

A = [0,1]^3, its face x = 1 one surface (a plain Straight's port).
B1 = [1,2]x[0,.5]x[0,1], B2 = [1,2]x[.5,1]x[0,1]: the same face cut at
y = 0.5 (a sub-partitioned junction port).  Variants:
  occ-fragment  OCC boxes, fragment: shared entities.  Does A stay a
                6-face transfinite volume?
  geo-coherence built-in kernel, A's face and B's two faces distinct
                entities, all transfinite; then removeDuplicateNodes.
                Is the mesh conformal (every interior quad in two hexes)?
  geo-raw       as geo-coherence, without the coherence step.
"""
import json
import sys
from collections import Counter

import gmsh
import numpy as np

N = 4


def faces_of(conn):
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return Counter(tuple(sorted(h[list(q)])) for h in conn for q in f)


def conformity(row):
    ntag, x, _ = gmsh.model.mesh.getNodes()
    types, tags, nodes = gmsh.model.mesh.getElements(3)
    conn = np.concatenate([n.reshape(-1, 8) for t, n in zip(types, nodes) if t == 5])
    cnt = faces_of(conn)
    # outer boundary of [0,2]x[0,1]^2 at N per unit: 2·(2N·N) + 2·(2N·N) + 2·(N·N)
    expected = 2 * (2 * N * N) * 2 + 2 * N * N
    boundary = sum(1 for v in cnt.values() if v == 1)
    row.update({"hexes": int(len(conn)), "nodes": int(len(ntag)),
                "boundary_quads": boundary, "expected_boundary_quads": expected,
                "conformal": boundary == expected})


def run(variant):
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 2)
    row = {"gmsh": gmsh.__version__, "variant": variant}
    try:
        if variant == "occ-fragment":
            occ = gmsh.model.occ
            a = occ.addBox(0, 0, 0, 1, 1, 1)
            b1 = occ.addBox(1, 0, 0, 1, 0.5, 1)
            b2 = occ.addBox(1, 0.5, 0, 1, 0.5, 1)
            out, _ = occ.fragment([(3, a)], [(3, b1), (3, b2)])
            occ.synchronize()
            row["faces_per_volume"] = {v: len(gmsh.model.getBoundary([(3, v)], oriented=False))
                                       for _, v in out}
            gmsh.model.mesh.setTransfiniteAutomatic()
            gmsh.model.mesh.generate(3)
            types = gmsh.model.mesh.getElements(3, a)[0]
            row["A_element_types"] = [gmsh.model.mesh.getElementProperties(t)[0] for t in types]
            conformity(row)
        else:
            geo = gmsh.model.geo
            vols = []
            for (x0, x1, y0, y1) in ((0, 1, 0, 1), (1, 2, 0, 0.5), (1, 2, 0.5, 1)):
                # each box its own entities: B's x = 1 faces aren't A's
                vols.append(_box(geo, x0, x1, y0, y1))
            geo.synchronize()
            msh = gmsh.model.mesh
            for dim, c in gmsh.model.getEntities(1):
                lo = gmsh.model.getBoundingBox(1, c)     # a reproducer: bbox is fine here
                dy = lo[4] - lo[1]
                n = N // 2 if abs(dy - 0.5) < 1e-9 else N
                msh.setTransfiniteCurve(c, n + 1)
            for dim, s in gmsh.model.getEntities(2):
                msh.setTransfiniteSurface(s)
                msh.setRecombine(2, s)
            for v in vols:
                msh.setTransfiniteVolume(v)
            msh.generate(3)
            if variant == "geo-coherence":
                msh.removeDuplicateNodes()
            conformity(row)
        row["ok"] = True
    except Exception as e:
        row["ok"] = False
        row["error"] = str(e)[:300]
    gmsh.finalize()
    print(json.dumps(row), flush=True)


def _box(geo, x0, x1, y0, y1):
    p = {}
    for x in (x0, x1):
        for y in (y0, y1):
            for z in (0, 1):
                p[x, y, z] = geo.addPoint(x, y, z)
    L = lambda a, b: geo.addLine(p[a], p[b])
    e = {}
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for z in (0, 1):
        for i in range(4):
            a, b = corners[i], corners[(i + 1) % 4]
            e[z, i] = L((*a, z), (*b, z))
    for i, c in enumerate(corners):
        e["v", i] = L((*c, 0), (*c, 1))
    S = lambda loop: geo.addPlaneSurface([geo.addCurveLoop(loop)])
    surfs = [S([e[0, 0], e[0, 1], e[0, 2], e[0, 3]]), S([e[1, 0], e[1, 1], e[1, 2], e[1, 3]])]
    for i in range(4):
        surfs.append(S([e[0, i], e["v", (i + 1) % 4], -e[1, i], -e["v", i]]))
    return geo.addVolume([geo.addSurfaceLoop(surfs)])


if __name__ == "__main__":
    for v in sys.argv[1:] or ["occ-fragment", "geo-raw", "geo-coherence"]:
        run(v)
