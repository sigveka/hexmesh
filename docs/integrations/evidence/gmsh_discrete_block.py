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
"""B3 (task 0117): can a block of hexes whose nodes we write ourselves sit
between two transfinite OCC straights, conformal by construction?

Two OCC straights (the 5-patch O-H section, nang 4, nrad 2) along z, with a
gap of one slab between them, are meshed by gmsh's transfinite meshing.
The gap is then filled with hexes written by hand: the port-face nodes are
read back from the straights' port surfaces and reused by tag; only the
interior nodes are new.  The block is a discrete volume; its wall a
discrete surface carrying quads.  Variants:
  bounded    the discrete volume declares the OCC port surfaces and its
             discrete wall as its boundary (the tutorial x2 way, which x2
             says OCC doesn't support)
  unbounded  no declared boundary: the hexes only reference the port
             surfaces' node tags

Usage, from the repository root:
  python3 docs/integrations/evidence/gmsh_discrete_block.py OUTDIR [--foam]
Writes OUTDIR/<variant>.{22,41}.msh, then again under OUTDIR/again/ and
compares the bytes, and prints one JSON row per variant, then one per
step-5 note (setOrder(2), refine, a second generate(3)).  With --foam
(and PYTHONPATH=.), converts each 2.2 file with gmshToFoam
-keepOrientation and runs checkMesh, on OpenFOAM v2406 in Docker
(hexmesh.study.openfoam).  Delete OUTDIR after.
"""
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import gmsh
import numpy as np

R, CORE = 1.0, 0.45            # pipe radius; core square half-diagonal / R
NANG, NRAD, NAX = 4, 2, 3      # per 90° arc, across the ring, axial per straight
L, GAP, NGAP = 2.0, 0.5, 4     # straight length, gap, written slabs in the gap
HEX_FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


def straight(z0):
    """The O-H straight from z0 to z0 + L: five OCC volumes, one shell."""
    occ = gmsh.model.occ
    c = CORE * R
    sq = [occ.addPoint(c * math.cos(a), c * math.sin(a), z0)
          for a in np.radians([45, 135, 225, 315])]
    rim = [occ.addPoint(R * math.cos(a), R * math.sin(a), z0)
           for a in np.radians([45, 135, 225, 315])]
    o = occ.addPoint(0, 0, z0)
    side = [occ.addLine(sq[i], sq[(i + 1) % 4]) for i in range(4)]
    arc = [occ.addCircleArc(rim[i], o, rim[(i + 1) % 4]) for i in range(4)]
    spoke = [occ.addLine(sq[i], rim[i]) for i in range(4)]
    faces = [occ.addPlaneSurface([occ.addCurveLoop(side)])]
    for i in range(4):
        j = (i + 1) % 4
        faces.append(occ.addPlaneSurface([occ.addCurveLoop([side[i], spoke[j], -arc[i], -spoke[i]])]))
    out = occ.extrude([(2, f) for f in faces], 0, 0, L)
    vols = [t for d, t in out if d == 3]
    occ.remove([(0, o)])
    return vols


def build():
    occ = gmsh.model.occ
    a = straight(0.0)
    b = straight(L + GAP)
    out, _ = occ.fragment([(3, v) for v in a], [(3, v) for v in b])  # shares faces within each
    occ.synchronize()
    msh = gmsh.model.mesh
    for _, cv in gmsh.model.getEntities(1):
        lo = np.array(gmsh.model.getBoundingBox(1, cv))
        dx, dy, dz = lo[3:] - lo[:3]
        p0, p1 = (gmsh.model.getValue(0, t, []) for t in
                  (abs(x[1]) for x in gmsh.model.getBoundary([(1, cv)])))
        if dz > 1e-6:
            n = NAX
        elif abs(np.linalg.norm(p0[:2]) - np.linalg.norm(p1[:2])) > 1e-9:
            n = NRAD
        else:
            n = NANG
        msh.setTransfiniteCurve(cv, n + 1)
    for _, s in gmsh.model.getEntities(2):
        msh.setTransfiniteSurface(s)
        msh.setRecombine(2, s)
    for _, v in gmsh.model.getEntities(3):
        msh.setTransfiniteVolume(v)
    msh.generate(3)
    return [v for _, v in out]


def at_z(z, dim=2):
    """The surfaces lying in the plane z."""
    return [t for _, t in gmsh.model.getEntities(dim)
            if abs(gmsh.model.getBoundingBox(dim, t)[2] - z) < 1e-6
            and abs(gmsh.model.getBoundingBox(dim, t)[5] - z) < 1e-6]


