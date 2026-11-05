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
"""Each stored validation level's section counts equal its run script's
assembly (task 0098, design answer Q4): ``results.json`` is the
calibration's single source, so it must not drift from the scripts."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _levels(case):
    with open(ROOT / f"validation/{case}/results.json", encoding="utf-8") as f:
        return json.load(f)["levels"]


@pytest.mark.parametrize("case", ["poiseuille", "rect_duct"])
def test_stored_counts_match_the_run_script(case):
    stored = _load("results", ROOT / "validation/tools/results.py")
    run = _load(f"run_{case}", ROOT / f"validation/{case}/run.py")
    checked = 0
    for lv in _levels(case):
        if case == "poiseuille":
            asm = run.assembly(lv["factor"])
        elif lv.get("mesh") in ("oh", "h", "hg"):
            asm = run.assembly(lv["ratio"], lv["k"], layout=lv["mesh"])
        else:
            assert "nang" not in lv                 # the Cartesian control: no hexmesh spec
            continue
        assert {k: lv[k] for k in stored.COUNTS} == stored.counts(asm), lv["name"]
        assert lv["cells"] == asm.cell_count(), lv["name"]
        checked += 1
    assert checked == {"poiseuille": 3, "rect_duct": 21}[case]
