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
Structured errors (decision 0040; task 0094): every error a user's input
can cause is a ``HexmeshError`` with a registered ``code``, a ``where``,
``value``, ``limit`` and ``hint``; ``to_dict()`` is JSON data and the
fields survive pickling.  That every construction passes a registered
code is ``tests/test_architecture.py``'s rule.
"""

from __future__ import annotations

import json
import pickle
import re
import warnings
from pathlib import Path

import pytest

from hexmesh import Assembly, HexmeshError, HexmeshWarning, PipeSpec, Straight
from hexmesh.assembly import AssemblyError, AssemblyTypeError, Bend, Drum, EquipmentError
from hexmesh.assembly.blocks import BlockLayout, LayoutError
from hexmesh.assembly.equipment import OnHead, OnShell
from hexmesh.core.shape import CircleShape
from hexmesh.errors import CODES, InternalError, ReaderError, SpecError, SpecTypeError, jsonable
from hexmesh.interchange.importers.pcf import read_pcf
from hexmesh.study import StudyError, load_study

ROOT = Path(__file__).resolve().parents[1]


def _spec():
    return (PipeSpec(nang=4).core("fluid", CircleShape(radius=0.1, nang=4), nrad=3)
            .shell("wall", dR=0.01, nrad=2))


# --- the classes -----------------------------------------------------------------

def test_fields_and_message():
    e = AssemblyError("length must be positive, got -1", code="size_not_positive",
                      where={"field": "length"}, value=-1, limit={"min_exclusive": 0},
                      hint="give a length > 0")
    assert str(e) == "length must be positive, got -1"          # the message alone
    assert isinstance(e, HexmeshError) and isinstance(e, ValueError)
    assert (e.code, e.where, e.value, e.limit, e.hint) == (
        "size_not_positive", {"field": "length"}, -1, {"min_exclusive": 0}, "give a length > 0")


def test_unregistered_code_is_refused():
    with pytest.raises(KeyError, match="not a registered error code"):
        HexmeshError("x", code="no_such_code")


@pytest.mark.parametrize("cls, bases", [
    (SpecTypeError, (SpecError, TypeError)),
    (AssemblyTypeError, (AssemblyError, TypeError)),
    (ReaderError, (HexmeshError,)),
    (EquipmentError, (HexmeshError,)),
    (LayoutError, (HexmeshError,)),
    (StudyError, (HexmeshError,)),
])
def test_former_types_are_kept(cls, bases):
    assert all(issubclass(cls, b) for b in bases)
    assert issubclass(cls, ValueError)


@pytest.mark.parametrize("make", [
    lambda: AssemblyError("x", code="size_not_positive", where={"fitting": 2, "label": "a"},
                          value=float("inf"), limit={"min_exclusive": 0}),
    lambda: SpecTypeError("x", code="shape_args_conflict", value=(1, 2)),
    lambda: HexmeshWarning("w", code="meshed_sj_low", value=0.21, limit=0.2),
])
def test_to_dict_is_json_and_pickles(make):
    e = make()
    d = e.to_dict()
    assert set(d) == {"type", "code", "message", "where", "value", "limit", "hint"}
    assert json.loads(json.dumps(d)) == d
    assert d["type"] == type(e).__name__ and d["message"] == str(e)
    back = pickle.loads(pickle.dumps(e))
    assert type(back) is type(e) and back.to_dict() == d


def test_jsonable():
    np = pytest.importorskip("numpy")
    assert jsonable({"a": np.float64(1.5), 2: (np.int64(3), {4}), "n": float("nan"),
                     "arr": np.arange(2)}) == {"a": 1.5, "2": [3, [4]], "n": "nan",
                                               "arr": [0, 1]}


def test_wrap_keeps_the_inner_fields():
    inner = AssemblyError("radius 0.05 is below", code="bend_radius_below_outer_radius",
                          where={"field": "radius"}, value=0.05, limit=0.11)
    outer = AssemblyError.wrap(inner, f"Bend #3: {inner}", code="fitting_invalid", fitting=3)
    assert outer.code == "bend_radius_below_outer_radius"
    assert outer.where == {"field": "radius", "fitting": 3}
    assert (outer.value, outer.limit) == (0.05, 0.11)
    plain = AssemblyError.wrap(ValueError("bad"), "Bend #3: bad", code="fitting_invalid",
                               fitting=3)
    assert plain.code == "fitting_invalid" and plain.where == {"fitting": 3}


# --- one raise per family --------------------------------------------------------

def test_spec_error():
    with pytest.raises(SpecError) as info:
        PipeSpec(n_outer=6)
    assert info.value.code == "n_outer_invalid"
    with pytest.raises(SpecError) as info:
        CircleShape(radius=-1, nang=4)
    assert info.value.code == "size_not_positive" and info.value.where == {"field": "radius"}


def test_assembly_error_names_the_fitting(gmsh_session):
    asm = Assembly(_spec())
    asm.add(Straight(0.5, 4), label="first")
    asm.add(Bend(0.3, 400, n_layers=6), label="wide")
    with pytest.raises(AssemblyError) as info:
        asm.validate()
    assert info.value.to_dict() == {           # the fitting's rule, located by the assembly
        "type": "AssemblyError", "code": "angle_out_of_range", "message": str(info.value),
        "where": {"field": "angle", "fitting": 1, "label": "wide"}, "value": 400,
        "limit": {"min_exclusive": 0, "max_exclusive": 360}, "hint": None}
    with pytest.raises(AssemblyError) as info:
        asm.add(Straight(0.5, 4), label="first")
    assert info.value.code == "label_duplicate"


def test_equipment_error():
    with pytest.raises(EquipmentError) as info:
        Drum("V-1", diameter=1.0, length=2.0, nozzles=[])
    assert info.value.code == "drum_name_invalid"
    assert info.value.where == {"part": "V-1", "field": "name"}


def test_layout_error():
    """An inverted block is a LayoutError; a layout that breaks its own
    rules is a bug (task 0111)."""
    from tests.test_blocks import A, B, BlockStraight, _one
    lay = BlockStraight(0.3, 3).layout(A, B, _one())
    ids, m = lay.blocks[1]
    lay.blocks[1] = ((ids[1], ids[0], *ids[2:]), m)
    with pytest.raises(LayoutError) as info:
        lay.validate()
    assert info.value.code == "block_inverted"
    with pytest.raises(InternalError) as info:
        BlockLayout().validate()
    assert info.value.code == "internal_invariant"
    assert not isinstance(info.value, HexmeshError)


def test_study_error(tmp_path):
    path = tmp_path / "study.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(StudyError) as info:
        load_study(path)
    assert info.value.code == "study_not_json"
    assert info.value.where == {"source": {"file": str(path)}}


def _nozzle(name, location, radius=0.05):
    from hexmesh.assembly.equipment import Nozzle
    return Nozzle(name, PipeSpec(nang=8).core("fluid", radius=radius, nrad=2), location)


def _drum(**kw):
    return Drum("V1", diameter=1.0, length=2.0, **kw)


@pytest.mark.parametrize("make, code, hint", [
    (lambda: Drum("V-1", diameter=1.0, length=2.0), "drum_name_invalid", "e.g. name='V_1'"),
    (lambda: _drum(head="torispherical"), "drum_head_args_invalid",
     "crown_radius=1, knuckle_radius=0.1"),
    (lambda: _drum(head="torispherical", crown_radius=0.4, knuckle_radius=0.2),
     "drum_head_args_invalid", "crown_radius above 0.5"),
    (lambda: _drum(axis=(0, 0, 1), up=(0, 0, 2)), "drum_up_parallel", "up=(1, 0, 0)"),
    (lambda: _drum(nozzles=[_nozzle("N1", OnShell(0.02, 0, 0.8))]).validate(),
     "nozzle_footprint_outside", "axial between 0.05 and 1.95"),
    (lambda: _drum(nozzles=[_nozzle("N1", OnHead("first", 0.48, 0, 0.5))]).validate(),
     "nozzle_footprint_outside", "offset at most 0.45"),
    (lambda: _drum(nozzles=[_nozzle("A", OnShell(1, 0, 0.8)),
                            _nozzle("B", OnShell(1.05, 0, 0.8))]).validate(),
     "nozzle_footprints_overlap", "axial positions at least 0.1 apart (now 0.05)"),
])
def test_equipment_hints(make, code, hint):
    """Task 0111: the drum's hints name the change, with its number."""
    with pytest.raises(EquipmentError) as info:
        make()
    assert info.value.code == code
    assert hint in info.value.hint


