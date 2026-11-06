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
Laminar flow in a helical pipe: hexmesh's SplinePipe on the SIET coil
(De Amicis et al. 2014), against Ito's correlation (task 0075).

The coil is the one measured at SIET (De Amicis et al. 2014, Table 2):
tube diameter d = 12.53 mm, helix diameter 1 m, pitch 0.8 m per turn
(κa = 0.0118, λ = τ/κ = 0.255).  A ``SplinePipe`` runs through
``PER_TURN`` points per turn of the exact helix, clamped to the helix
tangent at both ends.  A short straight before it carries a Poiseuille
inlet profile.

Steady laminar ``simpleFoam`` at Re = U_b d / ν = 1800, 2400 and 3000.
That is De = Re √(r/R) = 201, 269 and 336, inside the paper's measured
laminar range (Re ≈ 1750–3200).

The friction factor comes from turn-averaged pressures.  With the flow
developed, p = P(s) + F(section position), with F the same at every
turn (helical symmetry).  So the volume mean of p over one turn of cells
minus the mean over the next is the pressure drop over one turn length
L_turn, and f_D = Δp d / (L_turn · ½ U_b²).  f is reported for every
pair of consecutive turns, so the development is visible.  The gated
value is the pair ``GATED_PAIR``, away from the inlet and the outlet.

Gates (design answer to Q2, fixed before the runs): f within 5 % of Ito
(1959) at each Re, at the finest level; f converging (task 0089) at each
Re; the spline within 0.1 % of d of the helix.  The digitised measured
points of the paper's Fig. 12 (``data/``) are reported, not gated.

Run:   python3 validation/helical_pipe/run.py --np 4
Recheck: python3 -m validation.tools.recheck helical_pipe
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import math
import re
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from hexmesh import Assembly, PipeSpec, Session, SplinePipe, Straight  # noqa: E402
from hexmesh.assembly.fittings import _cubic_spline                     # noqa: E402
from hexmesh.study import openfoam as of                                # noqa: E402

_spec = importlib.util.spec_from_file_location("convergence",
                                               ROOT / "validation/tools/convergence.py")
conv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conv)       # richardson() (task 0089)
_spec = importlib.util.spec_from_file_location("stored", ROOT / "validation/tools/results.py")
stored = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stored)                # results.json (task 0093)

# --- the SIET coil (De Amicis et al. 2014, Table 2) ---------------------------
D = 12.53e-3                  # tube inner diameter [m]
A = D / 2
R_C = 0.5                     # helix radius [m]
B = 0.8 / (2 * math.pi)       # pitch per radian [m/rad]
TURNS = 4
PER_TURN = 32                 # spline points per turn (Agent notes: 3.4e-4 d)
L_TURN = math.hypot(2 * math.pi * R_C, 2 * math.pi * B)   # centreline per turn [m]
L_IN = 5 * D                  # the straight before the coil
U_B = 1.0                     # bulk velocity [m/s]
RES = (1800, 2400, 3000)
GATED_PAIR = 1                # turns 2 → 3 (0-based pair index)
DEV_LIMIT = 1e-3              # spline deviation gate, in d
F_LIMIT = 0.05                # f against Ito

# --- the levels: nang, with the axial layers scaled alike -------------------
LEVELS = (8, 12, 16)
LAYERS_PER_TURN = {8: 130, 12: 195, 16: 260}        # about 2, 1.33, 1 d per layer
LAYERS_IN = {8: 3, 12: 4, 16: 6}

DATA = HERE / "data" / "deamicis_2014_fig12.csv"


def helix(th):
    th = np.asarray(th, dtype=float)
    return np.stack([R_C * np.cos(th), R_C * np.sin(th), B * th], -1)


def _d1(th):
    th = np.asarray(th, dtype=float)
    return np.stack([-R_C * np.sin(th), R_C * np.cos(th), B * np.ones_like(th)], -1)


def _d2(th):
    th = np.asarray(th, dtype=float)
    return np.stack([-R_C * np.cos(th), -R_C * np.sin(th), np.zeros_like(th)], -1)


def tangent(th: float) -> np.ndarray:
    t = _d1(th)
    return t / np.linalg.norm(t)


