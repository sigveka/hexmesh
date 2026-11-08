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
Laminar flow through a 90° square-duct bend against the LDV measurements of
Taylor, Whitelaw & Yianneskis (1981), Re 790 (decision 0012, V3; task 0072).

    python3 validation/square_bend/run.py               # k = 1, 2, 3
    python3 validation/square_bend/run.py --levels 1 --np 4

**The rig** (NASA CR-3367, figs. 1–2): a 40 mm square duct, a 90° bend of
inner radius 72 mm and outer 112 mm (mean 92 mm, radius ratio 2.3), 0.3 m
(7.5 D_h) of straight duct from the contraction to the bend, and 2 m
downstream.  Bulk velocity V_c = 0.0198 m/s; Re = V_c D_h / ν = 790.

**The model.**  A plug inlet upstream of the bend, at the distance whose
developing profile best matches the measured one at X_H = −0.50
(:func:`match_inlet`, in a straight duct at k = 2; the task's "developed
inlet matched to the measured upstream profile").  The rig's own length,
7.5 D_h from the contraction, gives profiles that are too flat: the
boundary layers start inside the honeycomb and contraction.
10 D_h downstream to a zero-pressure outlet.  hexmesh's H section
(``layout="h"``, decision 0036) graded to the walls (``first_cell``).
Laminar steady ``simpleFoam``.

**The comparison** (``data/taylor_1981_table1.csv``, Table I transcribed
from the report's page images): U/V_c at every measured point of the 8
stations, interpolated from the cell centres (linear, in 3-D), and the
RMS difference per station; V/V_c where measured; the gapwise position of
the peak U on the symmetry plane.  Levels k = 1, 2, 3 (ratios 2 and 1.5):
GCI on the peak U on the symmetry plane at θ = 60° and 77.5°.

OpenFOAM v2406 in Docker by default.
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

from hexmesh import Assembly, Bend, PipeSpec, Session, Straight      # noqa: E402
from hexmesh.study import openfoam as of                             # noqa: E402

_spec = importlib.util.spec_from_file_location("convergence",
                                               ROOT / "validation/tools/convergence.py")
conv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conv)       # richardson() (task 0089)
_spec = importlib.util.spec_from_file_location("stored", ROOT / "validation/tools/results.py")
stored = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stored)                # results.json (task 0093)

# --- the rig -------------------------------------------------------------------
D = 0.040                     # side = hydraulic diameter [m]
H = D / 2
R_I, R_O = 0.072, 0.112       # bend radii [m]
R_MEAN = 0.5 * (R_I + R_O)
L_UP = 0.3                    # contraction exit → bend entry [m]
L_DOWN = 10 * D               # bend exit → outlet [m]
V_C = 0.0198                  # bulk velocity [m/s]
RE = 790
NU = V_C * D / RE
DATA = HERE / "data/taylor_1981_table1.csv"

# --- the mesh at k = 1 ---------------------------------------------------------
N = 12                        # cells per side
FIRST_CELL = D / 120          # wall cell, every side
AXIAL = {"up": 45, "bend": 24, "down": 60}
LEVELS = (1, 2, 3)
#: the stations whose peak U on the symmetry plane gets a GCI
GCI_STATIONS = ("theta=60", "theta=77.5")


def _spec() -> PipeSpec:
    return PipeSpec(nang_w=N, nang_h=N).core("fluid", half_w=H, half_h=H, layout="h",
                                             first_cell=FIRST_CELL)


def assembly(k: int = 1, l_up: float = L_UP) -> Assembly:
    """The rig at level *k*, with *l_up* of straight duct from the plug inlet
    to the bend (the axial count scaled with it)."""
    asm = Assembly(_spec(), position=[-l_up, 0, 0], direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(l_up, n_layers=max(1, round(AXIAL["up"] * l_up / L_UP))))
    asm.add(Bend(R_MEAN, 90, n_layers=AXIAL["bend"]))              # toward +z
    asm.add(Straight(L_DOWN, n_layers=AXIAL["down"]))
    return asm if k == 1 else asm.refined(k)


def meshes():
    """(label, caption, build) per mesh shown in README.md."""
    return [(f"k{k}", f"k = {k}: {N * k} cells per side", lambda k=k: assembly(k))
            for k in (1, 2)]


