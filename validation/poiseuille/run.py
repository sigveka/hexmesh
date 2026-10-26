#!/usr/bin/env python3
"""
Laminar Hagen–Poiseuille validation (decision 0012, docs/tasks/0020).

Steady laminar flow in a straight pipe, three refinement levels:

    hexmesh Assembly → write_openfoam → gmshToFoam → apply_boundary_roles
    → checkMesh → topoSet → simpleFoam → post-processing in Python

and errors against the exact solution.  Usage::

    python3 validation/poiseuille/run.py [--levels coarse medium fine]
                                         [--work DIR] [--results RESULTS.md]

Prints one JSON object per level, and the convergence table.
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

import gmsh                                                    # noqa: E402

from hexmesh import Assembly, PipeSpec, Session, Straight      # noqa: E402
from hexmesh.io.writers.openfoam_boundary import (             # noqa: E402
    apply_boundary_roles, roles_path,
)

OPENFOAM_RC = Path("/usr/share/openfoam/etc/bashrc")

# --- physics -----------------------------------------------------------------
D = 0.02                  # pipe diameter [m]
R = D / 2
NU = 1e-6                 # kinematic viscosity [m²/s]
RE = 100
U_MEAN = RE * NU / D      # 5e-3 m/s
LENGTH = 30 * D
X_A, X_B, X_MID = 15 * D, 25 * D, 20 * D       # measurement planes, profile
DP_EXACT = 32 * NU * U_MEAN * (X_B - X_A) / D**2   # kinematic, p/ρ
U_MAX_EXACT = 2 * U_MEAN
PLANES = {"planeA": X_A, "planeB": X_B, "planeM": X_MID}   # face zones (topoSet)

# --- refinement: every density parameter doubles per level (8× cells) -------
BASE = dict(nang=6, nrad=3, n_layers=(24, 16, 8))     # 15 D, 10 D, 5 D
LEVELS = {"coarse": 1, "medium": 2, "fine": 4}


def assembly(factor: int) -> Assembly:
    spec = PipeSpec(nang=BASE["nang"] * factor).core(
        "fluid", radius=R, nrad=BASE["nrad"] * factor)
    asm = Assembly(spec, position=[0, 0, 0], direction=[1, 0, 0], up=[0, 0, 1])
    # interfaces at the measurement planes, so p is sampled on mesh faces
    for length, n in zip((X_A, X_B - X_A, LENGTH - X_B), BASE["n_layers"]):
        asm.add(Straight(length, n_layers=n * factor))
    return asm


# --- OpenFOAM dictionaries ---------------------------------------------------

def _header(cls: str, obj: str, location: str = "") -> str:
    loc = f'    location    "{location}";\n' if location else ""
    return ("FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
            f"    class       {cls};\n{loc}    object      {obj};\n}}\n\n")


CONTROL = """application     simpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};
deltaT          1;
writeControl    timeStep;
writeInterval   {end_time};
purgeWrite      0;
writeFormat     ascii;
writePrecision  12;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable false;
"""

# pipeCyclic's schemes without the turbulence entries
SCHEMES = """ddtSchemes      { default steadyState; }
gradSchemes     { default Gauss linear; }
divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss limitedLinearV 1;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }
"""

# pipeCyclic's solvers and relaxation; residual control tightened (task 0020)
SOLUTION = """solvers
{
    p
    {
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-09;
        relTol          0.05;
    }
    U
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-10;
        relTol          0.1;
    }
}
SIMPLE
{
    nNonOrthogonalCorrectors 0;
    residualControl
    {
        p               1e-6;
        U               1e-7;
    }
}
relaxationFactors
{
    fields          { p 0.3; }
    equations       { U 0.7; }
}
"""

TOPOSET = """actions
(
{actions}
);
"""

ZONE = """    {{ name {n}Set; type faceSet; action new; source boxToFace;
      box ({x0} -1 -1) ({x1} 1 1); }}
    {{ name {n}; type faceZoneSet; action new; source setToFaceZone;
      faceSet {n}Set; }}"""

U0 = """dimensions      [0 1 -1 0 0 0 0];
internalField   uniform (0 0 0);
boundaryField
{{
    fluid_inlet  {{ type fixedValue; value uniform ({u} 0 0); }}
    fluid_outlet {{ type zeroGradient; }}
    fluid_wall   {{ type noSlip; }}
}}
"""

P0 = """dimensions      [0 2 -2 0 0 0 0];
internalField   uniform 0;
boundaryField
{
    fluid_inlet  { type zeroGradient; }
    fluid_outlet { type fixedValue; value uniform 0; }
    fluid_wall   { type zeroGradient; }
}
"""


def write_case(case: Path, end_time: int) -> None:
    for d in ("0", "constant", "system"):
        (case / d).mkdir(parents=True, exist_ok=True)
    files = {
        "system/controlDict": _header("dictionary", "controlDict", "system")
        + CONTROL.format(end_time=end_time),
        "system/fvSchemes": _header("dictionary", "fvSchemes", "system") + SCHEMES,
        "system/fvSolution": _header("dictionary", "fvSolution", "system") + SOLUTION,
        "system/topoSetDict": _header("dictionary", "topoSetDict", "system")
        + TOPOSET.format(actions="\n".join(
            ZONE.format(n=n, x0=x - 1e-3 * D, x1=x + 1e-3 * D)
            for n, x in PLANES.items())),
        "constant/transportProperties": _header("dictionary", "transportProperties",
                                                "constant")
        + f"transportModel  Newtonian;\nnu              {NU};\n",
        "constant/turbulenceProperties": _header("dictionary", "turbulenceProperties",
                                                 "constant")
        + "simulationType  laminar;\n",
        "0/U": _header("volVectorField", "U", "0") + U0.format(u=U_MEAN),
        "0/p": _header("volScalarField", "p", "0") + P0,
    }
    for name, text in files.items():
        (case / name).write_text(text)


def foam(cmd: str, case: Path, log: str) -> str:
    run = subprocess.run(["bash", "-c", f"source {OPENFOAM_RC} >/dev/null 2>&1; {cmd}"],
                         cwd=case, capture_output=True, text=True)
    (case / log).write_text(run.stdout + run.stderr)
    if run.returncode != 0:
        raise RuntimeError(f"{cmd} failed in {case} (see {log}):\n{run.stdout[-3000:]}"
                           f"{run.stderr[-2000:]}")
    return run.stdout


# --- post-processing ---------------------------------------------------------
#
# In Python, from the ASCII case files: function objects (controlDict
# ``functions`` and ``postProcess -func``) abort on this OpenFOAM build
# (docs/integrations/openfoam.md, "function objects").

_NUM = r"[-+0-9.eE]+"


def _list_body(text: str, start: int = 0) -> tuple[int, str]:
    """``N ( … )`` at or after *start*: (N, body between the parentheses)."""
    m = re.compile(r"(\d+)\s*\(").search(text, start)
    n, i, depth = int(m.group(1)), m.end(), 1
    j = i
    while depth:
        depth += {"(": 1, ")": -1}.get(text[j], 0)
        j += 1
    return n, text[i:j - 1]


def _strip_header(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*", "", text)
    return text[text.index("}", text.index("FoamFile")) + 1:]


def read_points(path: Path):
    import numpy as np
    n, body = _list_body(_strip_header(path.read_text()))
    return np.array(re.findall(_NUM, body), float).reshape(n, 3)


def read_faces(path: Path) -> list[list[int]]:
    n, body = _list_body(_strip_header(path.read_text()))
    faces = [[int(v) for v in f.split()] for f in re.findall(r"\d+\(([^)]*)\)", body)]
    assert len(faces) == n
    return faces


def read_labels(path: Path):
    import numpy as np
    n, body = _list_body(_strip_header(path.read_text()))
    return np.array(body.split(), int)


def read_zone(path: Path, name: str):
    import numpy as np
    text = _strip_header(path.read_text())
    i = re.search(rf"^{name}\s*\{{", text, re.M).end()
    _, body = _list_body(text, text.index("faceLabels", i))
    return np.array(body.split(), int)


def read_internal(path: Path, ncomp: int):
    import numpy as np
    text = _strip_header(path.read_text())
    i = text.index("internalField")
    n, body = _list_body(text, i)
    return np.array(re.findall(_NUM, body), float).reshape(n, ncomp) if ncomp > 1 \
        else np.array(body.split(), float)


def read_patch_values(path: Path, patch: str):
    import numpy as np
    text = _strip_header(path.read_text())
    i = re.search(rf"^\s*{patch}\s*\{{", text[text.index("boundaryField"):], re.M)
    j = text.index("boundaryField") + i.end()
    k = text.index("value", j)
    if text[k:].split(None, 2)[1] == "uniform":
        raise ValueError(f"{patch}: uniform value, expected a list")
    _, body = _list_body(text, k)
    return np.array(body.split(), float)


def results(case: Path) -> dict:
    import numpy as np
    mesh = case / "constant/polyMesh"
    pts, faces = read_points(mesh / "points"), read_faces(mesh / "faces")
    owner, neigh = read_labels(mesh / "owner"), read_labels(mesh / "neighbour")
    t = _latest_time(case)
    p = read_internal(t / "p", 1)
    U = read_internal(t / "U", 3)

    def face_geom(ids):
        c, a = [], []
        for f in ids:
            q = pts[faces[f]]
            c.append(q.mean(axis=0))
            a.append(0.5 * np.linalg.norm(np.cross(q[2] - q[0], q[3] - q[1])))
        return np.array(c), np.array(a)

    def face_values(ids, field):
        # linear interpolation; the axial spacing is uniform (one cell
        # length in every fitting), so the weights are exactly 1/2
        return 0.5 * (field[owner[ids]] + field[neigh[ids]])

    p_avg = {}
    for name in ("planeA", "planeB"):
        ids = read_zone(mesh / "faceZones", name)
        _, a = face_geom(ids)
        p_avg[name] = float(np.sum(a * face_values(ids, p)) / a.sum())
    dp = p_avg["planeA"] - p_avg["planeB"]

    ids = read_zone(mesh / "faceZones", "planeM")
    c, a = face_geom(ids)
    u = face_values(ids, U)[:, 0]
    r = np.hypot(c[:, 1], c[:, 2])
    exact = 2 * U_MEAN * (1 - (r / R) ** 2)
    # u_max is the centreline value.  No face centre lies on the axis (the
    # nearest four are ~0.12 R off it at the coarse level, a 1.5 % offset in
    # the exact profile), so fit u = c0 - c2 r² to the faces within R/3 and
    # take c0.  The four-face mean, and the exact profile sampled at the
    # same faces, are reported too.
    fit = r < R / 3
    c0, _ = np.linalg.lstsq(np.column_stack([np.ones(fit.sum()), r[fit] ** 2]),
                            u[fit], rcond=None)[0]
    u_max = float(c0)
    near = np.argsort(r)[:4]
    u_max_sampled_exact = float(exact[near].mean())
    q_in = -float(read_patch_values(t / "phi", "fluid_inlet").sum())
    q_out = float(read_patch_values(t / "phi", "fluid_outlet").sum())
    q_exact = U_MEAN * math.pi * R**2
    return {
        "dp": dp, "dp_err": abs(dp - DP_EXACT) / DP_EXACT,
        "u_max": u_max, "u_max_err": abs(u_max - U_MAX_EXACT) / U_MAX_EXACT,
        "u_max_fit_faces": int(fit.sum()),
        "u_near_axis": float(u[near].mean()),
        "u_max_axis_offset": float(r[near].mean()),
        "u_max_sampling_err": abs(u_max_sampled_exact - U_MAX_EXACT) / U_MAX_EXACT,
        "q_in": q_in, "q_out": q_out,
        "mass_err": abs(q_out - q_in) / q_in,
        "q_err": abs(q_in - q_exact) / q_exact,
        "q_plane_err": abs(float(np.sum(a * u)) - q_exact) / q_exact,
        "profile_err": float(np.max(np.abs(u - exact)) / U_MAX_EXACT),
        "profile": sorted(zip(r.tolist(), u.tolist())),
    }


def _latest_time(case: Path) -> Path:
    times = [d for d in case.iterdir() if d.is_dir() and re.fullmatch(r"[\d.e+-]+", d.name)]
    return max(times, key=lambda d: float(d.name))


def run_level(name: str, factor: int, work: Path, end_time: int) -> dict:
    case = work / name
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    with Session(f"poiseuille-{name}"):
        asm = assembly(factor)
        cells = asm.cell_count()
        print(f"[{name}] predicted cells: {cells}", flush=True)
        msh = case / "pipe.msh"
        asm.write_openfoam(msh)
        sj = asm.check_quality("scaled_jacobian").worst
    write_case(case, end_time)
    foam(f"gmshToFoam {msh.name}", case, "log.gmshToFoam")
    retyped = apply_boundary_roles(case, roles_path(msh))
    check = foam("checkMesh", case, "log.checkMesh")
    foam("topoSet", case, "log.topoSet")
    solve = foam("simpleFoam", case, "log.simpleFoam")
    m = re.search(r"SIMPLE solution converged in (\d+) iterations", solve)
    times = re.findall(r"^Time = (\d+)$", solve, re.M)
    out = {
        "level": name, "factor": factor, "cells": cells,
        "cells_foam": int(re.search(r"cells:\s+(\d+)", check).group(1)),
        "mesh_ok": "Mesh OK." in check, "retyped": retyped,
        "patches": sorted(re.findall(r"^\s+(fluid_\w+)\s*$",
                                     (case / "constant/polyMesh/boundary").read_text(), re.M)),
        "min_scaled_jacobian": sj,
        "max_non_orthogonality": float(
            re.search(r"non-orthogonality Max: ([\d.e+-]+)", check).group(1)),
        "max_skewness": float(re.search(r"Max skewness = ([\d.e+-]+)", check).group(1)),
        "converged": m is not None,
        "iterations": int(m.group(1)) if m else int(times[-1]),
    }
    out.update(results(case))
    return out


def orders(rows: list[dict], key: str) -> list[float]:
    return [math.log2(a[key] / b[key]) for a, b in zip(rows, rows[1:])]


def versions() -> dict:
    git = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE,
                         capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "hexmesh"], cwd=HERE,
                           capture_output=True, text=True).stdout.strip()
    foam_v = subprocess.run(["bash", "-c", f"source {OPENFOAM_RC} >/dev/null 2>&1; "
                             "echo $WM_PROJECT_VERSION"],
                            capture_output=True, text=True).stdout.strip()
    return {"hexmesh": git + ("+local" if dirty else ""), "gmsh": gmsh.__version__,
            "openfoam": foam_v, "date": datetime.date.today().isoformat()}


def table(rows: list[dict]) -> str:
    lines = ["| Level | Cells | min SJ | max non-orth. (°) | max skewness | Iterations "
             "| Δp (m²/s²) | e(Δp) | u_max (m/s) | e(u_max) | mass balance |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r['level']} | {r['cells']} | {r['min_scaled_jacobian']:.3f} "
            f"| {r['max_non_orthogonality']:.1f} | {r['max_skewness']:.3f} "
            f"| {r['iterations']} | {r['dp']:.6e} | {r['dp_err']:.3%} "
            f"| {r['u_max']:.6e} | {r['u_max_err']:.3%} | {r['mass_err']:.1e} |")
    return "\n".join(lines)


def main(argv=None) -> list[dict]:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--levels", nargs="+", default=list(LEVELS), choices=list(LEVELS))
    ap.add_argument("--work", type=Path, default=HERE / "work")
    ap.add_argument("--end-time", type=int, default=20000)
    ap.add_argument("--json", type=Path, help="write all results as JSON")
    args = ap.parse_args(argv)
    rows = []
    for name in args.levels:
        r = run_level(name, LEVELS[name], args.work, args.end_time)
        print(json.dumps({k: v for k, v in r.items() if k != "profile"}), flush=True)
        rows.append(r)
    print(f"\nexact: dp = {DP_EXACT:.6e}, u_max = {U_MAX_EXACT:.6e}\n")
    print(table(rows))
    if len(rows) > 1:
        print(f"\nobserved order, dp:    {orders(rows, 'dp_err')}")
        print(f"observed order, u_max: {orders(rows, 'u_max_err')}")
    if args.json:
        args.json.write_text(json.dumps({"versions": versions(), "levels": rows,
                                         "exact": {"dp": DP_EXACT, "u_max": U_MAX_EXACT}},
                                        indent=1))
    return rows


if __name__ == "__main__":
    main()
