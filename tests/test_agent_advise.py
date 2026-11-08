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
"""The resolution advisor and the ``hexmesh`` CLI (task 0098, decision 0040)."""

import importlib
import io
import json
import math
import sys
import warnings

import gmsh
import numpy as np
import pytest

from hexmesh import Assembly, PipeSpec, Session, Straight
from hexmesh.agent import AdviceError, advise, apply
from hexmesh.agent import _calibrate, cli
from hexmesh.assembly import limits
from hexmesh.core.grading import first_cell_height, progression_for_first_cell
from hexmesh.core.shape import core_wall_span

advise_mod = importlib.import_module("hexmesh.agent.advise")   # the module, not the function
WATER = {"density": 998.0, "viscosity": 1.00e-3}       # [white_2011, table A.1]
AIR = {"density": 1.205, "viscosity": 1.80e-5}         # [white_2011, table A.2]


def _pipe(radius, length=0.6, nang=6, nrad=3):
    a = Assembly(PipeSpec(nang=nang).core("fluid", radius=radius, nrad=nrad))
    a.add(Straight(length, n_layers=4))
    return a


def _example(name):
    return importlib.import_module(f"hexmesh.examples.{name}").build()


def _cal(shape, cls, aspect="2"):
    c = advise_mod.calibration()["shapes"]
    return (c["circle"] if shape == "circle" else c["rect"]["aspect"][aspect])["classes"][cls]


# --- hand-worked cases --------------------------------------------------------------

