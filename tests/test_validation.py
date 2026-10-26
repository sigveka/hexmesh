"""
Validation against an exact solution (decision 0012, docs/tasks/0020).

Runs ``validation/poiseuille/run.py`` (all three levels, a few minutes)
and checks the acceptance criteria.  Opt-in: ``-m openfoam``; skipped
without OpenFOAM.
"""

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "validation" / "poiseuille" / "run.py"
OPENFOAM_RC = Path("/usr/share/openfoam/etc/bashrc")


def _have_openfoam() -> bool:
    if not OPENFOAM_RC.exists():
        return False
    run = subprocess.run(["bash", "-c", f"source {OPENFOAM_RC} >/dev/null 2>&1; "
                          "command -v gmshToFoam"], capture_output=True)
    return run.returncode == 0


pytestmark = [pytest.mark.openfoam,
              pytest.mark.skipif(not _have_openfoam(), reason="gmshToFoam not available")]


# Task 0020 is blocked: interior wall nodes of a Straight lie on OCC plate
# surfaces up to 1.08 % of R inside the cylinder, so Δp is stuck at +2.6 %
# (validation/poiseuille/RESULTS.md).  With exact walls, Δp converges at
# about first order only.  Remove these marks when design has settled both.
blocked = pytest.mark.xfail(reason="task 0020 blocked: Straight wall sag, Δp order",
                            strict=False)


@pytest.fixture(scope="module")
def levels(tmp_path_factory):
    work = tmp_path_factory.mktemp("poiseuille")
    out = work / "results.json"
    run = subprocess.run([sys.executable, str(SCRIPT), "--work", str(work), "--json", str(out)],
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    return json.loads(out.read_text())["levels"]


def test_meshes_ok(levels):
    for r in levels:
        assert r["mesh_ok"], r["level"]
        assert r["cells_foam"] == r["cells"]                  # predicted = converted
        assert r["patches"] == ["fluid_inlet", "fluid_outlet", "fluid_wall"]
        assert r["retyped"] == ["fluid_wall"]
        assert r["converged"]


def test_cells_scale_by_eight(levels):
    assert [b["cells"] / a["cells"] for a, b in zip(levels, levels[1:])] == [8, 8]


@blocked
@pytest.mark.parametrize("key", ["dp_err", "u_max_err"])
def test_errors_decrease(levels, key):
    errs = [r[key] for r in levels]
    assert errs == sorted(errs, reverse=True) and len(set(errs)) == 3, errs


@blocked
@pytest.mark.parametrize("key", ["dp_err", "u_max_err"])
def test_fine_level_within_one_percent(levels, key):
    assert levels[-1][key] < 0.01


def test_mass_balance(levels):
    assert all(r["mass_err"] < 1e-3 for r in levels)


@blocked
def test_observed_order(levels):
    """Reported in RESULTS.md; second-order schemes should give about 2."""
    for key in ("dp_err", "u_max_err"):
        orders = [math.log2(a[key] / b[key]) for a, b in zip(levels, levels[1:])]
        assert min(orders) > 1.5, (key, orders)
