"""
Ring quality against outline aspect ratio (decision 0026 item 4, task 0047).
Not part of the test suite.

    python3 benchmarks/outline_quality.py                      # full sweep
    python3 benchmarks/outline_quality.py --json out.json --md out.md
    python3 benchmarks/outline_quality.py --aspects 1 4 --gaps 0.3 --nang 4

Three pairings, each a core and one shell:

* ``circle-in-rect``  circle core (radius r) in a rectangle shell; the
  corner lines run from the circle's 45° corners to the rectangle's
  corners, so they skew as the rectangle flattens;
* ``rect-in-circle``  rectangle core in a circle shell, which the corner
  lines (on the rectangle's diagonals) split into unequal arcs;
* ``rect-in-rect``    rectangle core in a ``dR`` shell: corner lines on the
  diagonals at both ends, for comparison.

Aspect ratio is the rectangle's w/h (width along the frame's right).  Gap
ratio is the ring's thinnest thickness over the inner outline's size: the
circle's radius; the rectangle's half-diagonal inside a circle; its
half-height inside a ``dR`` rectangle.  Each section runs through a
straight, an easy-way bend (roll 0: turning across the height) and a
hard-way bend (roll 90), each alone in its assembly.

Per case: min SICN and min scaled Jacobian (gmsh), max non-orthogonality
(OpenFOAM's: the angle between an interior face's normal and the line
joining its two cell centres) and where the cell with the lowest scaled
Jacobian sits: ``core``, ``corner line`` (it has a node on a ring corner
line), or the ring's ``long side`` / ``short side`` block.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math

import gmsh
import numpy as np

from hexmesh import Assembly, Bend, PipeSpec, Straight
from hexmesh.core.shape import CircleShape, RectShape

SIZE = 0.1          # inner outline size (see the module docstring)
NRAD = 4


def section(pairing: str, aspect: float, gap: float, nang: int) -> PipeSpec:
    spec = PipeSpec(nang=nang)
    if pairing == "circle-in-rect":
        hh = SIZE * (1 + gap)                       # thinnest: top and bottom
        return spec.core("core", CircleShape(SIZE, nang), nrad=NRAD).shell(
            "ring", outer=RectShape(aspect * hh, hh, nang, nang), nrad=NRAD)
    if pairing == "rect-in-circle":
        hh = SIZE / math.hypot(aspect, 1)           # half-diagonal = SIZE
        return spec.core("core", RectShape(aspect * hh, hh, nang, nang), nrad=NRAD).shell(
            "ring", outer=CircleShape(SIZE * (1 + gap), nang), nrad=NRAD)
    if pairing == "rect-in-rect":
        return spec.core("core", RectShape(aspect * SIZE, SIZE, nang, nang), nrad=NRAD).shell(
            "ring", dR=gap * SIZE, nrad=NRAD)
    raise ValueError(pairing)


def fitting(name: str, spec: PipeSpec, nang: int):
    e = spec.outlines[-1].max_extent
    if name == "straight":
        return Straight(2 * e, n_layers=2 * nang)
    return Bend(3 * e, 90, n_layers=3 * nang, roll=0 if name == "easy" else 90)


def _hexes():
    """Hex node coordinates (n, 8, 3), element tags and owning volume."""
    tags, nodes, vols = [], [], []
    for _, v in gmsh.model.getEntities(3):
        types, et, en = gmsh.model.mesh.getElements(3, v)
        for ty, t, n in zip(types, et, en):
            assert ty == 5, "hexes only"
            tags.append(t)
            nodes.append(n.reshape(-1, 8))
            vols.append(np.full(len(t), v))
    ntag, xyz, _ = gmsh.model.mesh.getNodes()
    order = np.argsort(ntag)
    xyz = xyz.reshape(-1, 3)[order]
    idx = np.searchsorted(ntag[order], np.concatenate(nodes))
    return np.concatenate(tags), xyz[idx], np.concatenate(vols), np.concatenate(nodes)


# hex8 faces in gmsh node order, each listed counter-clockwise seen from outside
_FACES = np.array([[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4],
                   [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]])


def _faces_and_centres(x: np.ndarray):
    """Face area vectors and cell centres as OpenFOAM computes them
    (``primitiveMesh``): faces as triangle fans about the point average,
    cells as pyramids from the face-centre average, volume-weighted."""
    f = x[:, _FACES]                                       # (n, 6, 4, 3)
    est = f.mean(axis=2, keepdims=True)
    nxt = np.roll(f, -1, axis=2)
    tri_n = np.cross(nxt - f, est - f)                     # 2 × triangle area vectors
    tri_a = np.linalg.norm(tri_n, axis=3)
    tri_c = f + nxt + est                                  # 3 × triangle centres
    area = 0.5 * tri_n.sum(axis=2)
    fc = (tri_a[..., None] * tri_c).sum(axis=2) / (3 * tri_a.sum(axis=2)[..., None])
    cest = fc.mean(axis=1, keepdims=True)
    vol = np.einsum("ijk,ijk->ij", area, fc - cest)        # 3 × pyramid volumes
    pc = 0.75 * fc + 0.25 * cest
    centres = (vol[..., None] * pc).sum(axis=1) / vol.sum(axis=1)[:, None]
    return area, centres


def max_non_orthogonality(x: np.ndarray, nodes: np.ndarray) -> float:
    """Largest angle (degrees) between an interior face's area vector and
    the line from its owner's centre to its neighbour's (OpenFOAM's
    ``checkMesh`` definition and construction)."""
    normal, centres = _faces_and_centres(x)
    keys = np.sort(nodes[:, _FACES], axis=2).reshape(-1, 4)
    cell = np.repeat(np.arange(len(x)), 6)
    _, inv, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    inv = inv.ravel()
    order = np.argsort(inv, kind="stable")
    shared = counts[inv[order]] == 2
    pairs = order[shared].reshape(-1, 2)                   # face slots, owner first
    a, b = cell[pairs[:, 0]], cell[pairs[:, 1]]
    n = normal.reshape(-1, 3)[pairs[:, 0]]
    d = centres[b] - centres[a]
    c = np.abs(np.einsum("ij,ij->i", n, d)) / (np.linalg.norm(n, axis=1) * np.linalg.norm(d, axis=1))
    return float(np.degrees(np.arccos(np.clip(c, -1, 1))).max())


def _in_plane(p: np.ndarray, frames) -> np.ndarray:
    """(u, v) of points *p* in the nearest station's frame."""
    pos = np.array([f.position for f in frames])
    k = np.argmin(np.linalg.norm(p[:, None] - pos[None], axis=2), axis=1)
    out = []
    for q, j in zip(p, k):
        w = q - frames[j].position
        out.append((w @ frames[j].right, w @ frames[j].up))
    return np.array(out)


