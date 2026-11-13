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
The network model and its builder (task 0065, decision 0032): a model built
by hand, with no importer; the spec callable's two forms; the builder's
independence from the importers; what the PCF importer puts in the model.
"""

import ast
import subprocess
import sys
from pathlib import Path

import gmsh
import numpy as np
import pytest

from hexmesh import interchange as ix
from hexmesh.assembly import AssemblyError, Bend, Straight, Tee
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec

ROOT = Path(__file__).resolve().parents[1]


def _spec(bore=0.1):
    return PipeSpec(nang=4).core("fluid", CircleShape(radius=bore / 2, nang=4), nrad=3)


def _line(model=None, system="L-1"):
    """Straight → bend → straight → tee (branch +y) → straights, metres."""
    m = model or ix.NetworkModel()
    m.networks[system] = ix.Network(system, kind="line")
    big, small = ix.Section(nominal=0.1), ix.Section(nominal=0.05)
    a = m.add_part(ix.Straight, [(0, 0, 0), (1, 0, 0)], system=system, name="RUN_IN")
    a_out = m.ports[a.ports[1]]
    m.ports[a.ports[0]].section = big
    m.ports[a.ports[0]].flow = "in"
    b = m.add_part(ix.Bend, [m.add_port((1, 0, 0)), m.add_port((1.3, 0.3, 0))],
                   corner=(1.3, 0, 0), system=system)
    c = m.add_part(ix.Straight, [(1.3, 0.3, 0), (1.3, 1.0, 0)], system=system)
    t = m.add_part(ix.Junction, [(1.3, 1.0, 0), (1.3, 1.2, 0), (1.0, 1.1, 0)], form="tee",
                   centre=(1.3, 1.1, 0), system=system)
    for q, sec in zip(t.ports, (big, big, small)):
        m.ports[q].section = sec
    m.add_part(ix.Straight, [(1.3, 1.2, 0), (1.3, 2.0, 0)], system=system)
    br = m.add_part(ix.Straight, [(1.0, 1.1, 0), (0.4, 1.1, 0)], system=system)
    for part in m.parts.values():
        for q in part.ports:
            if m.ports[q].section is None:
                m.ports[q].section = small if part is br else big
    m.add_part(ix.Terminal, [m.add_port((0.4, 1.1, 0), equipment={"tag": "P-1"})],
               name="pump_suction")
    return m, (a_out, b, c)


def test_hand_built_model_builds_and_meshes(gmsh_session):
    m, _ = _line()
    asm = ix.build(m, lambda bore: _spec(bore), axial_cell=0.1)
    kinds = [type(e.fitting) for e in asm.edges]
    assert kinds == [Straight, Bend, Straight, Tee, Straight, Straight]
    assert [e.label for e in asm.edges][:2] == ["RUN_IN", "BEND_1"]
    assert asm.edges[1].fitting.angle == pytest.approx(90)
    ends = {i.name: i for i in asm.open_interfaces()}
    assert {"L_1_end2", "pump_suction"} <= set(ends)       # the terminal names its end
    assert ends["pump_suction"].equipment and not ends["L_1_end2"].equipment
    assert asm.inlet.name == "L_1_end1"
    assert m.report["tolerance"] > 0 and m.report["joints"] == []
    asm.validate()
    predicted = asm.cell_count()
    asm.mesh()
    assert sum(len(t) for t in gmsh.model.mesh.getElements(3)[1]) == predicted


def test_declared_flow_chooses_the_root():
    m, _ = _line()
    parts = list(m.parts.values())
    assert np.allclose(ix.build(m, lambda bore: _spec(bore)).inlet.frame.position, 0)
    m.ports[parts[0].ports[0]].flow = None
    m.ports[parts[4].ports[1]].flow = "in"             # the run's far end, (1.3, 2, 0)
    asm = ix.build(m, lambda bore: _spec(bore))
    np.testing.assert_allclose(asm.inlet.frame.position, [1.3, 2.0, 0], atol=1e-12)
    assert asm.inlet.name == "L_1_end2"


def test_spec_receives_a_section_when_it_asks():
    m, _ = _line()
    seen = []

    def by_section(section: ix.Section):
        seen.append(section)
        return _spec(section.nominal)
    ix.build(m, by_section)
    assert seen and all(isinstance(s, ix.Section) for s in seen)
    assert {s.nominal for s in seen} >= {0.1, 0.05}
    bores = []
    ix.build(m, lambda bore: bores.append(bore) or _spec(bore))
    assert bores and all(isinstance(b, float) for b in bores)
    one = ix.build(m, lambda bore: _spec(bore)).to_dict()
    assert ix.build(m, by_section).to_dict() == one


def test_reject_and_formatter_name_the_part():
    m, (_, bend, _) = _line()
    bend.reject = "bends of this kind are out of scope"
    with pytest.raises(AssemblyError, match=r"part 1 \(BEND BEND_1 at .*out of scope"):
        ix.build(m, _spec())
    ix.register_formatter("test-format", lambda part, at, name: f"record <{name}>")
    try:
        bend.provenance = ix.Provenance(format="test-format")
        with pytest.raises(AssemblyError, match=r"record <BEND_1>: bends of this kind"):
            ix.build(m, _spec())
    finally:
        ix.FORMATTERS.pop("test-format")


def test_build_pieces_and_selection():
    m, _ = _line()
    m.networks["L-2"] = ix.Network("L-2")
    far = m.add_part(ix.Straight, [(0, 5, 0), (1, 5, 0)], system="L-2", id="far")
    m.ports[far.ports[0]].section = ix.Section(nominal=0.1)
    with pytest.raises(AssemblyError, match=r"2 unconnected pieces: line L-1 \(components "
                                            r"0–5\); network L-2 \(components 7\)"):
        ix.build(m, _spec())
    out = ix.build_pieces(m, lambda bore: _spec(bore))
    assert list(out) == ["L_1", "L_2"]
    assert [type(e.fitting) for e in out["L_2"].edges] == [Straight]
    alone = ix.build(m, _spec(), selection={"far"})
    assert alone.to_dict() == out["L_2"].to_dict()


def test_polyline_is_straights_or_a_spline():
    m = ix.NetworkModel()
    m.add_part(ix.Polyline, [(0, 0, 0), (1, 0, 0), (2, 0.2, 0), (3, 0.2, 0.1)], name="R")
    with pytest.raises(AssemblyError, match=r"R_2 .*changes direction"):
        ix.build(m, _spec())
    asm = ix.build(m, _spec(), kinks="spline", axial_cell=0.1)
    assert [type(e.fitting).__name__ for e in asm.edges] == ["Straight", "SplinePipe"]


def test_model_rejects_foreign_classes_and_reused_ids():
    m = ix.NetworkModel()
    with pytest.raises(TypeError):
        m.add_part(Straight, [(0, 0, 0), (1, 0, 0)])
    m.add_part(ix.Straight, [(0, 0, 0), (1, 0, 0)], id="a")
    with pytest.raises(ValueError, match="already used"):
        m.add_part(ix.Straight, [(1, 0, 0), (2, 0, 0)], id="a")


def test_builder_imports_no_importer():
    """Constraint 1: the builder and the model know no source format."""
    for f in ("build.py", "graph.py", "insulation.py", "model.py"):
        tree = ast.parse((ROOT / "hexmesh" / "interchange" / f).read_text(encoding="utf-8"))
        mods = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)] + \
               [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert not [x for x in mods if "readers" in x or "importers" in x or "pcf" in x
                    or "bathymetry" in x], f
    code = ("import sys, hexmesh.interchange; "
            "print([m for m in sys.modules if m.startswith(('hexmesh.io.readers', "
            "'hexmesh.interchange.importers'))])")
    run = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True,
                         text=True, check=True)
    assert run.stdout.strip() == "[]"


PCF = """\
ISOGEN-FILES ISOGEN.FLS
UNITS-BORE MM
UNITS-CO-ORDS MM
PIPELINE-REFERENCE L-1
    INSULATION-THICKNESS 50
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
    FLOW 2
    INSULATION ON
