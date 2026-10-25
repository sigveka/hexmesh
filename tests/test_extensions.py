"""
Inlet and outlet extensions (docs/tasks/0008).

``extend_open_ends`` adds straight runs, in diameters, before the inlet
(via ``prepend``) and after every open outlet.  Patch names must not
change, and the total length must be right.
"""

import json

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Bend, Reducer, Straight, Tee

from test_fitting_conformance import _one, _two


def _patch_groups(asm):
    asm.mesh()
    return sorted(gmsh.model.getPhysicalName(d, t) for d, t in gmsh.model.getPhysicalGroups(2))


def _straight():
    asm = Assembly(_two(), lc=0.1)
    asm.add(Straight(0.3, n_layers=3))
    return asm


def _tee(names=("main", "branch")):
    asm = Assembly(_one(), up=[0, 0, 1], lc=0.1)
    asm.add(Straight(0.2, n_layers=2))
    main, branch = asm.add(Tee(0.2, 0.25, 0.05), names=names)
    asm.add(main, Straight(0.2, n_layers=2))
    asm.add(branch, Straight(0.2, n_layers=2))
    return asm


def test_total_length_straight():
    asm = _straight()
    asm.extend_open_ends(upstream=5, downstream=10)
    d = 2 * 0.1                                     # core diameter
    assert np.allclose(asm.inlet.frame.position, [-5 * d, 0, 0])
    outlet, = [i for i in asm.open_interfaces() if i is not asm.inlet]
    assert np.allclose(outlet.frame.position, [0.3 + 10 * d, 0, 0])
    asm.validate()


def test_cells_per_diameter():
    asm = _straight()
    asm.extend_open_ends(upstream=5, downstream=10, cells_per_diameter=2)
    n = {e.kind: e.fitting.n_layers for e in asm.edges[1:]}
    assert n == {"add": 20, "prepend": 10}


def test_downstream_diameter_is_the_outlets_own():
    """After a reducer, the downstream run is in the outlet's diameters."""
    asm = Assembly(_one(), lc=0.1)
    asm.add(Reducer(_one(0.05), 0.15, n_layers=3))
    asm.extend_open_ends(upstream=0, downstream=10)
    assert asm.edges[-1].fitting.length == pytest.approx(10 * 0.1)
    assert len(asm.edges) == 2                      # upstream 0 skips the inlet


@pytest.mark.parametrize("build", [
    _straight,
    _tee,
    lambda: _tee(names=None),                       # unnamed ends: port<N>
    lambda: _tee(names=("main", None)),
])
def test_patch_names_unchanged(gmsh_session, build):
    before = build()
    gmsh.model.add("before")
    names_before = _patch_groups(before)
    gmsh.model.add("after")
    after = build()
    after.extend_open_ends(upstream=2, downstream=3, cells_per_diameter=2)
    assert _patch_groups(after) == names_before
    assert after.cell_count() > before.cell_count()
    _, _, elems = gmsh.model.mesh.getElements(3)
    assert sum(len(e) for e in elems) // 8 == after.cell_count()


def test_prepend_moves_inlet_name_and_validates():
    asm = _straight()
    old = asm.inlet
    new = asm.prepend(Straight(0.4, n_layers=2))
    assert asm.inlet is new and new.name == "inlet" and old.name is None
    assert not old.is_open
    asm.validate()


def test_prepend_only_straight():
    asm = _straight()
    with pytest.raises(TypeError, match="Straight"):
        asm.prepend(Bend(0.3, 90, n_layers=4))


def test_closed_loop_has_no_inlet_to_extend():
    from test_fitting_conformance import _ring
    from hexmesh.assembly import Closure
    asm = _ring(_one(), [90, 90, 90], Closure(n_layers=8))
    n = len(asm.edges)
    asm.extend_open_ends()
    assert len(asm.edges) == n
    with pytest.raises(AssemblyError, match="not an open end"):
        asm.prepend(Straight(0.2, n_layers=2))


def test_extension_round_trips_through_json():
    asm = _tee(names=("main", None))
    asm.extend_open_ends(upstream=2, downstream=3)
    again = Assembly.from_dict(json.loads(json.dumps(asm.to_dict())))
    assert again.to_dict() == asm.to_dict()
    assert again.inlet.index == asm.inlet.index
    assert [again.patch_name(i) for i in again.open_interfaces()] == \
        [asm.patch_name(i) for i in asm.open_interfaces()]


def test_after_build_rejected(gmsh_session):
    asm = _straight()
    asm.build()
    with pytest.raises(AssemblyError, match="after the assembly is built"):
        asm.extend_open_ends()
