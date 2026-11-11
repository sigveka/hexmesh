#!/usr/bin/env python3
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
Pulsatile flow through the smooth cosine constriction (decision 0012,
docs/tasks/0068), against the DNS of Varghese, Frankel & Fischer (2007),
Part 2 [varghese_and_frankel_etal_2007b], Purdue database.

    the stenosis mesh (validation/stenosis, task 0032) at refined(k)
    → gmshToFoam → apply_boundary_roles → checkMesh
    → the Womersley inlet (validation/womersley, task 0067):
      timeVaryingMappedFixedValue on Python-written boundaryData
    → pimpleFoam from rest, one period at a time, until periodic
    → sampled lines (axis, r = 0.48 D, the station diameters) at the
      DNS phases → comparison in Python

Inlet: α = 7.5, A = 0.667, Re = 600 on the mean centreline velocity
(u_c = D = 1, ν = 1/600; bulk Re 300).  The database's velocities are in
u_c units already (its u_i = 0.5 is the mean bulk velocity, u_c / 2).

Phases: the paper gives t/T ≈ 0.09 + k/6 for the database's six files,
read from its fig. 1.  Each file's flow rate (conserved along the pipe)
fixes its phase on the inlet waveform more precisely; the run writes at
both, and the comparison uses the flow-rate phases (task 0068, *Agent
notes*).  Usage::

    python3 validation/stenosis_pulsatile/run.py [--levels coarse k2 k3] [--np N]
        [--dt-halved [LEVEL]] [--periods-max N] [--work DIR] [--json FILE]
        [--keep-work] [--reference DIR] [--openfoam native|docker:IMAGE]

Results go to ``results.json`` here (task 0093): levels already in it are
reused, and each level's case directory is deleted once its results are
stored (the downloaded reference stays in the work directory).

The reference files carry no licence: without ``--reference`` they are
downloaded into the work directory (git-ignored) once.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from hexmesh import Session                                    # noqa: E402
from hexmesh.study import openfoam as of                       # noqa: E402


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# The steady case's geometry and levels (task 0032);
# the Womersley inlet and schemes (task 0067).
sten = _load("stenosis_run", "validation/stenosis/run.py")
conv = _load("convergence", "validation/tools/convergence.py")       # task 0089
stored = _load("stored", "validation/tools/results.py")              # task 0093
wom = _load("womersley_run", "validation/womersley/run.py")

REFERENCE_URL = ("https://engineering.purdue.edu/CFDLAB/DNS_stenoticflow_database/"
                 "Axi_puls/vel_p{i}.dat")

D, R = sten.D, sten.R
U_C, NU, PERIOD = wom.U_C, wom.NU, wom.PERIOD
X_IN, X_OUT, L_STEN = sten.X_IN, sten.X_OUT, sten.L_STEN
NOMINAL = [0.09 + k / 6 for k in range(6)]        # the paper's fig. 1, ±0.01
STATIONS = [-2.0, 0.0, 1.0, 2.0, 3.0, 4.0, 6.0, 10.0]
R_PROBE = sten.R_PROBE                            # 0.48 D: the recirculation probe
INLET_SAMPLES = 480                               # boundaryData times per period
MAX_CO = 0.5
PERIODIC_TOL = 5e-3                               # task: < 0.5 % between periods
MAX_PERIODS = 10
LEVELS = sten.LEVELS
DEFAULT_LEVELS = ["coarse", "k2", "k3"]           # task 0068, Q3: no k4
LINE_POINTS = 3801                                # along x: 0.005 D apart
DIAMETER_POINTS = 401


# --- case --------------------------------------------------------------------

CONTROL = """application     pimpleFoam;
startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         {end!r};
deltaT          {dt!r};
adjustTimeStep  yes;
maxCo           {co!r};
writeControl    adjustableRunTime;
writeInterval   {write!r};
purgeWrite      0;
writeFormat     ascii;
writePrecision  12;
writeCompression off;
timeFormat      general;
timePrecision   12;
runTimeModifiable false;
functions
{{
    sample
    {{
        type            sets;
        libs            (sampling);
        writeControl    writeTime;
        interpolationScheme cellPoint;
        setFormat       raw;
        fields          (U);
        sets
        {{
{sets}
        }}
    }}
}}
"""

LINE = "            {name} {{ type uniform; axis {axis}; start ({a}); end ({b}); nPoints {n}; }}"


