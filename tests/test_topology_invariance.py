"""
Topology is unchanged across geometry variants (docs/tasks/0007).

Parametric and surrogate studies need identical connectivity when only
geometry changes.  Two meshes are compared through a canonical node
correspondence, not GMSH tags:

1. every node is seeded with the geometric entity it is classified on,
   ``(dim, tag)``; the assembly creates entities in the same order for
   every variant, so these seeds are comparable;
2. seeds are refined by hex-edge neighbourhood (Weisfeiler–Lehman) on the
   union of both meshes until the partition is stable;
3. if every class holds exactly one node of each mesh, that is a
   bijection, and the meshes are isomorphic when it maps every hex (as a
   node set, per volume) onto a hex.

Beyond that, ``Assembly.mesh`` fixes every transfinite surface and volume
to start at corners chosen from tags (``corners.transfinite_*_corners``),
so raw GMSH node and element tags are identical across variants too
(``test_raw_numbering``).  A mirrored variant is the one exception: its
hexes list the same nodes in reversed vertex order, which keeps their
volume positive.
"""

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, Bend, Reducer, Straight, Tee
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec

_HEX_EDGES = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
              (0, 4), (1, 5), (2, 6), (3, 7)]


def _one(radius=0.1):
    return PipeSpec(nang=4).core("fluid", CircleShape(radius=radius, nang=4), nrad=3)


def _two(radius=0.1):
    return _one(radius).shell("wall", dR=0.025, nrad=2)


R_OUT = 0.125   # outer radius of _two()


# ---------------------------------------------------------------------------
# Mesh snapshot and comparison
# ---------------------------------------------------------------------------

def _snapshot(build):
    """Mesh *build()* in a fresh session; return (seeds, hexes, raw)."""
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add("variant")
    try:
        asm = build()
        asm.mesh()
        seeds = {}
        for d in range(4):
            for _, t in gmsh.model.getEntities(d):
                for n in gmsh.model.mesh.getNodes(d, t, includeBoundary=False)[0]:
                    seeds[int(n)] = (d, t)
        hexes, raw = [], []
        for _, v in sorted(gmsh.model.getEntities(3)):
            types, etags, ntags = gmsh.model.mesh.getElements(3, v)
            assert list(types) == [5], "non-hex elements"
            conn = ntags[0].reshape(-1, 8).astype(int)
            hexes += [(v, tuple(r)) for r in conn.tolist()]
            raw.append((v, etags[0].copy(), conn))
        return seeds, hexes, raw
    finally:
        gmsh.finalize()


def _correspondence(a, b):
    """Canonical node bijection a → b, or a string saying why there is none."""
    graphs = []
    for seeds, hexes, _ in (a, b):
        nb = {n: set() for n in seeds}
        for _, h in hexes:
            for i, j in _HEX_EDGES:
                nb[h[i]].add(h[j])
                nb[h[j]].add(h[i])
        graphs.append(nb)
    colour = [dict(a[0]), dict(b[0])]
    n_classes = -1
    while True:
        keys = [{n: (colour[k][n], tuple(sorted(colour[k][m] for m in g[n])))
                 for n in g} for k, g in enumerate(graphs)]
        ids = {key: i for i, key in enumerate(
            sorted(set(keys[0].values()) | set(keys[1].values()), key=repr))}
        colour = [{n: ids[keys[k][n]] for n in keys[k]} for k in range(2)]
        if len(ids) == n_classes:
            break
        n_classes = len(ids)
    members = [{}, {}]
    for k in range(2):
        for n, c in colour[k].items():
            members[k].setdefault(c, []).append(n)
    if members[0].keys() != members[1].keys():
        return "node classes differ"
    if any(len(members[0][c]) != 1 or len(members[1][c]) != 1 for c in members[0]):
        return "symmetry not broken: a class holds several nodes"
    return {members[0][c][0]: members[1][c][0] for c in members[0]}


def _isomorphic(a, b):
    m = _correspondence(a, b)
    if isinstance(m, str):
        return m
    ea = {(v, frozenset(m[x] for x in h)) for v, h in a[1]}
    eb = {(v, frozenset(h)) for v, h in b[1]}
    return True if ea == eb else f"{len(ea ^ eb)} hexes differ"


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------

