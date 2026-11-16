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
The frozen surface (task 0150 step 1): ``docs/api-1.0.json`` matches the
code.  A change to a public name, argument, default, the description
schema, the CLI's JSON, the manifest or the error codes fails here until
``python3 tools/api_inventory.py`` regenerates the file on purpose.
"""

import dataclasses
import importlib.util
import subprocess
import sys
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("api_inventory", ROOT / "tools/api_inventory.py")
api_inventory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(api_inventory)


def test_the_committed_inventory_matches_the_code():
    # a fresh process: what this one has imported changes what packages export
    run = subprocess.run([sys.executable, str(ROOT / "tools/api_inventory.py"), "--check"],
                         capture_output=True, text=True, cwd=ROOT)
    assert run.returncode == 0, (
        "the public surface changed; if on purpose, run python3 tools/api_inventory.py "
        "and commit docs/api-1.0.json\n" + run.stdout[-4000:] + run.stderr[-2000:])


def test_paths_are_recorded_the_same_on_every_platform():
    assert api_inventory._value(Path("study")) == {"path": "study"}
    assert api_inventory._value(PureWindowsPath("a\\b")) == {"path": "a/b"}


def test_a_dataclass_default_factory_is_recorded_by_its_product():
    @dataclasses.dataclass
    class C:
        a: int = 1
        b: list = dataclasses.field(default_factory=lambda: [2, 3])

    init = api_inventory._class(C)["members"]["__init__"]["signature"]
    assert init[1:] == [{"name": "a", "kind": "positional_or_keyword", "default": {"value": 1}},
                        {"name": "b", "kind": "positional_or_keyword",
                         "default": {"value": [2, 3]}}]


def test_a_class_value_is_recorded_by_its_name():
    assert api_inventory._value(Path) == {"class": "pathlib.Path"}
