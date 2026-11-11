"""``n_outer = 8`` is the 4-corner mesh, cut along its middle grid lines
(decision 0005, task 0088): the same nodes, the same elements, in the
face and in the sweeps.

Nodes are matched by position; only the nodes elements use count (the
builders' construction points carry orphan nodes)."""
import warnings

import gmsh
import numpy as np
import pytest
from scipy.spatial import cKDTree

from hexmesh import Session
from hexmesh.assembly import (Assembly, AssemblyError, Bend, MiterBend, Reducer, SplinePipe,
                              Straight, Transition)
from hexmesh.core.spec import PipeSpec
from hexmesh.errors import SpecError
from hexmesh.sections import build_face, place_partition_nodes

R = 0.05
EXACT = 1e-10            # in R: the task's bound


def _circle(n, nang=8, mprg=1.0, mbmp=1.0, radius=R, shell=True):
    s = PipeSpec(nang=nang, n_outer=n, mbmp=mbmp).core("fluid", radius=radius, nrad=4, mprg=mprg)
    return s.shell("wall", dR=0.2 * radius, nrad=2, mprg=1.1) if shell else s


def _rect(n, nang=8, mprg=1.0):
    """2:1, an O-H core."""
    return PipeSpec(nang_w=nang, nang_h=nang // 2, n_outer=n).core(
        "fluid", half_w=R, half_h=R / 2, nrad=4, mprg=mprg, layout="oh")


def _elements(dim: int) -> np.ndarray:
    out = [n.reshape(len(n) // gmsh.model.mesh.getElementProperties(int(t))[3], -1)
           for t, _, n in zip(*gmsh.model.mesh.getElements(dim))]
    return np.vstack(out).astype(int)


def _snapshot(dim: int):
    """(used node positions by tag, elements) of the current model."""
    el = _elements(dim)
    tags, x, _ = gmsh.model.mesh.getNodes()
    pos = dict(zip(tags.astype(int).tolist(), x.reshape(-1, 3)))
    return {k: pos[k] for k in np.unique(el).tolist()}, el


def _assert_same(a, b, scale, tol):
    """Same node and element counts, the same elements once nodes are
    matched by position, every node within *tol* × *scale*."""
    (pa, ea), (pb, eb) = a, b
    assert (len(pa), len(ea)) == (len(pb), len(eb))
    ka, xa = list(pa), np.array(list(pa.values()))
    kb, xb = list(pb), np.array(list(pb.values()))
    d, idx = cKDTree(xa).query(xb)
    assert d.max() <= tol * scale, d.max() / scale
    to_a = {k: ka[i] for k, i in zip(kb, idx)}
    assert len(set(to_a.values())) == len(ka)                  # one to one
    assert ({frozenset(r) for r in ea.tolist()}
            == {frozenset(to_a[n] for n in r) for r in eb.tolist()})
    return d.max() / scale


# --- the face -----------------------------------------------------------------

def _face(spec, stretch=None):
    """2-D: the face built as an assembly builds it, meshed, placed."""
    with Session("face"):
        face = build_face(spec, np.zeros(3), np.array([1.0, 0, 0]), np.array([0, 1.0, 0]),
                          0.1, stretch)
        gmsh.model.occ.synchronize()
        gmsh.model.mesh.generate(1)
        place_partition_nodes([face], 1)
        gmsh.model.mesh.generate(2)
        place_partition_nodes([face], 2)
        return _snapshot(2)


STRETCH = (np.array([np.cos(0.4), np.sin(0.4), 0.0]), 1.3)     # a miter station's


@pytest.mark.parametrize("nang, mprg, mbmp, stretch", [
    (8, 1.0, 1.0, None), (24, 1.2, 1.0, None), (8, 1.0, 1.3, None), (8, 1.1, 1.0, STRETCH)],
    ids=["uniform", "nang24-graded", "bump", "stretched"])
@pytest.mark.parametrize("make", [_circle, _rect], ids=["circle", "rect"])
def test_the_face_is_the_4_corner_face(make, nang, mprg, mbmp, stretch):
    if make is _rect and mbmp != 1.0:
        spec = lambda n: PipeSpec(nang_w=nang, nang_h=nang // 2, n_outer=n, mbmp=mbmp).core(
            "fluid", half_w=R, half_h=R / 2, nrad=4, mprg=mprg, layout="oh")
    elif make is _rect:
        spec = lambda n: _rect(n, nang, mprg)
    else:
        spec = lambda n: _circle(n, nang, mprg, mbmp)
    _assert_same(_face(spec(4), stretch), _face(spec(8), stretch), 1.2 * R, EXACT)


def test_halves_one_cell_across():
    """2 divisions on a side: its halves are one cell, their sub-patches
    have no interior nodes."""
    _assert_same(_face(_rect(4, nang=4)), _face(_rect(8, nang=4)), R, EXACT)


def test_a_blend_station_is_the_4_corner_one():
    """A Transition's station: a circle blended halfway to a square."""
    def station(n):
        a = _circle(n, shell=False)
        b = PipeSpec(nang_w=8, nang_h=8, n_outer=n).core(
            "fluid", half_w=0.04, half_h=0.04, nrad=4, layout="oh")
        return Transition(b, length=0.1, n_layers=2).station(a, 0.5)
    _assert_same(_face(station(4)), _face(station(8)), R, EXACT)


# --- sweeps -------------------------------------------------------------------

def _mesh(build, n, order=1):
    asm = build(n)
    with Session("sweep"), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        asm.mesh(order=order)
        return _snapshot(3)


def _asm(spec, *fittings):
    asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1])
    for f in fittings:
        asm.add(f)
    return asm