def meshes():
    """(label, caption, build) per mesh shown in README.md
    (``docs/gallery/build.py --validation``): the steady case's."""
    b = sten.BASE
    return [(name, f"{name}: nang {b['nang'] * k}, nrad {b['nrad'] * k}, "
                   f"{sum(b[n] for n in ('up', 'sten', 'near', 'far')) * k} axial layers",
             lambda k=k: sten.assembly(k))
            for name, k in ((n, LEVELS[n]) for n in DEFAULT_LEVELS)]


def sets_text() -> str:
    eps = 1e-6
    lines = [LINE.format(name="axis", axis="x", a=f"{X_IN + eps} 0 0", b=f"{X_OUT - eps} 0 0",
                         n=LINE_POINTS),
             LINE.format(name="probe", axis="x", a=f"{X_IN + eps} {R_PROBE} 0",
                         b=f"{X_OUT - eps} {R_PROBE} 0", n=LINE_POINTS)]
    for i, x in enumerate(STATIONS):
        rx = float(sten.radius(x)) - eps
        lines.append(LINE.format(name=f"station{i}", axis="y", a=f"{x} {-rx} 0",
                                 b=f"{x} {rx} 0", n=DIAMETER_POINTS))
    return "\n".join(lines)


U0 = """dimensions      [0 1 -1 0 0 0 0];
internalField   uniform (0 0 0);
boundaryField
{
    fluid_inlet
    {
        type            timeVaryingMappedFixedValue;
        mapMethod       nearest;
        offset          (0 0 0);
        value           uniform (0 0 0);
    }
    fluid_outlet { type zeroGradient; }
    fluid_wall   { type noSlip; }
}
"""


def write_control(case: Path, end: float, write: float, dt: float, co: float) -> None:
    (case / "system/controlDict").write_text(
        of.header("dictionary", "controlDict", "system")
        + CONTROL.format(end=end, dt=dt, co=co, write=write, sets=sets_text()), encoding="utf-8")


def write_case(case: Path, dt: float) -> None:
    """Dictionaries (before gmshToFoam, which needs controlDict), from rest."""
    for d in ("0", "constant", "system"):
        (case / d).mkdir(parents=True, exist_ok=True)
    files = {
        "system/fvSchemes": of.header("dictionary", "fvSchemes", "system") + wom.SCHEMES,
        "system/fvSolution": of.header("dictionary", "fvSolution", "system") + wom.SOLUTION,
        "constant/transportProperties": of.header("dictionary", "transportProperties",
                                                  "constant")
        + f"transportModel  Newtonian;\nnu              {NU!r};\n",
        "constant/turbulenceProperties": of.header("dictionary", "turbulenceProperties",
                                                   "constant")
        + "simulationType  laminar;\n",
        "constant/momentumTransport": of.header("dictionary", "momentumTransport", "constant")
        + "simulationType  laminar;\n",
        "0/U": of.header("volVectorField", "U", "0") + U0,
        "0/p": of.header("volScalarField", "p", "0") + wom.P0,
    }
    for name, text in files.items():
        (case / name).write_text(text, encoding="utf-8")
    write_control(case, end=dt, write=dt, dt=dt, co=MAX_CO)


def inlet_centres(case: Path) -> np.ndarray:
    mesh = case / "constant/polyMesh"
    pts, faces = of.read_points(mesh / "points"), of.read_faces(mesh / "faces")
    ids = of.read_patch_faces(mesh / "boundary", "fluid_inlet")
    c, _ = of.face_geometry(pts, [faces[i] for i in ids])
    return c


def write_inlet(case: Path, xi: np.ndarray, t0: float, t1: float) -> None:
    """boundaryData for [t0, t1] (and one sample either side) on the
    INLET_SAMPLES grid; older times are removed (each run reads the list
    once, at its start)."""
    bd = case / "constant/boundaryData/fluid_inlet"
    bd.mkdir(parents=True, exist_ok=True)
    pts = bd / "points"
    if not pts.exists():
        pts.write_text(wom._header("vectorField", "points") + f"{len(xi)}\n(\n"
                       + wom._vectors(xi) + "\n)\n", encoding="utf-8")
    h = PERIOD / INLET_SAMPLES
    i0, i1 = math.floor(t0 / h) - 1, math.ceil(t1 / h) + 1
    keep = {wom.time_name(max(i, 0) * h) for i in range(i0, i1 + 1)}
    for d in bd.iterdir():
        if d.is_dir() and d.name not in keep:
            shutil.rmtree(d)
    r = np.hypot(xi[:, 1], xi[:, 2])
    for i in range(max(i0, 0), i1 + 1):
        t = i * h
        d = bd / wom.time_name(t)
        if d.exists():
            continue
        d.mkdir()
        u = np.zeros_like(xi)
        u[:, 0] = wom.exact_u(r, t)
        (d / "U").write_text(wom._header("vectorField", "U") + f"{len(u)}\n(\n"
                             + wom._vectors(u) + "\n)\n", encoding="utf-8")