def _sbs(spec, fitting):
    def build():
        asm = Assembly(spec, lc=0.1)
        asm.add(Straight(0.2, n_layers=3))
        asm.add(fitting)
        asm.add(Straight(0.2, n_layers=3))
        return asm
    return build


def _tee(ratio):
    def build():
        asm = Assembly(_one(), direction=[1, 0, 0], up=[0, 0, 1], lc=0.1)
        asm.add(Straight(0.2, n_layers=3))
        main, branch = asm.add(Tee(0.2, 0.25, ratio * 0.1))
        asm.add(main, Straight(0.2, n_layers=3))
        asm.add(branch, Straight(0.2, n_layers=3))
        return asm
    return build


VARIANTS = {
    "bend-radius-2R-3R":   (_sbs(_two(), Bend(2 * R_OUT, 90, 6)),
                            _sbs(_two(), Bend(3 * R_OUT, 90, 6))),
    "bend-angle-45-90":    (_sbs(_two(), Bend(0.3, 45, 6)),
                            _sbs(_two(), Bend(0.3, 90, 6))),
    "bend-mirrored":       (_sbs(_two(), Bend(0.3, 90, 6)),
                            _sbs(_two(), Bend(0.3, -90, 6))),
    "bend-roll-0-30":      (_sbs(_two(), Bend(0.3, 90, 6)),
                            _sbs(_two(), Bend(0.3, 90, 6, roll=30))),
    "tee-ratio-0.4-0.6":   (_tee(0.4), _tee(0.6)),
    "straight-L-2L":       (_sbs(_two(), Straight(0.3, 4)),
                            _sbs(_two(), Straight(0.6, 4))),
    "reducer-outlet":      (_sbs(_two(), Reducer(_two(0.06), 0.2, 4)),
                            _sbs(_two(), Reducer(_two(0.08), 0.3, 4))),
}

# Mirror images: same node tags, hex vertex order reversed by handedness.
MIRRORED = {"bend-mirrored"}


@pytest.fixture(scope="module")
def snapshots():
    cache = {}

    def get(name):
        if name not in cache:
            a, b = VARIANTS[name]
            cache[name] = (_snapshot(a), _snapshot(b))
        return cache[name]
    return get


@pytest.mark.parametrize("name", VARIANTS)
def test_topology_invariant(snapshots, name):
    a, b = snapshots(name)
    assert len(a[1]) == len(b[1]) and len(a[0]) == len(b[0])
    assert _isomorphic(a, b) is True


def _raw_equal(a, b, as_sets=False):
    """Identical node tags per entity, element tags, and connectivity (as
    node sets per hex when *as_sets*)."""
    if a[0] != b[0]:
        return False
    for (va, ta, ca), (vb, tb, cb) in zip(a[2], b[2]):
        if va != vb or not np.array_equal(ta, tb):
            return False
        if as_sets:
            if [set(r) for r in ca.tolist()] != [set(r) for r in cb.tolist()]:
                return False
        elif not np.array_equal(ca, cb):
            return False
    return True


@pytest.mark.parametrize("name", [n for n in VARIANTS if n not in MIRRORED])
def test_raw_numbering(snapshots, name):
    """Identical GMSH node and element tags and connectivity."""
    a, b = snapshots(name)
    assert _raw_equal(a, b)


@pytest.mark.parametrize("name", sorted(MIRRORED))
def test_mirrored_variant_reverses_vertex_order_only(snapshots, name):
    a, b = snapshots(name)
    assert _raw_equal(a, b, as_sets=True)
    assert not _raw_equal(a, b)


# ---------------------------------------------------------------------------
# The comparison itself detects real differences
# ---------------------------------------------------------------------------

def test_density_change_detected(snapshots):
    a = _snapshot(_sbs(_two(), Bend(0.3, 90, 6)))
    b = _snapshot(_sbs(_two(), Bend(0.3, 90, 7)))
    assert _isomorphic(a, b) is not True


def test_rewired_hex_detected(snapshots):
    a, _ = snapshots("straight-L-2L")
    seeds, hexes, raw = a
    # replace one node of one hex by a neighbour on the same entity: the
    # node sets stay valid but the connectivity is different
    v, h = hexes[10]
    other = next(n for n in seeds if seeds[n] == seeds[h[0]] and n not in h)
    rewired = list(hexes)
    rewired[10] = (v, (other, *h[1:]))
    assert _isomorphic(a, (seeds, rewired, raw)) is not True