def test_laminar_poiseuille_water_re_100():
    """D 0.02 m, U = Re ν / D: Re 100, laminar, the medium class's cells
    along a diameter (calibration.json, circle), the calibrated uniform
    ring: first cell = the mid-arc span / nrad."""
    nu = WATER["viscosity"] / WATER["density"]
    u = 100 * nu / 0.02
    r = advise(_pipe(0.01), {"fluid": "water", "flow": {"velocity": u}})
    s, = r["sections"]
    assert s["re"] == pytest.approx(100, rel=1e-9) and s["regime"] == "laminar"
    n = _cal("circle", "medium")["n"]                   # 21.98 cells along D
    nang = math.ceil(n / 2)
    nang += nang % 2                                    # even: 12
    assert (r["density"]["nang"], r["density"]["nrad"]) == (nang, nang // 2) == (12, 6)
    assert r["density"]["mprg"] == 1.0
    assert s["first_cell"] == pytest.approx(core_wall_span(0.01) / 6, rel=1e-12)
    # axial: length / (aspect 6 × core cell D / (nang + 2 nrad))
    h = 0.02 / (12 + 12)
    assert r["fittings"][0]["counts"] == {"n_layers": math.ceil(0.6 / (6 * h))}
    assert r["calibration"]["circle"]["validated"] is True
    assert r["totals"]["cells"] == Assembly.from_dict(apply(_pipe(0.01).to_dict(),
                                                           r["table"])).cell_count()


def test_turbulent_smooth_pipe_air_re_5e4():
    """D 0.05 m, Re 5·10⁴: Blasius f = 0.3164 Re^-1/4 = 0.02116,
    u_τ = U √(f/8), y = ν / u_τ for y⁺ = 1 [blasius_1913]."""
    nu = AIR["viscosity"] / AIR["density"]
    u = 5e4 * nu / 0.05
    f = 0.3164 * 5e4 ** -0.25
    assert f == pytest.approx(0.02116, abs=1e-5)
    y1 = nu / (u * math.sqrt(f / 8))
    r = advise(_pipe(0.025), {"fluid": "air", "flow": {"velocity": u}})
    s, = r["sections"]
    assert s["regime"] == "turbulent" and s["re"] == pytest.approx(5e4, rel=1e-9)
    assert s["first_cell"] == pytest.approx(y1, rel=0.02)
    assert s["y_plus"] == pytest.approx(1, rel=0.02)
    q = 1 / r["density"]["mprg"]
    assert q <= limits.MAX_WALL_GROWTH + 1e-12
    assert first_cell_height(core_wall_span(0.025), r["density"]["nrad"], q) == \
        pytest.approx(s["first_cell"], rel=1e-12)
    assert r["calibration"]["circle"]["validated"] is True     # the core's counts...
    assert "advice_not_validated" in {n["code"] for n in r["notes"]}   # ...not the wall


def test_haaland_above_blasius_range():
    """Haaland, smooth: 1/√f = -1.8 log10(6.9/Re) [haaland_1983]."""
    f, src = advise_mod.friction_factor(1e6)
    assert f == pytest.approx((-1.8 * math.log10(6.9e-6)) ** -2) and "Haaland" in src
    assert f == pytest.approx(0.0116, abs=2e-4)          # the Moody chart's smooth curve


def test_two_to_one_duct():
    """a/b 2, half-sides 0.02 × 0.01: D_h = 4ab/(a+b) = 0.02667; the a/b 2
    medium class's cells across D_h; square cells, so nang_w = 2 nang_h."""
    a = Assembly(PipeSpec(nang_w=8, nang_h=4).core("fluid", half_w=0.02, half_h=0.01))
    a.add(Straight(0.5, n_layers=4))
    nu = WATER["viscosity"] / WATER["density"]
    d_h = 4 * 0.02 * 0.01 / 0.03
    r = advise(a, {"fluid": "water", "flow": {"velocity": 200 * nu / d_h}})
    s, = r["sections"]
    assert s["d_h"] == pytest.approx(d_h) and s["re"] == pytest.approx(200)
    n_short = math.ceil(_cal("rect", "medium", "2")["n"] * 0.02 / d_h)
    assert (r["density"]["nang_w"], r["density"]["nang_h"]) == (2 * n_short, n_short) == (60, 30)
    assert s["first_cell"] == pytest.approx(0.02 / 30)
    assert r["calibration"]["rect a/b 2"]["case"] == "rect_duct"


def test_aspect_between_measured_takes_the_worse_neighbour():
    a = Assembly(PipeSpec(nang_w=8, nang_h=4).core("fluid", half_w=0.03, half_h=0.01))
    a.add(Straight(0.5, n_layers=4))
    r = advise(a, {"fluid": "water", "flow": {"velocity": 0.001}})
    c, = r["calibration"].values()
    assert c["series"] == "a/b 4" and c["n"] == _cal("rect", "medium", "4")["n"]
    wide = Assembly(PipeSpec(nang_w=8, nang_h=4).core("fluid", half_w=0.06, half_h=0.01))
    wide.add(Straight(0.5, n_layers=4))
    c, = advise(wide, {"fluid": "water", "flow": {"velocity": 0.001}})["calibration"].values()
    assert c["validated"] is False and "past the largest measured" in c["basis"]


def test_flow_splits_by_downstream_area():
    r = advise(_example("networks.distribution_tree"),
               {"fluid": "water", "flow": {"flow_rate": 1e-4}})
    tee = [s for s in r["sections"] if s["name"] == "Tee1"]
    q_in = next(s["flow_rate"] for s in tee if s["port"] == 0)
    assert q_in == pytest.approx(1e-4)
    branch = next(s for s in tee if s["port"] > 0)
    assert 0 < branch["flow_rate"] < q_in


# --- calibration --------------------------------------------------------------------

def test_calibration_is_reproducible():
    path = advise_mod.CALIBRATION
    assert path.read_text(encoding="utf-8") == _calibrate.dumps(_calibrate.build())


def test_calibration_classes_cite_their_cases():
    cal = advise_mod.calibration()
    series = [cal["shapes"]["circle"]] + list(cal["shapes"]["rect"]["aspect"].values())
    for s in series:
        assert s["case"] in ("poiseuille", "rect_duct")
        for name, c in s["classes"].items():
            assert c["basis"] and isinstance(c["validated"], bool)
            if not c["validated"]:
                assert "extrapolated" in c["basis"] or c.get("out_of_range")
                assert c["nearest"]["level"]
            if not c.get("out_of_range"):
                assert max(c["errors"].values()) <= _calibrate.CLASSES[name] * (1 + 1e-6)
    fine = cal["shapes"]["circle"]["classes"]["fine"]
    assert fine["validated"] is False and fine["k"] <= 2 * 4


def test_fine_request_says_it_is_not_validated():
    r = advise(_pipe(0.01), {"fluid": "water", "flow": {"velocity": 0.005},
                             "accuracy": "fine"})
    assert r["calibration"]["circle"]["validated"] is False
    assert "extrapolated" in r["calibration"]["circle"]["basis"]
    assert "advice_not_validated" in {n["code"] for n in r["notes"]}


def test_every_report_states_the_scope_and_the_8x_rule():
    r = advise(_pipe(0.01), {"fluid": "water", "flow": {"velocity": 0.005}})
    notes = {n["code"]: n["message"] for n in r["notes"]}
    assert "straight runs" in notes["advice_calibration_scope"]
    assert "8×" in notes["advice_eight_x"]
    assert r["inputs"]["length_unit"] == "m" and r["units"]["length"] == "m"


# --- the budget ---------------------------------------------------------------------

def test_a_stack_of_rectangles_keeps_unequal_counts():
    """A shelled duct isn't tied (task 0101, decision 0041 option B): the
    lagged duct keeps nang_w ≠ nang_h, and the advice validates."""
    r = advise(_example("sections.lagged_duct"),
               {"fluid": "water", "flow": {"velocity": 0.002}})
    d = r["density"]
    assert d["nang"] is None and d["nang_w"] == 2 * d["nang_h"]
    assert not any("needs nang = nang_w = nang_h" in x for x in r["density_reasons"])
    assert r["validation"]["error"] is None


def test_a_circle_meeting_a_rectangle_names_what_ties_it():
    """A circle carries one count, so a circle → rectangle Transition still
    ties the counts, and the reason names the fitting."""
    r = advise(_example("sections.duct_transition"),
               {"fluid": "water", "flow": {"velocity": 0.002}})
    d = r["density"]
    assert d["nang"] == d["nang_w"] == d["nang_h"]
    assert any(x.startswith("Transition1 (a Transition) joins a circle to a rectangle")
               for x in r["density_reasons"])


def test_budget_reduces_in_order_and_keeps_the_first_cell():
    asm = _example("fittings.smooth_bend")
    inputs = {"fluid": "water", "flow": {"velocity": 0.5}}
    free = advise(asm, inputs)
    budget = free["totals"]["cells"] // 4
    r = advise(asm, {**inputs, "budget": budget})
    steps = [s["step"] for s in r["budget_steps"]]
    assert steps[0].startswith("straights' axial aspect")
    assert all(s.startswith("accuracy") for s in steps[1:-1] or steps[1:])
    cells = [free["totals"]["cells"]] + [s["cells_after"] for s in r["budget_steps"]]
    assert cells == sorted(cells, reverse=True) and r["totals"]["cells"] == cells[-1]
    assert r["totals"]["within_budget"] and r["ok"]
    first = {s["name"]: s["first_cell"] for s in free["sections"]}
    for s in r["sections"]:                 # turbulent: the y⁺ target never moves
        assert s["regime"] == "turbulent" and s["first_cell"] == pytest.approx(first[s["name"]])


def test_impossible_budget_is_a_coded_error_with_the_shortfall():
    r = advise(_example("fittings.smooth_bend"),
               {"fluid": "water", "flow": {"velocity": 0.005}, "budget": 10})
    assert not r["ok"] and r["error"]["code"] == "advice_budget_unreachable"
    assert r["error"]["value"] == r["totals"]["cells"] > 10
    assert r["error"]["limit"] == {"max": 10}
    assert [s["step"].split()[0] for s in r["budget_steps"]][-1] == "fittings'"


# --- inputs -------------------------------------------------------------------------

@pytest.mark.parametrize("inputs, code", [
    ({"fluid": "water", "flow": {"velocity": 1}, "wall": "wall-function"},
     "advice_wall_function_unsupported"),
    ({"fluid": "honey", "flow": {"velocity": 1}}, "advice_fluid_unknown"),
    ({"fluid": "water", "flow": {"velocity": -1}}, "advice_input_invalid"),
    ({"fluid": "water", "flow": {"speed": 1}}, "advice_input_invalid"),
    ({"fluid": "water", "flow": {"velocity": 1}, "accuracy": "best"}, "advice_input_invalid"),
    ({"fluid": "water", "flow": {"velocity": 1}, "length_unit": "in"}, "advice_input_invalid"),
    ({"fluid": "water", "flow": {"velocity": 1}, "budget": 0}, "advice_input_invalid"),
])
def test_bad_inputs_are_coded(inputs, code):
    with pytest.raises(AdviceError) as info:
        advise(_pipe(0.01), inputs)
    assert info.value.code == code


def test_millimetres_read_as_metres_warn():
    r = advise(_pipe(10.0, length=600), {"fluid": "water", "flow": {"velocity": 1e-6}})
    assert "advice_length_unit_suspect" in {n["code"] for n in r["notes"]}
    mm = advise(_pipe(10.0, length=600), {"fluid": "water", "flow": {"velocity": 0.005},
                                          "length_unit": "mm"})
    assert "advice_length_unit_suspect" not in {n["code"] for n in mm["notes"]}
    assert mm["sections"][0]["re"] == pytest.approx(0.005 * 0.02 / 1.002004e-6, rel=1e-3)


def test_apply_keeps_what_it_does_not_set():
    asm = _example("sections.insulated_pipe")
    r = advise(asm, {"fluid": "water", "flow": {"velocity": 0.005}})
    d = apply(asm.to_dict(), r["table"])
    shells = [(s["name"], s["nrad"]) for s in d["inlet"]["spec"]["shells"]]
    assert shells == [(s["name"], s["nrad"]) for s in asm.to_dict()["inlet"]["spec"]["shells"]]
    assert d["inlet"]["spec"]["nang"] == r["density"]["nang"]


# --- the round trip: advise → apply → build → mesh ----------------------------------

def _meshed_first_cell(asm):
    """The largest wall-normal edge of fitting 0's hexes."""
    msh = gmsh.model.mesh
    wall = {int(n) for d, t in gmsh.model.getPhysicalGroups(2)
            if gmsh.model.getPhysicalName(d, t).endswith("_wall")
            for e in gmsh.model.getEntitiesForPhysicalGroup(d, t)
            for n in msh.getNodes(2, e, includeBoundary=True)[0]}
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
             (0, 4), (1, 5), (2, 6), (3, 7)]
    longest = 0.0
    for v in asm.fitting_volumes()[0]:
        for _, _, nodes in zip(*msh.getElements(3, v)):
            for h in nodes.reshape(-1, 8).astype(int):
                for i, j in edges:
                    if (h[i] in wall) != (h[j] in wall):
                        a, b = msh.getNode(int(h[i]))[0], msh.getNode(int(h[j]))[0]
                        longest = max(longest, float(np.linalg.norm(a - b)))
    return longest