# --- reference ---------------------------------------------------------------

def read_reference(path: Path) -> dict[float, dict]:
    """One database file: per station x/D, the diameter (r from −0.5 to 0.5)
    and the axial velocity w, in u_c units."""
    zones: dict[float, list] = {}
    cur = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.search(r"Z =\s*([-+\d.Ee]+)", line)
        if m:
            cur = float(m.group(1))
            zones[cur] = []
        elif cur is not None and line.strip() and "VARIABLES" not in line:
            zones[cur].append([float(v) for v in line.split()])
    return {z: {"r": np.array(a)[:, 0], "w": np.array(a)[:, 4]} for z, a in zones.items()}


def flow_rate(r: np.ndarray, w: np.ndarray) -> float:
    m = r >= 0
    return float(2 * np.pi * np.trapz(w[m] * r[m], r[m]))


def _waveform():
    rr = np.linspace(0, R, 2001)
    ts = np.linspace(0, PERIOD, 4001)
    return ts, np.array([2 * np.pi * np.trapz(wom.exact_u(rr, t) * rr, rr) for t in ts])


def reference_phases(refs: list[dict]) -> list[dict]:
    """Per file: its flow rate (median over the straight-pipe stations; in
    the constriction the database's profiles miss it by up to 6 %) and the
    phase on the inlet waveform with that flow rate nearest the nominal
    one."""
    ts, q = _waveform()
    out = []
    for k, ref in enumerate(refs):
        qs = [flow_rate(z["r"], z["w"]) for x, z in ref.items() if abs(x) > L_STEN / 2]
        qm = float(np.median(qs))
        s = np.nonzero(np.diff(np.sign(q - qm)))[0]
        roots = [float(ts[i] + (qm - q[i]) * (ts[i + 1] - ts[i]) / (q[i + 1] - q[i])) / PERIOD
                 for i in s]
        nom = NOMINAL[k]
        phase = min(roots, key=lambda p: min(abs(p - nom), 1 - abs(p - nom)))
        out.append({"file": f"vel_p{k + 1}.dat", "nominal": nom, "flow_rate": qm,
                    "flow_rate_spread": float(np.ptp(qs) / abs(qm)), "phase": phase,
                    "roots": roots})
    return out


def reference(path: Path | None, work: Path) -> list[dict]:
    folder = path or work / "reference"
    folder.mkdir(parents=True, exist_ok=True)
    refs = []
    for i in range(1, 7):
        f = folder / f"vel_p{i}.dat"
        if not f.exists():
            with urllib.request.urlopen(REFERENCE_URL.format(i=i), timeout=60) as r:
                f.write_bytes(r.read())
        refs.append(read_reference(f))
    return refs


# --- running -----------------------------------------------------------------

def _times(root: Path) -> list[float]:
    return sorted(float(d.name) for d in root.iterdir() if d.is_dir()
                  and re.fullmatch(r"[\d.e+-]+", d.name) and d.name != "0")


def current_time(case: Path) -> float:
    t = _times(case)
    return t[-1] if t else 0.0


def run_to(case: Path, n_proc: int, end: float, co: float, tag: str) -> tuple[float, int]:
    """Advance to *end*, writing there (and only there); returns the
    solver's execution time and its number of time steps."""
    t = current_time(case)
    write_control(case, end=end, write=end - t, dt=PERIOD / INLET_SAMPLES / 20, co=co)
    log = of.run_solver(case, "pimpleFoam", n_proc=n_proc, log=f"log.pimpleFoam.{tag}")
    return float(re.findall(r"ExecutionTime = ([\d.e+-]+) s", log)[-1]), len(
        re.findall(r"^Time = ", log, re.M))