@pytest.mark.parametrize("study, hint", [
    ({"template": {"python": "m:f"}, "paramters": {}}, "rename 'paramters' to 'parameters'"),
    ({"template": {"python": "m:f"}, "budget": {"max_cell_variant": 1}},
     "rename 'max_cell_variant' to 'max_cells_variant'"),
    ({"template": {"python": "m:f"}, "zzz": 1}, None),           # nothing close: no hint
])
def test_study_key_hints(tmp_path, study, hint):
    path = tmp_path / "study.json"
    path.write_text(json.dumps(study), encoding="utf-8")
    with pytest.raises(StudyError) as info:
        load_study(path)
    assert info.value.code == "study_key_unknown"
    assert info.value.hint == hint


def test_study_function_hints(tmp_path):
    (tmp_path / "tpl_0111.py").write_text("x = 1\n", encoding="utf-8")
    path = tmp_path / "study.json"
    for target, hint in (("tpl_0111.build", "e.g. 'tpl_0111:build'"),
                         ("nosuch_0111:build", "put nosuch_0111.py in"),
                         ("tpl_0111:build", "define build(params) in tpl_0111")):
        path.write_text(json.dumps({"template": {"python": target}}), encoding="utf-8")
        with pytest.raises(StudyError) as info:
            load_study(path).builder()
        assert hint in info.value.hint, (target, info.value.hint)


