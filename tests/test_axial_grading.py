"""
Axial grading per fitting (docs/tasks/0001, DESIGN.md rule A5).

``axial_grading`` is the ratio of consecutive axial cell lengths, inlet →
outlet.  ``Straight`` grades the axial curves of its single slab; sweeps
with one layer per slab (``Bend``, ``Reducer``, ``SplinePipe``,
``Closure``) space their stations instead, by the same law.
"""

import math

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import (
    Assembly, AssemblyError, Bend, Closure, Elbow, Reducer, SplinePipe, Straight,
)
from hexmesh.assembly.blocks import LayoutError
from hexmesh.assembly.interface import Frame
from hexmesh.assembly.sweep import station_fractions
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec

from tests import test_fitting_conformance as kit
from tests.test_blocks import A, B, BlockStraight


def _one(radius=0.1):
    return PipeSpec(nang=4).core("fluid", CircleShape(radius=radius, nang=4), nrad=3)


def _two():
    return _one().shell("wall", dR=0.025, nrad=2)


def _ratios(positions):
    """Consecutive cell-length ratios of *positions*, merged within 1e-7."""
    p = np.sort(np.asarray(positions, dtype=float))
    p = p[np.concatenate([[True], np.diff(p) > 1e-7])]
    d = np.diff(p)
    return d, d[1:] / d[:-1]


def _mesh(fitting, spec, direction=(1, 0, 0), up=(0, 0, 1)):
    """Hex node coordinates of a single meshed *fitting*."""
    asm = Assembly(spec, direction=direction, up=up, lc=0.1)
    asm.add(fitting)
    asm.mesh()
    return asm, kit._hex_nodes()


# ---------------------------------------------------------------------------
# Station law (pure)
# ---------------------------------------------------------------------------

class TestStationFractions:
    def test_uniform(self):
        np.testing.assert_allclose(station_fractions(4), [0, .25, .5, .75, 1])

    @pytest.mark.parametrize("r", [1.3, 0.7])
    def test_geometric(self, r):
        u = station_fractions(6, r)
        assert u[0] == 0 and u[-1] == pytest.approx(1.0)
        d = np.diff(u)
        np.testing.assert_allclose(d[1:] / d[:-1], r)

    def test_reducer_stations(self):
        a = Frame.from_vectors([0, 0, 0], [1, 0, 0], [0, 0, 1])
        red = Reducer(_one(0.06), 0.3, n_layers=5, axial_grading=1.25)
        b = red.ports(a, _one())[0][0]
        path = red.path(a, b, _one())
        _, ratios = _ratios([f.position[0] for f in path.frames])
        np.testing.assert_allclose(ratios, 1.25, rtol=1e-9)
        radii = [s.core_shape.radius for s in path.specs]
        np.testing.assert_allclose(np.diff(radii)[1:] / np.diff(radii)[:-1], 1.25)

    def test_spline_and_closure_stations_on_a_line(self):
        a = Frame.from_vectors([0, 0, 0], [1, 0, 0], [0, 0, 1])
        b = Frame.from_vectors([1, 0, 0], [1, 0, 0], [0, 0, 1])
        spline = SplinePipe([(0, 0, 0), (0.4, 0, 0), (1, 0, 0)], n_layers=6,
                            end_tangent=(1, 0, 0), axial_grading=1.2)
        closure = Closure(n_layers=6, axial_grading=1.2)
        for fit in (spline, closure):
            path = fit.path(a, b, _one())
            _, ratios = _ratios([f.position[0] for f in path.frames])
            np.testing.assert_allclose(ratios, 1.2, rtol=1e-6)

    def test_elbow_passes_grading_to_bend(self):
        assert Elbow(90, n_layers=6, axial_grading=1.1).bend(_one()).axial_grading == 1.1

    def test_cell_count_unchanged(self):
        a = Frame.from_vectors([0, 0, 0], [1, 0, 0], [0, 0, 1])
        for g in (1.0, 1.4):
            fit = Bend(0.3, 90, n_layers=6, axial_grading=g)
            b = fit.ports(a, _one())[0][0]
            assert fit.cell_count([a, b], _one()) == 6 * 64     # 4² + 4·4·3 per section


class TestValidation:
    @pytest.mark.parametrize("g", [0.0, -1.2])
    def test_non_positive_rejected_before_gmsh(self, g):
        asm = Assembly(_one())
        asm.add(Straight(0.3, n_layers=3, axial_grading=g))
        with pytest.raises(AssemblyError, match="axial_grading must be positive"):
            asm.validate()

    def test_spline_rejects_at_add(self):
        asm = Assembly(_one())
        with pytest.raises(ValueError, match="axial_grading must be positive"):
            asm.add(SplinePipe([(0, 0, 0), (0.5, 0.1, 0)], n_layers=4, axial_grading=0))


