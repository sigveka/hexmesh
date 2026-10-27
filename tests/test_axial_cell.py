"""
``Assembly(axial_cell=…)``: ``n_layers=None`` from a target axial cell size
(task 0041, decision 0024).

* A sweep fitting added with ``n_layers=None`` gets
  ``max(floor, ceil(L / axial_cell))`` layers, ``L`` its centreline length
  and the floor its own validation limit; the count is stored in it.
* No ``axial_cell``: an error naming the fitting.  An explicit count wins.
"""

import math

import gmsh
import numpy as np
import pytest

from hexmesh import Session
from hexmesh.assembly import (
    Assembly, AssemblyError, Bend, Closure, Elbow, MiterBend, Reducer, SplinePipe,
    Straight, Transition,
)
from hexmesh.assembly.sweep import MAX_CHORD_TURN
from hexmesh.core.spec import PipeSpec


def _pipe(r=0.1):
    return PipeSpec(nang=4).core("fluid", radius=r, nrad=3)


def _asm(ac, spec=None):
    return Assembly(spec or _pipe(), direction=[1, 0, 0], up=[0, 0, 1], axial_cell=ac)


def _added(ac, fitting, spec=None):
    a = _asm(ac, spec)
    a.add(fitting)
    a.validate()
    return a, a.edges[-1].fitting


@pytest.mark.parametrize("fitting, ac, length", [
    (Straight(1.0), 0.3, 1.0),
    (Straight(0.9), 0.3, 0.9),                     # an exact multiple: 3, not 4
    (Bend(radius=0.3, angle=90), 0.1, 0.3 * math.pi / 2),
    (Bend(radius=0.3, angle=-60), 0.1, 0.3 * math.pi / 3),
    (Elbow(90, n_layers=None), 0.1, 0.3 * math.pi / 2),           # 1.5 D, D = 0.2
    (MiterBend(radius=0.3, angle=90, n_cuts=1, n_layers=None), 0.1, 0.3),   # one end leg
    (MiterBend(radius=0.4, angle=90, n_cuts=3, n_layers=None), 0.05,
     0.4 * math.tan(math.radians(15))),
    (Reducer(_pipe(0.06), 0.2), 0.05, 0.2),
    (Transition(PipeSpec(nang_w=4, nang_h=4).core("fluid", half_w=0.1, half_h=0.06,
                                                  nrad=3), 0.3), 0.04, 0.3),
], ids=["Straight", "Straight-exact", "Bend", "Bend-negative", "Elbow",
        "MiterBend", "MiterBend-3cuts", "Reducer", "Transition"])
def test_resolved_count(fitting, ac, length):
    _, f = _added(ac, fitting)
    assert f.n_layers == max(1, math.ceil(length / ac - 1e-9))


def test_spline_count_from_arc_length():
    pts = ((0, 0, 0), (0.5, 0.05, 0), (1.0, 0.1, 0.05))
    _, f = _added(0.05, SplinePipe(pts))
    from hexmesh.assembly.fittings import _arc_length
    from hexmesh.assembly.interface import Frame
    L = _arc_length(SplinePipe(pts, 1)._curve(Frame.from_vectors(None, [1, 0, 0], [0, 0, 1])))
    assert L > 1.0
    assert f.n_layers == math.ceil(L / 0.05 - 1e-9)


def test_spline_floor_is_the_chord_turn_limit():
    """A sharp spline with a coarse cell gets enough layers to validate."""
    pts = ((0, 0, 0), (1.0, 0, 0), (1.0, 1.0, 0), (0, 1.0, 0))
    a, f = _added(10.0, SplinePipe(pts))
    assert f.n_layers > 1
    turns = a.edges[0].fitting.path(a.interfaces[0].frame, a.interfaces[1].frame,
                                    a.inlet.spec).turns()
    assert max(turns) <= MAX_CHORD_TURN
    with pytest.raises(AssemblyError, match="use more axial layers"):
        b = _asm(10.0)
        b.add(SplinePipe(pts, f.n_layers - 1))
        b.validate()


