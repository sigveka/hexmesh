"""
PCF insulation and equipment connections (task 0038, decision 0023).

* ``to_assembly(insulation=True)`` adds an ``insulation`` shell where the
  PCF says (``INSULATION ON``, keypoint overrides) and ends or starts it one
  cell inside a straight neighbour.
* Ends at ``END-CONNECTION-EQUIPMENT`` are named ``<equipment>_<nozzle>``
  and marked, so ``extend_open_ends`` leaves them; the mark is saved.

Fixtures are hand-written (millimetres) from the guide's keyword syntax.
"""

import warnings

import gmsh
import numpy as np
import pytest

from hexmesh import Session
from hexmesh.assembly import Assembly, AssemblyError, Straight
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec
from hexmesh.io.readers.pcf import read_pcf


def _steel():
    return (PipeSpec(nang=4).core("fluid", CircleShape(radius=0.05, nang=4), nrad=3)
            .shell("steel", dR=0.005, nrad=2))


def _single():
    return PipeSpec(nang=4).core("fluid", CircleShape(radius=0.05, nang=4), nrad=3)


HEADER = """\
ISOGEN-FILES ISOGEN.FLS
UNITS-BORE MM
UNITS-CO-ORDS MM
"""


def _read(tmp_path, text, name="net.pcf"):
    p = tmp_path / name
    p.write_text(text)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        return read_pcf(p)


# Insulated pipe, bare valve, insulated pipe, bare flange at the open end.
VALVE_LINE = HEADER + """\
PIPELINE-REFERENCE L-1
    INSULATION-THICKNESS 50
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
    INSULATION ON
VALVE
    END-POINT 1000 0 0 100
    END-POINT 1300 0 0 100
    SKEY VVFL
PIPE
    END-POINT 1300 0 0 100
    END-POINT 2300 0 0 100
    INSULATION ON
FLANGE
    END-POINT 2300 0 0 100
    END-POINT 2400 0 0 100
    INSULATION OFF
"""


def _straights(asm):
    return {e.name: e.fitting for e in asm.edges}


# --- insulation -------------------------------------------------------------------

def test_off_by_default(tmp_path):
    asm = _read(tmp_path, VALVE_LINE).to_assembly(_steel(), axial_cell=0.05)
    assert all(not getattr(e.fitting, "stack_changes", ()) for e in asm.edges)
    assert asm.inlet.spec.layer_names == ["fluid", "steel"]


def test_switches_go_one_cell_into_the_bare_neighbour(tmp_path):
    net = _read(tmp_path, VALVE_LINE)
    assert net.insulation_thickness == {"L-1": pytest.approx(0.05)}
    asm = net.to_assembly(_steel(), axial_cell=0.05, insulation=True)
    f = _straights(asm)
    assert asm.inlet.spec.layer_names == ["fluid", "steel", "insulation"]
    assert asm.inlet.spec.shells[-1].dR == pytest.approx(0.05)
    assert not f["PIPE_1"].stack_changes and not f["PIPE_2"].stack_changes
    valve = f["VALVE_1"]
    assert [i for i, _ in valve.stack_changes] == [1, valve.n_layers - 1]
    assert [sp.layer_names[-1] for _, sp in valve.stack_changes] == ["steel", "insulation"]
    flange = f["FLANGE_1"]
    assert [i for i, _ in flange.stack_changes] == [1]
    assert asm.interfaces[-1].spec.layer_names == ["fluid", "steel"]


def _volume_x_ranges(name):
    tag = next(t for d, t in gmsh.model.getPhysicalGroups(3)
               if gmsh.model.getPhysicalName(d, t) == name)
    return [gmsh.model.getBoundingBox(3, v)[0::3]
            for v in gmsh.model.getEntitiesForPhysicalGroup(3, tag)]


def _surface_groups():
    return {gmsh.model.getPhysicalName(d, t): list(gmsh.model.getEntitiesForPhysicalGroup(d, t))
            for d, t in gmsh.model.getPhysicalGroups(2)}


def test_insulated_line_meshes_where_the_pcf_says(tmp_path):
    asm = _read(tmp_path, VALVE_LINE).to_assembly(_steel(), axial_cell=0.05,
                                                  insulation=True)
    asm.validate()
    predicted = asm.cell_count()
    with Session("pcf_insulation"):
        asm.mesh()
        types, tags, _ = gmsh.model.mesh.getElements(3)
        assert list(types) == [5]
        assert sum(len(t) for t in tags) == predicted
        # insulated: the pipes, plus one cell into the valve at each side
        # and one into the flange (cells of 0.05 m)
        allowed = [(0.0, 1.05), (1.25, 2.35)]
        for x0, x1 in _volume_x_ranges("insulation"):
            assert any(a - 1e-6 <= x0 and x1 <= b + 1e-6 for a, b in allowed), (x0, x1)
        g = _surface_groups()
        assert len(g["insulation_end"]) == 3 * 4             # three switches
        assert "interface_steel_insulation" in g
        assert asm.check_quality().ok


