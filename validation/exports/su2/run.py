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
SU2: the .su2 export checked end to end (decision 0057, task 0183).

    docker build -t hexmesh-su2:8.6.0 validation/exports/su2
    python3 validation/exports/su2/run.py --threads 4          # k = 1, 2, 3

**The mesh** is OpenFOAM Poiseuille's (``validation/poiseuille/run.py``,
the same ``assembly(k)``: 30 D of pipe, interfaces at 15 D and 25 D),
written with ``write()`` to ``.su2``.

**The import:** SU2's own count of hexahedra must be ``cell_count()``,
every boundary group a marker by name, and every volume element
correctly oriented (SU2's log).

**The solve:** SU2's incompressible laminar solver (constant density
and viscosity, no energy equation) at Re 100: a uniform inlet velocity,
the outlet at p = 0, the wall no-slip.  SU2 is vertex-based: the inlet's
nodes on the wall are no-slip, so the inlet passes less than U·A, by a
fraction of order h/R.  The exact values are therefore Poiseuille's at
the realised bulk velocity U_b, SU2's own mass flow through the outlet
(``MARKER_ANALYZE``) over ρπR²:

- Δp between 15 D and 25 D on the axis against 32 ν U_b ΔX / D²;
- u on the axis at 20 D against 2 U_b.

Both errors are gated at the finest level (2 %), with their order over
k = 1, 2, 3 reported (Richardson); the inlet's flux deficit is reported
with its order (1, expected).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from hexmesh import Session                                    # noqa: E402


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


conv = _load("convergence", "validation/tools/convergence.py")     # richardson() (task 0089)
stored = _load("stored", "validation/tools/results.py")            # results.json (task 0093)
pois = _load("poiseuille_run", "validation/poiseuille/run.py")     # the mesh and the flow

IMAGE = "hexmesh-su2:8.6.0"      # built from ./Dockerfile (SU2 v8.6.0, pinned zip and base)
VERSION = "v8.6.0"
LEVELS = (1, 2, 3)               # 5 184, 41 472, 139 968 cells
ERROR_MAX = 0.02                 # Δp and u_max against Poiseuille at U_b, finest level
ITER = 2000                      # fixed: stationary from about 1000 at k = 3 (task 0183)
GROUPS = ("fluid_inlet", "fluid_outlet", "fluid_wall")

D, R, NU, U_IN = pois.D, pois.R, pois.NU, pois.U_MEAN
X_A, X_B, X_MID = pois.X_A, pois.X_B, pois.X_MID

CONFIG = """\
% hexmesh export check (validation/exports/su2/run.py): laminar Poiseuille
SOLVER= INC_NAVIER_STOKES
KIND_TURB_MODEL= NONE
MATH_PROBLEM= DIRECT
INC_DENSITY_MODEL= CONSTANT
INC_ENERGY_EQUATION= NO
INC_DENSITY_INIT= 1.0
INC_VELOCITY_INIT= ( {u!r}, 0.0, 0.0 )
INC_NONDIM= DIMENSIONAL
INC_INLET_TYPE= VELOCITY_INLET
INC_OUTLET_TYPE= PRESSURE_OUTLET
VISCOSITY_MODEL= CONSTANT_VISCOSITY
MU_CONSTANT= {nu!r}
MARKER_HEATFLUX= ( fluid_wall, 0.0 )
MARKER_INLET= ( fluid_inlet, 288.15, {u!r}, 1.0, 0.0, 0.0 )
MARKER_OUTLET= ( fluid_outlet, 0.0 )
MARKER_PLOTTING= ( fluid_wall )
MARKER_MONITORING= ( fluid_wall )
NUM_METHOD_GRAD= GREEN_GAUSS
CFL_NUMBER= 100
LINEAR_SOLVER= FGMRES
LINEAR_SOLVER_PREC= ILU
LINEAR_SOLVER_ERROR= 1E-10
LINEAR_SOLVER_ITER= 20
CONV_NUM_METHOD_FLOW= FDS
MUSCL_FLOW= YES
SLOPE_LIMITER_FLOW= NONE
TIME_DISCRE_FLOW= EULER_IMPLICIT
ITER= {iters}
CONV_FIELD= RMS_PRESSURE
CONV_RESIDUAL_MINVAL= -99
MARKER_ANALYZE= ( fluid_inlet, fluid_outlet )
HISTORY_OUTPUT= (INNER_ITER, RMS_RES, FLOW_COEFF_SURF)
MESH_FILENAME= mesh.su2
MESH_FORMAT= SU2
OUTPUT_FILES= (RESTART_ASCII)
RESTART_FILENAME= restart
SCREEN_OUTPUT= (INNER_ITER, RMS_PRESSURE, RMS_VELOCITY-X)
SCREEN_WRT_FREQ_INNER= 100
"""


