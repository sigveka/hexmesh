#!/usr/bin/env python3
"""
Womersley flow: pulsatile laminar flow in a straight pipe, against the
exact solution (decision 0012, docs/tasks/0067).

The first time-dependent case.  It checks the transient solver path and
the time-varying, spatially varying inlet that the pulsatile stenosis
(task 0068) needs:

    hexmesh Assembly → write_openfoam → gmshToFoam → apply_boundary_roles
    → topoSet → boundaryData (Python) → pimpleFoam, one period at a time
    → post-processing in Python after each period

OpenFOAM v2406 in Docker (decision 0012's toolchain), unless ``--openfoam``
says otherwise.  Usage::

    python3 validation/womersley/run.py [--levels k1 k2 k4] [--dt-halved]
                                        [--np N] [--work DIR] [--json FILE]

Prints one JSON object per level, and the convergence tables.
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

import numpy as np                                             # noqa: E402
from scipy.special import jv                                   # noqa: E402

from hexmesh import Assembly, PipeSpec, Session, Straight      # noqa: E402
from hexmesh.io.writers.openfoam_boundary import (             # noqa: E402
    apply_boundary_roles, roles_path,
)
from hexmesh.study import openfoam as of                       # noqa: E402
from hexmesh.study.openfoam import (                           # noqa: E402
    cell_geometry, face_geometry, foam, header as _header, read_faces, read_internal,
    read_labels, read_patch_faces, read_points, read_zone,
)

# --- physics (the stenosis paper's inlet, varghese_and_frankel_etal_2007b eq. 2.1) --
D = 1.0
R = D / 2
U_C = 1.0                       # steady centreline velocity
RE = 600                        # u_c D / ν
NU = U_C * D / RE
ALPHA = 7.5                     # Womersley number (D/2) √(ω/ν)
OMEGA = ALPHA**2 * NU / R**2    # 0.375
PERIOD = 2 * math.pi / OMEGA    # ≈ 16.755
A = 0.667                       # oscillation amplitude
LENGTH = 10 * D
X_A, X_M, X_B = 4 * D, 5 * D, 6 * D     # pressure planes and the profile plane
PLANES = {"planeA": X_A, "planeM": X_M, "planeB": X_B}
PHASES = [0.09 + k / 6 for k in range(6)]   # t/T, the stenosis data's phases
T0 = PHASES[0] * PERIOD                     # start time: the first phase
SAMPLES = 48                                # field writes per period (phases on them)

# --- refinement: every density parameter doubles per level (8× cells) ------
BASE = dict(nang=8, nrad=4, mprg=0.85, n_layers=(16, 4, 4, 16), steps=240)
LEVELS = {"k1": 1, "k2": 2, "k4": 4}
MAX_PERIODS = 8
PERIODIC_TOL = 1e-3             # phase values change by less, period to period


_I32 = 1j ** 1.5


def exact_u(r, t):
    """Axial velocity: u_c [(1 − (r/R)²) + A Im{(1 − J₀(i^{3/2} α r/R)/J₀(i^{3/2} α)) e^{iωt}}]."""
    r = np.asarray(r, dtype=float)
    osc = (1 - jv(0, _I32 * ALPHA * r / R) / jv(0, _I32 * ALPHA)) * np.exp(1j * OMEGA * t)
    return U_C * ((1 - (r / R) ** 2) + A * np.imag(osc))


def exact_dpdx(t):
    """Kinematic axial pressure gradient: the Poiseuille part −4νu_c/R², and
    from ∂u/∂t = −∂p/∂x + ν∇²u with u's oscillatory part
    u_c A Im{F(r) e^{iωt}}, −∂p/∂x = Im{iω u_c A e^{iωt}} = ω u_c A cos ωt."""
    return -(4 * NU * U_C / R**2 + OMEGA * U_C * A * np.cos(OMEGA * t))


DPDX_AMPLITUDE = OMEGA * U_C * A


def assembly(factor: int) -> Assembly:
    spec = PipeSpec(nang=BASE["nang"] * factor).core(
        "fluid", radius=R, nrad=BASE["nrad"] * factor, mprg=BASE["mprg"] ** (1 / factor))
    asm = Assembly(spec, position=[0, 0, 0], direction=[1, 0, 0], up=[0, 0, 1])
    # interfaces on the measurement planes, so p and U are sampled on mesh faces
    edges = (X_A, X_M - X_A, X_B - X_M, LENGTH - X_B)
    for length, n in zip(edges, BASE["n_layers"]):
        asm.add(Straight(length, n_layers=n * factor))
    return asm


def meshes():
    """(label, caption, build) per mesh shown in README.md
    (``docs/gallery/build.py --validation``)."""
    return [(name, f"{name}: nang {BASE['nang'] * f}, nrad {BASE['nrad'] * f}, "
                   f"{sum(BASE['n_layers']) * f} axial layers",
             lambda f=f: assembly(f)) for name, f in LEVELS.items()]


# --- OpenFOAM dictionaries ---------------------------------------------------

CONTROL = """application     pimpleFoam;
startFrom       latestTime;
startTime       {t0!r};
stopAt          endTime;
endTime         {end!r};
deltaT          {dt!r};
writeControl    timeStep;
writeInterval   {write};
purgeWrite      0;
writeFormat     ascii;
writePrecision  12;
writeCompression off;
timeFormat      fixed;
timePrecision   9;
runTimeModifiable false;
adjustTimeStep  no;
"""

# second order in space (the Poiseuille case's limited scheme) and time
SCHEMES = """ddtSchemes      { default backward; }
gradSchemes     { default Gauss linear; }
divSchemes
{
    default         none;
    div(phi,U)      Gauss limitedLinearV 1;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }
"""

SOLUTION = """solvers
{
    p     { solver GAMG; smoother GaussSeidel; tolerance 1e-10; relTol 0.01; }
    pFinal { $p; relTol 0; }
    U     { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-12; relTol 0; }
    UFinal { $U; }
}
PIMPLE
{
    momentumPredictor yes;
    nOuterCorrectors 1;
    nCorrectors     3;
    nNonOrthogonalCorrectors 1;
}
"""

ZONE = """    {{ name {n}Set; type faceSet; action new; source boxToFace;
      box ({x0} -1 -1) ({x1} 1 1); }}
    {{ name {n}; type faceZoneSet; action new; source setToFaceZone;
      faceSet {n}Set; }}"""

U0 = """dimensions      [0 1 -1 0 0 0 0];
internalField   nonuniform List<vector>
{n}
(
{values}
);
boundaryField
{{
    fluid_inlet
    {{
        type            timeVaryingMappedFixedValue;
        mapMethod       nearest;
        offset          (0 0 0);
        value           uniform (0 0 0);
    }}
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


def _vectors(a) -> str:
    return "\n".join(f"({x!r} {y!r} {z!r})" for x, y, z in a)


def time_name(t: float) -> str:
    return f"{t:.9f}"


def mesh_geometry(case: Path):
    mesh = case / "constant/polyMesh"
    pts, faces = read_points(mesh / "points"), read_faces(mesh / "faces")
    owner, neigh = read_labels(mesh / "owner"), read_labels(mesh / "neighbour")
    fc, sf = face_geometry(pts, faces)
    return mesh, pts, faces, owner, neigh, fc, sf


def write_case(case: Path, factor: int, dt: float, end: float, inlet_times) -> dict:
    """Dictionaries, the exact initial field at T0, and the inlet's
    boundaryData at every solver time step (so the BC's linear time
    interpolation is exact at each step)."""
    for d in ("0", "constant", "system"):
        (case / d).mkdir(parents=True, exist_ok=True)
    steps = BASE["steps"] * factor
    files = {
        "system/controlDict": _header("dictionary", "controlDict", "system")
        + CONTROL.format(t0=T0, end=end, dt=dt, write=steps // SAMPLES),
        "system/fvSchemes": _header("dictionary", "fvSchemes", "system") + SCHEMES,
        "system/fvSolution": _header("dictionary", "fvSolution", "system") + SOLUTION,
        "system/topoSetDict": _header("dictionary", "topoSetDict", "system")
        + "actions\n(\n" + "\n".join(ZONE.format(n=n, x0=x - 1e-3 * D, x1=x + 1e-3 * D)
                                     for n, x in PLANES.items()) + "\n);\n",
        "constant/transportProperties": _header("dictionary", "transportProperties", "constant")
        + f"transportModel  Newtonian;\nnu              {NU!r};\n",
        "constant/turbulenceProperties": _header("dictionary", "turbulenceProperties", "constant")
        + "simulationType  laminar;\n",
        "constant/momentumTransport": _header("dictionary", "momentumTransport", "constant")
        + "simulationType  laminar;\n",
    }
    for name, text in files.items():
        (case / name).write_text(text)
    mesh, pts, faces, owner, neigh, fc, sf = mesh_geometry(case)
    cc, _ = cell_geometry(fc, sf, owner, neigh, int(owner.max()) + 1)
    u0 = np.zeros_like(cc)
    u0[:, 0] = exact_u(np.hypot(cc[:, 1], cc[:, 2]), T0)
    start = case / time_name(T0)
    start.mkdir(exist_ok=True)
    (start / "U").write_text(_header("volVectorField", "U", time_name(T0))
                             + U0.format(n=len(u0), values=_vectors(u0)))
    (start / "p").write_text(_header("volScalarField", "p", time_name(T0)) + P0)
    inlet = np.array(read_patch_faces(mesh / "boundary", "fluid_inlet"))
    xi = fc[inlet]
    bd = case / "constant/boundaryData/fluid_inlet"
    bd.mkdir(parents=True, exist_ok=True)
    (bd / "points").write_text(_header("vectorField", "points") + f"{len(xi)}\n(\n"
                               + _vectors(xi) + "\n)\n")
    write_inlet(case, xi, inlet_times)
    return {"inlet_faces": len(xi), "inlet_centres": xi}


def write_inlet(case: Path, xi, times) -> None:
    bd = case / "constant/boundaryData/fluid_inlet"
    r = np.hypot(xi[:, 1], xi[:, 2])
    for t in times:
        d = bd / time_name(t)
        if d.exists():
            continue
        d.mkdir()
        u = np.zeros_like(xi)
        u[:, 0] = exact_u(r, t)
        (d / "U").write_text(_header("vectorField", "U") + f"{len(u)}\n(\n" + _vectors(u) + "\n)\n")


# --- post-processing ---------------------------------------------------------

def sample(case: Path, t_dir: Path, geom) -> dict:
    """Mid-plane profile, plane-mean pressures and the applied inlet values
    at one written time."""
    mesh, pts, faces, owner, neigh, fc, sf = geom
    t = float(t_dir.name)
    U = read_internal(t_dir / "U", 3)
    p = read_internal(t_dir / "p", 1)
    out = {"t": t}
    for name in PLANES:
        ids = read_zone(mesh / "faceZones", name)
        a = np.linalg.norm(sf[ids], axis=1)
        # uniform axial spacing: the face value is the mean of its cells
        pv = 0.5 * (p[owner[ids]] + p[neigh[ids]])
        out[f"p_{name}"] = float(np.sum(a * pv) / a.sum())
        if name == "planeM":
            u = 0.5 * (U[owner[ids], 0] + U[neigh[ids], 0])
            r = np.hypot(fc[ids, 1], fc[ids, 2])
            ex = exact_u(r, t)
            err = (u - ex) / U_C
            near = np.argsort(r)[:4]
            out.update(profile_max=float(np.abs(err).max()),
                       profile_rms=float(np.sqrt(np.sum(a * err**2) / a.sum())),
                       u_axis=float(u[near].mean()), u_axis_exact=float(ex[near].mean()),
                       q=float(np.sum(a * u)), q_exact=float(np.sum(a * ex)))
    out["dpdx"] = (out["p_planeB"] - out["p_planeA"]) / (X_B - X_A)
    out["dpdx_exact"] = float(exact_dpdx(t))
    out["inlet_applied"] = patch_vectors(t_dir / "U", "fluid_inlet")[:, 0]
    return out


def patch_vectors(path: Path, patch: str) -> np.ndarray:
    """A patch's nonuniform vector ``value`` list (``read_patch_values``
    reads scalars only)."""
    text = of._strip_header(path.read_text())
    j = text.index("boundaryField")
    j += re.search(rf"^\s*{patch}\s*\{{", text[j:], re.M).end()
    k = re.compile(r"(?<!\w)value\s").search(text, j).start()
    _, body = of._list_body(text, k)
    return np.array(body.replace("(", " ").replace(")", " ").split(), float).reshape(-1, 3)


def fit_dpdx(rows: list[dict]) -> dict:
    """dpdx(t) ≈ c0 + c1 cos ωt + s1 sin ωt over one period: amplitude and
    phase (degrees, of the cos term) against the exact −ω u_c A cos ωt."""
    t = np.array([r["t"] for r in rows])
    y = np.array([r["dpdx"] for r in rows])
    M = np.column_stack([np.ones_like(t), np.cos(OMEGA * t), np.sin(OMEGA * t)])
    c0, c1, s1 = np.linalg.lstsq(M, y, rcond=None)[0]
    amp = math.hypot(c1, s1)
    # exact: c1 = −ω u_c A, s1 = 0; phase lag of the fitted term relative to it
    phase = math.degrees(math.atan2(-s1, -c1))
    mean = -4 * NU * U_C / R**2
    return {"dpdx_amplitude": amp, "dpdx_amplitude_err": (amp - DPDX_AMPLITUDE) / DPDX_AMPLITUDE,
            "dpdx_phase_deg": phase, "dpdx_mean": c0, "dpdx_mean_err": (c0 - mean) / abs(mean)}


def phase_rows(rows: list[dict], period_start: float) -> list[dict]:
    """The rows at the six phases (PHASES), by nearest time."""
    out = []
    for k, ph in enumerate(PHASES):
        # the period's samples exclude its start (the previous period's
        # end), so the first phase is its last sample
        target = period_start + ((ph - PHASES[0]) * PERIOD if k else PERIOD)
        out.append(min(rows, key=lambda r: abs(r["t"] - target)))
    return out


def _time_dirs(case: Path) -> list[Path]:
    return sorted((d for d in case.iterdir() if re.fullmatch(r"[\d.]+", d.name)
                   and (d / "U").exists()), key=lambda d: float(d.name))


def warm_start(src: Path, case: Path, dt: float) -> float:
    """*case* from *src*'s mesh, dictionaries and last state (with its
    old-time fields, so ``backward`` restarts exactly), at time step *dt*.
    Returns the start time: a whole number of periods after T0, so the
    phases stay on the samples."""
    last = _time_dirs(src)[-1]
    shutil.copytree(src, case, ignore=lambda d, names: [
        n for n in names if Path(d) == src and (re.fullmatch(r"[\d.]+", n)
                                                or n.startswith(("processor", "log.")))])
    shutil.rmtree(case / "constant/boundaryData/fluid_inlet")
    (case / "constant/boundaryData/fluid_inlet").mkdir()
    shutil.copy(src / "constant/boundaryData/fluid_inlet/points",
                case / "constant/boundaryData/fluid_inlet/points")
    shutil.copytree(last, case / last.name)
    tfile = case / last.name / "uniform/time"
    # a restart takes deltaT from uniform/time, not controlDict; deltaT0
    # stays the old step, which backward handles
    tfile.write_text(re.sub(r"^(deltaT\s+)[^;]+;", rf"\g<1>{dt!r};", tfile.read_text(),
                            count=1, flags=re.M))
    return float(last.name)


def run_level(name: str, factor: int, work: Path, n_proc: int, dt_factor: float = 1.0,
              warm_from: Path | None = None) -> dict:
    case = work / (name if dt_factor == 1 else f"{name}-dt{dt_factor:g}")
    if case.exists():
        shutil.rmtree(case)
    steps = int(round(BASE["steps"] * factor * dt_factor))      # dt_factor 2: Δt halved
    dt = PERIOD / steps
    if warm_from is not None:
        return run_periods(name, factor, case, n_proc, dt_factor, steps, dt,
                           start=warm_start(warm_from, case, dt), warm=True)
    case.mkdir(parents=True)
    with Session(f"womersley-{name}"):
        asm = assembly(factor)
        cells = asm.cell_count()
        print(f"[{case.name}] predicted cells: {cells}, {steps} steps per period", flush=True)
        msh = case / "pipe.msh"
        asm.write_openfoam(msh)
        sj = asm.check_quality("scaled_jacobian").worst
    times_1 = [T0 + i * dt for i in range(steps + 1)]
    (case / "system").mkdir(exist_ok=True)       # gmshToFoam needs the dictionaries
    (case / "system/controlDict").write_text(_header("dictionary", "controlDict", "system")
                                             + CONTROL.format(t0=T0, end=T0, dt=dt, write=1))
    (case / "system/fvSchemes").write_text(_header("dictionary", "fvSchemes", "system") + SCHEMES)
    (case / "system/fvSolution").write_text(_header("dictionary", "fvSolution", "system") + SOLUTION)
    foam(f"gmshToFoam {msh.name}", case, "log.gmshToFoam")
    retyped = apply_boundary_roles(case, roles_path(msh))
    check = foam("checkMesh", case, "log.checkMesh")
    write_case(case, factor, dt, T0 + PERIOD, times_1)
    foam("topoSet", case, "log.topoSet")
    out = {"level": name, "factor": factor, "dt_factor": dt_factor, "cells": cells,
           "cells_foam": int(re.search(r"cells:\s+(\d+)", check).group(1)),
           "mesh_ok": "Mesh OK." in check, "retyped": retyped, "min_scaled_jacobian": sj,
           "max_non_orthogonality": float(re.search(r"non-orthogonality Max: ([\d.e+-]+)",
                                                    check).group(1)),
           "steps_per_period": steps, "dt": dt}
    out.update(run_periods(name, factor, case, n_proc, dt_factor, steps, dt, start=T0))
    return out


def run_periods(name, factor, case, n_proc, dt_factor, steps, dt, start, warm=False) -> dict:
    """Run one period at a time from *start* until periodic; sample each."""
    geom = mesh_geometry(case)
    mesh, fc = geom[0], geom[5]
    centres = fc[np.array(read_patch_faces(mesh / "boundary", "fluid_inlet"))]
    out = {"level": name, "factor": factor, "dt_factor": dt_factor, "steps_per_period": steps,
           "dt": dt, "start": start, "warm_start": warm,
           "courant_estimate": (1 + A) * U_C * dt / (LENGTH / (sum(BASE["n_layers"]) * factor))}
    periods, inlet_check = [], 0.0
    for p in range(1, MAX_PERIODS + 1):
        end = start + p * PERIOD
        write_inlet(case, centres, [start + i * dt for i in range(p * steps + 1)])
        (case / "system/controlDict").write_text(
            _header("dictionary", "controlDict", "system")
            + CONTROL.format(t0=start, end=end, dt=dt, write=steps // SAMPLES))
        if n_proc > 1:
            (case / "system/decomposeParDict").write_text(
                _header("dictionary", "decomposeParDict", "system")
                + f"numberOfSubdomains {n_proc};\nmethod scotch;\n")
            foam("decomposePar -force -latestTime", case, f"log.decomposePar.{p}")
            log = foam(f"mpirun -np {n_proc} pimpleFoam -parallel", case, f"log.pimpleFoam.{p}")
            foam("reconstructPar -newTimes", case, f"log.reconstructPar.{p}")
            for d in case.glob("processor*"):
                shutil.rmtree(d)
        else:
            log = foam("pimpleFoam", case, f"log.pimpleFoam.{p}")
        if "FOAM FATAL" in log:
            raise RuntimeError(f"pimpleFoam failed in period {p}")
        written = [d for d in _time_dirs(case)
                   if start + (p - 1) * PERIOD + dt / 2 < float(d.name) <= end + dt / 2]
        rows = [sample(case, d, geom) for d in written]
        r_in = np.hypot(centres[:, 1], centres[:, 2])
        for r_ in rows:
            if "inlet_applied" in r_:
                inlet_check = max(inlet_check, float(np.abs(
                    r_.pop("inlet_applied") - exact_u(r_in, r_["t"])).max()))
        ph = phase_rows(rows, start + (p - 1) * PERIOD)
        periods.append({"period": p, "rows": rows, "phases": ph})
        # keep the last written time for the restart, drop the rest
        for d in written[:-1]:
            shutil.rmtree(d)
        if p >= 2:
            prev, cur = periods[-2]["phases"], periods[-1]["phases"]
            change = max(max(abs(a["u_axis"] - b["u_axis"]) / U_C,
                             abs(a["dpdx"] - b["dpdx"]) / DPDX_AMPLITUDE)
                         for a, b in zip(prev, cur))
            periods[-1]["change"] = change
            print(f"[{case.name}] period {p}: change {change:.2e}", flush=True)
            if change < PERIODIC_TOL:
                break
        else:
            print(f"[{case.name}] period {p} done", flush=True)
    last = periods[-1]
    ph = last["phases"]
    t = np.array([r["t"] for r in last["rows"]])
    ua = np.array([r["u_axis_exact"] for r in last["rows"]])
    peak, low = last["rows"][int(ua.argmax())], last["rows"][int(ua.argmin())]
    out.update({
        "periods": len(periods), "periodic_change": last.get("change"),
        "inlet_applied_err": inlet_check,
        "phases": [{"t_over_T": round(((r["t"]) / PERIOD) % 1, 4),
                    **{k: r[k] for k in ("profile_max", "profile_rms", "u_axis", "u_axis_exact",
                                         "dpdx", "dpdx_exact")}} for r in ph],
        "peak": {k: peak[k] for k in ("t", "profile_max", "profile_rms", "u_axis", "u_axis_exact")},
        "minimum": {k: low[k] for k in ("t", "profile_max", "profile_rms", "u_axis", "u_axis_exact")},
        "profile_max_all": max(r["profile_max"] for r in [*ph, peak, low]),
        "u_axis_peak": peak["u_axis"], "u_axis_peak_exact": peak["u_axis_exact"],
        "q_err_max": max(abs(r["q"] - r["q_exact"]) / abs(r["q_exact"]) for r in last["rows"]),
        **fit_dpdx(last["rows"]),
        "samples_per_period": len(t),
    })
    return out


def richardson(f1, f2, f3, r=2.0) -> dict:
    """Coarse → fine values f1, f2, f3; observed order, extrapolated value
    and fine-level GCI (celik_and_ghia_etal_2008, safety factor 1.25)."""
    e21, e32 = f2 - f1, f3 - f2
    if e21 == 0 or e32 == 0 or e21 * e32 < 0:
        return {"order": None, "extrapolated": None, "gci_fine": None,
                "note": "non-monotone or exact"}
    order = math.log(abs(e21 / e32)) / math.log(r)
    ext = f3 + (f3 - f2) / (r**order - 1)
    return {"order": order, "extrapolated": ext,
            # relative GCI, or absolute for a quantity whose exact value is 0
            "gci_fine": 1.25 * abs(f3 - f2) / (abs(f3) if abs(f3) > 1e-2 else 1.0) / (r**order - 1)}


def summarise(rows: list[dict]) -> dict:
    space = [r for r in rows if r["dt_factor"] == 1]
    space.sort(key=lambda r: r["factor"])
    out = {}
    if len(space) == 3:
        # The centreline value is sampled at the four faces nearest the
        # axis, which move with the level, so extrapolate its signed error
        # against the exact profile at the same points (exact limit 0), in
        # units of u_c.  The pressure-gradient amplitude is one quantity.
        errs = [(r["u_axis_peak"] - r["u_axis_peak_exact"]) / U_C for r in space]
        rich = richardson(*errs)
        out["u_axis_peak_err"] = {"values": errs, "exact": 0.0, **rich,
                                  "extrapolated_err": rich["extrapolated"]}
        vals = [r["dpdx_amplitude"] for r in space]
        rich = richardson(*vals)
        if rich["extrapolated"] is not None:
            rich["extrapolated_err"] = (rich["extrapolated"] - DPDX_AMPLITUDE) / DPDX_AMPLITUDE
        out["dpdx_amplitude"] = {"values": vals, "exact": DPDX_AMPLITUDE, **rich}
        errs = [r["profile_max_all"] for r in space]
        out["profile_max_all"] = {"values": errs, "orders": [math.log2(a / b) for a, b
                                                             in zip(errs, errs[1:])]}
    for h in (r for r in rows if r["dt_factor"] != 1):
        fine = next((r for r in space if r["level"] == h["level"]), None)
        if fine is None:
            continue
        out[f"time_step_{h['level']}"] = {
            "u_axis_peak_change": abs(h["u_axis_peak"] - fine["u_axis_peak"]) / U_C,
            "space_error_fine": abs(fine["u_axis_peak"] - fine["u_axis_peak_exact"]) / U_C,
            "dpdx_amplitude_change": abs(h["dpdx_amplitude"] - fine["dpdx_amplitude"]) / DPDX_AMPLITUDE,
            "dpdx_amplitude_space_error": abs(fine["dpdx_amplitude_err"]),
        }
        # second order in time: the error at Δt is 4/3 of the change on halving
        out[f"time_step_{h['level']}"]["note"] = "time error at the level's Δt ≈ 4/3 × change"
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--levels", nargs="+", default=list(LEVELS), choices=list(LEVELS))
    ap.add_argument("--dt-halved", nargs="?", const="last", metavar="LEVEL",
                    help="also run LEVEL (default: the finest given) with Δt halved, "
                         "warm-started from its periodic state")
    ap.add_argument("--np", type=int, default=1, help="MPI processes (levels k2 and up)")
    ap.add_argument("--work", type=Path, default=HERE / "work")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--openfoam", default=of.V2406,
                    help="runner: 'native' or 'docker:<image>' (default v2406 in Docker)")
    args = ap.parse_args()
    of.set_runner(args.openfoam)
    import gmsh
    meta = {"date": datetime.date.today().isoformat(),
            "commit": subprocess.run(["git", "describe", "--always", "--dirty"], cwd=HERE,
                                     capture_output=True, text=True).stdout.strip(),
            "gmsh": gmsh.__version__, "openfoam": of.openfoam_version(), "runner": of.runner()}
    print(json.dumps(meta), flush=True)
    # levels already in --json (same level and time step) are reused, so a
    # stopped series resumes; the file is rewritten after every level
    rows = []
    if args.json and args.json.exists():
        rows = json.loads(args.json.read_text())["levels"]

    def save():
        if args.json:
            args.json.write_text(json.dumps({"meta": meta, "levels": rows,
                                             "summary": summarise(rows)}, indent=1))

    def have(name, dt_factor):
        return any(r["level"] == name and r["dt_factor"] == dt_factor for r in rows)

    for name in args.levels:
        if have(name, 1.0):
            print(f"[{name}] reused from {args.json}", flush=True)
            continue
        n = args.np if LEVELS[name] > 1 else 1
        rows.append(run_level(name, LEVELS[name], args.work, n))
        print(json.dumps({k: v for k, v in rows[-1].items() if k != "phases"}), flush=True)
        save()
    name = args.levels[-1] if args.dt_halved == "last" else args.dt_halved
    if args.dt_halved and not have(name, 2.0):
        # warm from the level's periodic state: the time error alone
        rows.append(run_level(name, LEVELS[name], args.work, args.np, dt_factor=2.0,
                              warm_from=args.work / name))
        print(json.dumps({k: v for k, v in rows[-1].items() if k != "phases"}), flush=True)
        save()
    summary = summarise(rows)
    print(json.dumps(summary, indent=1), flush=True)
    save()


if __name__ == "__main__":
    main()