def walls_of(vols):
    out = set()
    for _, s in gmsh.model.getBoundary([(3, v) for v in vols], oriented=False):
        x0, y0, z0, x1, y1, z1 = gmsh.model.getBoundingBox(2, s)
        if z1 - z0 > 1e-6 and max(abs(x0), abs(y0), abs(x1), abs(y1)) > CORE * R * 1.01:
            # lateral and reaching the rim: a ring patch's outer face
            pts = gmsh.model.mesh.getNodes(2, s, includeBoundary=True)[1].reshape(-1, 3)
            if np.allclose(np.hypot(pts[:, 0], pts[:, 1]), R, atol=1e-6):
                out.add(s)
    return sorted(out)


def write_block(variant, port_a, port_b, vols):
    """The written hexes between the ports at z = L and z = L + GAP."""
    msh = gmsh.model.mesh
    quads = []
    for s in port_a:
        for t, _, n in zip(*msh.getElements(2, s)):
            assert t == 3
            quads.append(n.reshape(-1, 4))
    quads = np.concatenate(quads)
    a_tags, a_x = [], []
    for s in port_a:
        t, x, _ = msh.getNodes(2, s, includeBoundary=True)
        a_tags += list(t); a_x += list(x.reshape(-1, 3))
    b_by_xy = {}
    for s in port_b:
        t, x, _ = msh.getNodes(2, s, includeBoundary=True)
        for tag, p in zip(t, x.reshape(-1, 3)):
            b_by_xy[(round(p[0], 9), round(p[1], 9))] = int(tag)
    a = dict(zip(map(int, a_tags), np.array(a_x)))
    # one column of nodes per port node: level 0 is A's, level NGAP is B's
    nxt = int(msh.getMaxNodeTag()) + 1
    col, new = {}, {}
    rim = {t for t, p in a.items() if abs(np.hypot(p[0], p[1]) - R) < 1e-9}
    for t, p in a.items():
        col[t] = [t]
        for k in range(1, NGAP):
            z = L + GAP * k / NGAP          # straight interpolation: plain TFI here
            new[nxt] = (np.array([p[0], p[1], z]), t in rim)
            col[t].append(nxt); nxt += 1
        col[t].append(b_by_xy[(round(p[0], 9), round(p[1], 9))])
    # the discrete entities
    wall = gmsh.model.addDiscreteEntity(2)
    bnd = (port_a + port_b + [wall]) if variant == "bounded" else []
    vol = gmsh.model.addDiscreteEntity(3, -1, bnd)
    wt = [t for t, (p, r) in new.items() if r]
    vt = [t for t, (p, r) in new.items() if not r]
    msh.addNodes(2, wall, wt, np.array([new[t][0] for t in wt]).ravel())
    msh.addNodes(3, vol, vt, np.array([new[t][0] for t in vt]).ravel())
    hexes = []
    for q in quads:
        for k in range(NGAP):
            h = [col[int(t)][k] for t in q] + [col[int(t)][k + 1] for t in q]
            p = np.array([coord(t, a, new) for t in h])
            if np.dot(np.cross(p[1] - p[0], p[3] - p[0]), p[4] - p[0]) < 0:
                h = h[:4][::-1] + h[4:][::-1]
            hexes.append(h)
    hexes = np.array(hexes, dtype=np.int64)
    etag = int(msh.getMaxElementTag()) + 1
    msh.addElementsByType(vol, 5, list(range(etag, etag + len(hexes))), hexes.ravel().tolist())
    # wall quads: each rim edge of A's port, swept across the gap
    edges = Counter()
    for q in quads:
        for i in range(4):
            e = (int(q[i]), int(q[(i + 1) % 4]))
            if e[0] in rim and e[1] in rim:
                edges[tuple(sorted(e))] += 1
    wq = [[col[u][k], col[v][k], col[v][k + 1], col[u][k + 1]]
          for (u, v) in edges for k in range(NGAP)]
    etag += len(hexes)
    msh.addElementsByType(wall, 3, list(range(etag, etag + len(wq))), np.ravel(wq).tolist())
    return vol, wall, len(hexes), len(new)


def coord(t, a, new):
    if t in new:
        return new[t][0]
    return gmsh.model.mesh.getNode(int(t))[0]