def meshes():
    """(label, caption, build) per mesh shown in README.md."""
    return [("pipe", "OpenFOAM Poiseuille's pipe, k = 1, as SU2 reads it",
             lambda: pois.assembly(1))]


def write_case(d: Path, k: int, iters: int = ITER) -> dict:
    """The mesh (``mesh.su2``) and ``case.cfg`` in *d*."""
    d.mkdir(parents=True, exist_ok=True)
    asm = pois.assembly(k)
    with Session(f"su2-{k}"), asm.to_mesh() as m:
        m.write(str(d / "mesh.su2"))
    (d / "case.cfg").write_text(CONFIG.format(u=U_IN, nu=NU, iters=iters), encoding="utf-8")
    return {"cells": asm.cell_count(), **stored.counts(asm)}


def su2(d: Path, threads: int) -> str:
    """SU2_CFD on d/case.cfg in the pinned image; returns its log."""
    cmd = ["docker", "run", "--rm", "-u", f"{os.getuid()}:{os.getgid()}",
           "-e", f"OMP_NUM_THREADS={threads}", "-v", f"{d.resolve()}:/work", IMAGE,
           "SU2_CFD", "-t", str(threads), "case.cfg"]
    out = subprocess.run(cmd, capture_output=True, text=True)
    (d / "log.SU2_CFD").write_text(out.stdout + out.stderr, encoding="utf-8")
    if out.returncode or "Exit Success" not in out.stdout:
        raise RuntimeError(f"SU2_CFD failed ({out.returncode}): see {d / 'log.SU2_CFD'}")
    return out.stdout


def imported(log: str) -> dict:
    """What SU2 says it read: hexahedra, markers and their elements, the
    orientation, and the boundary elements it re-oriented."""
    markers = {m[2]: int(m[1]) for m in
               re.finditer(r"^(\d+) boundary elements in index \d+ \(Marker = (\S+)\)\.", log, re.M)}
    hexes = re.search(r"^(\d+) hexahedra\.", log, re.M)
    flipped = re.search(r"re-orientation of (\d+) (\w+) surface elements", log)
    return {"hexahedra": int(hexes[1]) if hexes else 0, "markers": markers,
            "oriented": "All volume elements are correctly oriented" in log,
            "reoriented_surface": int(flipped[1]) if flipped else 0,
            "converged": "All convergence criteria satisfied" in log}   # never: ITER is fixed


def history(d: Path) -> dict:
    """The last row of d/history.csv, by column name."""
    lines = (d / "history.csv").read_text(encoding="utf-8").splitlines()
    names = [c.strip().strip('"') for c in lines[0].split(",")]
    return {n: float(v) for n, v in zip(names, lines[-1].split(","))} | {"steps": len(lines) - 1}


