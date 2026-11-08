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
``hexmesh.agent.manifest()`` and ``hexmesh manifest`` (task 0102): every
registry appears, the stored support matrix and validation summary agree
with the library and the cases, and the output is deterministic, strict
JSON and fast, with no GMSH session.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from hexmesh.assembly.intent import FITTING_TYPES
from hexmesh.assembly.limits import LIMITS
from hexmesh.errors import CODES
from hexmesh.agent import _commands, _manifest, _probe, manifest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


summary = _load("summary", "validation/tools/summary.py")


@pytest.fixture(scope="module")
def m():
    return manifest()


def test_every_registry_appears(m):
    assert set(m["commands"]) == set(_commands.COMMANDS)
    assert set(_commands.RESULTS) == set(_commands.COMMANDS)
    assert set(m["errors"]) == set(CODES)
    assert set(m["limits"]) == set(LIMITS)
    assert set(m["support"]["fittings"]) == set(FITTING_TYPES)
    for name, limit in LIMITS.items():
        assert (m["limits"][name]["unit"], m["limits"][name]["kind"]) == (limit.unit, limit.kind)


def test_commands_come_from_the_parser(m):
    advise = {a["name"]: a for a in m["commands"]["advise"]["arguments"]}
    assert set(advise) == {"network", "--spec", "--insulation", "--inputs"}
    assert advise["network"]["positional"] and not advise["--inputs"]["positional"]
    assert m["commands"]["build"]["needs_gmsh"] and not m["commands"]["manifest"]["needs_gmsh"]
    assert {a["name"]: a["choices"] for a in m["commands"]["build"]["arguments"]}["--order"] \
        == [1, 2]
    assert [s["command"] for s in m["workflow"] if s["command"]] == \
        ["schema", "validate", "estimate", "describe", "advise", "apply", "build"]
    assert set(m["envelope"]["exit_codes"]) == {"0", "1", "2"}


def test_the_stored_support_matrix_is_the_library_s():
    """support.json against a fresh probe: refresh with the command."""
    assert _manifest.support() == _probe.probe(), \
        "hexmesh/agent/support.json is stale: python3 -m hexmesh.agent._probe"


def test_n_outer_8_shows_as_unsupported_with_what_the_library_raises(m):
    entry = m["support"]["fittings"]["Straight"]["specs"]["circle_n_outer_8"]
    assert entry["supported"] is False and entry["code"] == "section_not_supported"
    assert "n_outer=4" in entry["message"]
    assert m["support"]["fittings"]["Straight"]["specs"]["circle"] == {"supported": True}
    assert m["support"]["fittings"]["Closure"]["probed"] is False


def test_the_validation_summary_matches_the_cases(m):
    assert m["validation"] == summary.summary(), \
        "hexmesh/agent/validation.json is stale: python3 -m validation.tools.summary"
    cases = {p.parent.name for p in (ROOT / "validation").glob("*/case.json")}
    assert set(m["validation"]["cases"]) == cases
    for tag, names in m["validation"]["features"].items():
        for name in names:
            meta = json.loads((ROOT / "validation" / name / "case.json").read_text("utf-8"))
            assert tag in meta["tags"]["features"]


def test_a_changed_case_json_makes_the_summary_stale(tmp_path, monkeypatch):
    for case in ("poiseuille", "stenosis"):
        shutil.copytree(ROOT / "validation" / case, tmp_path / "validation" / case,
                        ignore=shutil.ignore_patterns("img", "*.png", "work"))
    monkeypatch.setattr(summary, "ROOT", tmp_path)
    before = summary.summary()
    path = tmp_path / "validation/stenosis/case.json"
    meta = json.loads(path.read_text("utf-8"))
    meta["status"] = "in progress"
    path.write_text(json.dumps(meta), encoding="utf-8")
    after = summary.summary()
    assert after != before and after["cases"]["stenosis"]["status"] == "in progress"


def test_deterministic_strict_json_and_no_gmsh_session(m):
    import gmsh
    first = json.dumps(m, sort_keys=True, allow_nan=False)
    assert json.dumps(manifest(), sort_keys=True, allow_nan=False) == first
    assert not gmsh.isInitialized()


def _timed(*args) -> tuple[float, subprocess.CompletedProcess]:
    t0 = time.perf_counter()
    out = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, check=True)
    return time.perf_counter() - t0, out


def test_the_manifest_does_no_expensive_work():
    """It reads stored data: about 4 ms; the live probe it replaced took
    1.3 s (task 0102)."""
    t0 = time.perf_counter()
    manifest()
    took = time.perf_counter() - t0
    assert took < 0.2, f"manifest() took {took:.2f} s: is it probing live?"


def test_the_cli_emits_it_in_its_envelope_quickly():
    """The command adds little to starting Python and importing hexmesh
    (about 0.6 s together locally, 2.5 s on a cold CI runner): timed
    against that baseline, not the wall clock (task 0105)."""
    _timed("-c", "import hexmesh.agent")               # warm the file cache
    base, _ = _timed("-c", "import hexmesh.agent")
    took, out = _timed("-m", "hexmesh.agent.cli", "manifest")
    _, again = _timed("-m", "hexmesh.agent.cli", "manifest")
    assert out.stdout == again.stdout and out.stderr == b""
    d = json.loads(out.stdout)
    assert d["command"] == "manifest" and d["ok"] is True
    assert d["result"]["format"] == "hexmesh.agent.manifest"
    assert took - base < 1.0, (f"hexmesh manifest took {took:.2f} s, {took - base:.2f} s "
                               f"over importing hexmesh ({base:.2f} s)")
