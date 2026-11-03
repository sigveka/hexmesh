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
"""
The H section layout (decision 0036, task 0084): ``layout=`` on the spec,
its errors, serialisation, signature and port type, the wall grading the
mesh gets, and the rejections before GMSH.
"""

import json
from pathlib import Path

import gmsh
import numpy as np
import pytest

from hexmesh import Session
from hexmesh.assembly import (Assembly, AssemblyError, Bend, Reducer, Straight, Tee,
                              Transition, Wye)
from hexmesh.assembly.interface import port_type
from hexmesh.assembly.signature import check_port_pairs, classify, signature
from hexmesh.core.grading import bump, bump_for_first_cell, bump_for_ratio
from hexmesh.core.shape import RectShape
from hexmesh.core.spec import LayoutNotSupported, PipeSpec

DATA = Path(__file__).parent / "data"


def _h(half_w=0.1, half_h=0.05, nw=8, nh=4, **kw):
    return PipeSpec(nang_w=nw, nang_h=nh).core("air", half_w=half_w, half_h=half_h,
                                              layout="h", **kw)


def _oh(half_w=0.1, half_h=0.05, nw=8, nh=4, nrad=2):
    return PipeSpec(nang_w=nw, nang_h=nh).core("air", half_w=half_w, half_h=half_h, nrad=nrad)


# ---------------------------------------------------------------------------
# The spec
# ---------------------------------------------------------------------------

def test_default_layout_is_oh():
    assert _oh().layout == "oh" and _oh().wall_grading is None


def test_nrad_on_h_names_both_fixes():
    with pytest.raises(ValueError, match=r"nrad=3 on an H core.*first_cell= or mprg=.*layout='oh'"):
        _h(nrad=3)


@pytest.mark.parametrize("make, match", [
    (lambda: PipeSpec(nang=4).core("air", radius=0.1, layout="h"), "rectangular core"),
    (lambda: PipeSpec(nang=4).core("air", half_w=0.1, half_h=0.05, layout="x"), "layout must be"),
    (lambda: _h(first_cell=0.002, mprg=1.2), "one of"),
    (lambda: _h(wall_bump=(0.5,)), "two positive"),
    (lambda: PipeSpec(nang_w=4, nang_h=4).core("air", half_w=0.1, half_h=0.05, nrad=2,
                                                wall_bump=(0.5, 0.5)), "H core"),
])
def test_bad_layouts(make, match):
    with pytest.raises((ValueError, TypeError), match=match):
        make()


def test_shells_on_h_name_the_task():
    with pytest.raises(LayoutNotSupported) as e:
        _h().shell("wall", dR=0.01, nrad=2)
    assert (e.value.layout, e.value.task) == ("h", "0086")


def test_wall_grading():
    assert _h().wall_grading is None
    assert _h(mprg=1.3).wall_grading == ("ratio", 1.3)
    kind, (cw, ch) = _h(first_cell=0.002).wall_grading
    assert kind == "bump"
    assert cw == bump_for_first_cell(0.2, 8, 0.002) and ch == bump_for_first_cell(0.1, 4, 0.002)
    assert _h(wall_bump=(cw, ch)).wall_grading == ("bump", (cw, ch))


@pytest.mark.parametrize("make", [_h, lambda: _h(first_cell=0.002), lambda: _h(mprg=1.2)])
def test_round_trip(make):
    s = make()
    d = s.to_dict()
    assert d["core"]["layout"] == "h"
    assert ("wall_bump" in d["core"]) == (s.wall_grading is not None
                                          and s.wall_grading[0] == "bump")
    assert PipeSpec.from_dict(d).to_dict() == d
    assert port_type(PipeSpec.from_dict(d)) == port_type(s)


def test_saved_before_0084_loads_as_oh_and_meshes_the_same():
    """``tests/data/saved_before_0084.json`` was written by the code before
    this task: no ``layout`` key.  It loads as O-H and meshes as a spec
    built today with the default."""
    saved = json.loads((DATA / "saved_before_0084.json").read_text(encoding="utf-8"))
    assert "layout" not in json.dumps(saved)
    asm = Assembly.from_dict(saved)
    assert asm.inlet.spec.layout == "oh"
    duct = PipeSpec(nang_w=4, nang_h=2).core("air", half_w=0.1, half_h=0.05, nrad=2)
    fresh = Assembly(duct, direction=[1, 0, 0], up=[0, 0, 1])
    fresh.add(Straight(0.3, n_layers=2))
    fresh.add(Bend(0.15, 90, n_layers=4))
    nodes = []
    for a in (asm, fresh):
        with Session("saved"):
            a.mesh()
            tags, xyz, _ = gmsh.model.mesh.getNodes()
            nodes.append((tags.copy(), xyz.copy()))
    assert np.array_equal(nodes[0][0], nodes[1][0])
    assert np.array_equal(nodes[0][1], nodes[1][1])


# ---------------------------------------------------------------------------
# Signature and port type
# ---------------------------------------------------------------------------

def test_port_type_includes_the_layout():
    assert port_type(_h()) != port_type(_oh())
    assert port_type(_h()) != port_type(_h(first_cell=0.002))


def test_oh_to_h_is_class_1_pillow():
    c = classify(signature(_oh()), signature(_h()))
    assert (c.cls, c.ends) == (1, "pillow")
    assert classify(signature(_oh(nw=6, nh=4)), signature(_h())).cls == 3


