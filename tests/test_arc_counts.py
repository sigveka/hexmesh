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
Per-arc counts on a circle (task 0147; decision 0041, its note of
2026-11-13): ``CircleShape(radius, arcs=[a, b, a, b])``.  The field takes
four counts; the layouts mesh opposite arcs equal; ``Straight``,
``Bend``, ``Reducer`` and ``Transition`` opt in, every other fitting
rejects it by name.
"""

import gmsh
import numpy as np
import pytest

import hexmesh
from hexmesh import (Assembly, Bend, PipeSpec, Reducer, Session, Straight, Transition)
from hexmesh.assembly import AssemblyError
from hexmesh.assembly.signature import classify, signature
from hexmesh.core.shape import CircleShape, RectShape, shape_from_dict
from hexmesh.errors import SpecError

ARCS = (2, 4, 2, 4)


def _circle(radius=0.05, arcs=ARCS, nrad=2, shells=0):
    spec = PipeSpec().core("fluid", CircleShape(radius, arcs=arcs), nrad=nrad)
    for i in range(shells):
        spec = spec.shell(f"wall{i}", dR=0.01, nrad=2)
    return spec


def _asm(spec):
    return Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1])


def _mesh(asm):
    """Cells meshed, element types, min SICN."""
    with Session("arcs"):
        asm.mesh()
        _, tags, _ = gmsh.model.mesh.getElements(3)
        t = [x for a in tags for x in a]
        q = np.array(gmsh.model.mesh.getElementQualities(t, "minSICN"))
        return len(t), list(gmsh.model.mesh.getElementTypes(3)), float(q.min())


# --- the field ---------------------------------------------------------------

def test_the_field_and_its_round_trip():
    c = CircleShape(0.05, arcs=[2, 4, 2, 4])
    assert c.arcs == ARCS and c.nang is None
    assert c.side_counts == ARCS and c.counts == (2, 4)
    assert [c.side_count(k, 4) for k in range(4)] == list(ARCS)
    assert c.angular_counts == {"nang_w": 2, "nang_h": 4}
    assert c.to_dict() == {"type": "circle", "radius": 0.05, "arcs": [2, 4, 2, 4]}
    assert shape_from_dict(c.to_dict()) == c
    assert c.grown(0.01).arcs == ARCS and c.scaled(2).arcs == ARCS
    assert repr(c) == "CircleShape(radius=0.05, arcs=(2, 4, 2, 4))"


def test_uniform_arcs_are_the_nang_circle():
    """Four equal counts are ``nang``: the same circle, saved as before."""
    c = CircleShape(0.05, arcs=[4, 4, 4, 4])
    assert c == CircleShape(0.05, 4) and c.arcs is None
    assert c.to_dict() == {"type": "circle", "radius": 0.05, "nang": 4}
    assert repr(CircleShape(0.05, 4)) == "CircleShape(radius=0.05, nang=4)"


@pytest.mark.parametrize("kw, code", [
    ({"nang": 2, "arcs": ARCS}, "arcs_with_nang"),
    ({"arcs": (2, 4, 2)}, "arcs_invalid"),
    ({"arcs": (2, 4, 2, 4, 2)}, "arcs_invalid"),
    ({"arcs": (2.0, 4, 2, 4)}, "arcs_invalid"),
    ({"arcs": (0, 4, 0, 4)}, "count_below_minimum"),
    ({}, "nang_missing"),
])
def test_bad_arcs(kw, code):
    with pytest.raises(SpecError) as e:
        CircleShape(0.05, **kw)
    assert e.value.code == code


def test_the_spec_and_assembly_round_trip():
    spec = _circle(shells=1)
    d = spec.to_dict()
    assert d["nang"] is None and (d["nang_w"], d["nang_h"]) == (2, 4)
    assert d["core"]["shape"]["arcs"] == [2, 4, 2, 4]
    assert PipeSpec.from_dict(d).to_dict() == d
    asm = _asm(spec)
    asm.add(Straight(0.2, n_layers=2))
    assert Assembly.from_dict(asm.to_dict()).to_dict() == asm.to_dict()


def test_the_description_schema_takes_arcs():
    jsonschema = pytest.importorskip("jsonschema")
    from hexmesh.agent import schema      # not the submodule: importing it shadows the function
    v = jsonschema.Draft202012Validator(schema())
    asm = _asm(_circle())
    asm.add(Straight(0.2, n_layers=2))
    d = asm.to_dict()
    assert not list(v.iter_errors(d))
    d["inlet"]["spec"]["core"]["shape"]["arcs"] = [2, 4, 2]
    assert list(v.iter_errors(d))


# --- the layouts' rules ---------------------------------------------------------

@pytest.mark.parametrize("make, code", [
    (lambda: _circle(arcs=(2, 3, 4, 5)), "arc_counts_not_opposite"),
    (lambda: _circle(arcs=(2, 4, 4, 2)), "arc_counts_not_opposite"),
    (lambda: PipeSpec(n_outer=8).core("f", CircleShape(0.05, arcs=ARCS), nrad=2),
     "arc_counts_need_n_outer_4"),
    (lambda: PipeSpec(nang=4).core("f", CircleShape(0.05, arcs=ARCS), nrad=2),
     "shape_counts_mismatch"),
    (lambda: _circle().shell("box", outer=RectShape(0.1, 0.1, 4, 4), nrad=2), "counts_mismatch"),
    (lambda: _circle().shell("pipe", outer=CircleShape(0.1, 4), nrad=2), "counts_mismatch"),
    (lambda: PipeSpec(nang_w=2, nang_h=4).core("f", RectShape(0.05, 0.04, 2, 4), nrad=2,
                                               layout="oh")
     .shell("p", outer=CircleShape(0.1, arcs=(4, 2, 4, 2)), nrad=2), "counts_mismatch"),
])
def test_layout_rejections(make, code):
    with pytest.raises(SpecError) as e:
        make()
    assert e.value.code == code


def test_a_circle_with_arcs_and_a_rectangle_share_a_stack():
    """The tie of decision 0041 lifted: a 2:4 rectangle around a (2, 4, 2, 4)
    circle, and the other way round."""
    spec = _circle().shell("box", outer=RectShape(0.1, 0.08, 2, 4), nrad=2)
    assert spec.side_counts == ARCS
    rect = (PipeSpec(nang_w=2, nang_h=4).core("f", RectShape(0.05, 0.03, 2, 4), nrad=2,
                                              layout="oh")
            .shell("p", outer=CircleShape(0.1, arcs=ARCS), nrad=2))
    assert [o.counts for o in rect.outlines] == [(2, 4), (2, 4)]


# --- the signature ------------------------------------------------------------------

def test_the_signature():
    """The pattern is carried by ``nang_w``/``nang_h`` (task 0147, Q6 (B)):
    a circle with arcs (a, b, a, b) has the signature of an O-H a:b
    rectangle; equal arcs that of ``nang``."""
    s = signature(_circle())
    assert (s.nang_w, s.nang_h, s.period) == (2, 4, 180.0)
    rect = PipeSpec(nang_w=2, nang_h=4).core("fluid", RectShape(0.05, 0.03, 2, 4), nrad=2,
                                               layout="oh")
    assert s == signature(rect)
    assert (signature(PipeSpec().core("fluid", CircleShape(0.05, arcs=(4,) * 4), nrad=2))
            == signature(PipeSpec(nang=4).core("fluid", radius=0.05, nrad=2)))
    assert int(classify(s, signature(_circle(arcs=(4, 8, 4, 8))))) == 2


# --- the fittings ------------------------------------------------------------------

@pytest.mark.parametrize("shells", [0, 1])
def test_the_sweeps_mesh(shells):
    asm = _asm(_circle(shells=shells))
    asm.add(Straight(0.2, n_layers=3))
    asm.add(Bend(radius=0.25, angle=90, n_layers=6))
    asm.add(Reducer(_circle(radius=0.04, shells=shells), length=0.1, n_layers=3))
    n, types, sicn = _mesh(asm)
    assert n == asm.cell_count() and types == [5] and sicn > 0.1


@pytest.mark.parametrize("shells", [0, 1])
def test_a_transition_to_a_duct_with_unequal_counts(shells):
    """The motivating case: a circle (2, 4, 2, 4) to a 2:4 rectangle."""
    duct = PipeSpec(nang_w=2, nang_h=4).core("fluid", RectShape(0.06, 0.04, 2, 4), nrad=2,
                                               layout="oh")
    if shells:
        duct = duct.shell("wall0", outer=RectShape(0.075, 0.055, 2, 4), nrad=2)
    asm = _asm(_circle(shells=shells))
    asm.add(Straight(0.2, n_layers=3))
    asm.add(Transition(duct, length=0.2, n_layers=4))
    asm.add(Straight(0.2, n_layers=3))
    n, types, sicn = _mesh(asm)
    assert n == asm.cell_count() and types == [5] and sicn > 0.1


def test_the_guide_example():
    """GUIDE, 'A round pipe into a duct with unequal counts': to an H duct."""
    pipe = PipeSpec().core("air", CircleShape(0.06, arcs=[8, 4, 8, 4]), nrad=3)
    duct = PipeSpec(nang_w=8, nang_h=4).core("air", half_w=0.1, half_h=0.05)
    asm = _asm(pipe)
    asm.add(Straight(0.3, n_layers=6))
    asm.add(Transition(duct, length=0.3, n_layers=6))
    asm.add(Straight(0.3, n_layers=6))
    n, types, _ = _mesh(asm)
    assert n == asm.cell_count() == 1536 and types == [5]


@pytest.mark.parametrize("name, make", [
    ("MiterBend", lambda: hexmesh.MiterBend(radius=0.25, angle=90)),
    ("Elbow", lambda: hexmesh.Elbow()),
    ("SplinePipe", lambda: hexmesh.SplinePipe(points=((0.3, 0, 0), (0.6, 0.2, 0)))),
    ("Switch", lambda: hexmesh.Switch(length=0.2)),
    ("Tee", lambda: hexmesh.Tee(branch_length=0.2, branch_radius=0.03)),
    ("Wye", lambda: hexmesh.Wye(angle=60, run_length=0.3, branch_length=0.3)),
])
def test_other_fittings_reject_arcs_by_name(name, make):
    asm = _asm(_circle())
    asm.add(Straight(0.2, n_layers=2))
    with pytest.raises(AssemblyError, match=f"{name} doesn't handle a circle with unequal "
                                            f"arc counts") as e:
        asm.add(make())
        asm.validate()
    assert e.value.code == "arcs_unsupported"


def test_a_closure_rejects_arcs():
    """``close`` has no resolve step: validate names it."""
    asm = _asm(_circle())
    asm.add(Straight(0.2, n_layers=2))
    asm.add(Bend(radius=0.3, angle=180, n_layers=8))
    tail = asm.add(Straight(0.2, n_layers=2))
    with pytest.raises(AssemblyError) as e:
        asm.close(tail, asm.inlet, hexmesh.Closure(n_layers=4))
        asm.validate()
    assert e.value.code == "arcs_unsupported" and "Closure" in str(e.value)


def test_a_round_tap_with_arcs_is_rejected():
    """A junction rejects arcs on its own shapes too: here a tee's branch."""
    asm = _asm(PipeSpec(nang=4).core("fluid", radius=0.05, nrad=2))
    with pytest.raises(AssemblyError) as e:
        asm.add(hexmesh.Tee(branch_length=0.2, branch=CircleShape(0.02, arcs=ARCS)))
        asm.validate()
    assert e.value.code == "arcs_unsupported" and "Tee" in str(e.value)