@pytest.mark.parametrize("name, inputs", [
    ("sections.graded_bend", {"fluid": "water", "flow": {"velocity": 0.5}}),     # turbulent
    ("sections.rect_duct", {"fluid": "water", "flow": {"velocity": 0.002},
                            "accuracy": "coarse"}),
    ("networks.distribution_tree", {"fluid": "water", "flow": {"velocity": 0.002},
                                    "accuracy": "coarse"}),
])
def test_round_trip_meshes_as_advised(name, inputs):
    asm = _example(name)
    r = advise(asm, inputs)
    built = Assembly.from_dict(apply(asm.to_dict(), r["table"]))
    with Session(name), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        built.mesh()
        meshed = sum(len(t) for t in gmsh.model.mesh.getElements(3)[1])
        first = _meshed_first_cell(built)
    assert meshed == r["totals"]["cells"]
    advised = next(s["first_cell"] for s in r["sections"] if s["fitting"] == 0)
    assert first == pytest.approx(advised, rel=1e-6)


# --- the CLI ------------------------------------------------------------------------

class _Out:
    def __init__(self):
        self.buffer = io.BytesIO()

    def flush(self):
        pass


def _cli(monkeypatch, *argv):
    out = _Out()
    monkeypatch.setattr(sys, "stdout", out)
    code = cli.main(list(argv))
    return code, out.buffer.getvalue()


