#!/usr/bin/env python3
"""
Solid rod with uniform heat generation (decision 0012, docs/tasks/0033).

Steady conduction with a uniform source in a rod whose wall is held at
T_w: the same Poisson equation as Poiseuille flow, with no pressure or
convection, so it tests the O-H cross-section on its own:

    hexmesh Assembly → write_openfoam → gmshToFoam → checkMesh
    → laplacianFoam (scalarSemiImplicitSource) → post-processing in Python

Two series of four levels (``nang`` 6 → 48, ``nrad`` = ``nang`` / 2):
uniform, and radially graded (``first_cell`` = 0.05 R at the coarsest
level, refined by ``Assembly.refined``, so each coarse cell splits into
cells of the same growth).  The axial count stays at 2: the problem is
axially uniform.  Usage::

    python3 validation/heated_rod/run.py [--levels 1 2 4 8] [--series uniform graded]
                                         [--work DIR] [--json FILE]
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

import sys                                                     # noqa: E402
sys.path.insert(0, str(ROOT))

import gmsh                                                    # noqa: E402

from hexmesh import Assembly, PipeSpec, Session, Straight      # noqa: E402
from hexmesh.assembly import intent                            # noqa: E402

# The Poiseuille case's OpenFOAM runner, readers and Richardson analysis.
_spec = importlib.util.spec_from_file_location("poiseuille_run",
                                               ROOT / "validation/poiseuille/run.py")
pois = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pois)

# --- physics -----------------------------------------------------------------

R = 0.01                   # rod radius [m]
LENGTH = 2 * R
DT = 1e-5                  # thermal diffusivity k/(ρc) [m²/s]
SU = 0.4                   # q'''/(ρc) [K/s]
T_W = 0.0                  # wall temperature [K]
DT0_EXACT = SU * R**2 / (4 * DT)     # centre excess q'''R²/(4k) = 1 K


def t_exact(r):
    return T_W + SU * (R**2 - np.asarray(r) ** 2) / (4 * DT)


BASE = dict(nang=6, nrad=3, n_layers=2)
FIRST_CELL = 0.05 * R      # graded series, coarsest level
LEVELS = (1, 2, 4, 8)
SERIES = ("uniform", "graded")


def assembly(series: str, k: int) -> Assembly:
    """Level *k* of *series*: the coarse rod refined k× across the section
    (``Assembly.refined``), with the axial count put back to 2."""
    extra = {"first_cell": FIRST_CELL} if series == "graded" else {}
    spec = PipeSpec(nang=BASE["nang"]).core("rod", radius=R, nrad=BASE["nrad"], **extra)
    asm = Assembly(spec, position=[0, 0, 0], direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(LENGTH, n_layers=BASE["n_layers"]), names=["outlet"])
    d = intent.refined_dict(asm.to_dict(), k)
    for e in d["edges"]:
        e["fitting"]["n_layers"] = BASE["n_layers"]
    return Assembly.from_dict(d)


# --- OpenFOAM dictionaries ---------------------------------------------------

H = pois._header

CONTROL = """application     laplacianFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};
deltaT          1;
writeControl    timeStep;
writeInterval   {end_time};
writeFormat     ascii;
writePrecision  17;
timeFormat      general;
runTimeModifiable false;
"""

SCHEMES = """ddtSchemes      { default steadyState; }
gradSchemes     { default Gauss linear; }
divSchemes      { default none; }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }
"""

# Each "time step" runs the non-orthogonal correctors again from the last
# T; residualControl stops at the first step that starts converged.
SOLUTION = """solvers
{
    T { solver PCG; preconditioner DIC; tolerance 1e-14; relTol 0; }
}
SIMPLE
{
    nNonOrthogonalCorrectors 10;
    residualControl { T 1e-11; }
}
"""

FVOPTIONS = f"""heat
{{
    type            scalarSemiImplicitSource;
    active          true;
    selectionMode   all;
    volumeMode      specific;
    injectionRateSuSp {{ T ({SU} 0); }}
}}
"""

T0 = f"""dimensions      [0 0 0 1 0 0 0];
internalField   uniform {T_W};
boundaryField
{{
    rod_inlet  {{ type zeroGradient; }}
    rod_outlet {{ type zeroGradient; }}
    rod_wall   {{ type fixedValue; value uniform {T_W}; }}
}}
"""


def write_case(case: Path, end_time: int) -> None:
    for d in ("0", "constant", "system"):
        (case / d).mkdir(parents=True, exist_ok=True)
    files = {
        "system/controlDict": H("dictionary", "controlDict", "system")
        + CONTROL.format(end_time=end_time),
        "system/fvSchemes": H("dictionary", "fvSchemes", "system") + SCHEMES,
        "system/fvSolution": H("dictionary", "fvSolution", "system") + SOLUTION,
        "constant/transportProperties": H("dictionary", "transportProperties", "constant")
        + f"DT              DT [0 2 -1 0 0 0 0] {DT};\n",
        "constant/fvOptions": H("dictionary", "fvOptions", "constant") + FVOPTIONS,
        "0/T": H("volScalarField", "T", "0") + T0,
    }
    for name, text in files.items():
        (case / name).write_text(text)


# --- geometry of the polyMesh, as OpenFOAM computes it ----------------------

def face_geometry(pts: np.ndarray, faces: list[list[int]]):
    """Face centres and area vectors (``primitiveMeshFaceCentresAndAreas``:
    triangles about the point average, centroids weighted by area)."""
    q = pts[np.array(faces)]                       # (F, 4, 3): all quads
    est = q.mean(axis=1)
    a, b = q, np.roll(q, -1, axis=1)
    n = np.cross(b - a, est[:, None] - a)          # 2 × triangle area vectors
    mag = np.linalg.norm(n, axis=2)
    c = (a + b + est[:, None]) / 3
    centres = (mag[..., None] * c).sum(1) / mag.sum(1)[:, None]
    return centres, 0.5 * n.sum(1)


def cell_geometry(fc, sf, owner, neigh, n_cells):
    """Cell centres and volumes (``primitiveMeshCellCentresAndVols``:
    pyramids from each face to the face-centre average)."""
    nf = len(neigh)
    cnt = np.bincount(owner, minlength=n_cells) + np.bincount(neigh, minlength=n_cells)
    est = np.zeros((n_cells, 3))
    np.add.at(est, owner, fc)
    np.add.at(est, neigh, fc[:nf])
    est /= cnt[:, None]
    vol = np.zeros(n_cells)
    ctr = np.zeros((n_cells, 3))
    for cells, faces, sign in ((owner, slice(None), 1.0), (neigh, slice(0, nf), -1.0)):
        f = fc[faces]
        pyr = sign * np.einsum("ij,ij->i", sf[faces], f - est[cells])
        np.add.at(vol, cells, pyr)
        np.add.at(ctr, cells, pyr[:, None] * (0.75 * f + 0.25 * est[cells]))
    return ctr / vol[:, None], vol / 3


def results(case: Path) -> dict:
    mesh = case / "constant/polyMesh"
    pts, faces = pois.read_points(mesh / "points"), pois.read_faces(mesh / "faces")
    owner, neigh = pois.read_labels(mesh / "owner"), pois.read_labels(mesh / "neighbour")
    t = pois._latest_time(case)
    T = pois.read_internal(t / "T", 1)
    fc, sf = face_geometry(pts, faces)
    cc, vol = cell_geometry(fc, sf, owner, neigh, len(T))
    r = np.hypot(cc[:, 1], cc[:, 2])
    err = T - t_exact(r)
    V = float(vol.sum())

    # Wall heat flow, as laplacianFoam discretises it: fixedValue patch,
    # corrected snGrad with no boundary correction, delta coefficient
    # 1/max(n·d, 0.05|d|) (nonOrthDeltaCoeffs).
    wall = pois.read_patch_faces(mesh / "boundary", "rod_wall")
    P = owner[wall]
    d = fc[wall] - cc[P]
    mag_sf = np.linalg.norm(sf[wall], axis=1)
    nd = np.einsum("ij,ij->i", sf[wall] / mag_sf[:, None], d)
    dc = 1.0 / np.maximum(nd, 0.05 * np.linalg.norm(d, axis=1))
    q_wall = float(np.sum(DT * mag_sf * dc * (T[P] - T_W)))
    q_gen = SU * V

    # centre excess: T = c0 − c2 r² fitted to the cells within R/3
    fit = r < R / 3
    c0, _ = np.linalg.lstsq(np.column_stack([np.ones(fit.sum()), r[fit] ** 2]),
                            T[fit], rcond=None)[0]
    worst = int(np.argmax(np.abs(err)))
    return {
        "volume": V, "volume_err_signed": (V - math.pi * R**2 * LENGTH) / (math.pi * R**2 * LENGTH),
        "q_gen": q_gen, "q_wall": q_wall, "energy_err": abs(q_wall - q_gen) / q_gen,
        "dt0": float(c0) - T_W, "dt0_err_signed": (float(c0) - T_W - DT0_EXACT) / DT0_EXACT,
        "dt0_fit_cells": int(fit.sum()),
        "l2_err": float(math.sqrt(np.sum(vol * err**2) / V)) / DT0_EXACT,
        "max_err": float(np.abs(err).max()) / DT0_EXACT,
        "mean_err_signed": float(np.sum(vol * err) / V) / DT0_EXACT,
        "max_err_r": float(r[worst] / R),
        "max_err_angle": float(math.degrees(math.atan2(cc[worst, 2], cc[worst, 1])) % 90),
    }


def run_level(series: str, k: int, work: Path, end_time: int) -> dict:
    name = f"{series}-{k}"
    case = work / name
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    with Session(f"heated-rod-{name}"):
        asm = assembly(series, k)
        cells = asm.cell_count()
        msh = case / "rod.msh"
        asm.write_openfoam(msh)
        sj = asm.check_quality("scaled_jacobian").worst
        spec = asm.inlet.spec
    write_case(case, end_time)
    pois.foam(f"gmshToFoam {msh.name}", case, "log.gmshToFoam")
    check = pois.foam("checkMesh", case, "log.checkMesh")
    solve = pois.foam("laplacianFoam", case, "log.laplacianFoam")
    res = [float(v) for v in re.findall(r"Initial residual = ([\d.e+-]+)", solve)]
    out = {
        "series": series, "k": k, "nang": spec.nang, "nrad": spec._core_nrad,
        "mprg": spec._core_mprg, "cells": cells,
        "cells_foam": int(re.search(r"cells:\s+(\d+)", check).group(1)),
        "mesh_ok": "Mesh OK." in check,
        "min_scaled_jacobian": sj,
        "max_non_orthogonality": float(
            re.search(r"non-orthogonality Max: ([\d.e+-]+)", check).group(1)),
        "max_skewness": float(re.search(r"Max skewness = ([\d.e+-]+)", check).group(1)),
        "fvoptions_read": "Selecting finite volume options type scalarSemiImplicitSource" in solve,
        "steps": len(re.findall(r"^Time = ", solve, re.M)),
        "last_initial_residual": res[-1],
        "converged": "reached convergence" in solve or res[-1] < 1e-10,
    }
    out.update(results(case))
    print(f"[{name}] " + json.dumps(out), flush=True)
    return out


# --- analysis ----------------------------------------------------------------

def orders(rows: list[dict], key: str) -> list[float]:
    return [math.log2(a[key] / b[key]) for a, b in zip(rows, rows[1:])]


def analyse(rows: list[dict]) -> dict:
    out = {"order_l2": orders(rows, "l2_err"), "order_max": orders(rows, "max_err"),
           "order_dt0": orders(rows, "dt0_err_signed") if all(
               r["dt0_err_signed"] for r in rows) else None}
    if len(rows) >= 3:
        rich = pois.richardson(*(r["dt0"] for r in rows[-3:]))
        rich["extrapolated_err"] = (rich["extrapolated"] - DT0_EXACT) / DT0_EXACT
        out["richardson_dt0"] = rich
    return out


def table(rows: list[dict]) -> str:
    lines = ["| series | nang | nrad | cells | Mesh OK | max non-orth. (°) | max skewness "
             "| energy balance | ΔT₀ error | L2 error | max error (at r/R) |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r['series']} | {r['nang']} | {r['nrad']} | {r['cells']} | {r['mesh_ok']} "
            f"| {r['max_non_orthogonality']:.1f} | {r['max_skewness']:.3f} "
            f"| {r['energy_err']:.1e} | {r['dt0_err_signed']:+.4%} | {r['l2_err']:.3e} "
            f"| {r['max_err']:.3e} ({r['max_err_r']:.2f}) |")
    return "\n".join(lines)


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--levels", nargs="+", type=int, default=list(LEVELS))
    ap.add_argument("--series", nargs="+", default=list(SERIES), choices=SERIES)
    ap.add_argument("--work", type=Path, default=HERE / "work")
    ap.add_argument("--end-time", type=int, default=200)
    ap.add_argument("--json", type=Path, help="write all results as JSON")
    args = ap.parse_args(argv)
    data = {"versions": pois.versions(), "exact": {"dt0": DT0_EXACT}, "series": {}}
    for series in args.series:
        rows = [run_level(series, k, args.work, args.end_time) for k in args.levels]
        data["series"][series] = {"levels": rows, "analysis": analyse(rows) if len(rows) > 1 else {}}
        print(f"\n{series}:\n" + table(rows))
        a = data["series"][series]["analysis"]
        if a:
            print("observed order, L2: " + ", ".join(f"{o:.2f}" for o in a["order_l2"]))
            print("observed order, max: " + ", ".join(f"{o:.2f}" for o in a["order_max"]))
            if "richardson_dt0" in a:
                rd = a["richardson_dt0"]
                print(f"ΔT₀ Richardson (last three): order {rd['order']:.2f}, extrapolated "
                      f"{rd['extrapolated']:.8f} ({rd['extrapolated_err']:+.4%} vs exact), "
                      f"GCI fine {rd['gci_fine']:.3%}")
    if args.json:
        args.json.write_text(json.dumps(data, indent=1))
    return data


if __name__ == "__main__":
    main()