# --- the stations ------------------------------------------------------------------
# The bend entry is at the origin, the duct along +x, turning toward +z
# about the centre C = (0, 0, R_MEAN).  r is the distance from the bend's
# axis; the gapwise coordinate g = (r − r_o)/(r_i − r_o) runs from the outer
# wall (0) to the inner (1); the span z/z½ runs along y from the symmetry
# plane.

def station_frame(station: str):
    """(point(r, s), streamwise unit vector, gapwise unit vector toward the
    inner wall) at *station* ("xh=-0.50", "theta=30", "xh=+0.25")."""
    kind, value = station.split("=")
    v = float(value)
    c = np.array([0.0, 0.0, R_MEAN])
    if kind == "theta":
        th = math.radians(v)
        out = np.array([math.sin(th), 0.0, -math.cos(th)])         # from C to the outer wall
        t = np.array([math.cos(th), 0.0, math.sin(th)])            # streamwise
        return (lambda r, s: c + r * out + s * np.array([0, 1.0, 0])), t, -out
    if v < 0:                                   # upstream: x = X_H · D before the entry
        x = v * D
        return (lambda r, s: np.array([x, s, R_MEAN - r])), np.array([1.0, 0, 0]), \
            np.array([0, 0, 1.0])
    # downstream of the exit (θ = 90°): the duct along +z, the outer wall at +x
    zz = R_MEAN + v * D
    return (lambda r, s: np.array([r, s, zz])), np.array([0, 0, 1.0]), np.array([-1.0, 0, 0])


def read_data(path: Path = DATA) -> dict[str, list[dict]]:
    rows = list(csv.DictReader(line for line in path.open(encoding="utf-8")
                               if not line.startswith("#")))
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["station"], []).append(
            {"z": float(r["z"]), "gap": float(r["gap"]), "U": float(r["U"]),
             "V": float(r["V"]) if r["V"] else None})
    return out


def station_points(station: str, rows: list[dict]):
    point, t, g = station_frame(station)
    pts = np.array([point(R_O + r["gap"] * (R_I - R_O), r["z"] * H) for r in rows])
    return pts, t, g


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