def test_keypoint_override_switches_mid_pipe(tmp_path):
    text = HEADER + """\
PIPELINE-REFERENCE L-1
    INSULATION-THICKNESS 50
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100 INSULATION-OFF
    INSULATION ON
"""
    asm = _read(tmp_path, text).to_assembly(_steel(), axial_cell=0.1, insulation=True)
    pipe = asm.edges[0].fitting
    assert pipe.n_layers == 10
    assert [i for i, _ in pipe.stack_changes] == [5]
    assert asm.interfaces[-1].spec.layer_names == ["fluid", "steel"]


def test_bare_tee_between_insulated_pipes(tmp_path):
    """The tee stays bare; the pipes either side stop the insulation."""
    text = HEADER + """\
PIPELINE-REFERENCE L-1
    INSULATION-THICKNESS 20
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
    INSULATION ON
TEE
    END-POINT 1000 0 0 100
    END-POINT 1200 0 0 100
    CENTRE-POINT 1100 0 0
    BRANCH1-POINT 1100 300 0 50
PIPE
    END-POINT 1200 0 0 100
    END-POINT 2000 0 0 100
    INSULATION ON
"""
    asm = _read(tmp_path, text).to_assembly(_single(), axial_cell=0.1, insulation=True)
    f = _straights(asm)
    assert [i for i, _ in f["PIPE_1"].stack_changes] == [f["PIPE_1"].n_layers - 1]
    assert [i for i, _ in f["PIPE_2"].stack_changes] == [1]
    asm.validate()
    predicted = asm.cell_count()
    with Session("pcf_insulated_tee"):
        asm.mesh()
        assert sum(len(t) for t in gmsh.model.mesh.getElements(3)[1]) == predicted


INSULATED_TEE = HEADER + """\
PIPELINE-REFERENCE L-1
    INSULATION-THICKNESS 20
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
    INSULATION ON
TEE
    END-POINT 1000 0 0 100
    END-POINT 1200 0 0 100
    CENTRE-POINT 1100 0 0
    BRANCH1-POINT 1100 300 0 50
    INSULATION ON
"""


@pytest.mark.parametrize("text, match", [
    (INSULATED_TEE, r"component 1 \(TEE TEE_1.*insulated junction"),
    (VALVE_LINE.replace("    INSULATION-THICKNESS 50\n", ""),
     r"pipeline 'L-1'.*component 0 \(PIPE PIPE_1.*no INSULATION-THICKNESS"),
    (HEADER + """\
PIPELINE-REFERENCE L-1
    INSULATION-THICKNESS 50
ELBOW
    END-POINT 0 0 0 100
    END-POINT 150 150 0 100
    CENTRE-POINT 150 0 0
    INSULATION ON
ELBOW
    END-POINT 150 150 0 100
    END-POINT 300 300 0 100
    CENTRE-POINT 150 300 0
""", r"component 0 \(ELBOW ELBOW_1.*no straight component next to it"),
    (VALVE_LINE.replace("""PIPELINE-REFERENCE L-1
    INSULATION-THICKNESS 50
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
    INSULATION ON
""", """PIPELINE-REFERENCE L-0
    INSULATION-THICKNESS 30
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
    INSULATION ON
PIPELINE-REFERENCE L-1
    INSULATION-THICKNESS 50
""").replace("""VALVE
    END-POINT 1000 0 0 100
    END-POINT 1300 0 0 100
    SKEY VVFL
""", """VALVE
    END-POINT 1000 0 0 100
    END-POINT 1300 0 0 100
    INSULATION ON
"""), r"insulation thickness changes from 0.03 m to 0.05 m"),
], ids=["insulated-tee", "no-thickness", "no-straight", "thickness-change"])
def test_insulation_errors_name_the_component(tmp_path, text, match):
    with pytest.raises(AssemblyError, match=match):
        _read(tmp_path, text).to_assembly(_steel() if "TEE" not in text else _single(),
                                          axial_cell=0.05, insulation=True)


def test_spec_with_insulation_shell_rejected(tmp_path):
    spec = _steel().shell("insulation", dR=0.02, nrad=2)
    with pytest.raises(ValueError, match="already has one"):
        _read(tmp_path, VALVE_LINE).to_assembly(spec, insulation=True)


# --- equipment --------------------------------------------------------------------