def prune(case: Path, keep: float) -> None:
    """Drop written times before *keep* (the period's start)."""
    for d in case.iterdir():
        if d.is_dir() and re.fullmatch(r"[\d.e+-]+", d.name) and d.name != "0" \
                and float(d.name) < keep - 1e-9:
            shutil.rmtree(d)


# --- sampling ----------------------------------------------------------------

def read_set(case: Path, t: float, name: str) -> np.ndarray:
    """Columns (coordinate, Ux, Uy, Uz) of sampled set *name* at time *t*."""
    base = case / "postProcessing/sample"
    d = min((p for p in base.iterdir() if p.is_dir()), key=lambda p: abs(float(p.name) - t))
    if abs(float(d.name) - t) > 1e-6:
        raise FileNotFoundError(f"no sample at t = {t} in {base}")
    return np.loadtxt(d / f"{name}_U.xy")


def sample(case: Path, t: float) -> dict:
    ax = read_set(case, t, "axis")
    pr = read_set(case, t, "probe")
    px, pu = pr[:, 0], pr[:, 1]
    down = px > L_STEN / 2
    out = {"t": t, "phase": (t / PERIOD) % 1,
           "centreline": ax[:, :2].tolist(),
           "u_peak": float(ax[:, 1].max()), "x_peak": float(ax[np.argmax(ax[:, 1]), 0]),
           "x_reattachment_probe": sten.last_rise(px[down], pu[down]),
           "features": features(px, pu), "stations": {}}
    for i, x in enumerate(STATIONS):
        s = read_set(case, t, f"station{i}")
        y, u = s[:, 0], s[:, 1]
        # axisymmetry: the profile against its mirror image
        asym = float(np.abs(u - np.interp(-y, y, u)).max())
        out["stations"][x] = {"y": y.tolist(), "u": u.tolist(), "asymmetry": asym}
    return out


def features(px: np.ndarray, pu: np.ndarray) -> dict:
    """Flow features from the axial velocity at r = 0.48 D along x (the
    paper's §3.1, design answer Q2): reverse flow past the constriction
    (its fraction of the downstream length, and its extent), and upstream
    of it (x in [−2.5 D, −1 D]: the upstream separation)."""
    down = px > L_STEN / 2
    up = (px >= -2.5 * D) & (px <= -L_STEN / 2)
    rev_d = px[down][pu[down] < 0]
    rev_u = px[up][pu[up] < 0]
    return {"reverse_fraction_down": float(np.mean(pu[down] < 0)),
            "reverse_down": [float(rev_d.min()), float(rev_d.max())] if len(rev_d) else None,
            "upstream_min_u": float(pu[up].min()),
            "reverse_up": [float(rev_u.min()), float(rev_u.max())] if len(rev_u) else None}


def dns_features(ref: dict) -> dict:
    """The same features from the DNS at its stations (1 D apart)."""
    zs = np.array(sorted(ref))
    pu = np.array([float(np.interp(R_PROBE, ref[z]["r"], ref[z]["w"])) for z in zs])
    out = features(zs, pu)
    out["probe"] = list(zip(zs.tolist(), pu.tolist()))
    return out


def compare(s: dict, ref: dict) -> dict:
    """Per station: RMS and max difference from the DNS (u_c), on our
    points; the upstream station also against the exact inlet."""
    out = {}
    for x, st in s["stations"].items():
        x = float(x)                    # str after a JSON round trip
        y, u = np.array(st["y"]), np.array(st["u"])
        z = ref[x]
        w = np.interp(y, z["r"], z["w"])
        d = u - w
        row = {"rms": float(np.sqrt(np.mean(d ** 2))), "max": float(np.abs(d).max()),
               "centre": float(np.interp(0.0, y, u)), "dns_centre": float(np.interp(0.0, z["r"], z["w"]))}
        if x == STATIONS[0]:
            e = wom.exact_u(np.abs(y), s["t"])
            row["womersley_max"] = float(np.abs(u - e).max())
            row["dns_womersley_max"] = float(np.abs(w - e).max())
        out[str(x)] = row
    return out


def change(prev: list[dict], cur: list[dict]) -> float:
    """Largest change of the centreline over the phases, of its peak."""
    worst = 0.0
    for a, b in zip(prev, cur):
        ua, ub = np.array(a["centreline"])[:, 1], np.array(b["centreline"])[:, 1]
        worst = max(worst, float(np.abs(ub - ua).max() / ub.max()))
    return worst


