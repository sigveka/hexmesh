#!/usr/bin/env python3
"""
Smooth cosine constriction, steady laminar flow at Re = 500 (decision 0012,
docs/tasks/0032), against the DNS of Varghese, Frankel & Fischer (2007),
Part 1 [varghese_and_frankel_etal_2007], Purdue database.

    hexmesh Assembly (profiled Reducer) → refined(k) → write_openfoam
    → gmshToFoam → apply_boundary_roles → checkMesh → parabolic inlet
    → pimpleFoam to a steady state (optionally in parallel)
    → post-processing in Python

``simpleFoam`` doesn't converge on this case (its iteration is unstable
around the steady state), so the flow is marched in time from rest until
it stops changing: the centreline and both reattachment measures move by
less than 0.1 % over 5 time units (task 0032, design answer to Q1).

Levels k = 2, 3, 4 of ``refined(k)``; k = 1 has no steady axisymmetric
state.  Compared with the DNS: centreline axial velocity at x/D = −2 … 15,
and the reattachment point, both where the wall shear stress vanishes and
where the axial velocity at r = 0.48 D turns positive (the database's
measure).  Richardson extrapolation at the non-constant ratios 4/3 and 3/2
[celik_and_ghia_etal_2008].  Usage::

    python3 validation/stenosis/run.py [--levels k2 k3 k4] [--np N]
        [--end-time T] [--reference vel.dat | --no-reference]
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
import math
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
R_PROBE = 0.48 * D        # the database's last point before the wall
# Centreline fit window, a fraction of R(x).  Past the throat the jet has
# a flat core and a shear layer, so a parabola over a wide window biases
# the axis value high: 0.35 R gave +0.06 U at x = 2 D on k = 3; 0.2 R and
# 0.12 R agree to 0.004 U (task 0032).
CENTRE_WINDOW = 0.2
CHUNK = 5.0               # time units between steadiness checks
STEADY_TOL = 1e-3         # 0.1 % change over CHUNK: steady

# --- the coarse level; refined(k) doubles every count -----------------------
# Both runs next to the constriction are graded to meet its axial spacing,
# L_STEN / sten, so no cell length jumps there.
BASE = dict(nang=6, nrad=3, up=16, sten=36, near=80, far=10)
# k = 1 ("coarse") has no steady axisymmetric state; it stays for the
# pipeline test (tests/test_validation.py).
LEVELS = {"coarse": 1, "k2": 2, "k3": 3, "k4": 4}
DEFAULT_LEVELS = ["k2", "k3", "k4"]


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
             lambda k=k: assembly(k))
            for name, k in ((n, LEVELS[n]) for n in DEFAULT_LEVELS)]


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


CONTROL = """application     pimpleFoam;
startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         {end_time:g};
deltaT          {delta_t:g};
adjustTimeStep  yes;
maxCo           0.8;
writeControl    adjustableRunTime;
writeInterval   {chunk:g};
purgeWrite      2;
writeFormat     ascii;
writePrecision  12;
writeCompression off;
timeFormat      general;
timePrecision   8;
runTimeModifiable false;
"""

# the Poiseuille case's schemes, in time (Euler) and without `bounded`
SCHEMES = pois.SCHEMES.replace("default steadyState;", "default Euler;").replace(
    "bounded Gauss", "Gauss")

# the Poiseuille case's solvers for the final correctors too; no relaxation
SOLUTION = """solvers
{
    "(p|pFinal)"
    {
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-09;
        relTol          0.05;
    }
    "(U|UFinal)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-10;
        relTol          0.1;
    }
}
PIMPLE
{
    nOuterCorrectors 1;
    nCorrectors     2;
    nNonOrthogonalCorrectors 0;
}
"""


def write_case(case: Path, end_time: float, n_proc: int, delta_t: float) -> None:
    """pimpleFoam, laminar, from rest (the inlet value is set by
    ``parabolic_inlet`` after conversion)."""
    for d in ("0", "constant", "system"):
        (case / d).mkdir(parents=True, exist_ok=True)
    files = {
        "system/controlDict": of.header("dictionary", "controlDict", "system")
        + CONTROL.format(end_time=end_time, delta_t=delta_t, chunk=CHUNK),
        "system/fvSchemes": of.header("dictionary", "fvSchemes", "system") + SCHEMES,
        "system/fvSolution": of.header("dictionary", "fvSolution", "system") + SOLUTION,
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


def set_end_time(case: Path, end_time: float) -> None:
    path = case / "system/controlDict"
    path.write_text(re.sub(r"^endTime\s+\S+;", f"endTime         {end_time:g};",
                           path.read_text(), flags=re.M))


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

def geometry(case: Path) -> dict:
    """What the post-processing needs from the mesh, computed once per case
    (the k = 4 mesh has about a million cells)."""
    mesh = case / "constant/polyMesh"
    pts, faces = of.read_points(mesh / "points"), of.read_faces(mesh / "faces")
    owner, neigh = of.read_labels(mesh / "owner"), of.read_labels(mesh / "neighbour")
    n_cells = int(owner.max()) + 1
    fc, sf = of.face_geometry(pts, faces)
    cc, _ = of.cell_geometry(fc, sf, owner, neigh, n_cells)
    x, r = cc[:, 0], np.hypot(cc[:, 1], cc[:, 2])

    # centreline slabs: the cells within CENTRE_WINDOW · R(x) of the axis, clustered
    # by x and split at gaps above SLAB_GAP (in a tapering slab a cell's
    # centroid x shifts with its radius, so exact x values don't group it)
    near = np.nonzero(r < CENTRE_WINDOW * radius(x))[0]
    near = near[np.argsort(x[near], kind="stable")]
    centre = np.split(near, np.nonzero(np.diff(x[near]) > SLAB_GAP)[0] + 1)

    # near-wall probe slabs, in the straight pipe past the constriction
    # (planar slabs there): the cells in the outer quarter of the radius
    outer = np.nonzero((x > L_STEN / 2) & (r > 0.75 * R))[0]
    outer = outer[np.argsort(x[outer], kind="stable")]
    probe = np.split(outer, np.nonzero(np.diff(x[outer]) > SLAB_GAP)[0] + 1)

    # wall shear stress: per wall face, the axial tangent and the distance
    # from the wall cell's centre; faces grouped by x
    wall = of.read_patch_faces(mesh / "boundary", "fluid_wall")
    cell = owner[wall]
    n = sf[wall] / np.linalg.norm(sf[wall], axis=1)[:, None]      # outward
    d = np.einsum("ij,ij->i", fc[wall] - cc[cell], n)
    tang = np.array([1.0, 0.0, 0.0]) - n[:, 0:1] * n
    tang /= np.linalg.norm(tang, axis=1)[:, None]
    wx = np.round(fc[wall, 0] / 1e-6).astype(np.int64)
    order = np.argsort(wx, kind="stable")
    _, starts = np.unique(wx[order], return_index=True)
    groups = np.split(order, starts[1:])
    return {"n_cells": n_cells, "x": x, "r": r, "centre": centre, "probe": probe,
            "wall_cell": cell, "wall_tang": tang, "wall_d": d, "wall_groups": groups,
            "wall_x": np.array([fc[wall[g], 0].mean() for g in groups])}


def results(geo: dict, t: Path) -> dict:
    """The flow quantities at time directory *t*."""
    U = of.read_internal(t / "U", 3)
    x, r = geo["x"], geo["r"]

    # centreline: per slab, u = c0 + c2 r² fitted near the axis (no cell
    # centre lies on it); c0 is the centreline value
    xs, uc = [], []
    for cells in geo["centre"]:
        rr, uu = r[cells], U[cells, 0]
        if np.ptp(rr) > 1e-9 * R:
            c0 = np.linalg.lstsq(np.column_stack([np.ones(len(rr)), rr ** 2]), uu,
                                 rcond=None)[0][0]
        else:
            c0 = uu.mean()
        xs.append(float(x[cells].mean()))
        uc.append(float(c0))
    xs, uc = np.array(xs), np.array(uc)

    # axial velocity at R_PROBE: per slab, u = (R − r)(a + b (R − r)) fitted
    # to the outer cells, so it vanishes at the wall
    px, pu = [], []
    for cells in geo["probe"]:
        y = R - r[cells]
        a = np.linalg.lstsq(np.column_stack([y, y ** 2]), U[cells, 0], rcond=None)[0]
        yp = R - R_PROBE
        px.append(float(x[cells].mean()))
        pu.append(float(yp * a[0] + yp ** 2 * a[1]))
    px, pu = np.array(px), np.array(pu)
    stations = np.arange(1.0, 16.0)
    su = np.interp(stations, px, pu)

    # wall shear stress (kinematic), axial sense: ν · u_t / d from the wall cell
    tau = NU * np.einsum("ij,ij->i", U[geo["wall_cell"]], geo["wall_tang"]) / geo["wall_d"]
    tx = geo["wall_x"]
    tw = np.array([tau[g].mean() for g in geo["wall_groups"]])
    sep, att = crossings(tx, tw)

    q_in = -float(of.read_patch_values(t / "phi", "fluid_inlet").sum())
    q_out = float(of.read_patch_values(t / "phi", "fluid_outlet").sum())
    peak = int(np.argmax(uc))
    return {
        "time": float(t.name),
        "centreline": list(zip(xs.tolist(), uc.tolist())),
        "wall_shear": list(zip(tx.tolist(), tw.tolist())),
        "probe": list(zip(px.tolist(), pu.tolist())),
        "u_peak": float(uc[peak]), "x_peak": float(xs[peak]),
        "x_separation": sep, "x_reattachment": att,
        "x_reattachment_probe": last_rise(px, pu),
        "x_reattachment_stations": last_rise(stations, su),
        "q_in": q_in, "q_out": q_out, "mass_err": abs(q_out - q_in) / q_in,
    }


def change(prev: dict, cur: dict) -> dict:
    """Relative change between two states: the centreline (largest, of the
    peak) and each reattachment measure."""
    xp, up = np.array(prev["centreline"]).T
    xc, uc = np.array(cur["centreline"]).T
    out = {"centreline": float(np.abs(np.interp(xp, xc, uc) - up).max() / up.max())}
    for key in ("x_reattachment", "x_reattachment_probe"):
        a, b = prev[key], cur[key]
        out[key] = float("inf") if a is None or b is None else abs(b - a) / abs(a)
    return out


def last_rise(x, f) -> float | None:
    """The last − → + sign change of *f* along *x*, linearly interpolated."""
    for i in range(len(x) - 2, -1, -1):
        if f[i] < 0 <= f[i + 1]:
            return float(x[i] - f[i] * (x[i + 1] - x[i]) / (f[i + 1] - f[i]))
    return None


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


def reference_reattachment(ref: dict, r_probe: float = R_PROBE) -> float:
    """x/D where the axial velocity at *r_probe* (0.02 D from the wall, the
    database's last point before it) turns positive past the throat: the
    stations are 1 D apart, so linear interpolation between them."""
    zs = sorted(z for z in ref if z > 0)
    att = last_rise(zs, [float(np.interp(r_probe, ref[z]["r"], ref[z]["w"])) for z in zs])
    if att is None:
        raise ValueError("no reattachment in the reference")
    return att


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

def richardson(f3: float, f2: float, f1: float, r21: float, r32: float) -> dict:
    """Three-level Richardson extrapolation at non-constant refinement
    ratios [celik_and_ghia_etal_2008], §2.1, steps 3–5: f1 the finest
    level, r21 = h2/h1, r32 = h3/h2.  The observed order solves
    p = |ln|ε32/ε21| + q(p)| / ln r21 by fixed-point iteration."""
    e21, e32 = f2 - f1, f3 - f2
    if e21 == 0 or e32 == 0:
        raise ValueError("two levels agree exactly")
    s = 1.0 if e32 / e21 > 0 else -1.0
    p = abs(math.log(abs(e32 / e21))) / math.log(r21)
    for _ in range(100):
        q = math.log((r21 ** p - s) / (r32 ** p - s))
        p_new = abs(math.log(abs(e32 / e21)) + q) / math.log(r21)
        if abs(p_new - p) < 1e-10:
            break
        p = p_new
    rp = r21 ** p
    ext = (rp * f1 - f2) / (rp - 1)
    e_a = abs((f1 - f2) / f1)
    return {"order": p, "extrapolated": ext, "e_a": e_a,
            "e_ext": abs((ext - f1) / ext), "gci_fine": 1.25 * e_a / (rp - 1),
            "oscillatory": s < 0}


def run_level(name: str, k: int, work: Path, max_time: float, n_proc: int) -> dict:
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
    # first step well under Co 0.8 at the throat (u ≈ 8, cell ≈ L/(36k));
    # adjustTimeStep grows it
    first = min(CHUNK, max_time)
    write_case(case, first, n_proc, delta_t=0.1 * L_STEN / (36 * k) / 8)
    of.foam(f"gmshToFoam {msh.name}", case, "log.gmshToFoam")
    retyped = apply_boundary_roles(case, roles_path(msh))
    check = of.foam("checkMesh", case, "log.checkMesh")
    scale = parabolic_inlet(case)
    geo = geometry(case)
    if n_proc > 1:
        of.foam("decomposePar -force", case, "log.decomposePar")

    # march in chunks of CHUNK time units until two successive states agree
    logs, states, changes, steady = [], [], [], False
    end, wall = first, 0.0
    while True:
        set_end_time(case, end)
        if n_proc > 1:
            log = of.foam(f"mpirun -np {n_proc} pimpleFoam -parallel", case,
                          f"log.pimpleFoam.{end:g}")
            of.foam("reconstructPar -latestTime", case, f"log.reconstructPar.{end:g}")
        else:
            log = of.foam("pimpleFoam", case, f"log.pimpleFoam.{end:g}")
        logs.append(log)
        wall += float(re.findall(r"ExecutionTime = ([\d.e+-]+) s", log)[-1])
        states.append(results(geo, of.latest_time(case)))
        if len(states) > 1:
            changes.append({"time": states[-1]["time"], **change(states[-2], states[-1])})
            print(f"[{name}] t = {end:g}: {json.dumps(changes[-1])}", flush=True)
            steady = all(v < STEADY_TOL for k_, v in changes[-1].items() if k_ != "time")
        if steady or end >= max_time:
            break
        prune(case, keep=2)
        end = min(end + CHUNK, max_time)

    hist = residuals("".join(logs))
    out = {
        "level": name, "factor": k, "cells": cells,
        "cells_foam": int(re.search(r"cells:\s+(\d+)", check).group(1)),
        "mesh_ok": "Mesh OK." in check, "retyped": retyped,
        "min_scaled_jacobian": sj,
        "max_non_orthogonality": float(
            re.search(r"non-orthogonality Max: ([\d.e+-]+)", check).group(1)),
        "max_skewness": float(re.search(r"Max skewness = ([\d.e+-]+)", check).group(1)),
        "inlet_scale": scale, "n_proc": n_proc,
        "steady": steady, "end_time": end,
        # the first state of the steady pair: the flow was steady from there
        "time_to_steady": states[-2]["time"] if steady else None,
        "time_steps": sum(len(re.findall(r"^Time = ", lg, re.M)) for lg in logs),
        "exec_time": wall, "changes": changes,
        "final_residuals": {f: v[-1] for f, v in hist.items()},
        "residual_history": {f: v[::max(1, len(v) // 200)] for f, v in hist.items()},
    }
    out.update(states[-1])
    return out


def prune(case: Path, keep: int) -> None:
    """Drop all but the last *keep* time directories, reconstructed and
    per processor (purgeWrite counts only one run's writes, and every
    chunk is a run)."""
    for root in [case, *case.glob("processor*")]:
        times = sorted((d for d in root.iterdir() if d.is_dir() and d.name != "0"
                        and re.fullmatch(r"[\d.e+-]+", d.name)), key=lambda d: float(d.name))
        for d in times[:-keep]:
            shutil.rmtree(d)


def residuals(log: str) -> dict[str, list[float]]:
    """Initial residual per time step of p and each U component (the first
    solve of each field in a step)."""
    out: dict[str, list[float]] = {}
    for block in re.split(r"^Time = \S+$", log, flags=re.M)[1:]:
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
             "| steady from t | wall time (s) | mass balance | u_peak / U | x_sep / D "
             "| x_reatt / D: τ_w = 0 | u(0.48 D) = 0 | at 1 D stations "
             "| max centreline err. (of DNS peak) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        f = (lambda v: "—" if v is None else f"{v:.3f}")
        cmp = r.get("compare")
        centre = ("—" if not cmp else
                  f"{cmp['max_centre_err']:.2%} at x = {cmp['max_centre_err_x']:g}")
        steady = (f"{r['time_to_steady']:g}" if r["steady"]
                  else f"not steady by {r['end_time']:g}")
        lines.append(
            f"| {r['level']} | {r['cells']} | {r['mesh_ok']} | {r['min_scaled_jacobian']:.3f} "
            f"| {r['max_non_orthogonality']:.1f} | {r['max_skewness']:.3f} "
            f"| {steady} | {r['exec_time']:.0f} "
            f"| {r['mass_err']:.1e} | {r['u_peak']:.4f} | {f(r['x_separation'])} "
            f"| {f(r['x_reattachment'])} | {f(r['x_reattachment_probe'])} "
            f"| {f(r['x_reattachment_stations'])} | {centre} |")
    return "\n".join(lines)


def extrapolate(rows: list[dict], ref: dict | None) -> dict:
    """Richardson over three levels: each scalar, and the centreline at
    every database station (the extrapolated value where the order is
    defined and not oscillatory, else the finest level's)."""
    ks = [r["factor"] for r in rows]
    r21, r32 = ks[2] / ks[1], ks[1] / ks[0]
    rich = {"ratios": [r21, r32]}
    for key in ("u_peak", "x_separation", "x_reattachment", "x_reattachment_probe"):
        try:
            rich[key] = richardson(*(r[key] for r in rows), r21, r32)
        except (TypeError, ValueError, ZeroDivisionError) as e:
            rich[key] = {"error": str(e)}
    if ref:
        zs = rows[-1]["compare"]["stations"]
        vals = np.array([r["compare"]["centre"] for r in rows])
        best, used = [], 0
        for i in range(len(zs)):
            try:
                e = richardson(*vals[:, i], r21, r32)
                ok = not e["oscillatory"] and math.isfinite(e["extrapolated"])
            except (ValueError, ZeroDivisionError):
                ok = False
            best.append(e["extrapolated"] if ok else float(vals[2, i]))
            used += ok
        dns = np.array(rows[-1]["compare"]["dns_centre"])
        peak = rows[-1]["compare"]["dns_peak"]
        err = (np.array(best) - dns) / peak
        i = int(np.argmax(np.abs(err)))
        rich["centreline"] = {"stations": zs, "best": best, "extrapolated_stations": used,
                              "max_err": float(abs(err[i])), "max_err_x": float(zs[i])}
    return rich


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--levels", nargs="+", default=DEFAULT_LEVELS, choices=list(LEVELS))
    ap.add_argument("--reference", type=Path,
                    help="the database's Re = 500 vel.dat (default: download it)")
    ap.add_argument("--no-reference", action="store_true", help="skip the comparison")
    ap.add_argument("--work", type=Path, default=HERE / "work")
    ap.add_argument("--end-time", type=float, default=60.0,
                    help="stop here if not steady before (time units, D / U)")
    ap.add_argument("--np", type=int, default=1, dest="n_proc",
                    help="MPI processes for pimpleFoam (levels other than coarse)")
    ap.add_argument("--json", type=Path, help="write all results as JSON")
    ap.add_argument("--repost", type=Path, metavar="JSON",
                    help="don't run: measure the latest fields of the levels in this "
                         "earlier --json output again (cases in --work)")
    args = ap.parse_args(argv)
    ref = (None if args.no_reference
           else read_reference(reference(args.reference, args.work)))
    ref_att = reference_reattachment(ref) if ref else None
    earlier = ({r["level"]: r for r in json.loads(args.repost.read_text())["levels"]}
               if args.repost else {})
    rows = []
    for name in (list(earlier) if earlier else args.levels):
        n = 1 if name == "coarse" else args.n_proc
        if earlier:
            case = args.work / name
            r = {**earlier[name], **results(geometry(case), of.latest_time(case))}
        else:
            r = run_level(name, LEVELS[name], args.work, args.end_time, n)
        if ref:
            r["compare"] = compare(r, ref)
            for key in ("x_reattachment", "x_reattachment_probe"):
                r[key + "_err"] = ((r[key] - ref_att) / ref_att
                                   if r[key] is not None else None)
        print(json.dumps({k: v for k, v in r.items()
                          if k not in ("centreline", "wall_shear", "probe", "compare",
                                       "residual_history")}), flush=True)
        rows.append(r)
        if args.json:      # after every level: the fine level takes hours
            write_json(args.json, rows, {}, ref, ref_att)
    if ref:
        print(f"\nDNS: peak centreline u/U = {max(v['centre'] for v in ref.values()):.4f}, "
              f"reattachment x/D = {ref_att:.3f}\n")
    print(table(rows))
    rich = extrapolate(rows, ref) if len(rows) == 3 else {}
    if rich:
        print("\n" + json.dumps(rich, indent=1))
    if args.json:
        write_json(args.json, rows, rich, ref, ref_att)
    return {"levels": rows, "richardson": rich}


def write_json(path: Path, rows, rich, ref, ref_att) -> None:
    path.write_text(json.dumps({
        "versions": pois.versions(), "levels": rows, "richardson": rich,
        "reference": None if not ref else {
            "reattachment": ref_att,
            "centre": {str(z): v["centre"] for z, v in sorted(ref.items())}},
    }, indent=1))


if __name__ == "__main__":
    main()
