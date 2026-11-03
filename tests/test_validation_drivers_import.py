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
Every validation driver imports (task 0090; the design session's answer
to 0084's follow-up 2): each ``validation/*/run.py`` and
``validation/tools/*.py`` is loaded as a module, not run, so a renamed or
moved hexmesh name fails the ordinary suite.  No OpenFOAM needed.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DRIVERS = sorted([*ROOT.glob("validation/*/run.py"), *ROOT.glob("validation/tools/*.py")])


@pytest.mark.parametrize("path", DRIVERS, ids=lambda p: str(p.relative_to(ROOT / "validation")))
def test_driver_imports(path, monkeypatch):
    name = f"_driver_{path.parent.name}_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)              # __name__ is not "__main__": nothing runs
    assert module.__name__ == name


def test_every_case_has_a_driver():
    cases = {p.parent.name for p in ROOT.glob("validation/*/case.json")}
    assert cases <= {p.parent.name for p in DRIVERS}