ELBOW
    END-POINT 1000 0 0 100
    END-POINT 1150 150 0 100
    CENTRE-POINT 1150 0 0
    ANGLE 9000
PIPE
    END-POINT 1150 150 0 100
    END-POINT 1150 800 0 100 INSULATION-OFF
END-CONNECTION-EQUIPMENT
    CO-ORDS 1150 800 0
    CONNECTION-REFERENCE V-1/N2
"""


def test_pcf_importer_fills_the_model(tmp_path):
    from hexmesh.interchange.importers.pcf import read_pcf
    p = tmp_path / "l.pcf"
    p.write_text(PCF, encoding="utf-8")
    net = read_pcf(p)
    m = net.to_model()
    parts = list(m.parts.values())
    assert [type(x) for x in parts] == [ix.Straight, ix.Bend, ix.Straight, ix.Terminal]
    assert [x.name for x in parts] == ["PIPE_1", "ELBOW_1", "PIPE_2", "V_1_N2"]
    pipe, elbow, _, term = parts
    assert m.networks["L-1"].kind == "pipeline"
    assert m.networks["L-1"].insulation_thickness == pytest.approx(0.05)
    assert [m.ports[q].flow for q in pipe.ports] == ["out", "in"]
    assert pipe.insulation == "on" and m.ports[parts[2].ports[1]].insulation == "off"
    assert m.ports[pipe.ports[0]].section.nominal == pytest.approx(0.1)
    assert elbow.stated_angle == pytest.approx(90) and np.allclose(elbow.corner, [1.15, 0, 0])
    assert m.ports[term.ports[0]].equipment == {"tag": "V-1", "nozzle": "N2"}
    assert elbow.provenance.format == "pcf" and elbow.provenance.record == "ELBOW"
    assert ix.describe(elbow, elbow.corner).startswith("component 1 (ELBOW ELBOW_1 at")
    assert net.to_assembly(_spec()).to_dict() == ix.build(m, _spec()).to_dict()
