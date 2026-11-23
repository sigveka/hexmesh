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
The local check (decision 0055; task 0178): its runner choice, the skip
path without one, the pre-push hook's path filter, and how a level is
compared with its stored values.  No OpenFOAM, no Docker.
"""

import importlib.util
import io
import json
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("local_check", ROOT / "tools/local_check.py")
lc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lc)


# --- the runner ---------------------------------------------------------------------

def test_the_environment_variable_wins():
    assert lc.pick_runner({"HEXMESH_OPENFOAM": "path"}, docker=lambda: True) == "path"


def test_docker_when_it_answers_else_none():
    assert lc.pick_runner({}, docker=lambda: True) == lc.DOCKER_RUNNER
    assert lc.pick_runner({}, docker=lambda: False) is None


def test_docker_absent_does_not_answer(monkeypatch):
    monkeypatch.setattr(lc.shutil, "which", lambda name: None)
    assert lc.docker_answers() is False


@pytest.mark.parametrize("require, code", [(False, 0), (True, 1)])
def test_no_runner_skips_the_openfoam_steps(monkeypatch, capsys, require, code):
    monkeypatch.delenv("HEXMESH_OPENFOAM", raising=False)
    monkeypatch.setattr(lc, "docker_answers", lambda: False)
    ran = []
    monkeypatch.setattr(lc, "STEPS", tuple(
        (k, t, lambda *a, k=k: ran.append(k) or (lc.PASS, "ran"), needs)
        for k, t, _, needs in lc.STEPS))
    assert lc.main(["--steps", "abcd"] + (["--require"] if require else [])) == code
    out = capsys.readouterr().out
    assert ran == ["d"]                                   # the card step needs no OpenFOAM
    assert out.count("no OpenFOAM runner") >= 3
    assert ("FAILED" if require else "passed (3 skipped)") in out


# --- the pre-push hook's filter -------------------------------------------------------

@pytest.mark.parametrize("files, hits", [
    (["README.md", "docs/GUIDE.md"], []),
    (["hexmesh/study/openfoam.py"], ["hexmesh/study/openfoam.py"]),
    (["hexmesh/assembly/_output.py", "hexmesh/assembly/tee.py"], ["hexmesh/assembly/_output.py"]),
    (["validation/poiseuille/run.py", ""], ["validation/poiseuille/run.py"]),
    (["hexmesh/studyx.py", "tools/validation/x"], []),
    (["?"], ["?"]),                                       # the hook couldn't list them
])
def test_the_hook_runs_the_check_only_for_watched_paths(files, hits):
    assert lc.touched(files) == hits


def test_if_touched_says_not_needed(monkeypatch, capsys):
    monkeypatch.setattr(lc.sys, "stdin", io.StringIO("README.md\nCHANGELOG.md\n"))
    monkeypatch.setattr(lc, "pick_runner", lambda: pytest.fail("the check ran"))
    assert lc.main(["--if-touched"]) == 0
    assert "not needed" in capsys.readouterr().out


@pytest.mark.posix_only
def test_the_hook_passes_the_pushed_files(tmp_path):
    """The hook itself: a push of a commit that changes a watched path
    reaches the check's filter (here a stand-in that prints its input)."""
    if not shutil.which("git"):
        pytest.skip("no git")
    repo = tmp_path / "repo"
    (repo / "tools" / "hooks").mkdir(parents=True)
    shutil.copy(ROOT / "tools/hooks/pre-push", repo / "tools/hooks/pre-push")
    (repo / "tools" / "local_check.py").write_text(
        "import sys; print('GOT', sorted(sys.stdin.read().split()))", encoding="utf-8")
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git[:3], "init", "-q"], check=True)
    (repo / "a.txt").write_text("a", encoding="utf-8")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "a"], check=True)
    base = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (repo / "validation").mkdir()
    (repo / "validation" / "x.py").write_text("x", encoding="utf-8")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "b"], check=True)
    head = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    out = subprocess.run(["sh", "tools/hooks/pre-push"], cwd=repo, capture_output=True, text=True,
                         input=f"refs/heads/main {head} refs/heads/next {base}\n")
    assert out.returncode == 0 and "GOT ['validation/x.py']" in out.stdout


# --- comparing a level with its stored values -------------------------------------------

def test_equal_within_the_tolerance_and_run_records_left_out():
    old = {"name": "a", "dp": 1.0, "cells": 10, "wall_s": 5.0, "environment": {"x": 1},
           "all": {"l2": 0.5, "max": [1.0, 2.0]}, "last_initial_residual": 3e-15}
    new = {**old, "dp": 1.0 + 5e-7, "wall_s": 9.0, "environment": {"x": 2},
           "last_initial_residual": 9e-15, "check_new_key": 1.0}
    assert lc.differences(new, old) == []


def test_differences_are_named():
    old = {"dp": 1.0, "cells": 10, "all": {"max": [1.0, 2.0]}, "gone": True}
    new = {"dp": 1.01, "cells": 11, "all": {"max": [1.0, 2.1]}}
    got = lc.differences(new, old)
    assert any(d.startswith("dp: 1.01, stored 1.0") for d in got)
    assert "cells: 11, stored 10" in got
    assert any(d.startswith("all.max.1:") for d in got)
    assert "gone: in the stored values only" in got


def test_compare_levels_by_name(tmp_path):
    stored = tmp_path / "stored.json"
    new = tmp_path / "new.json"
    stored.write_text(json.dumps({"levels": [{"name": "x_k1", "v": 1.0}]}), encoding="utf-8")
    new.write_text(json.dumps({"levels": [{"name": "x_k1", "v": 1.0},
                                          {"name": "y_k1", "v": 2.0}]}), encoding="utf-8")
    got = lc.compare_levels(new, stored, root=tmp_path)
    assert got == ["y_k1: not in stored.json"]
