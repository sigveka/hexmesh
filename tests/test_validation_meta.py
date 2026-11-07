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
Validation metadata (task 0073, decision 0012's categories): every case's
``case.json`` is valid against ``validation/case.schema.json``, and the
gallery's loader fails loudly on a missing or invalid one.

Stored results (task 0093): ``results.json`` next to every accepted
``RESULTS.md``, valid against ``validation/results.schema.json``, small,
written deterministically; the recheck reproduces every gate from it
with no OpenFOAM; and a driver's level store reuses, reruns and cleans
up as specified.

Graphs (task 0099): every case's ``figure.png`` and the four extra graphs
exist, are drawn from the current ``results.json`` (their
``source-sha256`` chunk), small, deterministic and embedded in
``RESULTS.md``.
"""

import importlib.util
import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def build():
    spec = importlib.util.spec_from_file_location("gallery_build", ROOT / "docs/gallery/build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_case_has_a_valid_case_json(build):
    cases = build.case_dirs()
    assert {"poiseuille", "heated_rod", "layered_conduction", "heated_pipe", "stenosis"} <= set(cases)
    for case in cases:
        meta = build.case_meta(case)
        assert meta["task"] and meta["category"] in build.CATEGORIES_V


def test_schema_rejects_bad_fields(build):
    good = json.loads((ROOT / "validation/poiseuille/case.json").read_text(encoding="utf-8"))
    schema = build.case_schema()
    jsonschema.validate(good, schema)
    for bad in ({"category": "V5"},
                {"tags": {**good["tags"], "features": ["elbow"]}},
                {"status": "done"},
                {"references": []}):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({**good, **bad}, schema)


def test_missing_or_invalid_case_json_stops_the_gallery(build, monkeypatch, tmp_path):
    root = tmp_path
    (root / "validation" / "x").mkdir(parents=True)
    (root / "validation" / "case.schema.json").write_text(
        (ROOT / "validation/case.schema.json").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(build, "ROOT", root)
    with pytest.raises(SystemExit, match="case.json: missing"):
        build.case_meta("x")
    (root / "validation" / "x" / "case.json").write_text('{"schemaVersion": 1}', encoding="utf-8")
    with pytest.raises(SystemExit, match="invalid"):
        build.case_meta("x")


def test_planned_tasks_carry_known_features(build):
    planned = build.planned_cases({build.case_meta(c)["task"] for c in build.case_dirs()})
    assert {p["task"] for p in planned} >= {"0050"}           # 0072 has its case directory
    assert all(p["features"] for p in planned)


def test_coverage_shows_unvalidated_features(build):
    # the straight-pipe cases alone: the junctions are then uncovered
    cases = [(c, build.case_meta(c)) for c in build.case_dirs()
             if Path(c).name in ("poiseuille", "heated_rod")]
    md = "\n".join(build.coverage_md(cases, []))
    assert "`wye` (none)" in md and "`duct-tap` (none)" in md
    assert "`straight` (none)" not in md


# --- stored results (task 0093) -------------------------------------------------

def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


stored = _load("stored", "validation/tools/results.py")
recheck = _load("recheck", "validation/tools/recheck.py")
SCHEMA = json.loads((ROOT / "validation/results.schema.json").read_text(encoding="utf-8"))


def test_every_case_with_results_md_is_rechecked():
    with_results = {p.parent.name for p in (ROOT / "validation").glob("*/RESULTS.md")}
    assert with_results == set(recheck.CASES)


@pytest.mark.parametrize("case", recheck.CASES)
def test_results_json_is_valid_small_and_deterministic(case):
    path = ROOT / "validation" / case / "results.json"
    raw = path.read_bytes()
    assert len(raw) <= stored.MAX_BYTES
    assert b"\r" not in raw and raw.endswith(b"\n")
    data = stored.load(path)
    jsonschema.validate(data, SCHEMA)
    assert data["case"] == case
    names = [lv["name"] for lv in data["levels"]]
    assert len(names) == len(set(names))
    assert stored.dumps(data).encode("utf-8") == raw            # as the store writes it


@pytest.mark.parametrize("case", recheck.CASES)
def test_recheck_reproduces_every_gate(case):
    """Each recheck has gates; an accepted case (``case.json``) passes
    them all.  A case still in progress reports failing gates (tasks 0049
    and 0072) until design rules on them."""
    rows = recheck.recheck(case)
    gated = [r for r in rows if r["verdict"] is not None]
    assert gated, f"{case}: no gate rechecked"
    meta = json.loads((ROOT / "validation" / case / "case.json").read_text(encoding="utf-8"))
    if meta["status"] == "accepted":
        assert [r["quantity"] for r in gated if r["verdict"] != "pass"] == []


def test_recheck_cli_exits_nonzero_on_a_failing_gate(monkeypatch, capsys):
    real = recheck.recheck
    monkeypatch.setattr(recheck, "recheck", lambda case: [
        {**r, "verdict": "fail"} if r["verdict"] else r for r in real(case)])
    assert recheck.main(["heated_rod"]) == 1
    assert "FAIL heated_rod" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        recheck.main(["no_such_case"])


def test_schema_rejects_bad_files():
    good = stored.load(ROOT / "validation/heated_rod/results.json")
    lv = good["levels"][0]
    for bad in ({**good, "format": "x"}, {**good, "levels": []},
                {**good, "levels": [{**lv, "precision": "approximately"}]},
                {**good, "levels": [{k: v for k, v in lv.items() if k != "environment"}]},
                {**good, "fields": {}}):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, SCHEMA)


# --- the level store -------------------------------------------------------------

ENV = {"hexmesh": "test", "gmsh": None, "openfoam": None, "runner": None,
       "python": None, "date": None}


def _case(work: Path, name: str) -> Path:
    case = work / name
    (case / "0").mkdir(parents=True)
    (case / "0/U").write_text("field\n", encoding="utf-8")
    return case


def test_a_stored_level_is_reused_and_its_work_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(stored, "environment", lambda: ENV)
    store = stored.Store(tmp_path / "results.json", "demo")
    work = tmp_path / "work"
    calls = []

    def run(name):
        def go():
            calls.append(name)
            _case(work, name)
            return {"x": 1.0 / 3}
        return go

    a = stored.run_level(store, "a", run("a"), work / "a")
    assert a["x"] == 1.0 / 3 and a["precision"] == stored.FULL and a["environment"] == ENV
    assert not (work / "a").exists() and not work.exists()     # the empty work/ goes too
    again = stored.Store(tmp_path / "results.json", "demo")
    assert stored.run_level(again, "a", run("a"), work / "a")["x"] == 1.0 / 3
    assert calls == ["a"]                                      # reused, not rerun
    stored.run_level(again, "b", run("b"), work / "b", keep_work=True)
    assert (work / "b/0/U").exists()


def test_a_rounded_level_is_rerun(tmp_path, monkeypatch):
    monkeypatch.setattr(stored, "environment", lambda: ENV)
    store = stored.Store(tmp_path / "results.json", "demo")
    store.put("a", {"x": 0.33}, precision=stored.ROUNDED, env=ENV)
    row = stored.run_level(store, "a", lambda: {"x": 1.0 / 3}, None)
    assert row["precision"] == stored.FULL and row["x"] == 1.0 / 3
    assert [lv["name"] for lv in stored.load(tmp_path / "results.json")["levels"]] == ["a"]


def test_a_failed_level_keeps_its_case(tmp_path, capsys):
    store = stored.Store(tmp_path / "results.json", "demo")
    case = _case(tmp_path / "work", "a")

    def boom():
        raise RuntimeError("solver diverged")

    with pytest.raises(RuntimeError):
        stored.run_level(store, "a", boom, case)
    assert (case / "0/U").exists()
    assert "kept in" in capsys.readouterr().out
    assert stored.load(tmp_path / "results.json") is None      # nothing stored


def test_write_is_deterministic_and_capped(tmp_path):
    path = tmp_path / "r.json"
    data = {"case": "demo", "levels": [{"name": "a", "b": float("nan"), "a": 2}], "extra": {}}
    stored.write(path, data)
    first = path.read_bytes()
    stored.write(path, json.loads(first))
    assert path.read_bytes() == first
    assert b'"b": "nan"' in first and first.index(b'"a": 2') < first.index(b'"b"')
    with pytest.raises(ValueError, match="cap"):
        stored.write(path, {**data, "extra": {"big": "x" * stored.MAX_BYTES}})
    assert path.read_bytes() == first                          # the old file stands
    with pytest.raises(ValueError, match="results of 'demo'"):
        stored.Store(path, "other")


# --- graphs (task 0099) ---------------------------------------------------------

EXTRA_GRAPHS = ("rect_duct/img/layouts.png", "stenosis/img/centreline.png",
                "stenosis_pulsatile/img/periodic.png", "heated_rod/img/series.png")


@pytest.fixture(scope="module")
def plots():
    pytest.importorskip("matplotlib")
    pytest.importorskip("PIL")
    return _load("plots", "validation/tools/plots.py")


def _graphs():
    return [ROOT / "validation" / c / "figure.png" for c in recheck.CASES] + \
        [ROOT / "validation" / g for g in EXTRA_GRAPHS]


def test_plots_cover_every_case(plots):
    assert set(plots.CASES) == set(recheck.CASES)


@pytest.mark.parametrize("png", _graphs(), ids=lambda p: str(p.relative_to(ROOT / "validation")))
def test_every_graph_is_current_small_and_embedded(plots, png):
    assert png.exists(), f"{png.relative_to(ROOT)} missing: python3 -m validation.tools.plots"
    assert plots.stale(png) is None, plots.stale(png)
    assert png.stat().st_size < 250_000
    chunks = plots.text_chunks(png)
    assert set(chunks) == {plots.SHA_KEY, plots.SOURCES_KEY}     # no software or time
    case = png.relative_to(ROOT / "validation").parts[0]
    results = (ROOT / "validation" / case / "RESULTS.md").read_text(encoding="utf-8")
    block = results[results.index(plots.GRAPHS_START):results.index(plots.GRAPHS_END)]
    assert png.relative_to(ROOT / "validation" / case).as_posix() in block


def test_a_changed_results_json_makes_its_graph_stale(plots, tmp_path, monkeypatch):
    case = tmp_path / "validation" / "poiseuille"
    (case).mkdir(parents=True)
    raw = (ROOT / "validation/poiseuille/results.json").read_bytes()
    (case / "results.json").write_bytes(raw)
    png = case / "figure.png"
    png.write_bytes((ROOT / "validation/poiseuille/figure.png").read_bytes())
    monkeypatch.setattr(plots, "ROOT", tmp_path)
    assert plots.stale(png) is None
    (case / "results.json").write_bytes(raw.replace(b'"coarse"', b'"coarse2"', 1))
    why = plots.stale(png)
    assert why and "python3 -m validation.tools.plots poiseuille" in why


def test_graphs_are_deterministic(plots, tmp_path):
    data = json.loads((ROOT / "validation/poiseuille/results.json").read_text(encoding="utf-8"))
    first = plots.poiseuille(data, tmp_path / "a")[0].read_bytes()
    assert plots.poiseuille(data, tmp_path / "b")[0].read_bytes() == first
