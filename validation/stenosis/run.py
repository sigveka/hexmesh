#!/usr/bin/env python3
"""
Smooth cosine constriction, steady laminar flow at Re = 500 (decision 0012,
docs/tasks/0032), against the DNS of Varghese, Frankel & Fischer (2007),
Part 1 [varghese_and_frankel_etal_2007], Purdue database.

    hexmesh Assembly (profiled Reducer) → refined(k) → write_openfoam
    → gmshToFoam → apply_boundary_roles → checkMesh → parabolic inlet
    → simpleFoam (optionally in parallel) → post-processing in Python

Three levels, every density doubled per level (8× cells).  Compared with
the DNS: centreline axial velocity at x/D = −2 … 15, and the reattachment
point of the wall shear stress downstream of the throat; Richardson
extrapolation and observed orders [celik_and_ghia_etal_2008].  Usage::

    python3 validation/stenosis/run.py [--levels coarse medium fine]
        [--np N] [--end-time N] [--reference vel.dat | --no-reference]
        [--work DIR] [--json FILE]

The reference is the database's Re = 500 axisymmetric steady file
(``Axi_stdy/Re500/vel.dat``).  It carries no licence, so it is not in the
repository: without ``--reference`` it is downloaded into the work
directory (git-ignored) once; ``--no-reference`` skips the comparison.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

import sys                                                     # noqa: E402
sys.path.insert(0, str(ROOT))

from hexmesh import Assembly, PipeSpec, Reducer, Session, Straight   # noqa: E402
from hexmesh.io.writers.openfoam_boundary import (             # noqa: E402
    apply_boundary_roles, roles_path,
)
from hexmesh.study import openfoam as of                       # noqa: E402


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# The Poiseuille case's simpleFoam dictionaries, Richardson analysis and
# version record (task 0020); OpenFOAM itself through hexmesh.study.openfoam.
pois = _load("poiseuille_run", "validation/poiseuille/run.py")

REFERENCE_URL = ("https://engineering.purdue.edu/CFDLAB/DNS_stenoticflow_database/"
                 "Axi_stdy/Re500/vel.dat")

# --- physics (dimensionless, as the DNS: D = 1) ------------------------------
D = 1.0
R = D / 2
U_MEAN = 1.0              # mean inlet velocity; the DNS uses 0.5 (its note)
RE = 500
NU = U_MEAN * D / RE
S0 = 0.25                 # 75 % area reduction: throat radius D/4
L_STEN = 2 * D            # eq. 2.1 of the paper: L = 2D
X_IN, X_OUT = -3 * D, 16 * D   # domain: 3 D upstream, 16 D downstream (p. 5)
X_SPLIT = 13 * D          # downstream: graded up to here, uniform after
DNS_U = 0.5               # the database's normalising velocity
SLAB_GAP = 1e-3 * D       # below the finest axial cell (0.014 D)

# --- the coarse level; refined(k) doubles every count -----------------------
# Both runs next to the constriction are graded to meet its axial spacing,
# L_STEN / sten, so no cell length jumps there.
BASE = dict(nang=6, nrad=3, up=16, sten=36, near=80, far=10)
LEVELS = {"coarse": 1, "medium": 2, "fine": 4}


def growth(first: float, length: float, n: int) -> float:
    """The ratio q of consecutive cells whose first is *first* and whose *n*
    cells fill *length* (bisection)."""
    lo, hi = 1.0 + 1e-12, 2.0
    for _ in range(200):
        q = 0.5 * (lo + hi)
        lo, hi = (q, hi) if first * (q ** n - 1) / (q - 1) < length else (lo, q)
    return 0.5 * (lo + hi)


def assembly(k: int = 1) -> Assembly:
    spec = PipeSpec(nang=BASE["nang"]).core("fluid", radius=R, nrad=BASE["nrad"])
    h = L_STEN / BASE["sten"]
    up, near = -L_STEN / 2 - X_IN, X_SPLIT - L_STEN / 2
    asm = Assembly(spec, position=[X_IN, 0, 0], direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(up, n_layers=BASE["up"],
                     axial_grading=1 / growth(h, up, BASE["up"])))
    asm.add(Reducer(spec, L_STEN, n_layers=BASE["sten"], profile=("cosine", S0)))
    asm.add(Straight(near, n_layers=BASE["near"],
                     axial_grading=growth(h, near, BASE["near"])))
    asm.add(Straight(X_OUT - X_SPLIT, n_layers=BASE["far"]))
    return asm if k == 1 else asm.refined(k)


def meshes():
    """(label, caption, build) per mesh shown in README.md
    (``docs/gallery/build.py --validation``)."""
    return [(name, f"{name}: nang {BASE['nang'] * k}, nrad {BASE['nrad'] * k}, "
                   f"{sum(BASE[n] for n in ('up', 'sten', 'near', 'far')) * k} axial layers",
             lambda k=k: assembly(k)) for name, k in LEVELS.items()]


def radius(x):
    """R(x) of the constriction (RESEARCH §7.3)."""
    x = np.asarray(x, float)
    r = R * (1 - S0 * (1 + np.cos(2 * np.pi * x / L_STEN)))
    return np.where(np.abs(x) <= L_STEN / 2, r, R)


# --- case --------------------------------------------------------------------

U0 = """dimensions      [0 1 -1 0 0 0 0];
internalField   uniform (0 0 0);
boundaryField
{
    fluid_inlet  { type fixedValue; value uniform (0 0 0); }
    fluid_outlet { type zeroGradient; }
    fluid_wall   { type noSlip; }
}
"""


def write_case(case: Path, end_time: int, n_proc: int) -> None:
    """simpleFoam, laminar, with the Poiseuille case's schemes and solvers
    (the inlet value is set by ``parabolic_inlet`` after conversion)."""
    for d in ("0", "constant", "system"):
        (case / d).mkdir(parents=True, exist_ok=True)
    files = {
        "system/controlDict": of.header("dictionary", "controlDict", "system")
        + pois.CONTROL.format(end_time=end_time),
        "system/fvSchemes": of.header("dictionary", "fvSchemes", "system") + pois.SCHEMES,
        "system/fvSolution": of.header("dictionary", "fvSolution", "system") + pois.SOLUTION,
        "constant/transportProperties": of.header("dictionary", "transportProperties",
                                                  "constant")
        + f"transportModel  Newtonian;\nnu              {NU};\n",
        "constant/turbulenceProperties": of.header("dictionary", "turbulenceProperties",
                                                   "constant")
        + "simulationType  laminar;\n",
        "0/U": of.header("volVectorField", "U", "0") + U0,
        "0/p": of.header("volScalarField", "p", "0") + pois.P0,
    }
    if n_proc > 1:
        files["system/decomposeParDict"] = (
            of.header("dictionary", "decomposeParDict", "system")
            # slabs along the pipe: this build's Scotch is a dummy
            # (docs/integrations/openfoam.md)
            + f"numberOfSubdomains {n_proc};\nmethod          simple;\n"
            f"simpleCoeffs {{ n ({n_proc} 1 1); delta 0.001; }}\n")
    for name, text in files.items():
        (case / name).write_text(text)


def parabolic_inlet(case: Path) -> float:
    """Replace the uniform inlet value in 0/U by a parabolic profile at the
    inlet face centres, scaled so its discrete flow rate is U_MEAN · A_mesh.
    Returns the scale (1 + the discrete-flow correction)."""
    mesh = case / "constant/polyMesh"
    pts, faces = of.read_points(mesh / "points"), of.read_faces(mesh / "faces")
    ids = of.read_patch_faces(mesh / "boundary", "fluid_inlet")
    c, sf = of.face_geometry(pts, [faces[i] for i in ids])
    a = np.linalg.norm(sf, axis=1)
    r = np.hypot(c[:, 1], c[:, 2])
    u = 2 * U_MEAN * (1 - (r / R) ** 2)
    scale = U_MEAN * a.sum() / float((u * a).sum())
    u *= scale
    values = "\n".join(f"({v:.12g} 0 0)" for v in u)
    path = case / "0/U"
    text = path.read_text()
    text = re.sub(r"fluid_inlet\s*\{[^}]*\}",
                  f"fluid_inlet  {{ type fixedValue; value nonuniform List<vector>\n"
                  f"{len(u)}\n(\n{values}\n); }}", text)
    path.write_text(text)
    return scale


# --- post-processing ---------------------------------------------------------

def results(case: Path) -> dict:
    mesh = case / "constant/polyMesh"
    pts, faces = of.read_points(mesh / "points"), of.read_faces(mesh / "faces")
    owner, neigh = of.read_labels(mesh / "owner"), of.read_labels(mesh / "neighbour")
    t = of.latest_time(case)
    U = of.read_internal(t / "U", 3)
    n_cells = len(U)
    fc, sf = of.face_geometry(pts, faces)
    cc, _ = of.cell_geometry(fc, sf, owner, neigh, n_cells)

    # centreline: per axial slab, u = c0 + c2 r² fitted to the cells within
    # 0.35 R(x) of the axis (no cell centre lies on it).  Slabs are the
    # clusters of those cells' x, split at gaps above SLAB_GAP: in a
    # tapering slab a cell's centroid x shifts with its radius, so exact
    # x values don't group a slab.
    x, r = cc[:, 0], np.hypot(cc[:, 1], cc[:, 2])
    near = np.nonzero(r < 0.35 * radius(x))[0]
    near = near[np.argsort(x[near], kind="stable")]
    cut = np.nonzero(np.diff(x[near]) > SLAB_GAP)[0] + 1
    xs, uc = [], []
    for cells in np.split(near, cut):
        rr, uu = r[cells], U[cells, 0]
        if np.ptp(rr) > 1e-9 * R:
            c0 = np.linalg.lstsq(np.column_stack([np.ones(len(rr)), rr ** 2]), uu,
                                 rcond=None)[0][0]
        else:
            c0 = uu.mean()
        xs.append(float(x[cells].mean()))
        uc.append(float(c0))
    xs, uc = np.array(xs), np.array(uc)

    # wall shear stress (kinematic), axial sense: ν · u_t / d from the wall
    # cell, u_t the velocity's component along the wall's axial tangent
    wall = of.read_patch_faces(mesh / "boundary", "fluid_wall")
    cell = owner[wall]
    n = sf[wall] / np.linalg.norm(sf[wall], axis=1)[:, None]      # outward
    d = np.einsum("ij,ij->i", fc[wall] - cc[cell], n)
    ex = np.array([1.0, 0.0, 0.0])
    tang = ex - n[:, 0:1] * n
    tang /= np.linalg.norm(tang, axis=1)[:, None]
    tau = NU * np.einsum("ij,ij->i", U[cell], tang) / d
    wx = np.round(fc[wall, 0] / 1e-6).astype(np.int64)
    order = np.argsort(wx, kind="stable")
    _, starts = np.unique(wx[order], return_index=True)
    tx = np.array([fc[wall[g], 0].mean() for g in np.split(order, starts[1:])])
    tw = np.array([tau[g].mean() for g in np.split(order, starts[1:])])
    sep, att = crossings(tx, tw)

    q_in = -float(of.read_patch_values(t / "phi", "fluid_inlet").sum())
    q_out = float(of.read_patch_values(t / "phi", "fluid_outlet").sum())
    peak = int(np.argmax(uc))
    return {
        "centreline": list(zip(xs.tolist(), uc.tolist())),
        "wall_shear": list(zip(tx.tolist(), tw.tolist())),
        "u_peak": float(uc[peak]), "x_peak": float(xs[peak]),
        "x_separation": sep, "x_reattachment": att,
        "q_in": q_in, "q_out": q_out, "mass_err": abs(q_out - q_in) / q_in,
    }


def crossings(x: np.ndarray, tau: np.ndarray) -> tuple[float | None, float | None]:
    """Separation (first + → − downstream of the throat) and reattachment
    (the last − → + after it), linearly interpolated."""
    def zero(i):
        return float(x[i] - tau[i] * (x[i + 1] - x[i]) / (tau[i + 1] - tau[i]))
    down = np.nonzero(x > 0)[0]
    s = [i for i in down[:-1] if tau[i] > 0 >= tau[i + 1]]
    if not s:
        return None, None
    a = [i for i in range(s[0], len(x) - 1) if tau[i] < 0 <= tau[i + 1]]
    return zero(s[0]), (zero(a[-1]) if a else None)


# --- reference ---------------------------------------------------------------

def read_reference(path: Path) -> dict:
    """The database's Tecplot file: per station x/D, rows (r, u, v, w) on
    D = 1, axial velocity w normalised by 0.5."""
    zones: dict[float, list] = {}
    cur = None
    for line in path.read_text().splitlines():
        m = re.search(r"Z =\s*([-+\d.Ee]+)", line)
        if m:
            cur = float(m.group(1))
            zones[cur] = []
        elif cur is not None and line.strip() and "VARIABLES" not in line:
            zones[cur].append([float(v) for v in line.split()])
    out = {}
    for z, rows in zones.items():
        a = np.array(rows)
        out[z] = {"centre": float(a[np.argmin(np.abs(a[:, 0])), 3]) / DNS_U,
                  "r": a[:, 0].tolist(), "w": (a[:, 3] / DNS_U).tolist()}
    return out


def reference_reattachment(ref: dict, r_probe: float = 0.48) -> float:
    """x/D where the axial velocity at *r_probe* (0.02 D from the wall, the
    database's last point before it) turns positive past the throat: the
    stations are 1 D apart, so linear interpolation between them."""
    zs = sorted(z for z in ref if z > 0)
    w = [float(np.interp(r_probe, ref[z]["r"], ref[z]["w"])) for z in zs]
    for i in range(len(zs) - 1, 0, -1):
        if w[i - 1] < 0 <= w[i]:
            return zs[i - 1] - w[i - 1] * (zs[i] - zs[i - 1]) / (w[i] - w[i - 1])
    raise ValueError("no reattachment in the reference")


def compare(row: dict, ref: dict) -> dict:
    xs, uc = np.array(row["centreline"]).T
    zs = np.array(sorted(ref))
    dns = np.array([ref[z]["centre"] for z in zs])
    ours = np.interp(zs, xs, uc)
    peak = float(dns.max())
    err = (ours - dns) / peak
    i = int(np.argmax(np.abs(err)))
    return {"stations": zs.tolist(), "dns_centre": dns.tolist(), "centre": ours.tolist(),
            "centre_err_peak": err.tolist(), "max_centre_err": float(abs(err[i])),
            "max_centre_err_x": float(zs[i]), "dns_peak": peak}


# --- driver ------------------------------------------------------------------

def run_level(name: str, k: int, work: Path, end_time: int, n_proc: int) -> dict:
    case = work / name
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    with Session(f"stenosis-{name}"):
        asm = assembly(k)
        cells = asm.cell_count()
        print(f"[{name}] predicted cells: {cells}", flush=True)
        msh = case / "stenosis.msh"
        asm.write_openfoam(msh)
        sj = asm.check_quality("scaled_jacobian").worst
    write_case(case, end_time, n_proc)
    of.foam(f"gmshToFoam {msh.name}", case, "log.gmshToFoam")
    retyped = apply_boundary_roles(case, roles_path(msh))
    check = of.foam("checkMesh", case, "log.checkMesh")
    scale = parabolic_inlet(case)
    if n_proc > 1:
        of.foam("decomposePar -force", case, "log.decomposePar")
        solve = of.foam(f"mpirun -np {n_proc} simpleFoam -parallel", case, "log.simpleFoam")
        of.foam("reconstructPar -latestTime", case, "log.reconstructPar")
    else:
        solve = of.foam("simpleFoam", case, "log.simpleFoam")
    m = re.search(r"SIMPLE solution converged in (\d+) iterations", solve)
    hist = residuals(solve)
    times = re.findall(r"^Time = (\d+)$", solve, re.M)
    out = {
        "level": name, "factor": k, "cells": cells,
        "cells_foam": int(re.search(r"cells:\s+(\d+)", check).group(1)),
        "mesh_ok": "Mesh OK." in check, "retyped": retyped,
        "min_scaled_jacobian": sj,
        "max_non_orthogonality": float(
            re.search(r"non-orthogonality Max: ([\d.e+-]+)", check).group(1)),
        "max_skewness": float(re.search(r"Max skewness = ([\d.e+-]+)", check).group(1)),
        "inlet_scale": scale, "n_proc": n_proc,
        "converged": m is not None,
        "iterations": int(m.group(1)) if m else int(times[-1]),
        "exec_time": float(re.findall(r"ExecutionTime = ([\d.e+-]+) s", solve)[-1]),
        "final_residuals": {f: v[-1] for f, v in hist.items()},
        "residual_history": {f: v[::max(1, len(v) // 200)] for f, v in hist.items()},
    }
    out.update(results(case))
    return out


def residuals(log: str) -> dict[str, list[float]]:
    """Initial residual per SIMPLE iteration of p and each U component
    (the first solve of each field in an iteration)."""
    out: dict[str, list[float]] = {}
    for block in re.split(r"^Time = \d+$", log, flags=re.M)[1:]:
        seen = set()
        for f, v in re.findall(r"Solving for (\w+), Initial residual = ([\d.e+-]+)", block):
            if f not in seen:
                seen.add(f)
                out.setdefault(f, []).append(float(v))
    return out


def reference(path: Path | None, work: Path) -> Path:
    """The database file: *path*, or downloaded once into *work*."""
    if path is not None:
        return path
    local = work / "reference" / "re500_vel.dat"
    if not local.exists():
        local.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(REFERENCE_URL, timeout=60) as r:
            local.write_bytes(r.read())
    return local


def table(rows: list[dict]) -> str:
    lines = ["| Level | Cells | Mesh OK | min SJ | max non-orth. (°) | max skewness "
             "| Iterations | mass balance | u_peak / U | x_sep / D | x_reatt / D "
             "| max centreline err. (of DNS peak) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        f = (lambda v: "—" if v is None else f"{v:.3f}")
        cmp = r.get("compare")
        centre = ("—" if not cmp else
                  f"{cmp['max_centre_err']:.2%} at x = {cmp['max_centre_err_x']:g}")
        lines.append(
            f"| {r['level']} | {r['cells']} | {r['mesh_ok']} | {r['min_scaled_jacobian']:.3f} "
            f"| {r['max_non_orthogonality']:.1f} | {r['max_skewness']:.3f} "
            f"| {r['iterations']}{'' if r['converged'] else ' (not converged)'} "
            f"| {r['mass_err']:.1e} | {r['u_peak']:.4f} | {f(r['x_separation'])} "
            f"| {f(r['x_reattachment'])} "
            f"| {centre} |")
    return "\n".join(lines)


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--levels", nargs="+", default=list(LEVELS), choices=list(LEVELS))
    ap.add_argument("--reference", type=Path,
                    help="the database's Re = 500 vel.dat (default: download it)")
    ap.add_argument("--no-reference", action="store_true", help="skip the comparison")
    ap.add_argument("--work", type=Path, default=HERE / "work")
    ap.add_argument("--end-time", type=int, default=20000)
    ap.add_argument("--np", type=int, default=1, dest="n_proc",
                    help="MPI processes for simpleFoam (levels other than coarse)")
    ap.add_argument("--json", type=Path, help="write all results as JSON")
    args = ap.parse_args(argv)
    ref = (None if args.no_reference
           else read_reference(reference(args.reference, args.work)))
    ref_att = reference_reattachment(ref) if ref else None
    rows = []
    for name in args.levels:
        n = 1 if name == "coarse" else args.n_proc
        r = run_level(name, LEVELS[name], args.work, args.end_time, n)
        if ref:
            r["compare"] = compare(r, ref)
            r["reattachment_err"] = ((r["x_reattachment"] - ref_att) / ref_att
                                     if r["x_reattachment"] is not None else None)
        print(json.dumps({k: v for k, v in r.items()
                          if k not in ("centreline", "wall_shear", "compare")}), flush=True)
        rows.append(r)
    if ref:
        print(f"\nDNS: peak centreline u/U = {max(v['centre'] for v in ref.values()):.4f}, "
              f"reattachment x/D = {ref_att:.3f}\n")
    print(table(rows))
    rich = {}
    if len(rows) == 3 and all(r["x_reattachment"] is not None for r in rows):
        for key in ("u_peak", "x_reattachment", "x_separation"):
            try:
                rich[key] = pois.richardson(*(r[key] for r in rows))
            except (ValueError, ZeroDivisionError) as e:
                rich[key] = {"error": str(e)}
        print("\n" + json.dumps(rich, indent=1))
    if args.json:
        args.json.write_text(json.dumps({
            "versions": pois.versions(), "levels": rows, "richardson": rich,
            "reference": None if not ref else {
                "reattachment": ref_att,
                "centre": {str(z): v["centre"] for z, v in sorted(ref.items())}},
        }, indent=1))
    return {"levels": rows, "richardson": rich}


if __name__ == "__main__":
    main()