def test_layer_termination_fittings_do_not_bridge_a_pillow():
    with pytest.raises(LayoutNotSupported, match="0085") as e:
        check_port_pairs(Straight(0.3, n_layers=2), [_oh(), _h()])
    assert e.value.task == "0085"


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n, h", [(4, 0.01), (8, 0.002), (16, 0.004), (33, 0.0005)])
def test_bump_for_first_cell(n, h):
    f = bump(n, bump_for_first_cell(0.2, n, h)) * 0.2
    assert f[1] - f[0] == pytest.approx(h, rel=1e-9)
    assert f[-1] - f[-2] == pytest.approx(h, rel=1e-9)


@pytest.mark.parametrize("n, r", [(4, 1.2), (8, 1.1), (17, 1.3)])
def test_bump_for_ratio(n, r):
    d = np.diff(bump(n, bump_for_ratio(n, r)))
    assert d[1] / d[0] == pytest.approx(r, rel=1e-9)


def test_mesh_has_the_first_cell_at_every_wall():
    with Session("h-first-cell"):
        asm = Assembly(_h(0.2, 0.05, 16, 4, first_cell=0.003), direction=[1, 0, 0], up=[0, 0, 1])
        asm.add(Straight(0.3, n_layers=3))
        assert asm.cell_count() == 16 * 4 * 3
        asm.mesh()
        assert len(gmsh.model.mesh.getElementsByType(5)[0]) == 16 * 4 * 3
        assert list(gmsh.model.mesh.getElementTypes(3)) == [5]
        x = gmsh.model.mesh.getNodes()[1].reshape(-1, 3)
        face = x[np.abs(x[:, 0]) < 1e-12]
        for axis in (1, 2):
            v = np.unique(np.round(face[:, axis], 10))
            assert v[1] - v[0] == pytest.approx(0.003, rel=1e-6)
            assert v[-1] - v[-2] == pytest.approx(0.003, rel=1e-6)


# ---------------------------------------------------------------------------
# Not yet: rejected before GMSH, naming the task
# ---------------------------------------------------------------------------

def _validate(spec, fitting):
    asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(fitting)
    asm.validate()


@pytest.mark.parametrize("fitting, task", [
    (lambda: Tee(run_length=0.2, branch_length=0.25, branch_radius=0.03), "0086"),
    (lambda: Wye(60, run_length=0.25, branch_length=0.4), "0086"),
    (lambda: Transition(_oh(), 0.3, 4), "0085"),
])
def test_junctions_and_transitions_reject_h(fitting, task):
    with pytest.raises(AssemblyError, match=rf"layout 'h' is not supported yet \(task {task}\)"):
        _validate(_h(), fitting())


def test_reducer_keeps_the_layout():
    with pytest.raises(AssemblyError, match="not layouts"):
        _validate(_h(), Reducer(_oh(0.07, 0.035), 0.2, n_layers=3))
    with pytest.raises(AssemblyError, match=r"first_cell= \(or wall_bump=\) at both"):
        _validate(_h(first_cell=0.003), Reducer(_h(0.07, 0.035), 0.2, n_layers=3))


def test_predicted_quality_is_the_tensor_grid():
    from hexmesh.assembly.section_quality import section_quality
    (q,) = section_quality(_h(0.2, 0.05, 16, 4, first_cell=0.004))
    assert q.min_sj == pytest.approx(1.0) and q.max_non_ortho == pytest.approx(0.0, abs=1e-9)


def test_refinement_series():
    from hexmesh.assembly.intent import refine_spec_dict
    d = refine_spec_dict(_h().to_dict(), 2)
    assert (PipeSpec.from_dict(d).nang_w, PipeSpec.from_dict(d).layout) == (16, "h")


def _side_nodes(spec, k):
    """Node fractions of side *k* (0: the nang_w side, 1: the nang_h side)."""
    from hexmesh.sections import h
    g = h.side_grading(spec, k)
    n = spec.core_shape.side_count(k, 4)
    return bump(n, g[1]) if g else np.arange(n + 1) / n


@pytest.mark.parametrize("k", [2, 4])
@pytest.mark.parametrize("side", [0, 1])
def test_refined_first_cell_series_nests(k, side):
    """A refined series keeps each side's Bump coefficient (design answer
    to Question 1): every k-th fine node is a coarse node."""
    from hexmesh.assembly.intent import refine_spec_dict
    coarse = _h(0.2, 0.05, 16, 4, first_cell=0.004)
    fine = PipeSpec.from_dict(refine_spec_dict(coarse.to_dict(), k))
    assert fine.wall_grading == coarse.wall_grading
    c, f = _side_nodes(coarse, side), _side_nodes(fine, side)
    assert len(f) == k * (len(c) - 1) + 1
    assert np.abs(f[::k] - c).max() <= 1e-12


def test_ratio_grading_refines_as_mprg():
    """An explicit ratio refines as every mprg does, ``mprg ** (1/k)``."""
    from hexmesh.assembly.intent import refine_spec_dict
    d = refine_spec_dict(_h(mprg=1.3).to_dict(), 2)
    assert "wall_bump" not in d["core"]
    assert PipeSpec.from_dict(d).wall_grading == ("ratio", pytest.approx(1.3 ** 0.5))