def results(d: Path) -> dict:
    """Δp and u_max from d/restart.csv (nodal values), U_b from the
    outlet's mass flow (d/history.csv)."""
    data = np.genfromtxt(d / "restart.csv", delimiter=",", skip_header=1)
    x, y, z, p, u = data[:, 1], data[:, 2], data[:, 3], data[:, 4], data[:, 5]
    tol = 1e-9 * D

    def at(x0):
        return np.abs(x - x0) < tol

    axis = (np.abs(y) < tol) & (np.abs(z) < tol)
    pa, pb = p[axis & at(X_A)], p[axis & at(X_B)]
    um = u[axis & at(X_MID)]
    if not (len(pa) == len(pb) == len(um) == 1):
        raise RuntimeError("no node on the axis at a measurement plane")
    h = history(d)
    u_b = -h["Avg_Massflow(fluid_outlet)"] / (np.pi * R ** 2)          # ρ = 1
    dp, u_max = float(pa[0] - pb[0]), float(um[0])
    dp_exact = 32 * NU * u_b * (X_B - X_A) / D ** 2
    return {"u_b": u_b, "inlet_deficit": 1 - u_b / U_IN, "steps": h["steps"],
            "massflow_in": h["Avg_Massflow(fluid_inlet)"],
            "massflow_out": h["Avg_Massflow(fluid_outlet)"], "dp": dp, "dp_exact_at_u_b": dp_exact,
            "dp_err": dp / dp_exact - 1, "u_max": u_max, "u_max_err": u_max / (2 * u_b) - 1}


def solve(d: Path, k: int, threads: int) -> dict:
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    log = su2(d, threads)
    return {"k": k, **meta, **imported(log), **results(d)}


