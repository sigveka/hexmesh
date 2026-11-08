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
Junction non-orthogonality, predicted against meshed (task 0104).  Not part
of the test suite.

    python3 benchmarks/junction_nonorth.py                 # kit and sweep
    python3 benchmarks/junction_nonorth.py --only kit      # or sweep
    python3 benchmarks/junction_nonorth.py --json out.json

For each junction, the prediction is ``BlockLayout.predicted_nonorth()`` on
the fitting's own block layout (pure, no GMSH); the measurement is
``quality_hex.max_non_orthogonality`` over the fitting's meshed hexes, the
definition ``checkMesh`` and the meshed check use.  Cases:

* ``kit``: every junction of the conformance kit
  (``tests/test_fitting_conformance.py``): tees, laterals, duct taps on
  O-H and H mains, wyes;
* ``sweep``: task 0060's tee sweep, angle × r/R × 0 / 2 shells × nang 4 /
  8, with 35° in place of 30° (which doesn't mesh).  A case the Tee
  rejects (predicted SJ below the floor) is recorded as rejected.

Writes ``benchmarks/junction_nonorth.json`` by default.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from hexmesh import Assembly, HexmeshError, PipeSpec, Session, Straight, Tee  # noqa: E402
from hexmesh._gmsh import gmsh  # noqa: E402
from hexmesh.quality_hex import max_non_orthogonality  # noqa: E402

OUT = ROOT / "benchmarks" / "junction_nonorth.json"
ANGLES = (90, 75, 60, 45, 35)
RATIOS = (0.3, 0.6, 0.9)


def _junction(asm: Assembly):
    return next(e for e in asm._edges if type(e.fitting).__name__ in ("Tee", "Wye"))


def measure(asm: Assembly) -> dict:
    """Predicted and meshed worst non-orthogonality of *asm*'s junction."""
    e = _junction(asm)
    t0 = time.perf_counter()
    layout = e.fitting.layout([p.frame for p in e.ports], e.ports[0].spec)
    predicted, block = layout.predicted_nonorth()
    seconds = time.perf_counter() - t0
    with Session("junction-nonorth"):
        asm.mesh()
        ntag, nx, _ = gmsh.model.mesh.getNodes()
        pos = np.full(int(ntag.max()) + 1, -1)
        pos[ntag.astype(int)] = np.arange(len(ntag))
        nx = nx.reshape(-1, 3)
        hexes = [n.reshape(-1, 8) for v in asm._fitting_volumes[e.index]
                 for t, _, n in zip(*gmsh.model.mesh.getElements(3, v)) if t == 5]
        conn = pos[np.vstack(hexes).astype(int)]
        meshed = max_non_orthogonality(nx[conn], conn)
    return {"predicted": round(predicted, 2), "meshed": round(meshed, 2),
            "error": round(predicted - meshed, 2), "block": block,
            "material": layout.blocks[block][1], "cells": len(conn),
            "predict_ms": round(1000 * seconds, 1)}


def kit_cases() -> dict:
    from test_fitting_conformance import CASES
    return {name: build for name, build in CASES.items()
            if name.startswith(("tee", "lateral", "wye"))}


def sweep_cases() -> dict:
    from test_fitting_conformance import _tee

    def spec(nang, shells):
        s = PipeSpec(nang=nang).core("fluid", radius=0.1, nrad=3)
        return s.shell("wall", dR=0.025, nrad=2).shell("insulation", dR=0.03, nrad=2) \
            if shells else s
    return {f"tee-{a}-{q}-{sh}sh-nang{n}":
            (lambda a=a, q=q, sh=sh, n=n: _tee(q, spec=spec(n, sh), angle=a))
            for a in ANGLES for q in RATIOS for sh in (0, 2) for n in (4, 8)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", choices=("kit", "sweep"))
    ap.add_argument("--json", type=Path, default=OUT)
    args = ap.parse_args(argv)
    warnings.simplefilter("ignore")
    groups = {"kit": kit_cases, "sweep": sweep_cases}
    out = {}
    for group, cases in groups.items():
        if args.only and group != args.only:
            continue
        for name, build in cases().items():
            try:
                asm = build()
                asm.validate()
                row = measure(asm)
            except HexmeshError as err:
                row = {"rejected": err.code}
            out[name] = {"group": group, **row}
            print(name, row, flush=True)
    args.json.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    rows = [r for r in out.values() if "error" in r]
    if rows:
        err = np.array([r["error"] for r in rows])
        print(f"{len(rows)} measured, {len(out) - len(rows)} rejected; error "
              f"{err.min():+.1f} to {err.max():+.1f}°, optimistic (< -1°) in "
              f"{int((err < -1).sum())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