# --- driver ------------------------------------------------------------------

def run_level(name: str, k: int, work: Path, n_proc: int, targets: list[float],
              co: float = MAX_CO, warm_from: Path | None = None,
              max_periods: int = MAX_PERIODS) -> dict:
    """*targets*: the phases (t/T) to write and sample in every period."""
    tag = name if co == MAX_CO else f"{name}-co{co:g}"
    case = work / tag
    if case.exists():
        shutil.rmtree(case)
    out = {"level": name, "factor": k, "max_co": co, "n_proc": n_proc}
    if warm_from is None:
        case.mkdir(parents=True)
        with Session(f"stenosis-pulsatile-{name}"):
            asm = sten.assembly(k)
            out["cells"] = asm.cell_count()
            print(f"[{tag}] predicted cells: {out['cells']}", flush=True)
            msh = case / "stenosis.msh"
            asm.write_openfoam(msh)
            out["min_scaled_jacobian"] = asm.check_quality("scaled_jacobian").worst
        write_case(case, dt=PERIOD / INLET_SAMPLES / 20)
        # every hex right-handed: skip gmshToFoam's orientation test (task 0108)
        out["retyped"] = of.convert(case, msh,
                                    keep_orientation=out["min_scaled_jacobian"] > 0)
        check = of.foam("checkMesh", case, "log.checkMesh")
        out.update({
            "cells_foam": int(re.search(r"cells:\s+(\d+)", check).group(1)),
            "mesh_ok": "Mesh OK." in check,
            "max_non_orthogonality": float(
                re.search(r"non-orthogonality Max: ([\d.e+-]+)", check).group(1))})
        start = 0.0
    else:
        # the level's periodic state, run on at a smaller Courant number
        shutil.copytree(warm_from, case, ignore=shutil.ignore_patterns("log.*", "postProcessing"))
        out["warm_from"] = current_time(case)
        # periods start on a period boundary, so the targets stay at their
        # phases: the next one after the restart time
        start = math.ceil(out["warm_from"] / PERIOD - 1e-9) * PERIOD
    xi = inlet_centres(case)

    periods, wall, steps, prev = [], 0.0, 0, None
    for p in range(1, max_periods + 1):
        t0 = start + (p - 1) * PERIOD
        # from the restart time: the previous period's last sample
        write_inlet(case, xi, min(t0, current_time(case)), t0 + PERIOD)
        rows, w0 = [], time.time()
        for ph in targets:
            t = t0 + ph * PERIOD
            ex, n = run_to(case, n_proc, t, co, f"{p}.{ph:.4f}")
            wall += ex
            steps += n
            rows.append(sample(case, t))
        prune(case, keep=t0 + targets[-1] * PERIOD)
        rec = {"period": p, "wall_time": time.time() - w0, "rows": rows}
        if prev is not None:
            rec["change"] = change(prev, rows)
            print(f"[{tag}] period {p}: change {rec['change']:.2e}", flush=True)
        else:
            print(f"[{tag}] period {p} done", flush=True)
        periods.append(rec)
        prev = rows
        if rec.get("change", 1.0) < PERIODIC_TOL:
            break
    last = periods[-1]
    out.update({"periods": len(periods), "periodic": last.get("change", 1.0) < PERIODIC_TOL,
                "periodic_change": last.get("change"), "exec_time": wall, "time_steps": steps,
                "wall_time_per_period": [r["wall_time"] for r in periods],
                "changes": [r.get("change") for r in periods],
                "rows": last["rows"]})
    return out


def evaluate(level: dict, refs: list[dict], phases: list[dict]) -> dict:
    """The DNS comparison at the flow-rate phases (and the nominal ones)."""
    def row_at(ph):
        return min(level["rows"], key=lambda r: min(abs(r["phase"] - ph), 1 - abs(r["phase"] - ph)))

    out = []
    for ref, ph in zip(refs, phases):
        for kind, target in (("flow_rate", ph["phase"]), ("nominal", ph["nominal"])):
            s = row_at(target)
            c = compare(s, ref)
            out.append({"file": ph["file"], "kind": kind, "phase": s["phase"], "stations": c,
                        "u_peak": s["u_peak"], "x_peak": s["x_peak"],
                        "x_reattachment_probe": s["x_reattachment_probe"],
                        "features": s["features"], "dns_features": dns_features(ref),
                        "max_asymmetry": max(v["asymmetry"] for v in s["stations"].values())})
    return out