def min_sj(hex_xyz):
    """Min corner scaled Jacobian of hexes (n, 8, 3), gmsh order."""
    nb = {0: (1, 3, 4), 1: (2, 0, 5), 2: (3, 1, 6), 3: (0, 2, 7),
          4: (7, 5, 0), 5: (4, 6, 1), 6: (5, 7, 2), 7: (6, 4, 3)}
    out = np.inf
    for c, (i, j, k) in nb.items():
        e = [hex_xyz[:, m] - hex_xyz[:, c] for m in (i, j, k)]
        e = [v / np.linalg.norm(v, axis=1)[:, None] for v in e]
        out = min(out, float(np.einsum("ij,ij->i", np.cross(e[0], e[1]), e[2]).min()))
    return out


def conformity(row, inlet, outlet, walls):
    msh = gmsh.model.mesh
    types, _, nodes = msh.getElements(3)
    conn = np.concatenate([n.reshape(-1, 8) for t, n in zip(types, nodes) if t == 5])
    cnt = Counter(tuple(sorted(h[list(q)])) for h in conn for q in HEX_FACES)
    boundary = sum(1 for v in cnt.values() if v == 1)
    nq = sum(len(msh.getElements(2, s)[1][0]) for s in inlet + outlet + walls)
    tags, x, _ = msh.getNodes()
    pos = {int(t): i for i, t in enumerate(tags)}
    xyz = x.reshape(-1, 3)[[pos[int(t)] for t in conn.ravel()]].reshape(-1, 8, 3)
    row.update({"hexes": int(len(conn)), "boundary_quads": boundary,
                "boundary_quads_expected": int(nq), "conformal": boundary == nq,
                "faces_in_3_or_more_hexes": sum(1 for v in cnt.values() if v > 2),
                "min_sj": round(min_sj(xyz), 6)})


def notes():
    """Step 5: what setOrder(2), refine() and a second generate(3) do with
    the written block (unbounded variant)."""
    rows = []
    for op in ("order2", "refine", "regenerate"):
        gmsh.initialize()
        gmsh.option.setNumber("General.Verbosity", 2)
        row = {"gmsh": gmsh.__version__, "note": op}
        build()
        vols = [t for _, t in gmsh.model.getEntities(3)]
        vol, wall, _, _ = write_block("unbounded", at_z(L), at_z(L + GAP), vols)
        msh = gmsh.model.mesh
        if op == "order2":
            msh.setOrder(2)
            row["block_types"] = [msh.getElementProperties(int(a))[0]
                                  for a in msh.getElements(3, vol)[0]]
            for name, s in (("block_wall", wall), ("straight_wall", walls_of(vols)[0])):
                t, _, n = msh.getElements(2, s)
                k = msh.getElementProperties(int(t[0]))[3]
                ho = np.unique(n[0].reshape(-1, k)[:, 4:].ravel())
                x = np.array([msh.getNode(int(q))[0] for q in ho])
                rr = np.hypot(x[:, 0], x[:, 1])
                row[f"{name}_high_order_radius"] = [round(float(rr.min()), 5),
                                                    round(float(rr.max()), 5)]
        else:
            msh.refine() if op == "refine" else msh.generate(3)
            conformity(row, at_z(0.0), at_z(2 * L + GAP), walls_of(vols) + [wall])
        row["nodes"] = int(len(msh.getNodes()[0]))
        rows.append(row)
        gmsh.finalize()
    return rows