def locate(asm: Assembly, spec: PipeSpec, x8: np.ndarray, vol: int) -> str:
    """Where the cell with nodes *x8* in volume *vol* sits."""
    core_vols = {v for d, t in gmsh.model.getPhysicalGroups(3)
                 if gmsh.model.getPhysicalName(d, t) == "core"
                 for v in gmsh.model.getEntitiesForPhysicalGroup(d, t)}
    if vol in core_vols:
        return "core"
    e = asm.edges[0]
    frames = e.fitting.path(*[p.frame for p in e.ports], spec).frames
    uv = _in_plane(x8, frames)
    corners = spec.corners()
    scale = spec.outlines[-1].max_extent
    for k in range(4):
        a, b = np.asarray(corners[0][k]), np.asarray(corners[1][k])
        t = np.clip((uv - a) @ (b - a) / ((b - a) @ (b - a)), 0, 1)
        if (np.linalg.norm(uv - (a + np.outer(t, b - a)), axis=1) < 1e-6 * scale).any():
            return "corner line"
    c = uv.mean(axis=0)
    angle = math.atan2(c[1], c[0]) % (2 * math.pi)
    outer = [math.atan2(p[1], p[0]) % (2 * math.pi) for p in corners[1]]
    k = max(j for j in range(4) if outer[j] <= angle) if angle >= outer[0] else 3
    width_side = k % 2 == 0                                 # blocks 0, 2: top, bottom
    wide = spec.outlines[-1].extent(0.0) >= spec.outlines[-1].extent(math.pi / 2)
    return "long side" if width_side == wide else "short side"


def measure(pairing: str, aspect: float, gap: float, nang: int, fit: str) -> dict:
    spec = section(pairing, aspect, gap, nang)
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add("q")
    try:
        asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1], lc=0.1)
        asm.add(fitting(fit, spec, nang))
        predicted = asm.cell_count()
        asm.mesh()
        tags, x, vols, nodes = _hexes()
        sicn = gmsh.model.mesh.getElementQualities(tags, "minSICN")
        sj = gmsh.model.mesh.getElementQualities(tags, "minSJ")
        worst = int(np.argmin(sj))
        return dict(pairing=pairing, aspect=aspect, gap=gap, nang=nang, fitting=fit,
                    cells=len(tags), predicted=predicted,
                    min_sicn=float(sicn.min()), min_sj=float(sj.min()),
                    max_non_ortho=max_non_orthogonality(x, nodes),
                    worst=locate(asm, spec, x[worst], int(vols[worst])))
    finally:
        gmsh.finalize()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pairings", nargs="+",
                    default=["circle-in-rect", "rect-in-circle", "rect-in-rect"])
    ap.add_argument("--aspects", nargs="+", type=float, default=[1, 1.5, 2, 3, 4, 6])
    ap.add_argument("--gaps", nargs="+", type=float, default=[0.1, 0.3, 1.0])
    ap.add_argument("--nang", nargs="+", type=int, default=[4, 8])
    ap.add_argument("--fittings", nargs="+", default=["straight", "easy", "hard"])
    ap.add_argument("--json")
    ap.add_argument("--md")
    args = ap.parse_args()
    rows = []
    for case in itertools.product(args.pairings, args.aspects, args.gaps, args.nang,
                                  args.fittings):
        r = measure(*case)
        assert r["cells"] == r["predicted"], r
        rows.append(r)
        print(f"{r['pairing']:15s} w/h {r['aspect']:<4g} gap {r['gap']:<4g} nang {r['nang']} "
              f"{r['fitting']:8s} SICN {r['min_sicn']:.3f}  SJ {r['min_sj']:.3f}  "
              f"non-orth {r['max_non_ortho']:5.1f}°  worst: {r['worst']}", flush=True)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(rows, f, indent=1)
    if args.md:
        with open(args.md, "w") as f:
            f.write("| pairing | w/h | gap | nang | fitting | min SICN | min SJ | "
                    "max non-orth (°) | worst cell |\n|---|---|---|---|---|---|---|---|---|\n")
            for r in rows:
                f.write(f"| {r['pairing']} | {r['aspect']:g} | {r['gap']:g} | {r['nang']} | "
                        f"{r['fitting']} | {r['min_sicn']:.3f} | {r['min_sj']:.3f} | "
                        f"{r['max_non_ortho']:.1f} | {r['worst']} |\n")


if __name__ == "__main__":
    main()
