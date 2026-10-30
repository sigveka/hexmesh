"""
Validation metadata (task 0073, decision 0012's categories): every case's
``case.json`` is valid against ``validation/case.schema.json``, and the
gallery's loader fails loudly on a missing or invalid one.
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
    good = json.loads((ROOT / "validation/poiseuille/case.json").read_text())
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
        (ROOT / "validation/case.schema.json").read_text())
    monkeypatch.setattr(build, "ROOT", root)
    with pytest.raises(SystemExit, match="case.json: missing"):
        build.case_meta("x")
    (root / "validation" / "x" / "case.json").write_text('{"schemaVersion": 1}')
    with pytest.raises(SystemExit, match="invalid"):
        build.case_meta("x")


def test_planned_tasks_carry_known_features(build):
    planned = build.planned_cases({build.case_meta(c)["task"] for c in build.case_dirs()})
    assert {p["task"] for p in planned} >= {"0071", "0072"}
    assert all(p["features"] for p in planned)


def test_coverage_shows_unvalidated_features(build):
    cases = [(c, build.case_meta(c)) for c in build.case_dirs()]
    md = "\n".join(build.coverage_md(cases, []))
    assert "`wye` (none)" in md and "`duct-tap` (none)" in md
    assert "`straight` (none)" not in md