def foam(outdir, variant):
    """gmshToFoam -keepOrientation (min SJ > 0, task 0108) and checkMesh on
    OpenFOAM v2406, with would_invert first."""
    import re
    from hexmesh.study import openfoam as F
    F.set_runner(F.V2406)
    msh = (Path(outdir) / f"{variant}.22.msh").resolve()
    case = Path(outdir) / f"case_{variant}"
    hdr = "FoamFile { version 2.0; format ascii; class dictionary; object %s; }\n"
    (case / "system").mkdir(parents=True, exist_ok=True)
    (case / "system/controlDict").write_text(hdr % "controlDict" + (
        "application icoFoam; startFrom startTime; startTime 0; stopAt endTime; endTime 1; "
        "deltaT 1; writeControl timeStep; writeInterval 1; writeFormat ascii; "
        "writeCompression off;\n"), encoding="utf-8", newline="\n")
    (case / "system/fvSchemes").write_text(hdr % "fvSchemes" + (
        "ddtSchemes {default Euler;} gradSchemes {default Gauss linear;} "
        "divSchemes {default none;} laplacianSchemes {default Gauss linear corrected;} "
        "interpolationSchemes {default linear;} snGradSchemes {default corrected;}\n"), encoding="utf-8", newline="\n")
    (case / "system/fvSolution").write_text(hdr % "fvSolution" + "solvers {}\n", encoding="utf-8", newline="\n")
    row = {"variant": variant, "would_invert": F.would_invert(msh)}
    F.foam(f"gmshToFoam -keepOrientation {msh}", case, "log.gmshToFoam", mounts=[msh.parent])
    out = F.foam("checkMesh", case, "log.checkMesh")
    row.update({
        "openfoam": (re.findall(r"Version:\s*(\S+)", out) or ["?"])[0],
        "mesh_ok": "Mesh OK." in out, "failed_checks": re.findall(r"\*\*\*.*", out),
        "cells": int(re.search(r"cells:\s+(\d+)", out).group(1)),
        "points": int(re.search(r"points:\s+(\d+)", out).group(1)),
        "regions": int(re.search(r"Number of regions: (\d+)", out).group(1)),
        "patches": dict((m[0], int(m[1])) for m in re.findall(
            r"^\s{4}(\w+)\s+(\d+)\s+\d+\s+ok", out, re.M)),
        "cell_zones": re.findall(r"^\s{4}(\w+)\s+\d+\s+\d+\s+[\d.]+\s+\(", out, re.M),
        "max_non_orthogonality": float(re.search(r"non-orthogonality Max: ([\d.e+-]+)",
                                                 out).group(1))})
    return row


def run(variant, outdir):
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 2)
    row = {"gmsh": gmsh.__version__, "variant": variant}
    try:
        build()
        msh = gmsh.model.mesh
        vols = [t for _, t in gmsh.model.getEntities(3)]
        n_straights = len(msh.getNodes()[0])
        port_a, port_b = at_z(L), at_z(L + GAP)
        inlet, outlet = at_z(0.0), at_z(2 * L + GAP)
        walls = walls_of(vols)
        vol, wall, nh, nnew = write_block(variant, port_a, port_b, vols)
        row.update({"straight_nodes": n_straights, "block_interior_nodes": nnew,
                    "block_hexes": nh, "total_nodes": int(len(msh.getNodes()[0])),
                    "node_count_ok": int(len(msh.getNodes()[0])) == n_straights + nnew})
        row["volume_boundary_declared"] = sorted(
            abs(t) for _, t in gmsh.model.getBoundary([(3, vol)], oriented=False))
        conformity(row, inlet, outlet, walls + [wall])
        gmsh.model.addPhysicalGroup(3, vols + [vol], name="fluid")
        gmsh.model.addPhysicalGroup(2, inlet, name="fluid_inlet")
        gmsh.model.addPhysicalGroup(2, outlet, name="fluid_outlet")
        gmsh.model.addPhysicalGroup(2, walls + [wall], name="wall")
        digests = {}
        for ver in ("2.2", "4.1"):
            gmsh.option.setNumber("Mesh.MshFileVersion", float(ver))
            gmsh.option.setNumber("Mesh.Binary", 0)
            p = Path(outdir) / f"{variant}.{ver.replace('.', '')}.msh"
            gmsh.write(str(p))
            digests[ver] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        row["sha256"] = digests
        # read back: does a fresh gmsh see the same hexes?
        gmsh.clear()
        gmsh.open(str(Path(outdir) / f"{variant}.41.msh"))
        types, _, nodes = gmsh.model.mesh.getElements(3)
        row["reread_41_hexes"] = int(sum(len(n) // 8 for t, n in zip(types, nodes) if t == 5))
        row["reread_41_volumes"] = [t for _, t in gmsh.model.getEntities(3)]
    except Exception as e:
        row["error"] = f"{type(e).__name__}: {e}"
    gmsh.finalize()
    return row


if __name__ == "__main__":
    outdir = Path(sys.argv[1])
    again = outdir / "again"
    again.mkdir(parents=True, exist_ok=True)
    for v in ("unbounded", "bounded"):
        row = run(v, outdir)
        run(v, again)
        row["byte_identical_rerun"] = all(
            (outdir / f"{v}.{x}.msh").read_bytes() == (again / f"{v}.{x}.msh").read_bytes()
            for x in ("22", "41"))
        print(json.dumps(row))
    for row in notes():
        print(json.dumps(row))
    if "--foam" in sys.argv:
        for v in ("unbounded", "bounded"):
            print(json.dumps(foam(outdir, v)))