@pytest.fixture
def files(tmp_path):
    net = tmp_path / "bend.json"
    _example("fittings.smooth_bend").save(net)
    inputs = tmp_path / "inputs.json"
    inputs.write_text(json.dumps({"fluid": "water", "flow": {"velocity": 0.005},
                                  "accuracy": "coarse"}), encoding="utf-8")
    return tmp_path, net, inputs


def test_every_subcommand_gives_the_same_json_twice(monkeypatch, files):
    tmp, net, inputs = files
    _, raw = _cli(monkeypatch, "advise", str(net), "--inputs", str(inputs))
    table = tmp / "table.json"
    table.write_text(json.dumps(json.loads(raw)["result"]["table"]), encoding="utf-8")
    runs = [("schema",), ("validate", str(net)), ("estimate", str(net)),
            ("describe", str(net)), ("advise", str(net), "--inputs", str(inputs)),
            ("apply", str(net), "--table", str(table)),
            ("preview", str(net), "--out", str(tmp / "v.png")),
            ("build", str(net), "--out", str(tmp / "m.msh"))]
    for argv in runs:
        code, first = _cli(monkeypatch, *argv)
        again = _cli(monkeypatch, *argv)[1]
        out = json.loads(first)
        assert code == 0 and out["ok"] and out["command"] == argv[0], (argv, out)
        assert out["version"] and b"\r" not in first
        if argv[0] not in ("build",):              # build re-meshes: same JSON, new file
            assert again == first, argv
    assert json.loads(_cli(monkeypatch, "estimate", str(net))[1])["result"]["cells"] == \
        _example("fittings.smooth_bend").cell_count()


