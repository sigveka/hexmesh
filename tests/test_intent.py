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
Save and load the network description (Intent layer, docs/tasks/0006).

Every conformance-kit case must round trip through JSON:
``from_dict(to_dict(a))`` gives identical interface frames and an identical
mesh (node count, element count, physical group names).
"""

import json
import math
from pathlib import Path

import gmsh
import numpy as np
import pytest

from hexmesh.core.shape import RectShape

from hexmesh.assembly import Assembly, AssemblyError, Bend, Straight
from hexmesh.assembly import intent
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
    text = path.read_text(encoding="utf-8")
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
    spec = PipeSpec(n_arc=4).core("fluid", radius=0.1, n_radial=3)
    a = Assembly(spec)
    a.add(Bend(0.3, 90, n_layers=4))
    a.add(Straight(0.5, n_layers=2))
    d = a.to_dict()
    d["edges"][0]["fitting"]["angle"] = 45.0
    b = Assembly.from_dict(d)
    assert np.allclose(a.interfaces[-1].frame.normal, [0, 0, 1])   # bends toward up
    assert np.allclose(b.interfaces[-1].frame.normal, [np.sqrt(0.5), 0, np.sqrt(0.5)])


def test_spec_round_trip_keeps_resolved_grading():
    spec = (PipeSpec(n_arc=6).core("fluid", radius=0.1, n_radial=4, first_cell=0.002)
            .shell("wall", dR=0.02, n_radial=3, first_cell=1e-3)
            .shell("box", outer=RectShape(0.2, 0.2, n_width=6, n_height=6), n_radial=2))
    again = PipeSpec.from_dict(json.loads(json.dumps(spec.to_dict())))
    assert again.to_dict() == spec.to_dict()
    assert again._core_radial_grading == spec._core_radial_grading
    assert again.shells == spec.shells


def test_registry_is_explicit():
    assert set(FITTING_TYPES) == {"Straight", "Bend", "MiterBend", "Elbow",
                                  "Reducer", "Transition", "SplinePipe", "Closure", "Tee",
                                  "Wye", "Switch"}
    with pytest.raises(ValueError, match="unknown fitting type"):
        fitting_from_dict({"type": "Valve"})
    with pytest.raises(ValueError, match="unknown fields"):
        fitting_from_dict({"type": "Straight", "length": 1.0, "n_layers": 2,
                           "colour": "red"})


def test_wrong_format_rejected():
    with pytest.raises(ValueError, match="not a hexmesh.assembly"):
        Assembly.from_dict({"format": "other"})


# --- description versions: the README's stability promise (task 0115) -------------

V1 = Path(__file__).parent / "data" / "description_v1.json"


def test_version_1_loads_as_its_version_2_equivalent():
    """A version-1 description (``rot`` in radians; hand-written to that
    format) builds what the same description at version 2 (degrees) builds."""
    v1 = json.loads(V1.read_text(encoding="utf-8"))
    assert v1["version"] == 1 and v1["inlet"]["spec"]["rot"] == pytest.approx(np.pi / 6)
    v2 = json.loads(json.dumps(v1))
    v2["version"], v2["inlet"]["spec"]["rot"] = 2, 30.0
    old, new = Assembly.from_dict(v1), Assembly.from_dict(v2)
    assert old.inlet.spec.rot == pytest.approx(30.0, abs=1e-12)    # migrated, not misread
    a, b = old.to_dict(), new.to_dict()
    assert a["version"] == b["version"] == intent.VERSION
    a["inlet"]["spec"]["rot"] = b["inlet"]["spec"]["rot"]          # radians round-off only
    assert a == b
    assert old.cell_count() == new.cell_count() == 288
    for i, j in zip(old.interfaces, new.interfaces):
        assert np.allclose(i.frame.position, j.frame.position, atol=1e-12)
        assert np.allclose(i.frame.up, j.frame.up, atol=1e-12)


@pytest.mark.parametrize("version", [99, 0, None, "2"])
def test_an_unknown_version_fails_naming_it(version):
    d = json.loads(V1.read_text(encoding="utf-8"))
    d["version"] = version
    with pytest.raises(AssemblyError) as e:
        Assembly.from_dict(d)
    assert e.value.code == "description_version_unsupported"
    assert e.value.value == version and e.value.where == {"field": "version"}
    assert repr(version) in str(e.value)


# --- version 2 → 3: the 1.0 names (decision 0053, task 0166) ------------------------

V2_EXAMPLES = Path(__file__).parent / "data" / "examples_v2.json"
#: the same 35 descriptions at the current version, as the examples built
#: them on 2026-11-17: fixed, so the test checks the migration only (an
#: example may change later, and ``subsea_pipeline`` drapes its route over a
#: surface differently on macOS)
CURRENT_EXAMPLES = Path(__file__).parent / "data" / "examples_current.json"


def _same(a, b, path="") -> list[str]:
    """Where *a* and *b* differ, numbers compared to 1e-9 (relative) and
    1e-15 (absolute): the fixture was saved on one machine, and a pose
    computed on another can differ in its last bit."""
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return [f"{path}: keys {sorted(a.keys() ^ b.keys())}"]
        return [d for k in a for d in _same(a[k], b[k], f"{path}.{k}")]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: length {len(a)} != {len(b)}"]
        return [d for k, (x, y) in enumerate(zip(a, b)) for d in _same(x, y, f"{path}[{k}]")]
    if isinstance(a, float) or isinstance(b, float):
        ok = (isinstance(a, (int, float)) and isinstance(b, (int, float))
              and not isinstance(a, bool) and not isinstance(b, bool)
              and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-15))
        return [] if ok else [f"{path}: {a!r} != {b!r}"]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


@pytest.mark.parametrize("name", sorted(json.loads(V2_EXAMPLES.read_text(encoding="utf-8"))))
def test_version_2_example_loads_as_today(name, gmsh_session):
    """Every example's description as 0.6 saved it (``nang``, ``nrad``,
    ``mprg``, …) loads as the same description at the current version."""
    old = json.loads(V2_EXAMPLES.read_text(encoding="utf-8"))[name]
    assert old["version"] == 2
    loaded = Assembly.from_dict(old).to_dict()
    expected = json.loads(CURRENT_EXAMPLES.read_text(encoding="utf-8"))[name]
    assert loaded["version"] == expected["version"] == intent.VERSION
    assert _same(loaded, expected) == []


def test_version_2_names_are_renamed_as_name_parts():
    d = intent._rename_fields({"nang_w": 8, "nang_h": 4, "branch_mprg": 1.2, "nrad": 3,
                               "lc": 0.1, "n_layers": 5, "inner": {"mbmp": 1.0}})
    assert d == {"n_width": 8, "n_height": 4, "branch_radial_grading": 1.2, "n_radial": 3,
                 "n_layers": 5, "inner": {"arc_bump": 1.0}}


# --- version 3 → 4: profiles as objects, a section kind (decision 0053, task 0165) -------

def _profiled_description(profile):
    from hexmesh import Profile, Reducer          # noqa: F401  (the profile's type)
    spec = PipeSpec(n_arc=8).core("fluid", radius=0.1, n_radial=3)
    asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.2, n_layers=2))
    asm.add(Reducer(spec, length=2.0, n_layers=80, profile=profile))
    return asm.to_dict()


def _as_version_3(d, old_profile):
    old = json.loads(json.dumps(d))
    old["version"] = 3
    old["edges"][1]["fitting"]["profile"] = old_profile
    for spec in (old["inlet"]["spec"], old["edges"][1]["fitting"]["outlet"]):
        del spec["kind"]
    return old


@pytest.mark.parametrize("make, old", [
    (lambda P: P.cosine(0.25), ["cosine", 0.25]),
    (lambda P: P.venturi(0.5, 10.0), ["venturi", 0.5, 10.0]),
    (lambda P: P.table([(0, 1), (0.5, 0.8), (1, 1)]), [[0, 1], [0.5, 0.8], [1, 1]]),
], ids=["cosine", "venturi", "table"])
def test_version_3_profile_tuple_loads_as_its_profile(make, old):
    from hexmesh import Profile
    today = _profiled_description(make(Profile))
    assert today["edges"][1]["fitting"]["profile"]["kind"] == make(Profile).kind
    loaded = Assembly.from_dict(_as_version_3(today, old))
    assert loaded.edges[1].fitting.profile == make(Profile)
    assert loaded.to_dict() == today


def test_every_spec_saves_its_kind_and_a_missing_kind_is_concentric():
    d = _profiled_description(None)
    assert d["inlet"]["spec"]["kind"] == PipeSpec.KIND == "concentric"
    bare = json.loads(json.dumps(d))
    del bare["inlet"]["spec"]["kind"]
    assert Assembly.from_dict(bare).to_dict() == d


def test_another_section_kind_is_a_coded_error():
    d = _profiled_description(None)
    d["inlet"]["spec"]["kind"] = "pipe_in_pipe"
    with pytest.raises(Exception, match="decision 0035") as e:
        Assembly.from_dict(d)
    assert e.value.code == "section_kind_unsupported"
    assert e.value.where == {"field": "kind"} and e.value.limit == ["concentric"]
