"""
Validation against an exact solution (decision 0012, docs/tasks/0020).

Runs ``validation/poiseuille/run.py`` (all three levels, a few minutes)
and checks the acceptance criteria.  Opt-in: ``-m openfoam``; skipped
without OpenFOAM.
"""

import json
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


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    work = tmp_path_factory.mktemp("poiseuille")
    out = work / "results.json"
    run = subprocess.run([sys.executable, str(SCRIPT), "--work", str(work), "--json", str(out)],
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    return json.loads(out.read_text())


@pytest.fixture(scope="module")
def levels(data):
    return data["levels"]


def test_meshes_ok(levels):
    for r in levels:
        assert r["mesh_ok"], r["level"]
        assert r["cells_foam"] == r["cells"]                  # predicted = converted
        assert r["patches"] == ["fluid_inlet", "fluid_outlet", "fluid_wall"]
        assert r["retyped"] == ["fluid_wall"]
        assert r["converged"]


def test_cells_scale_by_eight(levels):
    assert [b["cells"] / a["cells"] for a, b in zip(levels, levels[1:])] == [8, 8]


def test_mass_balance(levels):
    assert all(r["mass_err"] < 1e-3 for r in levels)


# Acceptance gates, decision 0015 (task 0020, revised).

@pytest.mark.parametrize("key", ["dp_err", "u_max_err"])
def test_errors_decrease(levels, key):
    """|error| against the exact circle decreases monotonically."""
    errs = [r[key] for r in levels]
    assert errs == sorted(errs, reverse=True) and len(set(errs)) == 3, errs


@pytest.mark.parametrize("key", ["dp_err", "u_max_err"])
def test_fine_level_within_one_percent(levels, key):
    assert levels[-1][key] < 0.01


@pytest.mark.parametrize("key", ["dp", "u_max"])
def test_extrapolated_within_a_tenth_percent(data, key):
    """Richardson-extrapolated value within 0.1 % of exact."""
    ext, exact = data["richardson"][key]["extrapolated"], data["exact"][key]
    assert abs(ext - exact) / exact < 1e-3, (ext, exact)


def test_u_max_observed_order(data):
    """Gated for u_max only; Δp's order competes with the polygon's
    geometric error and is reported, not gated (RESEARCH §7.4)."""
    assert data["richardson"]["u_max"]["order"] >= 1.5


def test_nonorthogonality_trend_meshes_ok(data):
    """checkMesh-only sweep; the trend itself is reported in RESULTS.md."""
    assert data["trend"] and all(t["mesh_ok"] for t in data["trend"])


# ---------------------------------------------------------------------------
# Heated rod (docs/tasks/0033): coarsest level of both series
# ---------------------------------------------------------------------------

ROD_SCRIPT = ROOT / "validation" / "heated_rod" / "run.py"


@pytest.fixture(scope="module")
def rod(tmp_path_factory):
    work = tmp_path_factory.mktemp("heated_rod")
    out = work / "results.json"
    run = subprocess.run([sys.executable, str(ROD_SCRIPT), "--levels", "1", "--work", str(work),
                          "--json", str(out)], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    return json.loads(out.read_text())


@pytest.mark.parametrize("series", ["uniform", "graded"])
def test_heated_rod_coarse(rod, series):
    r, = rod["series"][series]["levels"]
    assert r["mesh_ok"] and r["cells_foam"] == r["cells"] == 216
    assert r["fvoptions_read"] and r["converged"]
    assert r["energy_err"] < 1e-10                     # heat out = q''' · V_mesh
    assert -0.03 < r["dt0_err_signed"] < 0              # coarse: 1.4–1.7 % low


LAYERS_SCRIPT = ROOT / "validation" / "layered_conduction" / "run.py"


@pytest.fixture(scope="module")
def layers(tmp_path_factory):
    work = tmp_path_factory.mktemp("layered_conduction")
    out = work / "results.json"
    run = subprocess.run([sys.executable, str(LAYERS_SCRIPT), "--levels", "1", "--work",
                          str(work), "--json", str(out)], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    return json.loads(out.read_text())


@pytest.mark.parametrize("variant", ["fixed", "convection"])
def test_layered_conduction_coarse(layers, variant):
    """Task 0034: three solid regions coupled by chtMultiRegionSimpleFoam."""
    r, = layers["variants"][variant]["levels"]
    assert r["mesh_ok"] and r["cells_foam"] == r["cells"] == 456
    assert r["mapped_pairs_equal"] and r["converged"]
    for key in ("balance_rod", "balance_steel", "balance_outer"):
        assert abs(r[key]) < 1e-9, key                  # heat through each interface
    for key in ("t0_err", "t1_err", "t2_err"):
        assert -0.02 < r[key] < 0, key                  # coarse: about −1 % of the rise


STENOSIS_SCRIPT = ROOT / "validation" / "stenosis" / "run.py"


@pytest.fixture(scope="module")
def stenosis(tmp_path_factory):
    work = tmp_path_factory.mktemp("stenosis")
    out = work / "results.json"
    run = subprocess.run([sys.executable, str(STENOSIS_SCRIPT), "--levels", "coarse",
                          "--no-reference", "--end-time", "200", "--work", str(work),
                          "--json", str(out)],
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    return json.loads(out.read_text())


def test_stenosis_coarse(stenosis):
    """Task 0032: the pipeline runs the cosine constriction's coarse level
    (200 SIMPLE iterations) on a mesh checkMesh accepts.  Not a flow check:
    SIMPLE does not converge on this case (task 0032, Q1)."""
    r, = stenosis["levels"]
    assert r["mesh_ok"] and r["cells_foam"] == r["cells"] == 15336
    assert r["iterations"] == 200
    assert r["u_peak"] > 3                              # a jet forms (> 4 u_m in the DNS)
