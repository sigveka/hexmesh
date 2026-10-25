"""
Per-fitting wall patches (docs/tasks/0009).

``walls_by_fitting=True`` splits ``{outer}_wall`` into one group per
fitting, named by the fitting's ``label`` (``add(..., label=...)``) or
``<Type><index>``.  The kit checks rule A7 for every case
(``TestConformance.test_walls_by_fitting``).
"""

import json

import gmsh
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Bend, Straight, Tee

from test_fitting_conformance import _one, _two


def _groups():
    out = {}
    for d, t in gmsh.model.getPhysicalGroups(2):
        out[gmsh.model.getPhysicalName(d, t)] = set(gmsh.model.getEntitiesForPhysicalGroup(d, t))
    return out


def _elbow(**labels):
    asm = Assembly(_two(), lc=0.1)
    asm.add(Straight(0.3, n_layers=3), label=labels.get("first"))
    asm.add(Bend(0.3, 90, n_layers=4), label=labels.get("bend"))
    asm.add(Straight(0.3, n_layers=3))
    return asm


def test_default_names(gmsh_session):
    asm = _elbow()
    asm.mesh(walls_by_fitting=True)
    walls = {k for k in _groups() if k.startswith("wall_wall")}
    assert walls == {"wall_wall_Straight0", "wall_wall_Bend1", "wall_wall_Straight2"}


def test_labels_and_union(gmsh_session):
    gmsh.model.add("one")
    a = _elbow()
    a.mesh()
    single = _groups()["wall_wall"]
    gmsh.model.add("split")
    b = _elbow(first="approach", bend="elbow")
    b.mesh(walls_by_fitting=True)
    g = _groups()
    split = {k: v for k, v in g.items() if k.startswith("wall_wall_")}
    assert set(split) == {"wall_wall_approach", "wall_wall_elbow", "wall_wall_Straight2"}
    assert sum(len(v) for v in split.values()) == len(single)
    assert set().union(*split.values()) == set(b._fill.walls)
    assert "wall_wall" not in g
    # the other groups are untouched
    assert {k for k in g if not k.startswith("wall_wall")} == \
        {k for k in _groups() if not k.startswith("wall_wall")}


def test_off_by_default(gmsh_session):
    asm = _elbow(bend="elbow")
    asm.mesh()
    assert "wall_wall" in _groups()
    assert not any(k.startswith("wall_wall_") for k in _groups())


def test_tee_branch_walls(gmsh_session):
    asm = Assembly(_one(), up=[0, 0, 1], lc=0.1)
    asm.add(Straight(0.2, n_layers=2))
    main, branch = asm.add(Tee(0.2, 0.25, 0.05), label="tee")
    asm.add(main, Straight(0.2, n_layers=2), label="run")
    asm.add(branch, Straight(0.2, n_layers=2), label="branch")
    asm.mesh(walls_by_fitting=True)
    walls = {k for k in _groups() if k.startswith("fluid_wall_")}
    assert walls == {"fluid_wall_Straight0", "fluid_wall_tee", "fluid_wall_run",
                     "fluid_wall_branch"}


@pytest.mark.parametrize("bad", ["has space", "bend-1", "", "ü"])
def test_label_characters(bad):
    asm = Assembly(_one())
    with pytest.raises(AssemblyError, match="letters, digits"):
        asm.add(Straight(0.3, n_layers=2), label=bad)


def test_label_unique():
    asm = Assembly(_one())
    asm.add(Straight(0.3, n_layers=2), label="run")
    with pytest.raises(AssemblyError, match="already used"):
        asm.add(Straight(0.3, n_layers=2), label="run")


def test_label_clashing_with_a_later_default(gmsh_session):
    """A label equal to a later fitting's default name is caught at write time."""
    asm = Assembly(_one(), lc=0.1)
    asm.add(Straight(0.3, n_layers=2), label="Straight1")
    asm.add(Straight(0.3, n_layers=2))                  # default name Straight1
    with pytest.raises(AssemblyError, match="not unique"):
        asm.mesh(walls_by_fitting=True)


def test_labels_round_trip_through_json():
    a = _elbow(first="approach", bend="elbow")
    b = Assembly.from_dict(json.loads(json.dumps(a.to_dict())))
    assert [e.name for e in b.edges] == ["approach", "elbow", "Straight2"]
    assert b.to_dict() == a.to_dict()
