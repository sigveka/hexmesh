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
Network-model operations (task 0066): select, cut, join, merge, the
operation log, replay and undo.

A PCF line with a valve is cut at the valve, built as two assemblies,
then joined back; two PCF files of one line are merged and joined at
their shared end.
"""

import gmsh
import numpy as np
import pytest

from hexmesh import Session
from hexmesh import interchange as ix
from hexmesh.assembly import AssemblyError
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec


def _spec(bore=0.1):
    return PipeSpec(nang=4).core("fluid", CircleShape(radius=(bore or 0.1) / 2, nang=4), nrad=2)


def _by_bore(bore):
    return _spec(bore)


VALVED = """\
UNITS-BORE MM
UNITS-CO-ORDS MM
PIPELINE-REFERENCE L-1
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
VALVE
    END-POINT 1000 0 0 100
    END-POINT 1300 0 0 100
PIPE
    END-POINT 1300 0 0 100
    END-POINT 2000 0 0 100
ELBOW
    END-POINT 2000 0 0 100
    END-POINT 2150 150 0 100
    CENTRE-POINT 2150 0 0
PIPE
    END-POINT 2150 150 0 100
    END-POINT 2150 800 0 100
"""

#: one line in two files, its components identified (as an isometric's
#: sheets are): read together or separately, the parts are named alike
SHEET_1 = """\
UNITS-BORE MM
UNITS-CO-ORDS MM
PIPELINE-REFERENCE L-1
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
    COMPONENT-IDENTIFIER 11
ELBOW
    END-POINT 1000 0 0 100
    END-POINT 1150 150 0 100
    CENTRE-POINT 1150 0 0
    COMPONENT-IDENTIFIER 12
"""
SHEET_2 = """\
UNITS-BORE MM
UNITS-CO-ORDS MM
PIPELINE-REFERENCE L-1
PIPE
    END-POINT 1150 150 0 100
    END-POINT 1150 800 0 100
    COMPONENT-IDENTIFIER 21
"""


def _model(tmp_path, text=VALVED, name="line.pcf"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return ix.read_pcf(p).to_model(), p


def _at(model, part_id, k):
    return model.parts[part_id].ports[k]


def _canonical(model) -> dict:
    """The model as plain data, without the log's times."""
    def sec(s):
        return None if s is None else (s.shape, s.nominal, s.diameter, s.width, s.height)
    return {
        "ports": {q: (None if p.position is None else tuple(np.round(p.position, 12)), sec(p.section),
                      p.flow, p.insulation, p.tag) for q, p in model.ports.items()},
        "parts": {i: (type(p).__name__, tuple(p.ports), p.name, p.system)
                  for i, p in model.parts.items()},
        "connections": sorted((c.a, c.b, c.origin) for c in model.connections),
        "cuts": sorted((c.a, c.b) for c in model.cuts),
        "networks": {n: sorted(v.parts) for n, v in model.networks.items()},
        "log": [(e["op"], _timeless(e["args"])) for e in model.log],
    }


def _timeless(x):
    """*x* without any ``time`` key at any depth: an import's provenance
    carries its read time, so a replay a second later differs there
    (task 0113: a CI failure when the two reads straddled a second)."""
    if isinstance(x, dict):
        return {k: _timeless(v) for k, v in x.items() if k != "time"}
    if isinstance(x, (list, tuple)):
        return type(x)(_timeless(v) for v in x)
    return x


def _hexes(asm) -> int:
    with Session("ops"):
        asm.mesh()
        return sum(len(t) for t in gmsh.model.mesh.getElements(3)[1])


# --- cut at the valve, build both sides, join back ------------------------------------

def test_cut_at_the_valve_builds_two_sides_and_joining_restores_the_line(tmp_path):
    m, _ = _model(tmp_path)
    whole = ix.build(m, _spec(), axial_cell=0.1).to_dict()
    valve_out = _at(m, "1", 1)                    # VALVE's outlet, at x = 1.3 m
    cuts = m.cut_at(valve_out, names=("valve_out", "pipe_in"))
    assert [(c.a, c.b) for c in cuts] == [(valve_out, _at(m, "2", 0))]

    with pytest.raises(AssemblyError, match="unconnected pieces"):
        ix.build(m, _spec())
    upstream = m.select(from_port=_at(m, "0", 0))
    downstream = m.select(from_port=_at(m, "4", 1))
    assert set(upstream) == {"0", "1"} and set(downstream) == {"2", "3", "4"}
    sides = [ix.build(m, _spec(), sel, axial_cell=0.1) for sel in (upstream, downstream)]
    assert m.report["selection"] == {"parts": ["2", "3", "4"],
                                     "how": {"from_port": _at(m, "4", 1), "up_to": []}}
    names = [sorted(i.name for i in a.open_interfaces()) for a in sides]
    assert names == [["L_1_end1", "valve_out"], ["L_1_end1", "pipe_in"]]
    for a in sides:
        a.validate()
        assert _hexes(a) == a.cell_count()

    m.join(valve_out, _at(m, "2", 0))
    assert ix.build(m, _spec(), axial_cell=0.1).to_dict() == whole
    assert [e["op"] for e in m.log] == ["import", "cut_at", "join"]