def project(p: np.ndarray, th0: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(θ of the nearest helix point, the distance to it) for points *p*,
    by Newton on |helix(θ) − p|², from *th0* (else atan2, unwrapped by z)."""
    if th0 is None:
        phi = np.arctan2(p[:, 1], p[:, 0])
        th0 = phi + 2 * np.pi * np.round((p[:, 2] / B - phi) / (2 * np.pi))
    th = np.array(th0, dtype=float)
    for _ in range(30):
        r = helix(th) - p
        g = np.sum(r * _d1(th), -1)
        h = np.sum(_d1(th) ** 2, -1) + np.sum(r * _d2(th), -1)
        th -= g / h
    return th, np.linalg.norm(helix(th) - p, axis=-1)


def spline_points(per_turn: int = PER_TURN) -> np.ndarray:
    return helix(np.linspace(0, 2 * np.pi * TURNS, TURNS * per_turn + 1))


def spline_deviation(per_turn: int = PER_TURN, n: int = 100001) -> dict:
    """The largest distance, in d, of hexmesh's spline (``_cubic_spline``,
    clamped as ``SplinePipe`` clamps it) from the exact helix."""
    T = 2 * np.pi * TURNS
    curve = _cubic_spline(spline_points(per_turn), tangent(0.0), tangent(T))
    u = np.linspace(0, 1, n)
    _, dist = project(curve(u)[0], u * T)
    inner = (u > 0.1) & (u < 0.9)
    return {"points_per_turn": per_turn, "max_over_d": float(dist.max() / D),
            "interior_max_over_d": float(dist[inner].max() / D),
            "chord_sag_over_d": {str(nang): float((L_TURN / LAYERS_PER_TURN[nang]) ** 2
                                                  * (R_C / (R_C ** 2 + B ** 2)) / 8 / D)
                                 for nang in LEVELS}}


def assembly(nang: int = LEVELS[0]) -> Assembly:
    spec = PipeSpec(nang=nang).core("fluid", radius=A, nrad=nang // 2)
    t0, T = tangent(0.0), 2 * np.pi * TURNS
    asm = Assembly(spec, position=list(helix(0.0) - L_IN * t0), direction=list(t0),
                   up=[1.0, 0.0, 0.0])
    asm.add(Straight(L_IN, n_layers=LAYERS_IN[nang]))
    asm.add(SplinePipe(tuple(map(tuple, spline_points())), n_layers=TURNS * LAYERS_PER_TURN[nang],
                       end_tangent=tuple(tangent(T))))
    return asm


def meshes():
    """(label, caption, build) per mesh shown in README.md."""
    return [(f"n{n}", f"nang {n}, {LAYERS_PER_TURN[n]} layers per turn",
             lambda n=n: assembly(n)) for n in LEVELS[:2]]


def ito(re_: float) -> float:
    """Ito (1959), as De Amicis et al. (2014) eq. (2): f_c / f_s =
    21.5 De / (1.56 + log10 De)^5.73, De = Re √(r/R), f_s = 64/Re."""
    de = re_ * math.sqrt(A / R_C)
    return 64 / re_ * 21.5 * de / (1.56 + math.log10(de)) ** 5.73


def read_data(path: Path = DATA) -> list[dict]:
    if not path.exists():
        return []
    rows = csv.DictReader(line for line in path.open(encoding="utf-8")
                          if not line.startswith("#"))
    return [{k: float(v) for k, v in r.items()} for r in rows]


# --- OpenFOAM dictionaries ---------------------------------------------------

HDR = of.header

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
timeFormat      general;
runTimeModifiable false;
"""

SCHEMES = """ddtSchemes      { default steadyState; }
gradSchemes     { default Gauss linear; }
divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss linearUpwind grad(U);
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }
"""

SOLUTION = """solvers
{
    p
    {
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-10;
        relTol          0.05;
    }
    U
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-12;
        relTol          0.1;
    }
}
SIMPLE
{
    nNonOrthogonalCorrectors 1;
    consistent      yes;
    residualControl
    {
        p               1e-7;
        U               1e-8;
    }
}
relaxationFactors
{
    equations       { U 0.9; ".*" 0.9; }
}
"""

# the Poiseuille profile at the inlet, about its centre c along its normal t
U0 = """dimensions      [0 1 -1 0 0 0 0];
internalField   uniform (0 0 0);
boundaryField
{{
    fluid_inlet
    {{
        type            uniformFixedValue;
        uniformValue
        {{
            type        expression;
            expression  "{u2}*max(0, 1 - magSqr((pos() - {c}) - ((pos() - {c}) & {t})*{t})/{a2})*{t}";
        }}
    }}
    fluid_outlet    {{ type zeroGradient; }}
    fluid_wall      {{ type noSlip; }}
}}
"""

P0 = """dimensions      [0 2 -2 0 0 0 0];
internalField   uniform 0;
boundaryField
{
    fluid_inlet     { type zeroGradient; }
    fluid_outlet    { type fixedValue; value uniform 0; }
    fluid_wall      { type zeroGradient; }
}
"""


def _vec(v) -> str:
    return "vector({!r}, {!r}, {!r})".format(*map(float, v))