def test_profiled_reducer_floor_is_the_chord_tolerance():
    spec = PipeSpec(nang=6).core("fluid", radius=0.1, nrad=3)
    outlet = PipeSpec(nang=6).core("fluid", radius=0.1, nrad=3)
    a, f = _added(1.0, Reducer(outlet, 0.4, profile=("cosine", 0.25)), spec)
    assert f.n_layers > 1
    with pytest.raises(AssemblyError, match=f"use n_layers >= {f.n_layers}"):
        b = _asm(1.0, spec)
        b.add(Reducer(outlet, 0.4, f.n_layers - 1, profile=("cosine", 0.25)))
        b.validate()


@pytest.mark.parametrize("fitting, floor", [
    (Bend(radius=0.3, angle=180), 2),                # a 180° slab: antiparallel faces
    (Bend(radius=0.3, angle=270), 2),
    (Elbow(180, n_layers=None), 2),
    (Bend(radius=0.3, angle=170), 1),
])
def test_coarse_bend_gets_its_floor_and_validates(fitting, floor):
    _, f = _added(10.0, fitting)
    assert f.n_layers == floor


def test_closure_resolved_at_close():
    a = Assembly(_pipe(), up=[0, 0, 1], lc=0.1, axial_cell=0.1)
    for _ in range(3):
        a.add(Straight(0.6))
        a.add(Bend(radius=0.3, angle=90, n_layers=4))
    a.add(Straight(0.6))
    src = a.interfaces[-1]
    a.close(src, a.inlet, Closure())
    a.validate()
    closure = a.edges[-1].fitting
    L = Closure().centreline_length(src.frame, a.inlet.spec, a.inlet.frame)
    assert L > 0.25
    assert closure.n_layers == math.ceil(L / 0.1 - 1e-9)
    assert a.edges[0].fitting.n_layers == 6


def test_prepend_resolves():
    a = _asm(0.1)
    a.add(Straight(0.3))
    a.prepend(Straight(0.25))
    assert a.edges[-1].fitting.n_layers == 3


def test_round_trip_holds_resolved_counts():
    a = _asm(0.07)
    a.add(Straight(0.5))
    a.add(Bend(radius=0.3, angle=90))
    a.add(Straight(0.4))
    d = a.to_dict()
    assert d["axial_cell"] == 0.07
    assert [e["fitting"]["n_layers"] for e in d["edges"]] == [8, 7, 6]
    b = Assembly.from_dict(d)
    assert b.cell_count() == a.cell_count() and b.to_dict() == d
    assert b.axial_cell == 0.07


def test_refined_scales_axial_cell():
    a = _asm(0.1)
    a.add(Straight(0.5))
    r = a.refined(2)
    assert r.axial_cell == pytest.approx(0.05)
    assert r.edges[0].fitting.n_layers == 10
    assert r.cell_count() == 8 * a.cell_count()


def test_missing_axial_cell_names_the_fitting():
    a = Assembly(_pipe())
    with pytest.raises(AssemblyError, match=r"Bend\(radius=0.3.*axial_cell"):
        a.add(Bend(radius=0.3, angle=90))


def test_explicit_count_wins():
    _, f = _added(0.01, Straight(1.0, n_layers=3))
    assert f.n_layers == 3


def test_stack_changes_need_explicit_count():
    a = _asm(0.1)
    with pytest.raises(AssemblyError, match="stack_changes indices need an explicit"):
        a.add(Straight(1.0, stack_changes=((3, _pipe()),)))


def test_unresolved_count_rejected_outside_assembly():
    with pytest.raises(ValueError, match="resolved by Assembly.add"):
        Straight(1.0).check(_pipe())


def test_resolved_network_meshes_as_predicted():
    a = Assembly(_pipe(), direction=[1, 0, 0], up=[0, 0, 1], lc=0.1, axial_cell=0.05)
    a.add(Straight(0.3))
    a.add(Bend(radius=0.3, angle=90, toward=(0, 1, 0)))
    a.add(Reducer(_pipe(0.07), 0.15))
    a.add(Straight(0.2))
    predicted = a.cell_count()
    with Session("ac"):
        a.mesh()
        assert sum(len(t) for t in gmsh.model.mesh.getElements(3)[1]) == predicted
        assert a.check_quality().ok