def resample(case: Path, level: dict) -> dict:
    """Re-read a finished level's last period from its saved sample sets
    (after a change to the post-processing)."""
    level["rows"] = [sample(case, r["t"]) for r in level["rows"]]
    return level


def summarise(rows: list[dict]) -> dict:
    """Throat peak at peak flow (p2, flow-rate phase, x = 0) per level,
    and its Richardson extrapolation over three levels (ratios from k);
    the x = −2D departure from Womersley per level and phase."""
    space = sorted((r for r in rows if r["max_co"] == MAX_CO), key=lambda r: r["factor"])
    pick = lambda r, f: next(c for c in r["comparison"]
                             if c["file"] == f and c["kind"] == "flow_rate")
    out = {"throat_peak": {r["level"]: pick(r, "vel_p2.dat")["stations"]["0.0"]["centre"]
                           for r in space},
           "dns_throat_peak": pick(space[0], "vel_p2.dat")["stations"]["0.0"]["dns_centre"]
           if space else None,
           "upstream_womersley_max": {r["level"]: {c["file"]: c["stations"]["-2.0"]["womersley_max"]
                                                   for c in r["comparison"] if c["kind"] == "flow_rate"}
                                      for r in space}}
    if len(space) >= 3:
        f3, f2, f1 = (out["throat_peak"][r["level"]] for r in space[-3:])
        k3, k2, k1 = (r["factor"] for r in space[-3:])
        out["throat_peak_richardson"] = conv.richardson(f3, f2, f1, k1 / k2, k2 / k3)
    for h in (r for r in rows if r["max_co"] != MAX_CO):
        base = next((r for r in space if r["level"] == h["level"]), None)
        if base is not None:
            a = pick(base, "vel_p2.dat")["stations"]["0.0"]["centre"]
            b = pick(h, "vel_p2.dat")["stations"]["0.0"]["centre"]
            out[f"time_step_{h['level']}"] = {"throat_peak": [a, b], "change": abs(b - a),
                                             "space_change": (abs(a - out["throat_peak"][space[-1]["level"]])
                                                              if base is not space[-1] else None)}
    return out


def level_name(level: str, co: float = MAX_CO) -> str:
    """The level's name in results.json, like its case directory."""
    return level if co == MAX_CO else f"{level}-co{co:g}"


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--levels", nargs="+", default=DEFAULT_LEVELS, choices=list(LEVELS),
                    help='meshes to run: coarse, k2, k3, k4, where k multiplies the cells along each direction (default: %(default)s)')
    ap.add_argument("--np", type=int, default=1,
                    help='MPI processes per solve (default: %(default)s)')
    ap.add_argument("--dt-halved", nargs="?", const="last", metavar="LEVEL",
                    help="also run LEVEL (default: the finest given) at Co 0.25, "
                         "warm-started from its periodic state")
    ap.add_argument("--periods-max", type=int, default=MAX_PERIODS,
                    help='most pulse periods to run while waiting for a periodic state (default: %(default)s)')
    ap.add_argument("--work", type=Path, default=HERE / "work",
                    help="folder for each level's OpenFOAM case (default: validation/stenosis_pulsatile/work/, not committed); a level's case is deleted once its results are stored, unless --keep-work")
    stored.add_arguments(ap, HERE)
    ap.add_argument("--reference", type=Path, help="folder with vel_p1…6.dat")
    stored.add_openfoam_argument(ap, of.V2406)
    args = ap.parse_args(argv)
    of.set_runner(args.openfoam)
    args.work.mkdir(parents=True, exist_ok=True)

    refs = reference(args.reference, args.work)
    phases = reference_phases(refs)
    targets = sorted({round(p["phase"], 6) for p in phases} | {round(p, 6) for p in NOMINAL})
    print(json.dumps({"phases": [(p["file"], round(p["nominal"], 4), round(p["phase"], 4))
                                 for p in phases]}), flush=True)
    store = stored.Store(args.json, "stenosis_pulsatile")
    store.put_extra("phases", phases)
    store.put_extra("targets", targets)

    # stored levels whose cases are still here (--keep-work) are sampled again
    for r in store.levels():
        case = args.work / r["name"]
        if r["precision"] == stored.FULL and (case / "postProcessing/sample").exists():
            resample(case, r)
            r["comparison"] = evaluate(r, refs, phases)
            store.put(r["name"], r, env=r["environment"])

    def run(name, co=MAX_CO, warm_from=None):
        r = run_level(name, LEVELS[name], args.work, args.np, targets, co=co,
                      warm_from=warm_from, max_periods=args.periods_max)
        r["comparison"] = evaluate(r, refs, phases)
        return r

    halved = args.levels[-1] if args.dt_halved == "last" else args.dt_halved
    full = {lv["name"] for lv in store.levels() if lv["precision"] == stored.FULL}
    rows = []
    for name in args.levels:
        # the Δt-halved run warm-starts from this level's case: keep it until then
        keep = args.keep_work or (name == halved and level_name(halved, MAX_CO / 2) not in full)
        rows.append(stored.run_level(store, name, lambda name=name: run(name),
                                     args.work / name, keep))
    if halved:
        tag = level_name(halved, MAX_CO / 2)
        rows.append(stored.run_level(
            store, tag, lambda: run(halved, MAX_CO / 2, args.work / halved),
            args.work / tag, args.keep_work))
        if not args.keep_work:
            stored.remove_work(args.work / halved)
    summary = summarise(rows)
    print(json.dumps(summary, indent=1), flush=True)
    return {"meta": {"phases": phases, "targets": targets}, "levels": rows, "summary": summary}