# Two vessels before the first pipeline (the guide's layout); the line runs
# from V-101's nozzle N1 to V-102's N2, given once by nozzle reference and
# once as <equipment>/<nozzle>.
VESSELS = HEADER + """\
EQUIPMENT-REFERENCE V-101
    LOCATION -500 0 0
    NOZZLE
    REFERENCE N1
    DIRECTION EAST
    CO-ORDS 0 0 0 100 FL
    POSITION EDGE
EQUIPMENT-REFERENCE V-102
    NOZZLE
    REFERENCE V102-N2
    DIRECTION WEST
    CO-ORDS 2000 0 0 100 FL
PIPELINE-REFERENCE P-1
END-CONNECTION-EQUIPMENT
    END-POINT 0 0 0 100
    CONNECTION-REFERENCE N1
PIPE
    END-POINT 0 0 0 100
    END-POINT 2000 0 0 100
END-CONNECTION-EQUIPMENT
    CO-ORDS 2000 0 0
    CONNECTION-REFERENCE V-102/N2
"""


def test_equipment_blocks_parsed(tmp_path):
    net = _read(tmp_path, VESSELS)
    assert "EQUIPMENT-REFERENCE" not in net.header
    eq = [a for k, a in net.connections if k == "EQUIPMENT-REFERENCE"]
    assert [e["EQUIPMENT-REFERENCE"] for e in eq] == ["V-101", "V-102"]
    assert [n["REFERENCE"] for n in eq[0]["NOZZLES"]] == ["N1"]
    np.testing.assert_allclose(eq[1]["NOZZLES"][0]["_point"], [2, 0, 0])


def test_ends_named_after_nozzles_and_never_extended(tmp_path):
    asm = _read(tmp_path, VESSELS).to_assembly(_steel(), axial_cell=0.1)
    out = asm.interfaces[-1]
    assert asm.inlet.name == "V_101_N1" and out.name == "V_102_N2"
    assert asm.inlet.equipment and out.equipment
    before = [i.frame.position.copy() for i in (asm.inlet, out)]
    n = len(asm.edges)
    asm.extend_open_ends(upstream=5, downstream=5)
    assert len(asm.edges) == n
    for i, x in zip((asm.inlet, out), before):
        np.testing.assert_allclose(i.frame.position, x)
    with pytest.raises(AssemblyError, match="equipment end"):
        asm.prepend(Straight(0.2, n_layers=2))


def test_equipment_mark_survives_round_trip(tmp_path):
    asm = _read(tmp_path, VESSELS).to_assembly(_steel(), axial_cell=0.1)
    d = asm.to_dict()
    assert d["equipment"] == [0, 1]
    back = Assembly.from_dict(d)
    assert [i.equipment for i in back.interfaces] == [True, True]
    assert back.to_dict() == d


def test_unmarked_ends_still_extend(tmp_path):
    text = VESSELS[:VESSELS.rindex("END-CONNECTION-EQUIPMENT")]
    asm = _read(tmp_path, text).to_assembly(_steel(), axial_cell=0.1)
    n = len(asm.edges)
    asm.extend_open_ends(upstream=5, downstream=5)
    assert len(asm.edges) == n + 1                   # the free outlet only
    assert "equipment" in asm.to_dict()


def test_nozzle_component_form(tmp_path):
    text = VESSELS.replace("""END-CONNECTION-EQUIPMENT
    CO-ORDS 2000 0 0
    CONNECTION-REFERENCE V-102/N2
""", """NOZZLE
    CO-ORDS 2000 0 0
    CONNECTION-REFERENCE V102-N2
""")
    asm = _read(tmp_path, text).to_assembly(_steel(), axial_cell=0.1)
    assert asm.interfaces[-1].name == "V_102_V102_N2"


@pytest.mark.parametrize("old, new, match", [
    ("CO-ORDS 0 0 0 100 FL", "CO-ORDS 0 50 0 100 FL",
     r"END-CONNECTION-EQUIPMENT N1: nozzle N1 is at .* 0.05 m apart"),
    ("""    CO-ORDS 2000 0 0
    CONNECTION-REFERENCE V-102/N2""", """    CO-ORDS 2100 0 0
    CONNECTION-REFERENCE V-102/N2""",
     r"END-CONNECTION-EQUIPMENT V-102/N2 at .*no open pipe end there.*component 0 "
     r"\(PIPE PIPE_1.*0.1 m away"),
])
def test_equipment_position_mismatch(tmp_path, old, new, match):
    with pytest.raises(AssemblyError, match=match):
        _read(tmp_path, VESSELS.replace(old, new)).to_assembly(_steel(), axial_cell=0.1)
