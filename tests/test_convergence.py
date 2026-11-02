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
"""validation/tools/convergence.py: three-level Richardson with an explicit
status (task 0089)."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("convergence",
                                               ROOT / "validation/tools/convergence.py")
conv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conv)


def _series(p, hs, exact=1.0, c=0.01):
    return [exact + c * h ** p for h in hs]          # coarse → fine


def test_converging_constant_ratio_recovers_the_order():
    r = conv.richardson(*_series(2, (4, 2, 1)))
    assert r["status"] == "converging" and not r["oscillatory"]
    assert r["order"] == pytest.approx(2, abs=1e-12)
    assert r["extrapolated"] == pytest.approx(1.0, abs=1e-12)
    assert r["e_a"] == pytest.approx(0.03 / 1.01, abs=1e-15)
    assert r["gci_fine"] == pytest.approx(1.25 * r["e_a"] / 3, abs=1e-15)


def test_converging_non_constant_ratio():
    # h3 = 2, h2 = 4/3, h1 = 1: r32 = 3/2, r21 = 4/3
    r = conv.richardson(*_series(2, (2, 4 / 3, 1)), 4 / 3, 3 / 2)
    assert r["status"] == "converging"
    assert r["order"] == pytest.approx(2, abs=1e-9)
    assert r["extrapolated"] == pytest.approx(1.0, abs=1e-10)


def test_oscillatory_has_bounds_and_no_order():
    r = conv.richardson(1.02, 0.99, 1.005)
    assert r["status"] == "oscillatory" and r["oscillatory"]
    assert r["order"] is r["extrapolated"] is r["gci_fine"] is None
    assert r["bounds"] == [0.99, 1.02]


def test_diverging_has_no_order():
    r = conv.richardson(1.01, 1.03, 1.07)               # differences grow
    assert r["status"] == "diverging"
    assert r["order"] is r["extrapolated"] is None


def test_the_oh_square_duct_diverges():
    """Task 0071's O-H square: f·Re 58.414, 58.027, 57.569 (differences
    0.387 then 0.458).  The old |log| gave 'order 0.24'."""
    r = conv.richardson(58.41421322207989, 58.02693396330436, 57.56925173293786)
    assert r["status"] == "diverging" and r["extrapolated"] is None


@pytest.mark.parametrize("vals, which", [
    ((1.0, 1.0, 1.0), "all three"),
    ((1.1, 1.0, 1.0), "medium and fine"),
    ((1.0, 1.0, 0.9), "coarse and medium"),
])
def test_zero_difference_is_reported_without_dividing(vals, which):
    r = conv.richardson(*vals)
    assert r["status"] == "zero_difference" and which in r["note"]
    assert r["order"] is None


def test_absolute_scale_for_a_quantity_with_exact_zero():
    r = conv.richardson(*_series(2, (4, 2, 1), exact=0.0), scale=1.0)
    assert r["e_a"] == pytest.approx(0.03, abs=1e-15)
    assert r["extrapolated"] == pytest.approx(0.0, abs=1e-12)


def test_gate_fails_on_anything_but_converging():
    ok, why = conv.gate_extrapolated(conv.richardson(1.01, 1.03, 1.07), 1.0, 1.0)
    assert not ok and why.startswith("diverging")      # a generous limit doesn't help
    ok, why = conv.gate_extrapolated(conv.richardson(1.02, 0.99, 1.005), 1.0, 1.0)
    assert not ok and why.startswith("oscillatory")
    ok, _ = conv.gate_extrapolated(conv.richardson(*_series(2, (4, 2, 1))), 1.0, 1e-3)
    assert ok
    ok, _ = conv.gate_extrapolated(conv.richardson(*_series(2, (4, 2, 1))), 1.1, 1e-3)
    assert not ok


def test_describe_shows_status_instead_of_an_order():
    assert conv.describe(conv.richardson(*_series(2, (4, 2, 1)))) == "2.00"
    assert conv.describe(conv.richardson(1.01, 1.03, 1.07)) == "diverging"


def test_every_case_uses_the_shared_function():
    """No case takes Richardson from another case's driver (task 0089)."""
    for run in sorted((ROOT / "validation").glob("*/run.py")):
        text = run.read_text()
        assert "pois.richardson" not in text and "sten.richardson" not in text, run
        if "richardson(" in text:
            assert "tools/convergence.py" in text, f"{run}: load validation/tools/convergence.py"
