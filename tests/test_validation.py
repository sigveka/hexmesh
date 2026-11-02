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
Validation against an exact solution (decision 0012, docs/tasks/0020).

Runs ``validation/poiseuille/run.py`` (all three levels, a few minutes)
and checks the acceptance criteria.  Opt-in: ``-m openfoam``; skipped
without OpenFOAM.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "validation" / "poiseuille" / "run.py"
_spec = importlib.util.spec_from_file_location("convergence",
                                               ROOT / "validation/tools/convergence.py")
conv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conv)
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
    return json.loads(out.read_text(encoding="utf-8"))


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
    """Richardson-extrapolated value within 0.1 % of exact, on a converging
    series only (task 0089)."""
    ok, why = conv.gate_extrapolated(data["richardson"][key], data["exact"][key], 1e-3)
    assert ok, why


def test_u_max_observed_order(data):
    """Gated for u_max only; Δp's order competes with the polygon's
    geometric error and is reported, not gated (RESEARCH §7.4)."""
    rich = data["richardson"]["u_max"]
    assert rich["status"] == "converging" and rich["order"] >= 1.5, rich


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
    return json.loads(out.read_text(encoding="utf-8"))


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
    return json.loads(out.read_text(encoding="utf-8"))


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
                          "--no-reference", "--end-time", "10", "--work", str(work),
                          "--json", str(out)],
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    return json.loads(out.read_text(encoding="utf-8"))


def test_stenosis_coarse(stenosis):
    """Task 0032: the pipeline runs the cosine constriction's coarse level
    for 10 time units of pimpleFoam (two chunks, one steadiness check) on a
    mesh checkMesh accepts.  Not a flow check: the coarse level has no
    steady axisymmetric state (task 0032)."""
    r, = stenosis["levels"]
    assert r["mesh_ok"] and r["cells_foam"] == r["cells"] == 15336
    assert r["end_time"] == 10 and len(r["changes"]) == 1
    assert r["mass_err"] < 1e-6
    assert r["u_peak"] > 3                              # a jet forms (> 4 u_m in the DNS)
    assert r["x_reattachment"] and r["x_reattachment_probe"]


def _have_v2406() -> bool:
    import shutil
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "image", "inspect", "opencfd/openfoam-default:2406"],
                          capture_output=True).returncode == 0


@pytest.fixture(scope="module")
def womersley(tmp_path_factory):
    """Task 0067's coarsest level on v2406 in Docker (about 2 min)."""
    if not _have_v2406():
        pytest.skip("no opencfd/openfoam-default:2406 image")
    work = tmp_path_factory.mktemp("womersley")
    out = work / "results.json"
    run = subprocess.run([sys.executable, str(ROOT / "validation/womersley/run.py"),
                          "--levels", "k1", "--work", str(work), "--json", str(out)],
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    return json.loads(out.read_text(encoding="utf-8"))["levels"][0]


def test_womersley_coarse(womersley):
    """The coarsest level's measured values (RESULTS.md), with margin: the
    exact inlet is applied, the run becomes periodic, and the errors stay
    where they were measured (the gates are for the finest level)."""
    r = womersley
    assert r["mesh_ok"] and r["cells_foam"] == r["cells"]
    assert r["inlet_applied_err"] < 1e-8               # boundaryData at every step: exact
    assert r["periods"] <= 4 and r["periodic_change"] < 1e-3
    assert r["profile_max_all"] < 0.025                # 2.1 % of u_c measured
    assert abs(r["dpdx_amplitude_err"]) < 0.01 and abs(r["dpdx_phase_deg"]) < 2
    assert r["q_err_max"] < 1e-3
    assert [round(p["t_over_T"], 2) for p in r["phases"]] == [0.09, 0.26, 0.42, 0.59, 0.76, 0.92]


@pytest.fixture(scope="module")
def pulsatile_stenosis(tmp_path_factory):
    """Task 0068's coarsest level, one period from rest, on v2406 in
    Docker (about 5 min; downloads the DNS files once into the work
    directory)."""
    if not _have_v2406():
        pytest.skip("no opencfd/openfoam-default:2406 image")
    work = tmp_path_factory.mktemp("stenosis_pulsatile")
    out = work / "results.json"
    run = subprocess.run([sys.executable, str(ROOT / "validation/stenosis_pulsatile/run.py"),
                          "--levels", "coarse", "--periods-max", "1", "--work", str(work),
                          "--json", str(out)], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    return json.loads(out.read_text(encoding="utf-8"))


def test_pulsatile_stenosis_one_period(pulsatile_stenosis):
    """The pipeline end to end: mesh, the Womersley inlet on boundaryData,
    the sampled sets at every target phase, the DNS comparison.  One
    period from rest isn't periodic, so no accuracy is asserted."""
    r = pulsatile_stenosis["levels"][0]
    assert r["mesh_ok"] and r["cells_foam"] == r["cells"]
    assert r["periods"] == 1
    phases = [p["phase"] for p in pulsatile_stenosis["meta"]["phases"]]
    assert [round(p, 2) for p in phases] == [0.05, 0.26, 0.42, 0.56, 0.75, 0.89]
    assert len(r["rows"]) == len(pulsatile_stenosis["meta"]["targets"]) == 12
    assert len(r["comparison"]) == 12                      # 6 files × 2 phase sets
    c = next(c for c in r["comparison"] if c["file"] == "vel_p2.dat" and c["kind"] == "flow_rate")
    assert 3.0 < c["stations"]["0.0"]["centre"] < 6.0      # a throat jet at peak flow


@pytest.fixture(scope="module")
def rect_duct(tmp_path_factory):
    """Task 0071's coarse square duct, O-H and Cartesian control, on v2406
    in Docker (about 20 s)."""
    if not _have_v2406():
        pytest.skip("no opencfd/openfoam-default:2406 image")
    work = tmp_path_factory.mktemp("rect_duct")
    out = work / "results.json"
    run = subprocess.run([sys.executable, str(ROOT / "validation/rect_duct/run.py"),
                          "--ratios", "1", "--levels", "1", "--work", str(work),
                          "--json", str(out)], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    return json.loads(out.read_text(encoding="utf-8"))


def test_rect_duct_coarse(rect_duct):
    """The coarse square's measured values (RESULTS.md), with margin, and
    the exact series' checks."""
    r = next(r for r in rect_duct["levels"] if r["mesh"] == "oh")
    assert r["check_mesh_ok"] and r["check_cells_foam"] == r["cells"]
    assert r["converged"] and r["mass_err"] < 1e-8 and abs(r["area_err_signed"]) < 1e-12
    assert 0.02 < r["fRe_err_signed"] < 0.03                 # +2.6 % measured
    assert abs(r["u_c_err_signed"]) < 0.003 and r["profile_max_err"] < 0.03
    s = rect_duct["series"]["1"]
    assert abs(s["fRe"] - 56.908) < 1e-3 and s["terms_change"] < 1e-12


def test_rect_duct_control_coarse(rect_duct):
    """The coarse Cartesian control (RESULTS.md): its error has the
    opposite sign to the O-H's."""
    r = next(r for r in rect_duct["levels"] if r["mesh"] == "cartesian")
    assert r["check_mesh_ok"] and r["check_cells_foam"] == r["cells"] == 2000
    assert r["check_max_non_orthogonality"] < 1e-6
    assert r["converged"] and r["mass_err"] < 1e-8
    assert -0.045 < r["fRe_err_signed"] < -0.035               # -3.92 % measured
    assert -0.030 < r["u_c_err_signed"] < -0.022               # -2.62 % measured