U0 = """dimensions      [0 1 -1 0 0 0 0];
internalField   uniform ({u} 0 0);
boundaryField
{{
    fluid_inlet     {{ type fixedValue; value uniform ({u} 0 0); }}
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


def write_case(case: Path, end_time: int) -> None:
    for d in ("0", "constant", "system"):
        (case / d).mkdir(parents=True, exist_ok=True)
    files = {
        "system/controlDict": HDR("dictionary", "controlDict", "system")
        + CONTROL.format(end_time=end_time),
        "system/fvSchemes": HDR("dictionary", "fvSchemes", "system") + SCHEMES,
        "system/fvSolution": HDR("dictionary", "fvSolution", "system") + SOLUTION,
        "constant/transportProperties": HDR("dictionary", "transportProperties", "constant")
        + f"transportModel  Newtonian;\nnu              {NU!r};\n",
        "constant/turbulenceProperties": HDR("dictionary", "turbulenceProperties", "constant")
        + "simulationType  laminar;\n",
        "0/U": HDR("volVectorField", "U", "0") + U0.format(u=repr(V_C)),
        "0/p": HDR("volScalarField", "p", "0") + P0,
    }
    for name, text in files.items():
        (case / name).write_text(text, encoding="utf-8")


# --- post-processing -----------------------------------------------------------

def _sample(cc: np.ndarray, U: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """U at *pts*, linear in the Delaunay tetrahedra of the 40 cell centres
    nearest each."""
    from scipy.interpolate import LinearNDInterpolator
    from scipy.spatial import cKDTree
    near = np.unique(cKDTree(cc).query(pts, k=40)[1])
    return LinearNDInterpolator(cc[near], U[near])(pts)


def compare(cc: np.ndarray, U: np.ndarray, data: dict) -> dict:
    out = {}
    for station, rows in data.items():
        pts, t, g = station_points(station, rows)
        u = _sample(cc, U, pts)
        us, vs = u @ t / V_C, u @ g / V_C
        meas = np.array([r["U"] for r in rows])
        ok = np.isfinite(us)
        dv = [(vs[i], r["V"]) for i, r in enumerate(rows) if r["V"] is not None and ok[i]]
        sym = [i for i, r in enumerate(rows) if r["z"] == 0.0]
        # the measured values scaled to carry the computed flux through the
        # same points (a diagnostic: at k = 3 the measured grid carries
        # 0-3 % more than the computed field, task 0072 Agent notes)
        scale = grid_flux(rows, us) / grid_flux(rows, meas) if ok.all() else None
        gaps = np.array([rows[i]["gap"] for i in sym])
        out[station] = {
            "points": int(ok.sum()),
            "u_rms_diff": float(np.sqrt(np.mean((us[ok] - meas[ok]) ** 2))),
            "u_max_abs_diff": float(np.max(np.abs(us[ok] - meas[ok]))),
            "measured_grid_flux": grid_flux(rows, meas),
            "computed_grid_flux": grid_flux(rows, us) if ok.all() else None,
            "u_rms_diff_flux_matched": float(np.sqrt(np.mean((us - scale * meas) ** 2)))
            if scale else None,
            "v_rms_diff": float(np.sqrt(np.mean([(a - b) ** 2 for a, b in dv]))) if dv else None,
            "u": [None if not np.isfinite(v) else float(v) for v in us],
            "v": [None if not np.isfinite(v) else float(v) for v in vs],
            "peak_gap_measured": float(gaps[np.argmax(meas[sym])]),
            "peak_gap_computed": float(gaps[np.nanargmax(us[sym])]),
            "peak_u_symmetry": peak_on_symmetry(cc, U, station),
        }
    return out


def grid_flux(rows: list[dict], u) -> float:
    """∫∫ U/V_c over the half section by the trapezoid rule on the
    measured grid (gap 0.1–0.9, z/z½ 0–0.9), U = 0 at the walls: about
    0.9 for these profiles, whose true value is 1, so compare it between
    measurement and computation, not with 1."""
    gi = {0.1: 1, 0.3: 2, 0.5: 3, 0.7: 4, 0.9: 5}
    G = np.zeros((7, 11))
    for r, v in zip(rows, u):
        G[gi[r["gap"]], int(round(r["z"] * 10))] = v
    g = np.array([0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0])
    z = np.r_[np.arange(10) / 10, 1.0]
    return float(np.trapz(np.trapz(G, z, axis=1), g))


def peak_on_symmetry(cc: np.ndarray, U: np.ndarray, station: str, n: int = 81) -> float:
    """The largest U/V_c along the gap on the symmetry plane (fine line)."""
    point, t, _ = station_frame(station)
    g = np.linspace(0.02, 0.98, n)
    pts = np.array([point(R_O + x * (R_I - R_O), 0.0) for x in g])
    return float(np.nanmax(_sample(cc, U, pts) @ t / V_C))


def run_level(k: int, work: Path, end_time: int, n_proc: int, l_up: float = L_UP,
              inlet: str = "rig") -> dict:
    case = work / f"{inlet}_k{k}"
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    asm = assembly(k, l_up)
    with Session(f"square-bend-{k}"):
        cells = asm.cell_count()
        print(f"[k={k}] predicted cells: {cells}", flush=True)
        msh = case / "mesh.msh"
        asm.write_openfoam(str(msh))
        sj = asm.check_quality("scaled_jacobian").worst
    write_case(case, end_time)
    of.convert(case, msh, keep_orientation=sj > 0)
    check = of.check_mesh(case)
    log = of.run_solver(case, "simpleFoam", n_proc=n_proc)
    steps = re.findall(r"^Time = (\d+)", log, re.M)
    cc, U = _fields(case)
    return {"k": k, "inlet": inlet, "cells": cells, "l_up": l_up, "min_scaled_jacobian": sj,
            **stored.counts(asm),
            **{f"check_{key}": v for key, v in check.items()},
            "steps": int(steps[-1]) if steps else 0,
            "converged": "solution converged in" in log,
            "stations": compare(cc, U, read_data())}


# --- the inlet: the development length matched to X_H = -0.50 ----------------
MATCH_STATION = "xh=-0.50"
MATCH_LENGTH = 40 * D           # the straight duct the match is made in
INLET_K = 2                     # its level: one inlet for every level of the study


def inlet_assembly(k: int) -> Assembly:
    """The straight duct :func:`match_inlet` solves in, at level *k*."""
    asm = Assembly(_spec(), position=[0, 0, 0], direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(MATCH_LENGTH, n_layers=round(AXIAL["up"] * MATCH_LENGTH / L_UP)))
    return asm if k == 1 else asm.refined(k)


def match_inlet(k: int, work: Path, end_time: int, n_proc: int) -> dict:
    """Developing flow from a plug inlet in a straight duct: the distance
    x* from the inlet whose U profile best matches *MATCH_STATION* (least
    RMS difference, parabola through the best three of 0.25 D steps).
    The rig's plug inlet then sits x* + 0.5 D upstream of the bend."""
    case = work / f"inlet_k{k}"
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    asm = inlet_assembly(k)
    with Session(f"square-bend-inlet-{k}"):
        msh = case / "mesh.msh"
        asm.write_openfoam(str(msh))
        sj = asm.check_quality("scaled_jacobian").worst
    write_case(case, end_time)
    of.convert(case, msh, keep_orientation=sj > 0)
    log = of.run_solver(case, "simpleFoam", n_proc=n_proc)
    cc, U = _fields(case)
    data = read_data()
    rows = data[MATCH_STATION]
    meas = np.array([r["U"] for r in rows])
    rel = np.array([[0.0, r["z"] * H, R_MEAN - (R_O + r["gap"] * (R_I - R_O))] for r in rows])
    xs = np.arange(2.0, 35.01, 0.25) * D
    rms = []
    for x in xs:
        u = _sample(cc, U, rel + [x, 0, 0])[:, 0] / V_C
        rms.append(float(np.sqrt(np.mean((u - meas) ** 2))))
    i = int(np.clip(np.argmin(rms), 1, len(xs) - 2))
    a, b, c = np.polyfit(xs[i - 1:i + 2], rms[i - 1:i + 2], 2)
    x_star = float(-b / (2 * a))
    # the check: the same field 0.25 D further on against X_H = -0.25
    r25 = data["xh=-0.25"]
    m25 = np.array([r["U"] for r in r25])
    p25 = np.array([[x_star + 0.25 * D, r["z"] * H, R_MEAN - (R_O + r["gap"] * (R_I - R_O))]
                    for r in r25])
    u25 = _sample(cc, U, p25)[:, 0] / V_C
    return {"k": k, "converged": "solution converged in" in log, "x_star": x_star,
            "x_star_over_D": x_star / D, "l_up": x_star + 0.5 * D,
            "rms_at_x_star": float(np.interp(x_star, xs, rms)),
            "rms_at_rig_length": float(np.interp(L_UP - 0.5 * D, xs, rms)),
            "check_xh_m025_rms": float(np.sqrt(np.nanmean((u25 - m25) ** 2))),
            "rms_curve": {"x_over_D": (xs / D).tolist(), "rms": rms}}