def _transition(n):
    out = PipeSpec(nang_w=8, nang_h=8, n_outer=n).core(
        "fluid", half_w=0.04, half_h=0.04, nrad=4, mprg=1.1, layout="oh")
    return _asm(_circle(n, mprg=1.1, shell=False), Transition(out, length=0.15, n_layers=4))


SWEEPS = {
    # one layer per slab: every node on a station face or an axial curve
    "bend": lambda n: _asm(_circle(n, mbmp=1.3), Bend(radius=0.15, angle=90.0, n_layers=6)),
    "miter": lambda n: _asm(_circle(n, mprg=1.1), MiterBend(radius=0.15, angle=90.0, n_cuts=3)),
    "rect-bend": lambda n: _asm(_rect(n, mprg=1.1), Straight(0.2, n_layers=3),
                                Bend(radius=0.2, angle=60.0, n_layers=4)),
    "reducer": lambda n: _asm(_circle(n, mprg=1.1, shell=False),
                              Reducer(_circle(n, mprg=1.1, radius=0.03, shell=False),
                                      length=0.1, n_layers=3)),
    "transition": _transition,
    "spline": lambda n: _asm(_circle(n), SplinePipe(
        points=((0, 0, 0), (0.1, 0.05, 0), (0.2, 0.1, 0.05)), n_layers=6)),
}


@pytest.mark.parametrize("name", SWEEPS)
def test_a_sweep_is_the_4_corner_sweep(name):
    build = SWEEPS[name]
    _assert_same(_mesh(build, 4), _mesh(build, 8), 1.2 * R, EXACT)


def test_a_multi_layer_straight_is_the_4_corner_one_to_gmsh_s_own_fill():
    """Several layers in a slab of curved side faces: gmsh fills the
    4-corner mesh's side faces in their parameter space, 1.3e-7 R off the
    exact extrusion; the cut mesh's halves are 3e-9 R off.  So the two
    agree to the 4-corner mesh's own error, not 1e-10 R (task 0088)."""
    build = lambda n: _asm(_circle(n, nang=24, mprg=1.2), Straight(0.3, n_layers=4))
    a, b = _mesh(build, 4), _mesh(build, 8)
    _assert_same(a, b, 1.2 * R, 1e-6)
    for (pos, _), off in ((a, 1e-6), (b, 1e-8)):      # each against the exact extrusion
        x = np.array(list(pos.values()))
        inlet = x[np.abs(x[:, 0]) < 1e-12][:, 1:]
        assert cKDTree(inlet).query(x[:, 1:])[0].max() <= off * 1.2 * R


@pytest.mark.parametrize("name", ["miter", "bend"])
def test_second_order_on_arcs_is_the_4_corner_mesh(name):
    """Circular sides: the halves' mid-edge nodes are the full sides'.
    (A Transition's B-spline side faces aren't: gmsh places their
    mid-face nodes in each face's own parameter space, ~4e-4 R apart.)"""
    build = SWEEPS[name]
    _assert_same(_mesh(build, 4, 2), _mesh(build, 8, 2), 1.2 * R, 1e-9)


def test_junctions_reject_n_outer_8_with_their_code():
    from hexmesh.assembly import Tee
    asm = _asm(_circle(8, shell=False), Straight(0.1, n_layers=1))
    with pytest.raises(AssemblyError) as e:
        asm.add(Tee(branch_length=0.1, branch_radius=0.025))
    assert e.value.code == "junction_needs_rot_0_n_outer_4"


def test_the_h_layout_rejects_n_outer_8():
    """One patch, no partition (PipeSpec, task 0084)."""
    with pytest.raises(SpecError, match="layout='h' needs n_outer = 4"):
        PipeSpec(nang_w=8, nang_h=4, n_outer=8).core("air", half_w=R, half_h=R / 2, layout="h")


def test_the_cell_count_is_the_4_corner_one():
    for make in (_circle, _rect):
        a = _asm(make(4), Straight(0.2, n_layers=3), Bend(radius=0.2, angle=60.0, n_layers=4))
        b = _asm(make(8), Straight(0.2, n_layers=3), Bend(radius=0.2, angle=60.0, n_layers=4))
        assert a.cell_count() == b.cell_count()