def write_case(case: Path, re_: float, end_time: int) -> None:
    for d in ("0", "constant", "system"):
        (case / d).mkdir(parents=True, exist_ok=True)
    t0 = tangent(0.0)
    files = {
        "system/controlDict": HDR("dictionary", "controlDict", "system")
        + CONTROL.format(end_time=end_time),
        "system/fvSchemes": HDR("dictionary", "fvSchemes", "system") + SCHEMES,
        "system/fvSolution": HDR("dictionary", "fvSolution", "system") + SOLUTION,
        "constant/transportProperties": HDR("dictionary", "transportProperties", "constant")
        + f"transportModel  Newtonian;\nnu              {U_B * D / re_!r};\n",
        "constant/turbulenceProperties": HDR("dictionary", "turbulenceProperties", "constant")
        + "simulationType  laminar;\n",
        "0/U": HDR("volVectorField", "U", "0") + U0.format(
            u2=repr(2 * U_B), c=_vec(helix(0.0) - L_IN * t0), t=_vec(t0), a2=repr(A * A)),
        "0/p": HDR("volScalarField", "p", "0") + P0,
    }
    for name, text in files.items():
        (case / name).write_text(text, encoding="utf-8")


# --- post-processing -----------------------------------------------------------

def _fields(case: Path):
    mesh = case / "constant/polyMesh"
    pts, faces = of.read_points(mesh / "points"), of.read_faces(mesh / "faces")
    owner, neigh = of.read_labels(mesh / "owner"), of.read_labels(mesh / "neighbour")
    t = of.latest_time(case)
    p = of.read_internal(t / "p", 1).ravel()
    U = of.read_internal(t / "U", 3)
    fc, sf = of.face_geometry(pts, faces)
    cc, vol = of.cell_geometry(fc, sf, owner, neigh, len(p))
    return cc, vol, p, U


def friction(cc, vol, p, U) -> dict:
    """Turn means of p and of the velocity along the helix tangent
    (volume-weighted, cells binned by the θ of their nearest helix point),
    and f_D per pair of consecutive turns.  The tangential mean over a
    turn is the bulk velocity u_b the mesh carries (Q / A for a uniform
    section): the faceted section is smaller than πa², and the inlet
    parabola is set at face centres, so u_b exceeds U_B by about 1 %.
    f_D = Δp d / (L_turn ½ u_b²), with u_b the mean over the pair's two
    turns, and Re = u_b d / ν: the flow the mesh carries."""
    th, _ = project(cc)
    ut = np.einsum("ij,ij->i", U, _d1(th) / np.linalg.norm(_d1(th), axis=1)[:, None])
    means, bulk = [], []
    for k in range(TURNS):
        m = (th >= 2 * np.pi * k) & (th < 2 * np.pi * (k + 1))
        means.append(float(np.sum(p[m] * vol[m]) / np.sum(vol[m])))
        bulk.append(float(np.sum(ut[m] * vol[m]) / np.sum(vol[m])))
    ub = [0.5 * (bulk[k] + bulk[k + 1]) for k in range(TURNS - 1)]
    f = [(means[k] - means[k + 1]) * D / (L_TURN * 0.5 * ub[k] ** 2) for k in range(TURNS - 1)]
    return {"turn_mean_p": means, "u_bulk_per_turn": bulk, "u_bulk_per_pair": ub,
            "f_per_pair": f}


def run_level(re_: float, nang: int, work: Path, end_time: int, n_proc: int) -> dict:
    case = work / f"re{re_}_n{nang}"
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    asm = assembly(nang)
    with Session(f"helix-{re_}-{nang}"):
        cells = asm.cell_count()
        print(f"[re={re_} nang={nang}] predicted cells: {cells}", flush=True)
        msh = case / "mesh.msh"
        asm.write_openfoam(str(msh))
        sj = asm.check_quality("scaled_jacobian").worst
    write_case(case, re_, end_time)
    of.convert(case, msh, keep_orientation=sj > 0)
    check = of.check_mesh(case)
    log = of.run_solver(case, "simpleFoam", n_proc=n_proc)
    steps = re.findall(r"^Time = (\d+)", log, re.M)
    cc, vol, p, U = _fields(case)
    fr = friction(cc, vol, p, U)
    f = fr["f_per_pair"][GATED_PAIR]
    re_b = re_ * fr["u_bulk_per_pair"][GATED_PAIR] / U_B         # ν = U_B d / re_
    return {"re": re_, "nang": nang, "cells": cells, "layers_per_turn": LAYERS_PER_TURN[nang],
            "min_scaled_jacobian": sj, **stored.counts(asm),
            **{f"check_{k}": v for k, v in check.items()},
            "steps": int(steps[-1]) if steps else 0,
            "converged": "solution converged in" in log,
            **fr, "re_bulk": re_b, "f": f, "f_ito": ito(re_b), "f_err_ito": f / ito(re_b) - 1,
            "fc_over_fs": f / (64 / re_b),
            "turn_agreement": fr["f_per_pair"][-1] / fr["f_per_pair"][GATED_PAIR] - 1}