def test_cut_names_the_open_ends_from_their_ports_by_default(tmp_path):
    m, _ = _model(tmp_path)
    a, b = _at(m, "1", 1), _at(m, "2", 0)
    m.cut((a, b))
    out = ix.build_pieces(m, _spec())
    assert [sorted(i.name for i in x.open_interfaces()) for x in out.values()] == \
        [["L_1_end1", f"L_1_{a}"], ["L_1_end1", f"L_1_{b}"]]
    with pytest.raises(AssemblyError, match="aren't connected") as e:
        m.cut((a, b))
    assert e.value.code == "model_ports_not_met"
    with pytest.raises(AssemblyError, match="already an open end"):
        m.cut_at(a)


def test_a_selection_up_to_builds_only_the_parts_before_it(tmp_path):
    m, _ = _model(tmp_path)
    sel = m.select(from_port=_at(m, "0", 0), up_to=["3"])        # up to the elbow, included
    assert set(sel) == {"0", "1", "2", "3"}
    asm = ix.build(m, _spec(), sel, axial_cell=0.1)
    assert [e.label for e in asm.edges] == ["PIPE_1", "VALVE_1", "PIPE_2", "ELBOW_1"]
    assert sorted(i.name for i in asm.open_interfaces()) == ["L_1_end1", f"L_1_{_at(m, '3', 1)}"]
    by_port = m.select(from_port=_at(m, "0", 0), up_to=[_at(m, "2", 0)])  # not crossed
    assert set(by_port) == {"0", "1"}
    assert set(m.select(network="L-1")) == set(m.parts)
    assert set(m.select(["3", "4"])) == {"3", "4"}
    for bad, code in (({}, "selection_invalid"), ({"parts": ["9"]}, "model_id_unknown"),
                      ({"network": "L-9"}, "model_id_unknown"),
                      ({"from_port": _at(m, "0", 0), "up_to": ["nope"]}, "model_id_unknown")):
        with pytest.raises(AssemblyError) as e:
            m.select(**bad)
        assert e.value.code == code


# --- join's checks ----------------------------------------------------------------------

def _two(dx=0.0, reverse=False, nominal=0.1):
    """Two straights meeting near x = 1, as two models merged.  *reverse*:
    the second runs back over the first, so its port faces the same way."""
    a, b = ix.NetworkModel(), ix.NetworkModel()
    pa = a.add_part(ix.Straight, [(0, 0, 0), (1, 0, 0)], id="a", system="L")
    for q in pa.ports:
        a.ports[q].section = ix.Section(nominal=0.1)
    far = (0.5, 0, 0) if reverse else (2, 0, 0)
    pb = b.add_part(ix.Straight, [(1 + dx, 0, 0), far], id="b", system="L")
    for q in pb.ports:
        b.ports[q].section = ix.Section(nominal=nominal)
    m = ix.NetworkModel.merge(a, b, prefix="b_")
    return m, pa.ports[1], "b_" + pb.ports[0]


def test_join_rejects_a_gap_a_direction_and_a_section_with_the_numbers():
    m, p, q = _two(dx=0.01)
    with pytest.raises(AssemblyError, match=r"0\.01 m apart, more than the tolerance") as e:
        m.join(p, q)
    assert e.value.code == "join_gap" and e.value.value == pytest.approx(0.01)
    m.join(p, q, tol=0.02)                                       # a wider tolerance accepts it
    m, p, q = _two(reverse=True)
    with pytest.raises(AssemblyError, match=r"don't face each other.*180° from opposed") as e:
        m.join(p, q)
    assert e.value.code == "join_direction" and e.value.value == pytest.approx(180)
    m, p, q = _two(nominal=0.05)
    with pytest.raises(AssemblyError, match=r"different sections.*nominal=0\.1.*nominal=0\.05"):
        m.join(p, q)
    m, p, q = _two()
    c = m.join(p, q)
    assert (c.a, c.b, c.origin) == (p, q, "declared")


