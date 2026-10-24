"""
Fitting conformance kit (DESIGN.md §6.1) — the design rules, checked for
every fitting.

Each case builds a small assembly with the fitting under test placed so
that its ports are shared with neighbours (or closing a loop).  Every case
runs the same checks:

* topology    ``ports`` / ``validate`` / ``cell_count`` run without
              GMSH                                               (P3, P4)
* realisation port faces untouched by ``fill``                   (A1, A2)
              no duplicated surfaces, no coincident hex nodes    (P2)
              interior interfaces shared by exactly two fittings (P2)
              hex mesh valid (minSICN > 0)
              every surface in at most one physical group and
              every boundary face of the mesh in one             (A7)
              cell count predicted before GMSH equals the mesh   (P4)
* order       every fill order gives the identical mesh          (A6)

A new fitting is added by writing one case function and listing it in
``CASES``.  A fitting is not finished until it passes the kit.
"""

import math

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, Bend, Closure, Straight, Tee
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

def _one():
    return PipeSpec(nang=4).core("fluid", CircleShape(radius=0.1, nang=4), nrad=3)


def _two():
    return _one().shell("wall", dR=0.025, nrad=2)


def _between(spec, fitting, **kw):
    """Straight → fitting → Straight."""
    asm = Assembly(spec, direction=[0, 1, 0], up=[0, 0, 1], lc=0.1, **kw)
    asm.add(Straight(0.2, n_layers=2))
    asm.add(fitting)
    asm.add(Straight(0.2, n_layers=2))
    return asm


def _ring(spec, rolls, closer, extra_straight=False):
    asm = Assembly(spec, up=[0, 0, 1], lc=0.1)
    for r in rolls:
        asm.add(Straight(0.6, n_layers=3))
        asm.add(Bend(radius=0.3, angle=90, n_layers=4, roll=r))
    if extra_straight:
        asm.add(Straight(0.6, n_layers=3))
    asm.close(asm.interfaces[-1], asm.inlet, closer)
    return asm


def _rolled_outlet(spec, fitting, degrees):
    """fitting whose outlet interface is rolled by a symmetry angle.

    Exercises a non-zero corner correspondence: the faces are identical but
    corner 0 of the inlet meets corner k of the outlet.
    """
    from hexmesh.assembly.interface import Frame
    from hexmesh.core.cursor import _rodrigues
    asm = Assembly(spec, direction=[0, 1, 0], up=[0, 0, 1], lc=0.1)
    out = asm.add(fitting)
    f = out.frame
    out.frame = Frame(f.position, f.normal,
                      _rodrigues(f.up, f.normal, math.radians(degrees)))
    asm.add(Straight(0.2, n_layers=2))
    return asm


def _tee(ratio, direction=(0, 1, 0)):
    """Straight → Tee → Straight on both outlets."""
    asm = Assembly(_one(), direction=list(direction), up=[0, 0, 1], lc=0.1)
    asm.add(Straight(0.2, n_layers=2))
    main, branch = asm.add(Tee(run_length=0.2, branch_length=0.25,
                               branch_radius=ratio * 0.1), names=["main", "branch"])
    asm.add(main, Straight(0.2, n_layers=2))
    asm.add(branch, Straight(0.2, n_layers=2))
    return asm