# --- refinement --------------------------------------------------------------------

def test_refined_nests():
    """refined(2) doubles each arc (the arcs are density, decision 0041's
    correction to answer 5), and every coarse node is a fine node."""
    pytest.importorskip("scipy")
    from scipy.spatial import cKDTree
    asm = _asm(_circle(shells=1))
    asm.add(Straight(0.2, n_layers=3))
    asm.add(Bend(radius=0.25, angle=90, n_layers=6))
    fine = asm.refined(2)
    assert fine.to_dict()["inlet"]["spec"]["core"]["shape"]["arcs"] == [4, 8, 4, 8]
    assert fine.cell_count() == 8 * asm.cell_count()

    def nodes(a):
        with Session("n"):
            a.mesh()
            return gmsh.model.mesh.getNodes()[1].reshape(-1, 3)
    d, _ = cKDTree(nodes(fine)).query(nodes(asm))
    assert d.max() < 1e-12


def test_advise_refuses_arcs():
    """Its calibration is for one count per arc (task 0147): refused, coded."""
    from hexmesh.agent import AdviceError, advise
    asm = _asm(_circle())
    asm.add(Straight(0.5, n_layers=10))
    with pytest.raises(AdviceError) as e:
        advise(asm, {"fluid": "water", "flow": {"velocity": 0.01}})
    assert e.value.code == "advice_arcs_unsupported"