def _fields(case: Path):
    mesh = case / "constant/polyMesh"
    pts, faces = of.read_points(mesh / "points"), of.read_faces(mesh / "faces")
    owner, neigh = of.read_labels(mesh / "owner"), of.read_labels(mesh / "neighbour")
    U = of.read_internal(of.latest_time(case) / "U", 3)
    fc, sf = of.face_geometry(pts, faces)
    cc, _ = of.cell_geometry(fc, sf, owner, neigh, len(U))
    return cc, U


# --- analysis -----------------------------------------------------------------

# The inlets (task 0072, design answer to Q3): the plug matched to
# X_H = -0.50 alone is gated, from X_H = -0.25 on (X_H = -0.50 is its
# calibration station, reported); the rig's plug at 7.5 D_h is a reported
# sensitivity.
INLETS = ("matched", "rig")
GATED_INLET = "matched"


def analyse(levels: list[dict], inlet: str = "rig") -> dict:
    rows = sorted((r for r in levels if r["inlet"] == inlet), key=lambda r: r["k"])
    out = {}
    if [r["k"] for r in rows] == list(LEVELS):
        ks = [r["k"] for r in rows]
        for st in GCI_STATIONS:
            vals = [r["stations"][st]["peak_u_symmetry"] for r in rows]
            out[st] = conv.richardson(*vals, r21=ks[2] / ks[1], r32=ks[1] / ks[0])
    return out


def table(row: dict) -> str:
    lines = [f"k = {row['k']} ({row['cells']} cells)", "",
             "| station | U RMS diff / V_c | max | flux-matched RMS | V RMS diff | "
             "peak g measured | computed |", "|---|---|---|---|---|---|---|"]
    for st, s in row["stations"].items():
        v = f"{s['v_rms_diff']:.3f}" if s["v_rms_diff"] is not None else "—"
        fm = s["u_rms_diff_flux_matched"]
        fm = f"{fm:.3f}" if fm is not None else "—"
        lines.append(f"| {st} | {s['u_rms_diff']:.3f} | {s['u_max_abs_diff']:.3f} | {fm} | {v} | "
                     f"{s['peak_gap_measured']:.1f} | {s['peak_gap_computed']:.1f} |")
    return "\n".join(lines)


