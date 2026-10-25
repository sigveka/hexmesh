"""
Save and load the network description (Intent layer, docs/tasks/0006).

Every conformance-kit case must round trip through JSON:
``from_dict(to_dict(a))`` gives identical interface frames and an identical
mesh (node count, element count, physical group names).
"""

import json

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, Bend, Straight
from hexmesh.assembly.intent import FITTING_TYPES, fitting_from_dict
from hexmesh.core.spec import PipeSpec

from test_fitting_conformance import CASES


def _round_trip(asm):
    return Assembly.from_dict(json.loads(json.dumps(asm.to_dict())))


def _mesh_summary(asm):
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add("intent")
    try:
        asm.mesh()
        n_nodes = len(gmsh.model.mesh.getNodes()[0])
        n_elems = {d: sum(len(t) for t in gmsh.model.mesh.getElements(d)[1])
                   for d in (2, 3)}
        groups = sorted((d, gmsh.model.getPhysicalName(d, t))
                        for d, t in gmsh.model.getPhysicalGroups())
        return n_nodes, n_elems, groups
    finally:
        gmsh.finalize()


@pytest.mark.parametrize("name", CASES)
def test_kit_case_round_trips(name):
    a = CASES[name]()
    b = _round_trip(a)
    assert b.to_dict() == a.to_dict()
    assert len(b.interfaces) == len(a.interfaces)
    for ia, ib in zip(a.interfaces, b.interfaces):
        for k in ("position", "normal", "up"):
            assert np.array_equal(getattr(ia.frame, k), getattr(ib.frame, k)), (ia, k)
        assert ia.name == ib.name
        assert ia.spec.to_dict() == ib.spec.to_dict()
    assert _mesh_summary(b) == _mesh_summary(a)


def test_file_is_readable_json(tmp_path):
    a = CASES["tee-0.5"]()
    path = tmp_path / "net.json"
    a.save(path)
    text = path.read_text()
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"
    assert '"type": "Tee"' in text
    assert Assembly.load(path).to_dict() == a.to_dict()


def test_closure_and_tail_recorded():
    d = CASES["closure-planar"]().to_dict()
    assert d["edges"][-1]["close"] == [6, 0]
    assert d["tail"] is None


def test_hand_set_frame_stored_as_override():
    d = CASES["straight-rolled-90"]().to_dict()
    assert list(d["edges"][0]["frames"]) == ["0"]
    assert all("frames" not in e for e in d["edges"][1:])


def test_editing_a_parameter_moves_downstream():
    """The file is intent, not geometry: downstream poses follow an edit."""
    spec = PipeSpec(nang=4).core("fluid", radius=0.1, nrad=3)
    a = Assembly(spec)
    a.add(Bend(0.3, 90, n_layers=4))
    a.add(Straight(0.5, n_layers=2))
    d = a.to_dict()
    d["edges"][0]["fitting"]["angle"] = 45.0
    b = Assembly.from_dict(d)
    assert np.allclose(a.interfaces[-1].frame.normal, [0, 0, 1])   # bends toward up
    assert np.allclose(b.interfaces[-1].frame.normal, [np.sqrt(0.5), 0, np.sqrt(0.5)])


def test_spec_round_trip_keeps_resolved_grading():
    spec = (PipeSpec(nang=6).core("fluid", radius=0.1, nrad=4, first_cell=0.002)
            .shell("wall", dR=0.02, nrad=3, first_cell=1e-3)
            .square_shell("box", 0.2, 0.2, 2))
    again = PipeSpec.from_dict(json.loads(json.dumps(spec.to_dict())))
    assert again.to_dict() == spec.to_dict()
    assert again._core_mprg == spec._core_mprg
    assert again.shells == spec.shells


def test_registry_is_explicit():
    assert set(FITTING_TYPES) == {"Straight", "Bend", "MiterBend", "Elbow",
                                  "Reducer", "SplinePipe", "Closure", "Tee"}
    with pytest.raises(ValueError, match="unknown fitting type"):
        fitting_from_dict({"type": "Valve"})
    with pytest.raises(ValueError, match="unknown fields"):
        fitting_from_dict({"type": "Straight", "length": 1.0, "n_layers": 2,
                           "colour": "red"})


def test_wrong_format_rejected():
    with pytest.raises(ValueError, match="not a hexmesh.assembly"):
        Assembly.from_dict({"format": "other"})