# --- analysis -----------------------------------------------------------------

def analyse(levels: list[dict]) -> dict:
    """Richardson on f at each Re (nang 8, 12, 16: ratios 1.5, 4/3)."""
    out = {}
    for re_ in RES:
        rows = sorted((r for r in levels if r["re"] == re_), key=lambda r: r["nang"])
        if [r["nang"] for r in rows] == list(LEVELS):
            out[str(re_)] = conv.richardson(*(r["f"] for r in rows),
                                            r21=LEVELS[2] / LEVELS[1], r32=LEVELS[1] / LEVELS[0])
    return out


def table(levels: list[dict]) -> str:
    lines = ["| Re | nang | cells | f per turn pair | f (gated pair) | Ito | vs Ito | "
             "fc/fs | steps |", "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(levels, key=lambda r: (r["re"], r["nang"])):
        pairs = ", ".join(f"{x:.5f}" for x in r["f_per_pair"])
        lines.append(f"| {r['re']} | {r['nang']} | {r['cells']} | {pairs} | {r['f']:.5f} | "
                     f"{r['f_ito']:.5f} | {r['f_err_ito']:+.2%} | {r['fc_over_fs']:.3f} | "
                     f"{r['steps']} |")
    return "\n".join(lines)


def recheck(data: dict) -> list[dict]:
    """The gates from ``results.json`` (task 0075, design answer Q2): the
    spline within 0.1 % of d of the helix; at each Re, f converging and,
    at the finest level, within 5 % of Ito.  The digitised measured
    points (Fig. 12) and the turn-to-turn agreement are reported."""
    dev = data["extra"]["spline_deviation"]
    out = [stored.row(f"spline vs helix, {dev['points_per_turn']} points per turn",
                      gate=f"within {DEV_LIMIT:.1%} of d", ok=dev["max_over_d"] <= DEV_LIMIT,
                      value=f"{dev['max_over_d']:.2e} d")]
    rich = analyse(data["levels"])
    for re_ in RES:
        r = rich.get(str(re_))
        if r is not None:
            out.append(stored.row(f"Re {re_}: f (nang 8, 12, 16)", rich=r, gate="converging",
                                  ok=r["status"] == "converging",
                                  value=f"GCI {r['gci_fine']:.2%}" if r["gci_fine"] is not None
                                  else r["status"], note=r["note"]))
        rows = [lv for lv in data["levels"] if lv["re"] == re_]
        if rows:
            lv = max(rows, key=lambda x: x["nang"])
            out.append(stored.row(f"Re {re_}: f (nang {lv['nang']})",
                                  gate=f"within {F_LIMIT:.0%} of Ito",
                                  ok=abs(lv["f_err_ito"]) <= F_LIMIT,
                                  value=f"{lv['f_err_ito']:+.2%}",
                                  note=f"turns 3→4 vs 2→3: {lv['turn_agreement']:+.2%}"))
    return out


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--res", nargs="+", type=int, default=list(RES))
    ap.add_argument("--levels", nargs="+", type=int, default=list(LEVELS))
    ap.add_argument("--work", type=Path, default=HERE / "work")
    ap.add_argument("--end-time", type=int, default=5000)
    ap.add_argument("--np", type=int, default=1, dest="n_proc",
                    help="MPI processes per solve (check other runs first, CLAUDE.md)")
    stored.add_arguments(ap, HERE)
    ap.add_argument("--openfoam", default=of.V2406,
                    help="runner: native, or docker:IMAGE (default: v2406 in Docker)")
    args = ap.parse_args(argv)
    of.set_runner(args.openfoam)
    store = stored.Store(args.json, "helical_pipe")
    store.put_extra("reference", "De Amicis et al. (2014), the SIET coil; Ito (1959) as their eq. (2)")
    store.put_extra("spline_deviation", spline_deviation())
    for re_ in args.res:
        for nang in args.levels:
            r = stored.run_level(store, f"re{re_}_n{nang}",
                                 lambda re_=re_, nang=nang: run_level(
                                     re_, nang, args.work, args.end_time, args.n_proc),
                                 args.work / f"re{re_}_n{nang}", args.keep_work)
            print(table([r]), flush=True)
    rich = analyse(store.levels())
    store.put_extra("richardson_f", rich)
    print(table(store.levels()), flush=True)
    return rich


if __name__ == "__main__":
    main()
