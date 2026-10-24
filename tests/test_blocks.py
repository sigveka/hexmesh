"""
Block builder (DESIGN.md §6.1 "Blocks").

``BlockStraight`` re-expresses the OH slab as explicit hex blocks.  It must
validate without GMSH, pass the conformance kit, and reproduce the sweep
``Straight`` mesh node for node — the proof that the builder binds port
entities, orients blocks and solves divisions correctly.
"""

import math

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, Straight
from hexmesh.assembly.blocks import (
    BlockLayout, LayoutError, bind_face, face_vertices,
)
from hexmesh.assembly.corners import frame_offset
from hexmesh.assembly.interface import Frame
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec

from tests import test_fitting_conformance as kit


class BlockStraight(Straight):
    """Straight run built through BlockLayout instead of Sweep."""

    def layout(self, a, b, spec):
        lay = BlockLayout()
        face_vertices(lay, "A", a, spec)
        face_vertices(lay, "B", b, spec)
        n, j = spec.n_outer, frame_offset(a, b, spec)
        names = spec.layer_names
        for lvl in range(len(names) + 1):
            for k in range(n):
                lay.edge(("A", lvl, k), ("B", lvl, (k + j) % n), divisions=self.n_layers)

        def top(ids):
            return [("B", lvl, (c + j) % n) for (_, lvl, c) in ids]

        core = [("A", 0, k) for k in range(n)]
        lay.block(core + top(core), names[0])
        for lvl, name in enumerate(names):
            for k in range(n):
                kk = (k + 1) % n
                bottom = [("A", lvl, k), ("A", lvl, kk), ("A", lvl + 1, kk), ("A", lvl + 1, k)]
                lay.block(bottom + top(bottom), name)
        return lay

    def validate(self, frames, spec):
        super().validate(frames, spec)
        self.layout(*frames, spec).validate()

    def fill(self, faces, frames, spec, lc):
        lay = self.layout(frames[0], frames[1], spec)
        bind_face(lay, "A", faces[0])
        bind_face(lay, "B", faces[1])
        return lay.realise()


def _one():
    return PipeSpec(nang=4).core("fluid", CircleShape(radius=0.1, nang=4), nrad=3)


def _two():
    return _one().shell("wall", dR=0.025, nrad=2)


A = Frame.from_vectors([0, 0, 0], [0, 1, 0], [0, 0, 1])
B = Frame(A.position + 0.3 * A.normal, A.normal, A.up)


# ---------------------------------------------------------------------------
# Pure validation
# ---------------------------------------------------------------------------

class TestValidation:
    @pytest.mark.parametrize("spec, blocks", [(_one(), 5), (_two(), 9)])
    def test_oh_slab_validates_without_gmsh(self, spec, blocks):
        report = BlockStraight(0.3, 3).layout(A, B, spec).validate()
        assert not gmsh.isInitialized()
        assert report["blocks"] == blocks
        assert report["min_corner_sj"] > 0.3

    def test_division_conflict(self):
        lay = BlockStraight(0.3, 3).layout(A, B, _one())
        lay.edge(("A", 1, 0), ("B", 1, 0), divisions=5)   # parallel axials disagree
        with pytest.raises(LayoutError, match="division conflict"):
            lay.validate()

    def test_missing_division(self):
        lay = BlockLayout()
        for i, c in enumerate([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                               (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]):
            lay.vertex(i, c)
        lay.block(range(8), "fluid")
        with pytest.raises(LayoutError, match="no division count"):
            lay.validate()

    def test_port_not_tiled(self):
        lay = BlockStraight(0.3, 3).layout(A, B, _one())
        lay.blocks.pop(0)                                   # drop the core block
        with pytest.raises(LayoutError, match="port face .* not used"):
            lay.validate()

    def test_inverted_block(self):
        lay = BlockStraight(0.3, 3).layout(A, B, _one())
        ids, m = lay.blocks[1]
        lay.blocks[1] = ((ids[1], ids[0], *ids[2:]), m)     # fold one corner
        with pytest.raises(LayoutError, match="inverted or degenerate"):
            lay.validate()

    def test_left_handed_input_is_mirrored(self):
        lay = BlockLayout()
        cube = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
        for i, c in enumerate(cube):
            lay.vertex(i, c)
        lay.block([0, 3, 2, 1, 4, 7, 6, 5], "fluid")
        assert lay.corner_jacobians().min() == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Realisation
# ---------------------------------------------------------------------------

def _mesh_nodes(fitting, spec, roll=0.0):
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add("blocks")
    try:
        asm = Assembly(spec, direction=[0, 1, 0], up=[0, 0, 1], lc=0.1)
        out = asm.add(fitting)
        if roll:
            from hexmesh.core.cursor import _rodrigues
            f = out.frame
            out.frame = Frame(f.position, f.normal,
                              _rodrigues(f.up, f.normal, math.radians(roll)))
        asm.mesh()
        c = kit._hex_nodes()
        n = sum(len(t) for t in gmsh.model.mesh.getElements(3)[1])
        groups = sorted(gmsh.model.getPhysicalName(d, t)
                        for d, t in gmsh.model.getPhysicalGroups())
        return n, c[np.lexsort(c.T)], groups
    finally:
        gmsh.finalize()


@pytest.mark.parametrize("spec", [_one(), _two()], ids=["1layer", "2layer"])
@pytest.mark.parametrize("roll", [0.0, 90.0])
def test_block_straight_reproduces_sweep(spec, roll):
    n_s, c_s, g_s = _mesh_nodes(Straight(0.3, n_layers=3), spec, roll)
    n_b, c_b, g_b = _mesh_nodes(BlockStraight(0.3, n_layers=3), spec, roll)
    assert n_b == n_s
    assert g_b == g_s
    np.testing.assert_allclose(c_b, c_s, atol=1e-9)


@pytest.mark.parametrize("case", ["block-straight", "block-straight-2layer"])
def test_block_straight_passes_kit(case):
    spec = _one() if case == "block-straight" else _two()
    kit.CASES[case] = lambda: kit._between(spec, BlockStraight(0.3, n_layers=3))
    try:
        t = kit.TestConformance()
        t.test_topology_without_gmsh(case)
        t.test_realisation(case)
        t.test_order_independence(case)
    finally:
        del kit.CASES[case]
