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
``tools/promote.py`` (decision 0052; task 0156): main moves only to a
commit whose newest ``tests`` run is green, by a fast-forward.  ``git``
and ``gh`` are faked: no network, no push.
"""

import importlib.util
import json
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("promote", ROOT / "tools" / "promote.py")
promote = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(promote)

SHA, MAIN = "a" * 40, "b" * 40
GREEN = [{"name": n, "status": "completed", "conclusion": "success"}
         for n in ("ubuntu-latest, Python 3.11", "windows-latest, Python 3.x")]


class Fake:
    """``git`` and ``gh`` answers, and the commands asked."""

    def __init__(self, runs=None, jobs=GREEN, ancestor=True, main=MAIN):
        self.runs = [{"databaseId": 7, "status": "completed", "conclusion": "success",
                      "createdAt": "2026-11-13T09:00:00Z", "headBranch": "next",
                      "event": "push"}] if runs is None else runs
        self.jobs, self.ancestor, self.main, self.calls = jobs, ancestor, main, []

    def __call__(self, argv):
        self.calls.append(argv)
        out, code = "", 0
        if argv[:2] == ["git", "rev-parse"]:
            out = self.main if argv[-1] == "origin/main" else SHA
        elif argv[:3] == ["gh", "run", "list"]:
            out = json.dumps(self.runs)
        elif argv[:3] == ["gh", "run", "view"]:
            out = json.dumps({"jobs": self.jobs})
        elif argv[:3] == ["git", "merge-base", "--is-ancestor"]:
            code = 0 if self.ancestor else 1
        return subprocess.CompletedProcess(argv, code, out, "")

    @property
    def pushed(self):
        return [c for c in self.calls if c[:2] == ["git", "push"]]


def test_a_green_fast_forward_is_pushed_to_main():
    fake = Fake()
    lines = promote.promote("aaaa", run=fake)
    assert fake.pushed == [["git", "push", "origin", f"{SHA}:refs/heads/main"]]
    assert "run 7 (next, push) green, 2 jobs" in lines[0] and lines[-1] == "pushed: main is aaaaaaa"


def test_dry_run_checks_but_does_not_push():
    fake = Fake()
    assert promote.promote("aaaa", dry_run=True, run=fake)[-1].startswith("dry run")
    assert not fake.pushed


@pytest.mark.parametrize("fake, says", [
    (Fake(runs=[]), "no tests.yml run on aaaaaaa: push it to next first"),
    (Fake(runs=[{"databaseId": 8, "status": "in_progress", "conclusion": None,
                 "createdAt": "2026-11-13T10:00:00Z", "headBranch": "next", "event": "push"}]),
     "run 8 on aaaaaaa is in_progress: gh run watch 8"),
    (Fake(jobs=[*GREEN[:1], {"name": "windows-latest, Python 3.x", "status": "completed",
                             "conclusion": "failure"}]),
     "windows-latest, Python 3.x: failure"),
    (Fake(jobs=[]), "no jobs"),
    (Fake(ancestor=False), "doesn't descend from origin/main"),
])
def test_refused_with_the_reason(fake, says):
    with pytest.raises(promote.Refused, match=says.replace("(", r"\(").replace(")", r"\)")):
        promote.promote("aaaa", run=fake)
    assert not fake.pushed


def test_the_newest_run_decides():
    """A green run, then a failed rerun: the rerun is what counts."""
    old = {"databaseId": 1, "status": "completed", "conclusion": "success",
           "createdAt": "2026-11-13T08:00:00Z", "headBranch": "next", "event": "push"}
    new = {**old, "databaseId": 2, "conclusion": "failure", "createdAt": "2026-11-13T09:00:00Z"}
    with pytest.raises(promote.Refused, match="run 2 on aaaaaaa isn't green"):
        promote.promote("aaaa", run=Fake(runs=[old, new], jobs=[]))


def test_already_main_pushes_nothing():
    fake = Fake(main=SHA)
    assert promote.promote("aaaa", run=fake)[-1].endswith("already there")
    assert not fake.pushed


def test_main_exits_1_and_says_refused(capsys):
    assert promote.main(["aaaa"], run=Fake(runs=[])) == 1
    assert capsys.readouterr().err.startswith("refused: no tests.yml run")