CASES = {
    "straight":            lambda: _between(_one(), Straight(0.3, n_layers=3)),
    "straight-2layer":     lambda: _between(_two(), Straight(0.3, n_layers=3)),
    "bend":                lambda: _between(_one(), Bend(0.3, 90, n_layers=6)),
    "bend-rolled-2layer":  lambda: _between(_two(), Bend(0.3, -60, n_layers=4, roll=45)),
    "closure-planar":      lambda: _ring(_one(), [90, 90, 90], Closure(n_layers=8)),
    "closure-twisted":     lambda: _ring(_one(), [60, 0], Closure(n_layers=12),
                                         extra_straight=True),
    "bend-as-closer":      lambda: _ring(_one(), [90, 90, 90],
                                         Bend(0.3, 90, n_layers=4, roll=90),
                                         extra_straight=True),
    "straight-rolled-90":  lambda: _rolled_outlet(_two(), Straight(0.3, n_layers=3), 90),
    "bend-rolled-180":     lambda: _rolled_outlet(_one(), Bend(0.3, 90, n_layers=4), 180),
    "tee-0.5":             lambda: _tee(0.5),
    "tee-0.9-oblique":     lambda: _tee(0.9, direction=(1, 1, 0.2)),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session(name="kit"):
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add(name)


def _face_snapshot(asm):
    """Port-face entities: surface → (boundary curves, boundary point coords)."""
    snap = {}
    for iface in asm.interfaces:
        for _, cs in iface.face.layers:
            for s in cs.surfaces:
                curves = gmsh.model.getBoundary([(2, s)], oriented=False)
                pts = gmsh.model.getBoundary([(2, s)], recursive=True)
                snap[s] = (
                    sorted(abs(c) for _, c in curves),
                    sorted(tuple(np.round(gmsh.model.getValue(0, p, []), 12))
                           for _, p in pts),
                )
    return snap


def _hex_nodes():
    _, _, enodes = gmsh.model.mesh.getElements(3)
    used = np.unique(np.concatenate(enodes))
    tags, xyz, _ = gmsh.model.mesh.getNodes()
    lookup = dict(zip(tags, xyz.reshape(-1, 3)))
    return np.round(np.array([lookup[t] for t in used]), 9)


def _boundary_faces():
    """Node-sets of hex faces that belong to exactly one hex."""
    faces = gmsh.model.mesh.getElementFaceNodes(5, 4)   # 5 = hex8, quads
    faces = np.sort(faces.reshape(-1, 4), axis=1)
    uniq, counts = np.unique(faces, axis=0, return_counts=True)
    return {tuple(f) for f in uniq[counts == 1]}


def _grouped_quads():
    """Node-sets of quads on surfaces in physical groups, plus group count per surface."""
    quads, owners = set(), {}
    for d, t in gmsh.model.getPhysicalGroups(2):
        for s in gmsh.model.getEntitiesForPhysicalGroup(d, t):
            owners[s] = owners.get(s, 0) + 1
            types, _, nodes = gmsh.model.mesh.getElements(2, s)
            for ty, nd in zip(types, nodes):
                if ty == 3:   # quad4
                    for q in np.sort(nd.reshape(-1, 4), axis=1):
                        quads.add(tuple(q))
    return quads, owners


# ---------------------------------------------------------------------------
# The kit
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", CASES)
class TestConformance:

    def test_topology_without_gmsh(self, case):
        assert not gmsh.isInitialized()
        asm = CASES[case]()
        asm.validate()
        assert asm.cell_count() > 0
        assert not gmsh.isInitialized()

    def test_realisation(self, case):
        _session()
        try:
            asm = CASES[case]()
            predicted = asm.cell_count()
            asm.build_faces()
            before = _face_snapshot(asm)
            asm.fill()
            assert _face_snapshot(asm) == before, "fill modified a port face"

            # No duplicated surfaces anywhere in the model
            com = [tuple(np.round(gmsh.model.occ.getCenterOfMass(2, s), 9))
                   for _, s in gmsh.model.getEntities(2)]
            assert len(com) == len(set(com)), "coincident surfaces in model"

            # Interior interfaces shared by exactly two fittings
            for iface in asm.interfaces:
                assert len(iface.edges) in (1, 2)

            asm.mesh()
            c = _hex_nodes()
            assert len(c) == len(np.unique(c, axis=0)), "coincident hex nodes"

            report = asm.check_quality()
            assert report.ok, str(report)

            n_hex = sum(len(t) for t in gmsh.model.mesh.getElements(3)[1])
            assert n_hex == predicted, f"predicted {predicted} cells, meshed {n_hex}"

            quads, owners = _grouped_quads()
            assert all(n == 1 for n in owners.values()), "surface in two groups"
            missing = _boundary_faces() - quads
            assert not missing, f"{len(missing)} boundary faces in no group"
        finally:
            gmsh.finalize()

    def test_order_independence(self, case):
        meshes = []
        for reverse in (False, True):
            _session()
            try:
                asm = CASES[case]()
                order = list(range(len(asm.edges)))
                asm.build(order[::-1] if reverse else order)
                asm.mesh()
                c = _hex_nodes()
                n = sum(len(t) for t in gmsh.model.mesh.getElements(3)[1])
                meshes.append((n, c[np.lexsort(c.T)]))
            finally:
                gmsh.finalize()
        (n_a, c_a), (n_b, c_b) = meshes
        assert n_a == n_b
        np.testing.assert_allclose(c_a, c_b, atol=1e-9)


# ---------------------------------------------------------------------------
# The kit must catch violations
# ---------------------------------------------------------------------------

class _OwnOutlet(Straight):
    """Violates A1/A2: builds its own outlet face instead of using the port."""

    def fill(self, faces, frames, spec, lc):
        from hexmesh.assembly.sweep import _fill_slab
        from hexmesh.assembly.interface import build_face
        own = build_face(spec, frames[1], lc)
        gmsh.model.occ.synchronize()
        return _fill_slab(faces[0], own, self.n_layers)


class _NoWalls(Straight):
    """Violates A7: does not report its wall surfaces."""

    def fill(self, faces, frames, spec, lc):
        result = super().fill(faces, frames, spec, lc)
        result.walls.clear()
        return result


@pytest.mark.parametrize("bad, message", [
    (_OwnOutlet(0.3, n_layers=3), "coincident surfaces"),
    (_NoWalls(0.3, n_layers=3), "boundary faces in no group"),
])
def test_kit_detects_violations(bad, message):
    CASES["_bad"] = lambda: _between(_one(), bad)
    try:
        with pytest.raises(AssertionError, match=message):
            TestConformance().test_realisation("_bad")
    finally:
        del CASES["_bad"]