def run_level(k: int, work: Path, threads: int) -> dict:
    d = work / f"k{k}"
    if d.exists():
        shutil.rmtree(d)
    meta = write_case(d, k)
    (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return solve(d, k, threads)


# --- analysis -------------------------------------------------------------------------

#: the convergence quantities; k = 1, 2, 3 are spacing ratios 2 and 1.5
SERIES = ("dp_err", "u_max_err", "inlet_deficit")


def analyse(levels: list[dict]) -> dict:
    rows = sorted((r for r in levels if r["k"] in (1, 2, 3)), key=lambda r: r["k"])
    if len(rows) != 3:
        return {}
    return {q: conv.richardson(*(r[q] for r in rows), r21=1.5, r32=2.0, scale=1.0)
            for q in SERIES}


def recheck(data: dict) -> list[dict]:
    """The import at every level; Δp and u_max within 2 % of Poiseuille
    at U_b at the finest level; their orders reported."""
    out = []
    levels = sorted(data["levels"], key=lambda r: r["k"])
    for lv in levels:
        ok = (lv["hexahedra"] == lv["cells"] and lv["oriented"]
              and set(lv["markers"]) == set(GROUPS))
        out.append(stored.row(f"import (k = {lv['k']}): hexahedra, markers, orientation",
                              gate="hexahedra = cell_count(), every group a marker",
                              ok=ok, value=f"{lv['hexahedra']} / {lv['cells']}",
                              note=", ".join(sorted(lv["markers"]))))
    for q, r in analyse(levels).items():
        out.append(stored.row(f"{q} (k = 1, 2, 3)", rich=r,
                              note=f"order {r['order']:.2f}" if r["status"] == "converging"
                              else r["note"]))
    if levels:
        lv = levels[-1]
        for q in ("dp_err", "u_max_err"):
            out.append(stored.row(f"{q} (k = {lv['k']})", gate=f"|e| <= {ERROR_MAX:g}",
                                  ok=abs(lv[q]) <= ERROR_MAX, value=f"{lv[q]:+.4f}",
                                  note="Poiseuille at the realised U_b"))
    return out


def table(levels: list[dict]) -> str:
    lines = ["| k | cells | hexahedra | markers | U_b/U_in | Δp error | u_max error |",
             "|---|---|---|---|---|---|---|"]
    for r in sorted(levels, key=lambda r: r["k"]):
        lines.append(f"| {r['k']} | {r['cells']} | {r['hexahedra']} | {len(r['markers'])} | "
                     f"{r['u_b'] / U_IN:.4f} | {r['dp_err']:+.4f} | {r['u_max_err']:+.4f} |")
    return "\n".join(lines)


def _environment(store) -> dict:
    """The store's start (task 0184), with the SU2 image."""
    return {**store.start, "su2": f"{IMAGE} (SU2 {VERSION}, ./Dockerfile)", "runner": "docker"}


# --- volunteer runs (validation/volunteer.py; decision 0044, task 0179) -------------

def _parse(level: str) -> int:
    m = re.fullmatch(r"k([1-9])", level)
    if not m:
        raise ValueError(f"su2 has no level {level!r}: k1 … k9 (refined(k))")
    return int(m[1])


def check_level(level: str) -> None:
    """Raise ``ValueError`` unless this driver can build *level*."""
    _parse(level)


def prepare(level: str, d: Path, mesh_only: bool = False) -> dict:
    """Write *level*'s mesh and configuration in *d*."""
    meta = write_case(d, _parse(level))
    (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return {"msh": d / "mesh.su2", "check": None}


def run(level: str, d: Path, n_proc: int) -> None:
    """Solve *level* in *d* (*n_proc* threads); values to d/level.json."""
    (d / "level.json").write_text(json.dumps(solve(d, _parse(level), n_proc)), encoding="utf-8")


def collect(level: str, d: Path) -> dict:
    path = d / "level.json"
    if not path.exists():
        raise ValueError(f"{level} isn't finished: run the job again")
    return {"values": json.loads(path.read_text(encoding="utf-8")), "extra": {}}


def recompute(values: dict) -> dict:
    """What a level's stored numbers must equal, from its own values."""
    return {"cells": pois.assembly(values["k"]).cell_count(),
            "dp_err": values["dp"] / values["dp_exact_at_u_b"] - 1,
            "u_max_err": values["u_max"] / (2 * values["u_b"]) - 1}


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--levels", nargs="+", type=int, default=list(LEVELS),
                    help="refinement levels k (every count ×k: k³× the cells); "
                         "default %(default)s")
    ap.add_argument("--work", type=Path, default=HERE / "work",
                    help="folder for each level's SU2 case (default: "
                         "validation/exports/su2/work/, not committed); deleted once stored, "
                         "unless --keep-work")
    ap.add_argument("--threads", type=int, default=1,
                    help="OpenMP threads per solve (check other runs first, CLAUDE.md)")
    stored.add_arguments(ap, HERE)
    args = ap.parse_args(argv)
    store = stored.Store(args.json, "su2_poiseuille")
    store.put_extra("method", {"image": IMAGE, "su2": VERSION, "re": pois.RE,
                               "exact": "Poiseuille at the realised bulk velocity U_b "
                                        "(SU2's outlet mass flow over rho pi R^2)",
                               "error_max": ERROR_MAX})
    for k in args.levels:
        name = f"k{k}"
        if (lv := store.level(name)) and lv["precision"] == stored.FULL:
            print(f"[k={k}] reused from {store.path}", flush=True)
            continue
        store.begin()
        r = run_level(k, args.work, args.threads)
        store.put(name, r, env=_environment(store), cores=args.threads)   # OpenMP threads
        print(f"[k={k}] {r['hexahedra']} hexahedra of {r['cells']}, markers "
              f"{sorted(r['markers'])}, U_b/U_in {r['u_b'] / U_IN:.4f}, "
              f"Δp {r['dp_err']:+.4f}, u_max {r['u_max_err']:+.4f}", flush=True)
        if not args.keep_work:
            stored.remove_work(args.work / name)
    rich = analyse(store.levels())
    if rich:
        store.put_extra("richardson", rich)
    print(table(store.levels()))
    for r in recheck(store.data):
        print(f"{r['quantity']}: {r['value']} ({r['verdict']}); {r['note']}")
    return rich


if __name__ == "__main__":
    main()