def recheck(data: dict) -> list[dict]:
    """The gates from ``results.json`` (task 0072, design answers Q1-Q3),
    on the matched inlet: the peak U's mesh convergence at GCI_STATIONS,
    and at the finest level the peak's gapwise position on the symmetry
    plane at every station from X_H = -0.25 on, which carries its outward
    shift through the bend.  Reported: the calibration station
    (MATCH_STATION), the U/V_c RMS against the measurements (5 %), and
    the rig inlet's same checks."""
    out = []
    for inlet in INLETS:
        gated = inlet == GATED_INLET
        for st, r in analyse(data["levels"], inlet).items():
            out.append(stored.row(f"{inlet} inlet: peak U/V_c on the symmetry plane, {st} "
                                  "(k = 1, 2, 3)", rich=r,
                                  gate="converging, as measured" if gated else None,
                                  ok=r["status"] == "converging" if gated else None,
                                  value=f"GCI {r['gci_fine']:.2%}" if r["gci_fine"] is not None
                                  else r["status"], note=r["note"]))
        fine = max(stored.series(data, inlet=inlet), key=lambda r: r["k"])
        for st, s in fine["stations"].items():
            g = gated and st != MATCH_STATION
            hit = s["peak_gap_computed"] == s["peak_gap_measured"]
            out.append(stored.row(f"{inlet} inlet, {st}: peak position on the symmetry plane "
                                  f"(k = {fine['k']})",
                                  gate="at the measured gapwise point" if g else None,
                                  ok=hit if g else None,
                                  value=f"g = {s['peak_gap_computed']:.1f} "
                                        f"(measured {s['peak_gap_measured']:.1f})",
                                  note="" if g else ("calibration station" if gated else
                                                     "sensitivity: " + ("at" if hit else "off")
                                                     + " the measured point")))
        for st, s in fine["stations"].items():
            out.append(stored.row(f"{inlet} inlet, {st}: U/V_c RMS difference (k = {fine['k']})",
                                  value=f"{s['u_rms_diff']:.3f}",
                                  note="5 % comparison: " +
                                       ("within" if s["u_rms_diff"] <= 0.05 else "missed")))
    return out


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--levels", nargs="+", type=int, default=list(LEVELS))
    ap.add_argument("--inlets", nargs="+", choices=INLETS, default=list(INLETS))
    ap.add_argument("--work", type=Path, default=HERE / "work")
    ap.add_argument("--end-time", type=int, default=5000)
    ap.add_argument("--np", type=int, default=1, dest="n_proc",
                    help="MPI processes per solve (check other runs first, CLAUDE.md)")
    stored.add_arguments(ap, HERE)
    ap.add_argument("--openfoam", default=of.V2406,
                    help="runner: native, or docker:IMAGE (default: v2406 in Docker)")
    args = ap.parse_args(argv)
    of.set_runner(args.openfoam)
    store = stored.Store(args.json, "square_bend")
    store.put_extra("reference", "Taylor, Whitelaw & Yianneskis (1981), NASA CR-3367, Table I")
    match = store.data["extra"].get("inlet")
    if match is None:
        match = match_inlet(INLET_K, args.work, args.end_time, args.n_proc)
        store.put_extra("inlet", match)
        if not args.keep_work:
            stored.remove_work(args.work / f"inlet_k{INLET_K}")
    print(f"matched inlet: plug {match['l_up'] / D:.2f} D_h upstream of the bend (to "
          f"{MATCH_STATION}: RMS {match['rms_at_x_star']:.3f})", flush=True)
    l_ups = {"rig": L_UP, "matched": match["l_up"]}
    for inlet in args.inlets:
        for k in args.levels:
            r = stored.run_level(store, f"{inlet}_k{k}",
                                 lambda k=k, inlet=inlet: run_level(
                                     k, args.work, args.end_time, args.n_proc,
                                     l_ups[inlet], inlet),
                                 args.work / f"{inlet}_k{k}", args.keep_work)
            print(f"{inlet} inlet, " + table(r), flush=True)
    rich = {inlet: analyse(store.levels(), inlet) for inlet in INLETS}
    store.put_extra("richardson_peak_u", rich)
    return rich


if __name__ == "__main__":
    main()