def _throat(r: dict) -> tuple[float, float]:
    """(ours, the DNS's) centreline velocity at x = 0, p2, flow-rate phase;
    stored as such where the level is rounded from RESULTS.md."""
    if "throat_peak" in r:
        return r["throat_peak"], r["dns_throat_peak"]
    c = next(c for c in r["comparison"] if c["file"] == "vel_p2.dat" and c["kind"] == "flow_rate")
    s = c["stations"]["0.0"]
    return s["centre"], s["dns_centre"]


#: gate 1 (task 0068 Q2): within 5 % of the DNS, and above 3.65 u_c
THROAT_TOL, THROAT_MIN = 0.05, 3.65


def recheck(data: dict) -> list[dict]:
    """Every Richardson row and gate from ``results.json`` (task 0093):
    the throat peak at peak flow (finest level) within 5 % of the DNS and
    above 3.65 u_c; the flow features of the paper's §3.1, as judged in
    RESULTS.md (``extra.feature_verdicts``); the three-level Richardson
    and the time-step change, reported."""
    space = sorted((r for r in data["levels"] if r["max_co"] == MAX_CO), key=lambda r: r["factor"])
    vals = [_throat(r)[0] for r in space]
    ks = [r["factor"] for r in space]
    out = [stored.row("throat peak (p2, x = 0)",
                      rich=conv.richardson(*vals, ks[2] / ks[1], ks[1] / ks[0]),
                      note="reported: the coarse level is outside the asymptotic range")]
    ours, dns = _throat(space[-1])
    err = (ours - dns) / dns
    out.append(stored.row(f"throat peak, {space[-1]['name']}",
                          gate=f"within {THROAT_TOL:.0%} of the DNS and above {THROAT_MIN} u_c",
                          ok=abs(err) <= THROAT_TOL and ours > THROAT_MIN,
                          value=f"{ours:.3f}, {err:+.1%}"))
    for h in (r for r in data["levels"] if r["max_co"] != MAX_CO):
        base = next(r for r in space if r["level"] == h["level"])
        change = (h["throat_peak_change"] if "throat_peak_change" in h
                  else abs(_throat(h)[0] - _throat(base)[0]))
        out.append(stored.row(f"time step ({h['name']})",
                              value=f"throat peak change {change:.4f} u_c"))
    verdicts = data["extra"].get("feature_verdicts", [])
    out.append(stored.row("flow features of §3.1", gate="present, as in the DNS",
                          ok=bool(verdicts) and all(v["verdict"] == "present" for v in verdicts),
                          value=f"{sum(v['verdict'] == 'present' for v in verdicts)} of "
                                f"{len(verdicts)} present",
                          note="the verdicts are RESULTS.md's judgement, stored, not recomputed"))
    return out

if __name__ == "__main__":
    main()