PCF = """\
ISOGEN-FILES ISOGEN.FLS
UNITS-BORE MM
UNITS-CO-ORDS {units}
PIPE
    END-POINT 0 0 0 200
    END-POINT 1000 0 0 200
ELBOW
    END-POINT 1000 0 0 200
    END-POINT 1300 300 0 200
    CENTRE-POINT 1300 0 0
    ANGLE 4600
PIPE
    END-POINT 1300 300 0 200
    END-POINT 1300 1300 0 200
"""


def test_reader_error(tmp_path):
    path = tmp_path / "line.pcf"
    path.write_text(PCF.format(units="FURLONG"), encoding="utf-8")
    with pytest.raises(ReaderError) as info:
        read_pcf(path)
    assert info.value.code == "pcf_unit_unknown"
    assert info.value.where == {"field": "UNITS-CO-ORDS"} and info.value.value == "FURLONG"


def test_builder_error_carries_provenance(tmp_path):
    path = tmp_path / "line.pcf"
    path.write_text(PCF.format(units="MM"), encoding="utf-8")
    with pytest.raises(AssemblyError) as info:
        read_pcf(path).to_assembly(_spec())
    d = info.value.to_dict()
    assert d["code"] == "stated_angle_disagrees"
    assert d["value"] == pytest.approx(46) and d["limit"] == pytest.approx(90)
    assert d["where"]["part"] == "1"                    # the network-model part id
    src = d["where"]["source"]
    assert src["file"] == str(path) and src["format"] == "pcf" and src["record"] == "ELBOW"
    assert src["record_id"] == "1" and src["line"] == 7         # task 0096


def test_warning_is_coded(tmp_path):
    path = tmp_path / "line.pcf"
    path.write_text(PCF.format(units="MM").replace("UNITS-CO-ORDS MM\n", ""), encoding="utf-8")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        read_pcf(path)
    w = [c.message for c in caught if isinstance(c.message, HexmeshWarning)]
    assert [x.code for x in w] == ["pcf_units_missing"]
    assert issubclass(type(w[0]), UserWarning)


# --- the documented table --------------------------------------------------------

def test_api_lists_every_code():
    text = (ROOT / "API.md").read_text(encoding="utf-8")
    section = text.split("\n## Errors", 1)[1].split("\n## ", 1)[0]
    section = section.split("| code | rule | class |", 1)[1]
    listed = re.findall(r"^\| `([a-z0-9_]+)` \|", section, flags=re.M)
    assert sorted(listed) == sorted(CODES), (
        f"API.md Errors: missing {sorted(set(CODES) - set(listed))}, "
        f"stale {sorted(set(listed) - set(CODES))}")
