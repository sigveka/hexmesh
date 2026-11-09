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
"""B2 (task 0116): a transfinite hex volume with one side made of two
surfaces.  Unit box, built-in kernel; the top face (z = 1) is split at
x = 0.5 into two quads, so the volume has 7 faces.  Variants:
  six       - control: the top one 6-sided surface, a 6-face volume
  plain     - both halves transfinite, no compound
  compound  - setCompound on the two halves (and the split top curves)
  recombine - compound + recombined compound surface
Prints one JSON line per variant: ok/error, element types, hex count,
whether the nodes form the expected n^3 grid."""
import json
import sys

import gmsh
import numpy as np

N = 4          # cells per side


def build(variant):
    gmsh.model.add(variant)
    geo = gmsh.model.geo
    P = {}
    for x in (0, 1):
        for y in (0, 1):
            for z in (0, 1):
                P[x, y, z] = geo.addPoint(x, y, z)
    P["m0"] = geo.addPoint(0.5, 0, 1)
    P["m1"] = geo.addPoint(0.5, 1, 1)
    L = lambda a, b: geo.addLine(P[a], P[b])
    # bottom
    b0, b1, b2, b3 = L((0, 0, 0), (1, 0, 0)), L((1, 0, 0), (1, 1, 0)), L((1, 1, 0), (0, 1, 0)), L((0, 1, 0), (0, 0, 0))
    # verticals
    v00, v10, v11, v01 = L((0, 0, 0), (0, 0, 1)), L((1, 0, 0), (1, 0, 1)), L((1, 1, 0), (1, 1, 1)), L((0, 1, 0), (0, 1, 1))
    # top, split at x = 0.5
    tf0, tf1 = L((0, 0, 1), "m0"), L("m0", (1, 0, 1))            # front top (y = 0)
    tb0, tb1 = L((0, 1, 1), "m1"), L("m1", (1, 1, 1))            # back top (y = 1)
    t_r, t_l, t_m = L((1, 0, 1), (1, 1, 1)), L((0, 1, 1), (0, 0, 1)), L("m0", "m1")
    S = lambda curves: geo.addPlaneSurface([geo.addCurveLoop(curves)])
    bottom = S([b0, b1, b2, b3])
    front = S([b0, v10, -tf1, -tf0, -v00])
    right = S([b1, v11, -t_r, -v10])
    back = S([b2, v01, tb0, tb1, -v11])
    left = S([b3, v00, -t_l, -v01])
    if variant == "six":          # control: the top one surface (6 faces)
        top0 = S([tf0, tf1, t_r, -tb1, -tb0, t_l])
        top1 = None
    else:
        top0 = S([tf0, t_m, -tb0, t_l])
        top1 = S([tf1, t_r, -tb1, -t_m])
    tops = [s for s in (top0, top1) if s is not None]
    vol = geo.addVolume([geo.addSurfaceLoop([bottom, front, right, back, left] + tops)])
    geo.synchronize()
    msh = gmsh.model.mesh
    for c in (b0, b1, b2, b3, v00, v10, v11, v01, t_r, t_l, t_m):
        msh.setTransfiniteCurve(c, N + 1)
    for c in (tf0, tf1, tb0, tb1):
        msh.setTransfiniteCurve(c, N // 2 + 1)
    corners_top = {"front": [P[0, 0, 0], P[1, 0, 0], P[1, 0, 1], P[0, 0, 1]],
                   "back": [P[1, 1, 0], P[0, 1, 0], P[0, 1, 1], P[1, 1, 1]]}
    msh.setTransfiniteSurface(bottom)
    msh.setTransfiniteSurface(right)
    msh.setTransfiniteSurface(left)
    msh.setTransfiniteSurface(front, cornerTags=corners_top["front"])
    msh.setTransfiniteSurface(back, cornerTags=corners_top["back"])
    if variant == "six":
        msh.setTransfiniteSurface(top0, cornerTags=[P[0, 0, 1], P[1, 0, 1], P[1, 1, 1], P[0, 1, 1]])
    else:
        msh.setTransfiniteSurface(top0)
        msh.setTransfiniteSurface(top1)
    if variant in ("compound", "recombine"):
        msh.setCompound(1, [tf0, tf1])
        msh.setCompound(1, [tb0, tb1])
        msh.setCompound(2, [top0, top1])
    for s in [bottom, front, right, back, left] + tops:
        msh.setRecombine(2, s)
    msh.setTransfiniteVolume(vol, cornerTags=[P[0, 0, 0], P[1, 0, 0], P[1, 1, 0], P[0, 1, 0],
                                              P[0, 0, 1], P[1, 0, 1], P[1, 1, 1], P[0, 1, 1]])
    return vol


def run(variant):
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 2)
    row = {"gmsh": gmsh.__version__, "variant": variant}
    try:
        vol = build(variant)
        if variant == "recombine":
            gmsh.option.setNumber("Mesh.CompoundClassify", 0)
        gmsh.model.mesh.generate(3)
        types, tags, nodes = gmsh.model.mesh.getElements(3, vol)
        row["element_types"] = [gmsh.model.mesh.getElementProperties(t)[0] for t in types]
        hexes = sum(len(t) for ty, t in zip(types, tags) if ty == 5)
        row["hexes"] = hexes
        ntag, x, _ = gmsh.model.mesh.getNodes(3, vol, includeBoundary=True)
        x = x.reshape(-1, 3)
        grid = np.allclose(np.round(x * N), x * N, atol=1e-9)
        row["nodes"] = len(x)
        row["structured"] = bool(hexes == N ** 3 and len(x) == (N + 1) ** 3 and grid)
        row["ok"] = True
    except Exception as e:
        row["ok"] = False
        row["error"] = str(e)[:300]
    gmsh.finalize()
    print(json.dumps(row), flush=True)


if __name__ == "__main__":
    for v in sys.argv[1:] or ["six", "plain", "compound", "recombine"]:
        run(v)