def test_exit_codes(monkeypatch, files):
    tmp, net, inputs = files
    code, raw = _cli(monkeypatch, "estimate", str(tmp / "missing.json"))
    assert code == 1 and json.loads(raw)["error"]["code"] == "cli_input_unreadable"
    tight = tmp / "tight.json"
    tight.write_text(json.dumps({"fluid": "water", "flow": {"velocity": 0.005},
                                 "budget": 10}), encoding="utf-8")
    code, raw = _cli(monkeypatch, "advise", str(net), "--inputs", str(tight))
    assert code == 2 and json.loads(raw)["error"]["code"] == "advice_budget_unreachable"
    bad = tmp / "bad.json"
    bad.write_text(json.dumps({"fluid": "water", "flow": {"velocity": 1},
                               "wall": "wall-function"}), encoding="utf-8")
    code, raw = _cli(monkeypatch, "advise", str(net), "--inputs", str(bad))
    assert code == 1 and json.loads(raw)["error"]["code"] == "advice_wall_function_unsupported"


def test_validate_with_two_errors_is_incomplete(monkeypatch, tmp_path):
    d = _example("fittings.smooth_bend").to_dict()
    d["edges"][0]["fitting"]["length"] = -1.0           # two independent errors
    d["edges"][2]["fitting"]["length"] = -2.0
    path = tmp_path / "two.json"
    path.write_text(json.dumps(d), encoding="utf-8")
    code, raw = _cli(monkeypatch, "validate", str(path))
    out = json.loads(raw)["result"]
    assert code == 1 and not out["ok"]
    assert len(out["errors"]) == 2 or out["complete"] is False


PCF_LINE = """\
UNITS-BORE MM
UNITS-CO-ORDS MM
PIPELINE-REFERENCE L-1
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
ELBOW
    END-POINT 1000 0 0 100
    END-POINT 1150 150 0 100
    CENTRE-POINT 1150 0 0
PIPE
    END-POINT 1150 150 0 100
    END-POINT 1150 800 0 100
"""


