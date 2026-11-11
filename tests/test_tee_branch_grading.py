"""A tee branch with its own radial grading (task 0131; decision 0028,
amendment 2026-11-10): ``Tee(branch_first_cell=…)`` or ``branch_mprg``."""
import json
import math
import warnings

import gmsh
import numpy as np
import pytest

from hexmesh import Session
from hexmesh.assembly import Assembly, AssemblyError, AssemblyTypeError, Straight, Tee
from hexmesh.assembly.tee import branch_spec
from hexmesh.core.shape import RectShape
from hexmesh.core.spec import PipeSpec

R, r = 0.05, 0.025
MAIN_CELL = 5e-4


def _main():
    return PipeSpec(nang=8).core("fluid", radius=R, nrad=10, first_cell=MAIN_CELL)


def _asm(spec=None, **kw):
    """Straight, the tee, a Straight on each port."""
    asm = Assembly(spec or _main(), direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.3, n_layers=2))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")           # r/R 0.5: the junction core warns
        run, branch = asm.add(Tee(branch_length=0.1, branch_radius=kw.pop("radius", r), **kw))
    asm.add(branch, Straight(0.1, n_layers=2))
    asm.add(run, Straight(0.1, n_layers=2))
    return asm, branch


def _wall_cell(p, n):
    """The largest wall cell over the radial spokes of the meshed plane
    through *p* normal to *n*: per wall node with a node inward along its
    radius (the O-grid's other spokes aren't radial), its radius minus
    that node's."""
    _, xyz, _ = gmsh.model.mesh.getNodes()
    d = xyz.reshape(-1, 3) - p
    d = d[np.abs(d @ n) < 1e-7]
    rad = np.linalg.norm(d, axis=1)
    rw = rad.max()
    cells = []
    for w in d[np.abs(rad - rw) < 1e-9]:
        u = w / rw
        on = (np.linalg.norm(np.cross(d, u), axis=1) < 1e-9 + 1e-7 * rad) & (d @ u > 1e-6 * rw)
        s = np.sort(rad[on])
        if len(s) > 1:
            cells.append(s[-1] - s[-2])
    return max(cells)


def _meshed(asm):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        asm.mesh()


@pytest.mark.parametrize("cell", [2e-4, 5e-4])
def test_the_branch_port_wall_cell_is_branch_first_cell(cell):
    """The grading is the one ``PipeSpec.core(first_cell=…)`` resolves,
    bit for bit; the meshed cell is *cell* to 1e-6 relative (a plain
    pipe's own first_cell meshes 5e-8 off: gmsh's node positions, so
    1e-9 holds for the grading, not the nodes)."""
    asm, branch = _asm(branch_first_cell=cell)
    assert asm.edges[1].fitting.branch_first_cell is None       # resolved, stored as mprg
    own = PipeSpec(nang=8).core("fluid", radius=r, nrad=10, first_cell=cell)
    assert asm.edges[1].fitting.branch_mprg == own._core_mprg
    with Session("tee"):
        _meshed(asm)
        port = _wall_cell(branch.frame.position, branch.frame.normal)
    assert port == pytest.approx(cell, rel=1e-6)


def test_the_run_blends_from_the_main_grading_to_the_port():
    """Monotone along the branch run: the turning station keeps the
    main's grading, the port has its own."""
    from hexmesh.assembly.tee import turning_height
    asm, branch = _asm(branch_first_cell=1e-3)
    f = branch.frame
    run = 0.1 - turning_height(R, r, 0.0)
    with Session("tee"):
        _meshed(asm)
        cells = [_wall_cell(f.position - k * run / 3 * f.normal, f.normal) for k in range(4)]
    assert cells[0] == pytest.approx(1e-3, rel=1e-6)
    assert all(a > b for a, b in zip(cells, cells[1:]))


def test_the_branch_port_spec_carries_it_and_the_next_straight_matches():
    asm, branch = _asm(branch_mprg=0.8)
    assert branch.spec._core_mprg == 0.8
    assert branch.spec.to_dict() == branch_spec(_main(), r, mprg=0.8).to_dict()
    nxt = asm.edges[2]
    assert nxt.ports[0].spec is branch.spec
    assert nxt.ports[1].spec.to_dict() == branch.spec.to_dict()
    with Session("tee"):
        _meshed(asm)                       # conformal: mesh() checks the shared faces


def test_without_it_the_branch_copies_the_main_grading():
    asm, branch = _asm()
    assert branch.spec._core_mprg == _main()._core_mprg
    d = asm.to_dict()["edges"][1]["fitting"]
    assert "branch_first_cell" not in d and "branch_mprg" not in d


def test_it_round_trips_and_validates_against_the_schema():
    jsonschema = pytest.importorskip("jsonschema")
    from hexmesh.agent import schema
    asm, branch = _asm(branch_first_cell=2e-4)
    d = json.loads(json.dumps(asm.to_dict()))
    mprg = d["edges"][1]["fitting"]["branch_mprg"]
    assert mprg == branch.spec._core_mprg and "branch_first_cell" not in d["edges"][1]["fitting"]
    assert list(jsonschema.Draft202012Validator(schema()).iter_errors(d)) == []
    back = Assembly.from_dict(d)
    assert back.to_dict() == d
    assert back.edges[2].ports[0].spec.to_dict() == branch.spec.to_dict()


def test_refined_takes_the_kth_root():
    asm, _ = _asm(branch_first_cell=2e-4)
    m = asm.edges[1].fitting.branch_mprg
    fine = asm.refined(2)
    assert fine.edges[1].fitting.branch_mprg == pytest.approx(math.sqrt(m), rel=1e-12)


def test_both_is_an_error():
    with pytest.raises(AssemblyTypeError) as e:
        Tee(branch_length=0.1, branch_radius=r, branch_first_cell=1e-4, branch_mprg=0.8)
    assert e.value.code == "grading_args_conflict"


def test_an_equal_tee_rejects_it():
    with pytest.raises(AssemblyError) as e:
        _asm(radius=R, branch_mprg=0.8)
    assert e.value.code == "branch_grading_unsupported"
    assert e.value.where["field"] == "branch_mprg"
    assert "grading-only Reducer" in e.value.hint


def test_a_duct_tap_rejects_it():
    duct = PipeSpec(nang_w=8, nang_h=8).core("air", half_w=0.1, half_h=0.1, layout="oh", nrad=3)
    asm = Assembly(duct, direction=[1, 0, 0], up=[0, 0, 1])
    with pytest.raises(AssemblyError) as e:
        asm.add(Tee(branch_length=0.2, branch=RectShape(half_w=0.03, half_h=0.03, nang_w=8,
                                                        nang_h=8), branch_first_cell=1e-4))
    assert e.value.code == "branch_grading_unsupported"
    assert e.value.where["field"] == "branch_first_cell"


def test_advise_drops_it_as_the_table_sets_every_grading():
    from hexmesh.agent import advise, apply
    asm, _ = _asm(branch_first_cell=2e-4)
    r = advise(asm, {"fluid": "water", "flow": {"velocity": 0.005}})
    d = apply(asm.to_dict(), r["table"])
    assert "branch_mprg" not in d["edges"][1]["fitting"] or \
        d["edges"][1]["fitting"]["branch_mprg"] is None
    Assembly.from_dict(d)