def test_join_needs_open_ports(tmp_path):
    m, _ = _model(tmp_path)
    with pytest.raises(AssemblyError, match=r"port '\w+' isn't open; it is connected to") as e:
        m.join(_at(m, "0", 1), _at(m, "2", 0))          # the pipe's outlet meets the valve
    assert e.value.code == "join_port_not_open"


# --- merge ------------------------------------------------------------------------------

def test_two_sheets_merged_and_joined_build_as_one_read(tmp_path):
    s1 = tmp_path / "s1.pcf"
    s2 = tmp_path / "s2.pcf"
    s1.write_text(SHEET_1, encoding="utf-8")
    s2.write_text(SHEET_2, encoding="utf-8")
    together = ix.read_pcf([s1, s2]).to_assembly(_spec()).to_dict()
    a, b = ix.read_pcf(s1).to_model(), ix.read_pcf(s2).to_model()
    with pytest.raises(AssemblyError, match="ids are in both models") as e:
        ix.NetworkModel.merge(a, b)
    assert e.value.code == "merge_id_clash"
    m = ix.NetworkModel.merge(a, b, prefix="s2_")
    m.join(a.parts["1"].ports[1], "s2_" + b.parts["0"].ports[0])
    assert ix.build(m, _spec()).to_dict() == together
    inferred = ix.NetworkModel.merge(a, b, prefix="s2_", infer=True)
    assert [(c.origin, c.a, c.b) for c in inferred.connections] == \
        [("inferred", a.parts["1"].ports[1], "s2_" + b.parts["0"].ports[0])]
    assert ix.build(inferred, _spec()).to_dict() == together
    # the merged log replays: s2 is re-read through its import entry
    fresh = ix.read_pcf(s1).to_model()
    assert _canonical(m.replay(fresh)) == _canonical(m)


# --- the log ------------------------------------------------------------------------------

def test_the_log_replays_on_a_fresh_import_and_undo_restores_the_cut(tmp_path):
    m, path = _model(tmp_path)
    assert m.log[0]["op"] == "import"
    assert m.log[0]["args"] == {"importer": "pcf", "source": [str(path)],
                                "options": {"unit_scale": None, "joint_max": 1.6e-3,
                                            "ignore_types": None}}
    assert set(m.log[0]) == {"op", "args", "time", "version"}
    a, b = _at(m, "1", 1), _at(m, "2", 0)
    m.cut_at(a)
    cut_state = _canonical(m)
    m.join(a, b)
    assert len(m.log) == 3
    fresh = ix.read_pcf(path).to_model()
    assert _canonical(m.replay(fresh)) == _canonical(m)
    m.undo()
    assert _canonical(m) == cut_state
    m.undo()
    assert _canonical(m)["cuts"] == [] and [e["op"] for e in m.log] == ["import"]
    with pytest.raises(AssemblyError, match="no logged operation") as e:
        m.undo()
    assert e.value.code == "model_undo_empty"


def test_a_hand_built_merge_cannot_be_replayed_without_its_source():
    m, p, q = _two()
    fresh = ix.NetworkModel()
    fresh.add_part(ix.Straight, [(0, 0, 0), (1, 0, 0)], id="a", system="L")
    with pytest.raises(AssemblyError, match="no import entry") as e:
        m.replay(fresh)
    assert e.value.code == "model_replay_needs_source"


WELDED = """\
UNITS-BORE MM
UNITS-CO-ORDS MM
PIPELINE-REFERENCE L-1
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
WELD
    END-POINT 1000 0 0 100
    END-POINT 1000 0 0 100
PIPE
    END-POINT 1000 0 0 100
    END-POINT 2000 0 0 100
"""


def test_a_cut_that_other_ports_bypass_is_an_error(tmp_path):
    """At a weld three ports meet: cutting one pair leaves the pipes joined
    through the others; cut_at() separates them all."""
    m, _ = _model(tmp_path, WELDED)
    pipe, weld = m.parts["0"], m.parts["1"]
    m.cut((pipe.ports[1], weld.ports[0]))
    with pytest.raises(AssemblyError, match="is bypassed") as e:
        ix.build(m, _spec())
    assert e.value.code == "model_cut_bypassed"
    m.undo()
    m.cut_at(pipe.ports[1])
    assert len(ix.build_pieces(m, _spec())) == 2