def test_cli_reads_pcf_with_a_spec(monkeypatch, tmp_path):
    """A .pcf network with --spec (task 0066): the same answers as the
    assembly read_pcf builds, saved and passed as a description."""
    from hexmesh.interchange import read_pcf
    pcf = tmp_path / "line.pcf"
    pcf.write_text(PCF_LINE, encoding="utf-8")
    spec = PipeSpec(nang=4).core("fluid", radius=0.05, nrad=2)
    one = tmp_path / "spec.json"
    one.write_text(json.dumps(spec.to_dict()), encoding="utf-8")
    sizes = tmp_path / "sizes.json"
    sizes.write_text(json.dumps([{"nominal": 0.1, "spec": spec.to_dict()}]), encoding="utf-8")
    net = tmp_path / "line.json"
    read_pcf(pcf).to_assembly(spec).save(net)
    for cmd in ("validate", "estimate", "describe"):
        _, want = _cli(monkeypatch, cmd, str(net))
        for s in (one, sizes):
            code, raw = _cli(monkeypatch, cmd, str(pcf), "--spec", str(s))
            assert code == 0 and json.loads(raw)["result"] == json.loads(want)["result"], cmd
    code, raw = _cli(monkeypatch, "describe", str(pcf))
    assert code == 1 and json.loads(raw)["error"]["code"] == "cli_input_unreadable"
    sizes.write_text(json.dumps([{"nominal": 0.05, "spec": spec.to_dict()}]), encoding="utf-8")
    code, raw = _cli(monkeypatch, "estimate", str(pcf), "--spec", str(sizes))
    err = json.loads(raw)["error"]
    assert code == 1 and err["code"] == "cli_spec_size_missing" and err["value"] == 0.1


def test_cli_insulation_on_the_shipped_sample(monkeypatch, tmp_path):
    """``--insulation`` (task 0114) means ``to_assembly(insulation=True)``:
    the insulated count with it, the bare one without, both Python's."""
    from hexmesh.examples.applications import pcf_line
    from hexmesh.interchange import read_pcf
    sizes = tmp_path / "sizes.json"
    sizes.write_text(json.dumps([{"nominal": b, "spec": pcf_line.pipe(b).to_dict()}
                                 for b in (0.1, 0.08, 0.05)]), encoding="utf-8")
    net = read_pcf(pcf_line.SAMPLE)
    for flag, insulated in (((), False), (("--insulation",), True)):
        code, raw = _cli(monkeypatch, "estimate", str(pcf_line.SAMPLE), "--spec", str(sizes),
                         *flag)
        want = net.to_assembly(pcf_line.pipe, insulation=insulated).cell_count()
        assert code == 0 and json.loads(raw)["result"]["cells"] == want, flag
    assert want > net.to_assembly(pcf_line.pipe).cell_count()


def test_cli_insulation_on_a_description_is_an_input_error(monkeypatch, files):
    _, net, _ = files
    code, raw = _cli(monkeypatch, "estimate", str(net), "--insulation")
    err = json.loads(raw)["error"]
    assert code == 1 and err["code"] == "cli_input_unreadable"
    assert err["where"] == {"field": "insulation"} and "insulation shell" in err["hint"]


def test_every_network_command_takes_insulation():
    from hexmesh.agent._commands import parser
    sub = next(a for a in parser("")._actions if a.dest == "command")
    takes = {name for name, p in sub.choices.items()
             if any("--insulation" in a.option_strings for a in p._actions)}
    assert takes == set(sub.choices) - {"manifest", "schema"}


def test_calibration_is_read_as_utf8():
    src = (advise_mod.__file__)
    text = open(src, encoding="utf-8").read()
    assert 'open(CALIBRATION, encoding="utf-8")' in text


def test_growth_solver_matches_the_spec():
    """``first_cell=`` on a spec and the advisor's mprg agree."""
    y = 1e-4
    q = progression_for_first_cell(core_wall_span(0.025), 10, y)
    spec = PipeSpec(nang=12).core("fluid", radius=0.025, nrad=10, first_cell=y)
    assert spec.to_dict()["core"]["mprg"] == pytest.approx(1 / q)