# ---------------------------------------------------------------------------
# Realised meshes
# ---------------------------------------------------------------------------

class TestMeshedSpacing:
    @pytest.mark.parametrize("r", [1.3, 0.75])
    @pytest.mark.parametrize("spec", [_one(), _two()], ids=["1layer", "2layer"])
    def test_straight(self, gmsh_session, spec, r):
        _, nodes = _mesh(Straight(0.4, n_layers=6, axial_grading=r), spec)
        d, ratios = _ratios(nodes[:, 0])
        assert len(d) == 6
        np.testing.assert_allclose(ratios, r, rtol=1e-5)   # nodes rounded to 1e-9

    def test_straight_against_axis(self, gmsh_session):
        """Flow along -y: the first (smallest) cell is still at the inlet."""
        _, nodes = _mesh(Straight(0.4, n_layers=5, axial_grading=1.5), _one(),
                         direction=(0, -1, 0))
        d, ratios = _ratios(-nodes[:, 1])          # distance from the inlet
        np.testing.assert_allclose(ratios, 1.5, rtol=1e-5)
        assert d[0] == d.min()

    @pytest.mark.parametrize("r", [1.2, 0.8])
    def test_bend(self, gmsh_session, r):
        R = 0.3
        _, nodes = _mesh(Bend(R, 90, n_layers=6, axial_grading=r), _one())
        # roll 0 bends toward up (+z) about the centre (0, 0, R)
        angles = np.arctan2(nodes[:, 0], R - nodes[:, 2])
        d, ratios = _ratios(angles)
        assert len(d) == 6
        np.testing.assert_allclose(ratios, r, rtol=1e-5)   # nodes rounded to 1e-9
        assert sum(d) == pytest.approx(math.pi / 2)

    def test_uniform_grading_is_identical(self):
        """axial_grading=1.0 meshes exactly as the default (no records change)."""
        def nodes(fit):
            kit._session()
            try:
                asm = Assembly(_two(), lc=0.1)
                asm.add(fit)
                asm.mesh()
                c = kit._hex_nodes()
                return c[np.lexsort(c.T)]
            finally:
                gmsh.finalize()
        np.testing.assert_array_equal(nodes(Straight(0.3, 4)),
                                      nodes(Straight(0.3, 4, axial_grading=1.0)))


# ---------------------------------------------------------------------------
# Block layouts: grading direction is shared by a division class
# ---------------------------------------------------------------------------

class TestBlockGrading:
    def _layout(self):
        return BlockStraight(0.3, 3).layout(A, B, _one())

    def test_class_grading_propagates_with_direction(self):
        lay = self._layout()
        lay.edge(("A", 1, 0), ("B", 1, 0), divisions=3, grading=("Progression", 1.3))
        lay.validate()
        classes = lay._classes
        # another axial edge of the class, declared A → B: same ratio
        n, g = classes[frozenset({("A", 0, 2), ("B", 0, 2)})]
        assert n == 3 and g == ("Progression", 1.3)

    def test_reversed_declaration_agrees(self):
        lay = self._layout()
        lay.edge(("A", 1, 0), ("B", 1, 0), divisions=3, grading=("Progression", 1.3))
        lay.edge(("B", 1, 1), ("A", 1, 1), divisions=3, grading=("Progression", 1 / 1.3))
        lay.validate()
        g = lay._classes[frozenset({("A", 1, 1), ("B", 1, 1)})][1]
        assert g[0] == "Progression" and g[1] == pytest.approx(1 / 1.3)   # oriented B → A

    def test_opposite_direction_rejected(self):
        lay = self._layout()
        lay.edge(("A", 1, 0), ("B", 1, 0), divisions=3, grading=("Progression", 1.3))
        lay.edge(("B", 1, 1), ("A", 1, 1), divisions=3, grading=("Progression", 1.3))
        with pytest.raises(LayoutError, match="grading conflict"):
            lay.validate()

    def test_bump_needs_equal_coefficient(self):
        lay = self._layout()
        lay.edge(("A", 1, 0), ("B", 1, 0), divisions=3, grading=("Bump", 0.5))
        lay.edge(("B", 1, 1), ("A", 1, 1), divisions=3, grading=("Bump", 0.5))
        lay.validate()                                      # direction-free
        lay.edge(("A", 1, 2), ("B", 1, 2), divisions=3, grading=("Bump", 0.4))
        with pytest.raises(LayoutError, match="grading conflict"):
            lay.validate()
