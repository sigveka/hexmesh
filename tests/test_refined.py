"""
``Assembly.refined(k)``: uniform refinement for convergence studies
(decision 0015 Q3, docs/tasks/0026).
"""

import gmsh
import numpy as np
import pytest

import test_fitting_conformance as kit
from hexmesh.assembly import Assembly, Reducer, Straight
from hexmesh.assembly.signature import classify, signature
from hexmesh.core.spec import PipeSpec

# meshing every kit case at k = 2 is slow for the spline and closure cases
SLOW = {"spline-3d-2layer", "spline-s-bend", "spline-graded",
        "closure-planar", "closure-twisted", "closure-graded", "bend-as-closer"}


@pytest.mark.parametrize("case", kit.CASES)
@pytest.mark.parametrize("k", [2, 3])
def test_cell_count_scales_by_k_cubed(case, k):
    asm = kit.CASES[case]()
    assert asm.refined(k).cell_count() == k**3 * asm.cell_count()


@pytest.mark.parametrize("case", kit.CASES)
def test_refined_one_is_identity(case):
    asm = kit.CASES[case]()
    assert asm.refined(1).to_dict() == asm.to_dict()


@pytest.mark.parametrize("case", kit.CASES)
def test_original_unchanged(case):
    asm = kit.CASES[case]()
    before = asm.to_dict()
    asm.refined(2)
    assert asm.to_dict() == before


@pytest.mark.parametrize("case", kit.CASES)
def test_signatures_differ_in_density_only(case):
    """Each interface's spec changes in counts and grading: class 2, never 3."""
    asm = kit.CASES[case]()
    fine = asm.refined(2)
    for a, b in zip(asm.interfaces, fine.interfaces):
        c = classify(signature(a.spec), signature(b.spec))
        assert int(c) == 2, (a.index, c)
        # fields are named per layer ("core nrad", "shell `wall` mprg")
        assert {d.field.split()[-1] for d in c.differences} <= {"nang", "nang_w", "nang_h", "nrad", "mprg"}, c


@pytest.mark.parametrize("case", sorted(set(kit.CASES) - SLOW))
def test_refined_meshes_as_predicted(case):
    kit._session()
    try:
        fine = kit.CASES[case]().refined(2)
        fine.validate()
        fine.mesh()
        _, tags, _ = gmsh.model.mesh.getElements(3)
        assert sum(len(t) for t in tags) == fine.cell_count()
    finally:
        gmsh.finalize()


@pytest.mark.parametrize("k", [0, -1, 1.5, 2.0, "2", True, None])
def test_bad_factor_rejected(k):
    with pytest.raises(ValueError, match="integer >= 1"):
        kit.CASES["straight"]().refined(k)


def test_numpy_integer_accepted():
    asm = kit.CASES["straight"]()
    assert asm.refined(np.int64(2)).cell_count() == 8 * asm.cell_count()


# --- graded spacing: every coarse node is a node of refined(k) ---------------

def _graded():
    spec = (PipeSpec(nang=4).core("fluid", radius=0.1, nrad=4, first_cell=0.005)
            .shell("wall", dR=0.02, nrad=3, first_cell=0.002))
    asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.3, n_layers=5, axial_grading=1.3))
    # a reducer may change radii only, so its outlet keeps the inlet's grading
    outlet = (PipeSpec(nang=4).core("fluid", radius=0.07, nrad=4,
                                    mprg=spec.to_dict()["core"]["mprg"])
              .shell("wall", dR=0.02, nrad=3, mprg=spec.to_dict()["shells"][0]["mprg"]))
    asm.add(Reducer(outlet, length=0.2, n_layers=4, axial_grading=0.8))
    return asm


def _nodes(asm):
    """(nodes on curves, all hex nodes) after meshing."""
    kit._session()
    try:
        asm.mesh()
        _, _, enodes = gmsh.model.mesh.getElements(3)
        used = np.unique(np.concatenate(enodes))
        tags, xyz, _ = gmsh.model.mesh.getNodes()
        lookup = dict(zip(tags, xyz.reshape(-1, 3)))
        _, cxyz, _ = gmsh.model.mesh.getNodes(1, -1, includeBoundary=True)
        return cxyz.reshape(-1, 3), np.array([lookup[t] for t in used])
    finally:
        gmsh.finalize()


@pytest.mark.parametrize("k", [2, 3])
def test_coarse_nodes_nest_in_refined(k):
    """Each coarse cell is split into k: radial (first_cell, mprg) and axial
    (axial_grading) progressions nest, uniform ones to rounding.

    Tolerance 1e-8 R, not the task's 1e-12 R: gmsh places "Progression"
    nodes ~1e-9 × the curve length off the closed-form geometric series
    (docs/integrations/gmsh.md), coarse and fine alike.
    """
    from scipy.spatial import cKDTree
    R = 0.12
    (c_curve, c_all), (f_curve, f_all) = _nodes(_graded()), _nodes(_graded().refined(k))
    for coarse, fine in ((c_curve, f_curve), (c_all, f_all)):
        d, _ = cKDTree(fine).query(coarse)
        assert d.max() < 1e-8 * R, d.max()


def test_uniform_nodes_nest_exactly():
    """Without grading, every coarse node is a refined node to rounding."""
    from scipy.spatial import cKDTree
    asm = kit.CASES["straight-2layer"]()
    (_, c_all), (_, f_all) = _nodes(asm), _nodes(asm.refined(2))
    d, _ = cKDTree(f_all).query(c_all)
    assert d.max() < 1e-12 * 0.125, d.max()


def test_first_cell_shrinks():
    """first_cell is stored as the resolved mprg, so the refined first cell
    is smaller (documented)."""
    asm = _graded()
    spec = asm.inlet.spec
    fine = asm.refined(2).inlet.spec
    assert fine.to_dict()["core"]["mprg"] == pytest.approx(spec.to_dict()["core"]["mprg"] ** 0.5)
