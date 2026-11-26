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
A volunteer's bend run under NumPy 2 (task 0196): the probes went into the
controlDict as ``np.float64(…)``, every rank of the first pimpleFoam chunk
stopped, and ``histories`` then crashed on series with no rows.  Here:
numbers in OpenFOAM text, the empty histories, and the resume.  No
OpenFOAM: the solver is a stand-in.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("bend_run", ROOT / "validation/turbulent_bend/run.py")
run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run)

HEADER = "# Volume field value\n# Time    volAverage(p)\n"


class Np2(float):
    """A float that prints as a NumPy 2 scalar does, on any NumPy."""

    def __repr__(self):
        return f"np.float64({float.__repr__(self)})"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- numbers in OpenFOAM text ---------------------------------------------------------

def test_num_reads_back_and_never_says_np():
    import numpy as np
    for x in (Np2(0.1), np.float64(0.1), np.float32(0.25), 0.1, 3):
        assert run.of.num(x) in ("0.1", "0.25", "3.0")
        assert float(run.of.num(x)) == float(x)
    assert run.of._format(np.float64(1e-3)) == "0.001"


def test_the_probes_are_numbers_openfoam_reads():
    probes = [[Np2(0.1), Np2(-0.2), Np2(3.5)]]
    text = run._pimple_control(50, Np2(1.5), probes)
    assert "(0.1 -0.2 3.5)" in text and "timeStart       1.5;" in text
    assert "np." not in text and "float64" not in text


def test_the_numpy_2_trap_is_gone_from_the_other_writers():
    import numpy as np
    mms = _load("mms_run", "validation/mms/run.py")
    helical = _load("helical_run", "validation/helical_pipe/run.py")
    w = [Np2(1.5), Np2(2.5), Np2(0.5)]
    for text in (mms._expr(w, Np2(2.0)), mms._grad_expr(w), helical._vec(np.array(w)),
                 helical._vec(w)):
        assert "np." not in text and "float64" not in text, text


def _series(case: Path, name: str, file: str, rows: list[str] | None, header: str = HEADER):
    """*case*'s function object *name* with *rows* in *file*; None: no file."""
    d = case / "postProcessing" / name / "0"
    d.mkdir(parents=True, exist_ok=True)
    if rows is not None:
        (d / file).write_text(header + "".join(r + "\n" for r in rows), encoding="utf-8")


def _full(case: Path, times=(1.0, 2.0)):
    _series(case, "pBefore", "volFieldValue.dat", [f"{t} 1.0" for t in times])
    _series(case, "pAfter", "volFieldValue.dat", [f"{t} 0.5" for t in times])
    _series(case, "lda", "U", [f"{t} (0 0.4 0) (0 0.2 0)" for t in times], "# Probe 0\n")


def test_rows_give_the_history(tmp_path):
    _full(tmp_path)
    h = run.histories(tmp_path, 0.02)
    assert list(h["t"]) == [1.0, 2.0] and h["w"].shape == (2, 2)


@pytest.mark.parametrize("what, make", [
    ("an empty file", lambda c: _series(c, "pBefore", "volFieldValue.dat", [], header="")),
    ("a header-only file", lambda c: _series(c, "pAfter", "volFieldValue.dat", [])),
    ("a missing series", lambda c: shutil.rmtree(c / "postProcessing" / "lda")),
])
def test_a_series_without_rows_is_no_history_yet(tmp_path, what, make):
    _full(tmp_path)
    make(tmp_path)
    assert run.histories(tmp_path, 0.02) is None, what
    assert len(run.empty_series(tmp_path)) == 1


def test_no_rows_is_still_two_dimensional(tmp_path):
    _series(tmp_path, "pBefore", "volFieldValue.dat", [])
    t, v = run._history(tmp_path, "pBefore", "volFieldValue.dat")
    assert t.shape == (0,) and v.ndim == 2 and v[:0, :].shape[0] == 0


class _Chunk(Exception):
    """The stand-in solver was asked for a chunk."""


def _crashed_level(d: Path) -> Path:
    """A run directory as the crash left it: the steady start done
    (``start.json``), the transient set up, an empty ``postProcessing``."""
    d.mkdir()
    (d / "setup.json").write_text(json.dumps({"cells": 1}), encoding="utf-8")
    (d / "start.json").write_text(json.dumps(
        {"precursor": {"f": 0.02, "f_err_mckeon": 0.0077}, "steps": 2000, "k_bend": 0.2595,
         "start": "steady from rest", "wall_s": 1000.0}), encoding="utf-8")
    (d / "zones.json").write_text(json.dumps({"zones": []}), encoding="utf-8")
    case = d / "transient"
    (case / "0").mkdir(parents=True)
    (case / "system").mkdir()
    (case / "system" / "controlDict").write_text(        # as NumPy 2 wrote it
        "functions { lda { probeLocations ( (np.float64(0.1) 0 0) ); } }", encoding="utf-8")
    _series(case, "pBefore", "volFieldValue.dat", [])
    _series(case, "pAfter", "volFieldValue.dat", [])
    return case


def _solver(case, *a, **k):
    """pimpleFoam's view of the controlDict: it can't read a NumPy repr."""
    text = (case / "system" / "controlDict").read_text(encoding="utf-8")
    if "np.float64(" in text:
        return "--> FOAM FATAL IO ERROR: (openfoam-2406)\nfile: stream/functions/lda/probeLocations"
    raise _Chunk()


def test_a_crashed_level_resumes_into_its_first_chunk(tmp_path, monkeypatch):
    """The volunteer's run directory: the steady start kept, the broken
    controlDict rewritten, the first chunk run."""
    case = _crashed_level(tmp_path / "source")
    monkeypatch.setattr(run.of, "latest_time", lambda c: c / "0")
    monkeypatch.setattr(run.of, "run_solver", _solver)
    monkeypatch.setattr(run, "solve", lambda *a, **k: pytest.fail("the steady start ran again"))
    with pytest.raises(_Chunk):
        run.transient_run(tmp_path / "source", 1, "fixed", 1)
    assert (case / "0").is_dir()


def test_a_chunk_that_writes_no_rows_names_its_log(tmp_path, monkeypatch):
    _crashed_level(tmp_path / "source")
    monkeypatch.setattr(run.of, "latest_time", lambda c: c / "0")
    monkeypatch.setattr(run.of, "run_solver", lambda *a, **k: "Time = 2\n")
    with pytest.raises(SystemExit, match=r"the chunk from t = 0 wrote no pBefore/pAfter/lda "
                                         r"rows; see transient/log\.pimpleFoam\.0"):
        run.transient_run(tmp_path / "source", 1, "fixed", 1)
