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
Loss coefficients of an equal-diameter 90° tee, RANS k-ω SST (decision
0042 criterion 4, task 0162), against Štigler, Klas & Šperka (2014).

    python3 validation/junction_loss/run.py --points div_a:0.6 --levels 1
    python3 validation/junction_loss/run.py                 # every point, the default level

**Network.**  An equal `Tee` (D = 0.1 m), each branch a `Straight` 25 D
long from the tee, as in the paper's CFD.  The paper's branch labels:
`a` is the inlet port (`fluid_inlet`), `b` the main outlet (`fluid_b`),
`c` the branch (`fluid_c`); γ = 90°.

**Configurations** (their figure 3), at flow-rate ratio q:
- Div a: in at a, out at b and c; q = Q_c / Q_a.
- Com a: in at b and c, out at a; q = Q_c / Q_a.
- Div c: in at c, out at a and b; q = Q_a / Q_c.
- Com c: in at a and b, out at c; q = Q_a / Q_c.

The branch carrying the total flow (a, or c) has U = 1 m/s and
Re = 10⁵ (the paper gives none; task 0162 step 1).  The other two
branches share it by q.  One branch is a pressure outlet (p = 0), and the
others have fixed flow rates (`flowRateInletVelocity`,
`flowRateOutletVelocity`).  Inlets are uniform, with 5 % intensity, as
in the paper's CFD (velocity inlets, 25 D to develop).

**Model.**  k-ω SST with Spalding's wall function
(`nutUSpaldingWallFunction`), task 0049's gated wall-function variant.
At Re 10⁵, a wall-resolved mesh along 75 D of pipe would cost many times
the cells.  Steady `simpleFoam`.

**Coefficients** (their eqs. 5, 8, 15, 16).  The static pressure of
each branch is area-averaged per axial cell layer, at stations
STATIONS from the junction centre.  It is carried back to the centre
along the solution's own friction gradient: a straight line through
the stations, as the paper does for its CFD ("in case of numerical
solution they are evaluated from the numerical solution", §3).  The
friction part (ξ_PF, ξ_MFb) is thereby removed, so ξ_PG and ξ_MGb follow
directly; ξ_MGb takes the total branch's pressure as 0.

The experiment's way, the developed gradient f(Re_i) v_i² / (2 D) with
McKeon's f in place of the measured one, is reported beside it
(``xi_PG_mckeon``, ``xi_MGb_mckeon``), never gated.  It was the compared
value until 2026-11-17 (task 0162's notes).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from hexmesh import Assembly, PipeSpec, Session, Straight, Tee   # noqa: E402
from hexmesh.study import openfoam as of                         # noqa: E402


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


conv = _load("convergence", "validation/tools/convergence.py")     # richardson() (task 0089)
stored = _load("stored", "validation/tools/results.py")             # results.json (task 0093)
tp = _load("turbulent_pipe", "validation/turbulent_pipe/run.py")   # the precursor's templates

# --- physics -----------------------------------------------------------------
R = 0.05                  # every branch's radius [m]
D = 2 * R
U_TOTAL = 1.0             # mean velocity of the branch carrying the total flow [m/s]
RE = 1e5                  # its Reynolds number
BRANCH = 25 * D           # each branch's straight, from the tee
STATIONS = np.arange(10, 18.5, 1.0) * D   # pressure stations from the junction centre
GAMMA = 90.0

# --- the mesh, at k = 1 ----------------------------------------------------------
N_ARC, N_LAYERS = 8, 50    # 50 layers: 0.5 D long cells along each branch
WALL_YPLUS = 30           # the wall cell's height at k = 1 [viscous units, total branch]
GROWTH_MAX = 1.3          # the radial growth ratio at k = 1
LEVELS = (1, 2, 3)        # refined(k)
DEFAULT_LEVEL = 2

# --- the fixed-wall family (task 0186) ----------------------------------------
#: refined(k) splits the wall cell k ways, so y⁺ falls with k (task 0050).
#: The family keeps it FIXED_YPLUS viscous units high at every level, its
#: centre at y⁺ 25 (0050 Q4 asks ≳ 20; WALL_YPLUS's 30 puts it at 15), as
#: the bend does.  Both in the total branch, at McKeon's u_τ.
REFINED, FIXED = "refined", "fixed_wall"
FIXED_YPLUS = 50
FIXED_LEVELS = (1, 2)     # here; k = 3 is the volunteer card's (task 0168)
FIXED_POINT = "div_a:0.6"
F_GATE = 0.05             # the precursor's f against McKeon (task 0049's wall-function gate)
PRECURSOR = R             # the periodic pipe's length, task 0049's

#: configuration → (the branch with the total flow, the pressure outlet,
#: signed flows (out +) per branch as a function of q, total 1)
CONFIGS = {
    "div_a": ("a", "b", lambda q: {"a": -1.0, "b": 1 - q, "c": q}),
    "com_a": ("a", "a", lambda q: {"a": 1.0, "b": -(1 - q), "c": -q}),
    "div_c": ("c", "b", lambda q: {"a": q, "b": 1 - q, "c": -1.0}),
    "com_c": ("c", "c", lambda q: {"a": -q, "b": -(1 - q), "c": 1.0}),
}
LABEL = {"div_a": "Div a", "com_a": "Com a", "div_c": "Div c", "com_c": "Com c"}
QS = (0.2, 0.4, 0.6, 0.8, 1.0)
PATCH = {"a": "fluid_inlet", "b": "fluid_b", "c": "fluid_c"}
CONVERGENCE_POINTS = ("div_a:0.6", "com_a:0.6")
RE_POINT, RE_CHECK = "div_a:0.6", (5e4, 2e5)

REFERENCE = HERE / "reference/stigler_2014.csv"


def nu(re: float = RE) -> float:
    return U_TOTAL * D / re


def mckeon(re_b: float) -> float:
    """Darcy f of a smooth pipe, McKeon et al. (2005) eq. 3.5, by iteration."""
    f = 0.02
    for _ in range(50):
        f = (1.920 * math.log10(re_b * math.sqrt(f)) - 0.475) ** -2
    return f


def first_cell(re: float = RE, yplus: float = WALL_YPLUS) -> float:
    u_tau = U_TOTAL * math.sqrt(mckeon(re) / 8)
    return yplus * nu(re) / u_tau


def wall_ring(first: float) -> int:
    """The smallest n_radial whose growth toward the centre is at most GROWTH_MAX."""
    for n in range(2, 100):
        try:
            spec = PipeSpec(n_arc=N_ARC).core("fluid", radius=R, n_radial=n, first_cell=first)
        except Exception:                          # first cell too large for n cells
            continue
        if 1 / spec.to_dict()["core"]["radial_grading"] <= GROWTH_MAX:
            return n
    raise ValueError(f"no ring for a first cell of {first}")


def fixed_spec(k: int = 1, re: float = RE) -> PipeSpec:
    """The section of the fixed-wall family at level *k* (task 0186, the
    bend's rule from task 0050): n_arc and the radial cells outside the
    wall cell × k, the wall cell FIXED_YPLUS viscous units high."""
    first = first_cell(re, FIXED_YPLUS)
    n = 1 + (wall_ring(first) - 1) * k
    return PipeSpec(n_arc=N_ARC * k).core("fluid", radius=R, n_radial=n, first_cell=first)


def _network(spec: PipeSpec, k: int) -> Assembly:
    """The tee network on section *spec*, the axial counts × k."""
    asm = Assembly(spec, position=[0, 0, 0], direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(BRANCH, n_layers=N_LAYERS * k))
    main, branch = asm.add(Tee(branch_length=2 * R, branch_radius=R))
    asm.add(main, Straight(BRANCH, n_layers=N_LAYERS * k), names=["b"])
    asm.add(branch, Straight(BRANCH, n_layers=N_LAYERS * k), names=["c"])
    return asm


def assembly(k: int = 1, re: float = RE, family: str = REFINED) -> Assembly:
    """The tee at level *k*: ``refined(k)`` of k = 1 (task 0162, the wall
    cell split k ways), or the fixed-wall family (task 0186)."""
    if family == FIXED:
        return _network(fixed_spec(k, re), k)
    first = first_cell(re)
    spec = PipeSpec(n_arc=N_ARC).core("fluid", radius=R, n_radial=wall_ring(first), first_cell=first)
    asm = _network(spec, 1)
    return asm if k == 1 else asm.refined(k)


def precursor(k: int = 1, re: float = RE) -> Assembly:
    """The periodic pipe on the fixed-wall section at level *k*, for the
    wall function's check (task 0049's two layers at k = 1)."""
    asm = Assembly(fixed_spec(k, re), position=[0, 0, 0], direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(PRECURSOR, n_layers=tp.N_LAYERS * k))
    return asm


def meshes():
    """(label, caption, build) per mesh shown in README.md."""
    return [("tee", f"the 90° tee, k = {DEFAULT_LEVEL}", lambda: assembly(DEFAULT_LEVEL))]


# --- OpenFOAM dictionaries -----------------------------------------------------

H = of.header

CONTROL = """application     simpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};
deltaT          1;
writeControl    timeStep;
writeInterval   {interval};
purgeWrite      {purge};
writeFormat     ascii;
writePrecision  12;
timeFormat      general;
runTimeModifiable false;
"""

SCHEMES = """ddtSchemes      { default steadyState; }
gradSchemes     { default cellLimited Gauss linear 1; }
divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss linearUpwind grad(U);
    div(phi,k)      bounded Gauss upwind;
    div(phi,omega)  bounded Gauss upwind;
    div(phi,epsilon) bounded Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear limited corrected 0.5; }
interpolationSchemes { default linear; }
snGradSchemes   { default limited corrected 0.5; }
wallDist        { method meshWave; }
"""

SOLUTION = """solvers
{
    p
    {
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-9;
        relTol          0.05;
    }
    "(U|k|omega|epsilon)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-10;
        relTol          0.1;
    }
}
SIMPLE
{
    nNonOrthogonalCorrectors 1;
    consistent      yes;
    residualControl
    {
        p               1e-5;
        U               1e-6;
        "(k|omega|epsilon)" 1e-6;
    }
}
relaxationFactors
{
    fields          { p 1; }
    equations       { U 0.8; "(k|omega|epsilon)" 0.6; }
}
"""

#: the gated model, and realizable k-ε for comparison with Štigler et al.'s
#: CFD (task 0162 step 4); the turbulence fields each solves for
MODELS = {"sst": ("kOmegaSST", "omega"), "rke": ("realizableKE", "epsilon")}

# --- the transient run, set up as the paper's CFD (task 0162 Q3, part 2) ----------
# pimpleFoam from rest.  The slowest branch (b at Div a, q = 0.6: 0.4 m/s)
# takes 6.25 s to flush, so: settle for three of its flow-throughs (20 s),
# then average p over 12 s, about two more (``fieldAverage``), with 12
# samples, one a second, for the spread.  Fixed before the run.
TRANSIENT_END, TRANSIENT_WINDOW, TRANSIENT_SAMPLES = 32.0, 12.0, 12

CONTROL_TRANSIENT = """application     pimpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};
deltaT          1e-4;
adjustTimeStep  yes;
maxCo           1;
maxDeltaT       0.01;
writeControl    adjustableRunTime;
writeInterval   {interval};
purgeWrite      {purge};
writeFormat     ascii;
writePrecision  12;
timeFormat      general;
timePrecision   8;
runTimeModifiable false;
functions
{{
    pAverage
    {{
        type            fieldAverage;
        libs            (fieldFunctionObjects);
        timeStart       {window_start};
        writeControl    writeTime;
        fields          ( p {{ mean on; prime2Mean off; base time; }} );
    }}
}}
"""

SOLUTION_TRANSIENT = """solvers
{
    p
    {
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-6;
        relTol          0.01;
    }
    pFinal
    {
        $p;
        relTol          0.01;          // relTol 0 stalls at 1.3e-6 for 1000 iterations
    }
    "(U|k|epsilon)Final"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-8;
        relTol          0;
    }
}
PIMPLE
{
    nOuterCorrectors 1;
    nCorrectors     2;
    nNonOrthogonalCorrectors 1;
}
"""

TURBULENCE = """simulationType  RAS;
RAS
{{
    RASModel        {ras};
    turbulence      on;
    printCoeffs     on;
}}
"""

DIMS = {"U": "[0 1 -1 0 0 0 0]", "p": "[0 2 -2 0 0 0 0]", "k": "[0 2 -2 0 0 0 0]",
        "omega": "[0 0 -1 0 0 0 0]", "epsilon": "[0 2 -3 0 0 0 0]",
        "nut": "[0 2 -1 0 0 0 0]"}


# --- the time-accurate run with the convergence stop (task 0186) ------------------
# The bend's method (task 0050, design answer Q5) for a steady solve that
# plateaus: simpleFoam from rest for TA_STEADY iterations, then pimpleFoam
# from its fields, SST with Spalding's wall as the steady levels, in
# resumable chunks of half a flow-through.  p is written TA_SAMPLES times a
# flow-through and both coefficients read from each; the run stops when
# both stay within TA_BAND relative over the last flow-through, else at
# TA_MAX flow-throughs.  The coefficients are the final fields'.
TA_STEADY = 2000          # the fixed-wall k = 1 plateau sets in by iteration ~800
TA_CHUNK = 0.5            # flow-throughs per pimpleFoam run
TA_SAMPLES = 10           # p samples per flow-through
TA_BAND = 1e-4            # ξ's relative band over the last flow-through (0050 Q5)
TA_MAX = 12               # flow-throughs
TA_SETTLE = 2             # flow-throughs before the samples' time mean (reported, not the stop)
TA_SCHEMES = (SCHEMES.replace("default steadyState;", "default backward;")
              .replace("bounded Gauss", "Gauss"))
#: the bend's (task 0050) with the tee's non-orthogonal corrector; ddtCorr
#: at v2406's default (on)
TA_SOLUTION = """solvers
{
    p
    {
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-7;
        relTol          0.01;
    }
    pFinal
    {
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-7;
        relTol          0;
    }
    "(U|k|omega)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-9;
        relTol          0.1;
    }
    "(U|k|omega)Final"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-9;
        relTol          0;
    }
}
PIMPLE
{
    momentumPredictor yes;
    nOuterCorrectors 2;
    nCorrectors     2;
    nNonOrthogonalCorrectors 1;
}
relaxationFactors
{
    equations       { ".*" 1; }
}
"""
TA_CONTROL = """application     pimpleFoam;
startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};
deltaT          1e-4;
adjustTimeStep  yes;
maxCo           1;
maxDeltaT       1;
writeControl    adjustableRunTime;
writeInterval   {interval};
purgeWrite      0;
writeFormat     ascii;
writePrecision  12;
timeFormat      general;
timePrecision   12;
runTimeModifiable false;
"""


def flow_through(flows: dict) -> float:
    """Seconds from the slowest inlet branch's end to the slowest outlet's,
    each branch at its mean velocity (Div a, q 0.6: 2.5 + 6.25 s)."""
    v = {b: abs(f) * U_TOTAL for b, f in flows.items() if f != 0}
    return (max(BRANCH / v[b] for b in v if flows[b] < 0)
            + max(BRANCH / v[b] for b in v if flows[b] > 0))


def turbulence(v: float) -> tuple[float, float, float]:
    """k, ω and ε for 5 % intensity and a 0.07 D mixing length at speed *v*."""
    k = max(1.5 * (0.05 * v) ** 2, 1e-10)
    omega = math.sqrt(k) / (0.09 ** 0.25 * 0.07 * D)
    return k, omega, 0.09 * k * omega


def boundary(field: str, branch: str, flow: float, pressure: bool, area: float) -> str:
    """One branch's condition for *field*: flow *flow* (out +, m³/s)."""
    k, omega, epsilon = turbulence(abs(flow) / area)
    inlet = flow < 0 or (flow == 0 and not pressure)
    if field == "U":
        if pressure:
            return "type pressureInletOutletVelocity; value uniform (0 0 0);"
        if inlet:
            return f"type flowRateInletVelocity; volumetricFlowRate constant {of.num(-flow)}; " \
                   "value uniform (0 0 0);"
        return f"type flowRateOutletVelocity; volumetricFlowRate constant {of.num(flow)}; " \
               "value uniform (0 0 0);"
    if field == "p":
        return "type fixedValue; value uniform 0;" if pressure else "type zeroGradient;"
    if field == "nut":
        return "type calculated; value uniform 0;"
    value = {"k": k, "omega": omega, "epsilon": epsilon}[field]
    if inlet:
        return f"type fixedValue; value uniform {of.num(value)};"
    return f"type inletOutlet; inletValue uniform {of.num(value)}; value uniform {of.num(value)};"


WALL = {"U": "type noSlip;", "p": "type zeroGradient;",
        "k": "type kqRWallFunction; value uniform {k};",
        "omega": "type omegaWallFunction; value uniform {omega};",
        "epsilon": "type epsilonWallFunction; value uniform {epsilon};",
        "nut": "type nutUSpaldingWallFunction; value uniform 0;"}
#: the transient run's wall: nearest v2406 has to Fluent's non-equilibrium
#: wall functions (the paper's), the log law with the velocity scale
#: C_μ^¼ k^½ and ε and G set in the wall cell; it lacks their
#: pressure-gradient term.  Both switch to the laminar law below y⁺ ≈ 11;
#: the wall cell sits near y⁺ 14 at k = 2.
NUT_TRANSIENT = "type nutkWallFunction; value uniform 0;"
#: --wall: nut's wall function; ``nutk`` is the transient set-up's, run steady
#: to separate the wall treatment from the solver (task 0162 Q4)
NUT_WALL = {"spalding": WALL["nut"], "nutk": NUT_TRANSIENT}


def write_case(case: Path, flows: dict, pressure_branch: str, area: float, end_time: float,
               interval: float, purge: int, re: float, model: str = "sst",
               transient: bool = False, window: float = 0.0, wall: str | None = None) -> None:
    ras, extra = MODELS[model]
    wall = wall or ("nutk" if transient else "spalding")
    for d in ("0", "constant", "system"):
        (case / d).mkdir(parents=True, exist_ok=True)
    if transient:
        control = CONTROL_TRANSIENT.format(end_time=f"{end_time:g}", interval=f"{interval:g}",
                                           purge=purge, window_start=f"{end_time - window:g}")
        schemes = SCHEMES.replace("default steadyState;", "default backward;")
        solution = SOLUTION_TRANSIENT
    else:
        control = CONTROL.format(end_time=int(end_time), interval=int(interval), purge=purge)
        schemes, solution = SCHEMES, SOLUTION
    files = {
        "system/controlDict": H("dictionary", "controlDict", "system") + control,
        "system/fvSchemes": H("dictionary", "fvSchemes", "system") + schemes,
        "system/fvSolution": H("dictionary", "fvSolution", "system") + solution,
        "constant/transportProperties": H("dictionary", "transportProperties", "constant")
        + f"transportModel  Newtonian;\nnu              {of.num(nu(re))};\n",
        "constant/turbulenceProperties": H("dictionary", "turbulenceProperties", "constant")
        + TURBULENCE.format(ras=ras),
    }
    for name, text in files.items():
        (case / name).write_text(text, encoding="utf-8")
    k0, omega0, epsilon0 = turbulence(U_TOTAL)
    internal = {"U": "uniform (0 0 0)", "p": "uniform 0", "k": f"uniform {of.num(k0)}",
                "omega": f"uniform {of.num(omega0)}", "epsilon": f"uniform {of.num(epsilon0)}",
                "nut": "uniform 0"}
    for f, dims in DIMS.items():
        if f in ("omega", "epsilon") and f != extra:
            continue
        cls = "volVectorField" if f == "U" else "volScalarField"
        rows = [f"    {PATCH[b]:12s} {{ {boundary(f, b, flows[b], b == pressure_branch, area)} }}"
                for b in ("a", "b", "c")]
        cond = NUT_WALL[wall] if f == "nut" else WALL[f]
        rows.append(f'    "fluid_wall.*" {{ {cond.format(k=of.num(k0), omega=of.num(omega0), epsilon=of.num(epsilon0))} }}')
        text = (H(cls, f, "0") + f"dimensions      {dims};\ninternalField   {internal[f]};\n"
                "boundaryField\n{\n" + "\n".join(rows) + "\n}\n")
        (case / "0" / f).write_text(text, encoding="utf-8")


def write_precursor(case: Path, end_time: int, re: float = RE) -> None:
    """The periodic pipe at the total branch's U and Re, with the tee's
    schemes, solver settings and wall (task 0186): it checks the wall
    function on the level's section against McKeon's f (task 0049)."""
    for d in ("0", "constant", "system"):
        (case / d).mkdir(parents=True, exist_ok=True)
    solution = SOLUTION.replace("    consistent      yes;\n",
                                "    consistent      yes;\n    pRefCell        0;\n"
                                "    pRefValue       0;\n", 1)
    files = {
        "system/controlDict": H("dictionary", "controlDict", "system")
        + CONTROL.format(end_time=end_time, interval=end_time, purge=0),
        "system/fvSchemes": H("dictionary", "fvSchemes", "system") + SCHEMES,
        "system/fvSolution": H("dictionary", "fvSolution", "system") + solution,
        "system/createPatchDict": H("dictionary", "createPatchDict", "system")
        + tp.CREATE_PATCH.format(L=of.num(PRECURSOR)),
        "constant/fvOptions": H("dictionary", "fvOptions", "constant")
        + tp.FVOPTIONS.format(u=of.num(U_TOTAL)),
        "constant/transportProperties": H("dictionary", "transportProperties", "constant")
        + f"transportModel  Newtonian;\nnu              {of.num(nu(re))};\n",
        "constant/turbulenceProperties": H("dictionary", "turbulenceProperties", "constant")
        + TURBULENCE.format(ras=MODELS["sst"][0]),
    }
    for name, text in files.items():
        (case / name).write_text(text, encoding="utf-8")
    k0, omega0, _ = turbulence(U_TOTAL)
    internal = {"U": f"uniform ({of.num(U_TOTAL)} 0 0)", "p": "uniform 0",
                "k": f"uniform {of.num(k0)}", "omega": f"uniform {of.num(omega0)}",
                "nut": "uniform 0"}
    for f in ("U", "p", "k", "omega", "nut"):
        cls = "volVectorField" if f == "U" else "volScalarField"
        w = WALL[f].format(k=of.num(k0), omega=of.num(omega0))
        (case / "0" / f).write_text(
            H(cls, f, "0") + f"dimensions      {DIMS[f]};\ninternalField   {internal[f]};\n"
            "boundaryField\n{\n    cyc_in      { type cyclic; }\n"
            f"    cyc_out     {{ type cyclic; }}\n    fluid_wall  {{ {w} }}\n}}\n",
            encoding="utf-8")


# --- post-processing -------------------------------------------------------------

def _wall_faces(case: Path) -> tuple[dict, np.ndarray, np.ndarray, np.ndarray]:
    """Per wall patch (``fluid_wall*``) its face labels; and the mesh's face
    centres, area vectors and owners."""
    mesh = case / "constant/polyMesh"
    pts, faces = of.read_points(mesh / "points"), of.read_faces(mesh / "faces")
    fc, sf = of.face_geometry(pts, faces)
    text = (mesh / "boundary").read_text(encoding="utf-8")
    names = re.findall(r"^\s*(fluid_wall\w*)\s*\n\s*\{", text, re.M)
    return ({n: of.read_patch_faces(mesh / "boundary", n) for n in names},
            fc, sf, of.read_labels(mesh / "owner"))


def wall_yplus(case: Path, cc: np.ndarray, re: float = RE) -> dict:
    """The wall cells' y⁺ at the last time: d √(ν_eff |U| / d) / ν per wall
    face, d the cell centre's distance from the face (as OpenFOAM's yPlus,
    ν_eff with the wall function's ν_t); area-weighted mean, and range,
    over every wall and per branch's straight (task 0186)."""
    walls, fc, sf, owner = _wall_faces(case)
    t = of.latest_time(case)
    U = of.read_internal(t / "U", 3)
    v = nu(re)
    out = {}
    for name, idx in walls.items():
        area = np.linalg.norm(sf[idx], axis=1)
        n = sf[idx] / area[:, None]
        c = owner[idx]
        d = np.abs(np.einsum("ij,ij->i", cc[c] - fc[idx], n))
        nut = of.read_patch_values(t / "nut", name, len(idx))
        yp = d * np.sqrt((v + nut) * np.linalg.norm(U[c], axis=1) / d) / v
        out[name] = (yp, area)
    yp = np.concatenate([y for y, _ in out.values()])
    area = np.concatenate([a for _, a in out.values()])
    per = {name: {"mean": float(np.average(y, weights=a)), "min": float(y.min()),
                  "max": float(y.max())} for name, (y, a) in out.items()}
    return {"mean": float(np.average(yp, weights=area)), "min": float(yp.min()),
            "max": float(yp.max()), "patches": per}


def precursor_results(case: Path, log: str, reynolds: float = RE) -> dict:
    """f from the periodic pipe's momentum balance, against McKeon (task
    0049's gate F_GATE), and its wall cells' y⁺."""
    walls, fc, sf, owner = _wall_faces(case)
    wall = walls["fluid_wall"]
    mesh = case / "constant/polyMesh"
    neigh = of.read_labels(mesh / "neighbour")
    cc, vol = of.cell_geometry(fc, sf, owner, neigh, int(max(owner.max(), neigh.max())) + 1)
    a_wall = float(np.linalg.norm(sf[wall], axis=1).sum())
    grads = [float(v) for v in re.findall(r"pressure gradient = ([-\d.eE+]+)", log)]
    tau = grads[-1] * vol.sum() / a_wall
    U = of.read_internal(of.latest_time(case) / "U", 3)
    ub = float(np.sum(vol * U[:, 0]) / vol.sum())
    f = 8 * tau / ub ** 2
    n = sf[wall] / np.linalg.norm(sf[wall], axis=1)[:, None]
    d = np.abs(np.einsum("ij,ij->i", cc[owner[wall]] - fc[wall], n))
    yplus = math.sqrt(tau) * d / nu(reynolds)
    f_ref = tp.mckeon(reynolds)
    steps = re.findall(r"^Time = (\d+)", log, re.M)
    return {"f": f, "f_mckeon": f_ref, "f_err_mckeon": f / f_ref - 1,
            "f_ok": bool(abs(f / f_ref - 1) <= F_GATE), "u_b": ub,
            "yplus_first_mean": float(yplus.mean()), "yplus_first_max": float(yplus.max()),
            "steps": int(steps[-1]) if steps else 0,
            "converged": "solution converged in" in log}


def run_precursor(case: Path, k: int, reynolds: float = RE, end_time: int = 4000) -> dict:
    """Mesh, set up and solve the periodic pipe of level *k* in *case*.  One
    process: decomposed, its cross-flow residuals floor above
    residualControl (task 0050)."""
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    write_precursor(case, end_time, reynolds)
    asm = precursor(k, reynolds)
    with Session(f"junction-loss-precursor-{k}"):
        msh = case / "mesh.msh"
        asm.write_openfoam(str(msh))
        sj = asm.check_quality("scaled_jacobian").worst
    of.convert(case, msh, keep_orientation=sj > 0)
    of.foam("createPatch -overwrite", case, "log.createPatch")
    log = of.run_solver(case, "simpleFoam", n_proc=1)
    return {"cells": asm.cell_count(), **precursor_results(case, log, reynolds)}

def geometry(case: Path) -> dict:
    """The mesh, its cell centres and volumes, the junction centre, and
    each branch's outward axis and port area."""
    mesh = case / "constant/polyMesh"
    pts, faces = of.read_points(mesh / "points"), of.read_faces(mesh / "faces")
    owner, neigh = of.read_labels(mesh / "owner"), of.read_labels(mesh / "neighbour")
    fc, sf = of.face_geometry(pts, faces)
    n_cells = int(max(owner.max(), neigh.max())) + 1
    cc, vol = of.cell_geometry(fc, sf, owner, neigh, n_cells)
    port = {}
    for b, patch in PATCH.items():
        idx = of.read_patch_faces(mesh / "boundary", patch)
        area = np.linalg.norm(sf[idx], axis=1)
        port[b] = {"centre": (fc[idx] * area[:, None]).sum(0) / area.sum(),
                   "area": float(area.sum())}
    # a and b lie on the x axis, c on the z axis through the centre
    centre = np.array([port["c"]["centre"][0], 0.0, port["a"]["centre"][2]])
    axes = {b: (port[b]["centre"] - centre) / np.linalg.norm(port[b]["centre"] - centre)
            for b in PATCH}
    return {"cc": cc, "vol": vol, "centre": centre, "axes": axes, "port": port}


def layer_pressure(g: dict, p: np.ndarray, branch: str) -> tuple[np.ndarray, np.ndarray]:
    """(distance from the centre, volume-averaged p) per axial cell layer
    of *branch* beyond 2 D from the centre: the area average of the layer."""
    rel = g["cc"] - g["centre"]
    s = rel @ g["axes"][branch]
    radial = np.linalg.norm(rel - np.outer(s, g["axes"][branch]), axis=1)
    sel = (s > 2 * D) & (radial < 1.01 * R)
    key = np.round(s[sel] / (1e-4 * D)).astype(np.int64)      # one key per layer
    layers, inv = np.unique(key, return_inverse=True)
    vol = np.bincount(inv, weights=g["vol"][sel])
    pv = np.bincount(inv, weights=g["vol"][sel] * p[sel])
    sv = np.bincount(inv, weights=g["vol"][sel] * s[sel])
    return sv / vol, pv / vol


def coefficients(g: dict, p: np.ndarray, flows: dict, total: str, re: float) -> dict:
    """ξ_PG and ξ_MGb from the centre pressures (eqs. 5, 8, 15, 16)."""
    area = float(np.mean([g["port"][b]["area"] for b in PATCH]))
    q_total = U_TOTAL * area
    out = {"area": area}
    centre_p, fit = {}, {}
    for b in PATCH:
        s, pl = layer_pressure(g, p, b)
        v = abs(flows[b]) * q_total / area
        re_b = re * v / U_TOTAL
        grad = mckeon(re_b) * v ** 2 / (2 * D) if v > 0 else 0.0
        sign = 1.0 if flows[b] > 0 else -1.0      # out: p falls away from the centre
        at = [float(np.interp(x, s, pl)) for x in STATIONS]
        centre_p[b] = float(np.mean([pi + sign * grad * x for pi, x in zip(at, STATIONS)]))
        slope, icept = np.polyfit(STATIONS, at, 1)
        fit[b] = {"intercept": float(icept), "slope": float(slope),
                  "friction_slope": -sign * grad,
                  "residual_rms": float(np.sqrt(np.mean(
                      (np.polyval([slope, icept], STATIONS) - at) ** 2)))}
    ref = centre_p[total]
    pr = {b: centre_p[b] - ref for b in PATCH}
    v = {b: abs(flows[b]) * q_total / area for b in PATCH}
    qv = {b: flows[b] * q_total for b in PATCH}
    vx, qx = v[total], abs(qv[total])
    power = sum((0.5 * v[b] ** 2 + pr[b]) * qv[b] for b in PATCH)
    xi_pg_mckeon = -2 * power / (vx ** 2 * qx)
    cg = math.cos(math.radians(GAMMA))
    xi_mgb_mckeon = ((v["a"] ** 2 + pr["a"]) - (v["b"] ** 2 + pr["b"])
                     - (v["c"] ** 2 + pr["c"]) * cg) / vx ** 2
    # the compared value: the solution's own gradient, the straight-line fits (§3)
    prf = {b: fit[b]["intercept"] - fit[total]["intercept"] for b in PATCH}
    xi_pg = -2 * sum((0.5 * v[b] ** 2 + prf[b]) * qv[b] for b in PATCH) / (vx ** 2 * qx)
    xi_mgb = ((v["a"] ** 2 + prf["a"]) - (v["b"] ** 2 + prf["b"])
              - (v["c"] ** 2 + prf["c"]) * cg) / vx ** 2
    out.update(xi_PG=xi_pg, xi_MGb=xi_mgb, xi_PG_mckeon=xi_pg_mckeon,
               xi_MGb_mckeon=xi_mgb_mckeon, centre_p=prf, centre_p_mckeon=pr, fit=fit)
    return out


PROFILE = np.arange(3, 24, 1.0) * D      # where the local slope is reported


def profile(g: dict, p: np.ndarray, flows: dict, re: float) -> dict:
    """Each branch's local pressure slope (a line through the layers within
    ±1 D) at PROFILE, over the developed friction slope: 1 where the flow
    is developed, as the extrapolation to the centre assumes."""
    out = {"s_D": [float(x / D) for x in PROFILE]}
    for b in PATCH:
        s, pl = layer_pressure(g, p, b)
        v = abs(flows[b]) * U_TOTAL
        if v == 0:
            out[b] = None
            continue
        grad = mckeon(re * v / U_TOTAL) * v ** 2 / (2 * D)
        sign = 1.0 if flows[b] > 0 else -1.0      # out: p falls away from the centre
        ratio = []
        for x in PROFILE:
            near = np.abs(s - x) <= D + 1e-9
            ratio.append(float(np.polyfit(s[near], pl[near], 1)[0] / (-sign * grad))
                         if near.sum() >= 2 else None)
        out[b] = ratio
    return out


# --- one point ---------------------------------------------------------------------

def point_name(config: str, q: float, k: int, re: float = RE, model: str = "sst",
               transient: bool = False, wall: str | None = None,
               family: str = REFINED, accurate: bool = False) -> str:
    """``div_a_q0.6_k2`` and its variants; ``fixed_…`` in the fixed-wall
    family and ``transient_fixed_…`` time-accurate with the convergence
    stop (task 0186), so 0162's levels keep their names."""
    tail = "" if re == RE else f"_re{re:.0e}".replace("+0", "").replace("+", "")
    own = "nutk" if transient else "spalding"
    return (("transient_" if accurate else "") + ("fixed_" if family == FIXED else "")
            + f"{config}_q{q:.1f}_k{k}{tail}" + ("" if model == "sst" else f"_{model}")
            + ("_transient" if transient else "")
            + ("" if wall in (None, own) else f"_{wall}"))


def prepare_point(case: Path, config: str, q: float, k: int, end_time: float,
                  reynolds: float = RE, window: float = 1000, samples: int = 10,
                  model: str = "sst", transient: bool = False,
                  wall: str | None = None, family: str = REFINED) -> dict:
    """Mesh one point into *case*, write its OpenFoam case and check the
    mesh; what :func:`collect_point` needs is saved as ``point.json``."""
    total, pressure, flows_of = CONFIGS[config]
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    asm = assembly(k, reynolds, family)
    with Session(f"junction-loss-{config}-{q}-{k}"):
        cells = asm.cell_count()
        print(f"[{case.name}] predicted cells: {cells}", flush=True)
        msh = case / "mesh.msh"
        asm.write_openfoam(str(msh), walls_by_fitting=True)
        sj = asm.check_quality("scaled_jacobian").worst
    area = math.pi * R ** 2
    # the last samples + 1 writes span the last *window* iterations
    interval = window / samples if transient else max(window // samples, 1)
    write_case(case, {b: f * U_TOTAL * area for b, f in flows_of(q).items()}, pressure, area,
               end_time, interval, samples + 1, reynolds, model, transient, window, wall)
    of.convert(case, msh, keep_orientation=sj > 0)
    point = {"config": config, "q": q, "k": k, "re": reynolds, "model": model,
             "solver": "pimpleFoam" if transient else "simpleFoam",
             "wall": wall or ("nutk" if transient else "spalding"), "window": window, "cells": cells, "worst_sj": sj,
             **({"family": FIXED, "first_cell": first_cell(reynolds, FIXED_YPLUS)}
                if family == FIXED else {}),
             **{f"check_{key}": v for key, v in of.check_mesh(case).items()},
             **stored.counts(asm)}
    (case / "point.json").write_text(json.dumps(point, indent=1), encoding="utf-8")
    return point


def collect_point(case: Path) -> dict:
    """The coefficients of a solved point (:func:`prepare_point`, then
    ``simpleFoam``), averaged over its window."""
    point = json.loads((case / "point.json").read_text(encoding="utf-8"))
    config, q, reynolds, window = point["config"], point["q"], point["re"], point.pop("window")
    total, _, flows_of = CONFIGS[config]
    flows = flows_of(q)
    solver = point.get("solver", "simpleFoam")
    log = (case / f"log.{solver}").read_text(encoding="utf-8", errors="replace")
    steps = re.findall(r"^Time = ([\d.e+-]+)", log, re.M)
    g = geometry(case)
    last = float(of.latest_time(case).name)
    times = sorted((d for d in case.iterdir() if d.name.replace(".", "").isdigit()
                    and d.name != "0" and float(d.name) >= last - window - 1e-9 * window),
                   key=lambda d: float(d.name))
    # A steady solve whose coefficients still wander (task 0162 step 4):
    # report the mean over the window, with the samples' standard
    # deviation as its spread.  The coefficients are linear in p, so the
    # mean field's are the samples' mean.
    ps = [of.read_internal(d / "p", 1).ravel() for d in times]
    series = [coefficients(g, pi, flows, total, reynolds) for pi in ps]
    p_mean = np.mean(ps, axis=0)
    if solver == "pimpleFoam":                 # the time average over the window
        p_mean = of.read_internal(times[-1] / "pMean", 1).ravel()
    res = coefficients(g, p_mean, flows, total, reynolds)
    yplus = wall_yplus(case, g["cc"], reynolds)
    coefs = ("xi_PG", "xi_MGb", "xi_PG_mckeon", "xi_MGb_mckeon")
    spread = {f"{c}_spread": float(np.std([s[c] for s in series], ddof=1))
              if len(series) > 1 else None for c in coefs}
    drift = {c: series[-1][c] - series[0][c] for c in coefs} if len(series) > 1 else None
    steady = solver == "simpleFoam"
    return {**point, "steps": (int(steps[-1]) if steady else len(steps)) if steps else 0,
            **({} if steady else {"end_time": float(steps[-1]) if steps else 0.0}),
            "converged": "solution converged in" in log, "drift": drift, **res, **spread,
            "yplus": yplus,
            "window": {"steps": [float(d.name) for d in times],
                       **{c: [s[c] for s in series] for c in coefs}},
            "profile": profile(g, p_mean, flows, reynolds)}


def run_point(config: str, q: float, k: int, work: Path, end_time: float, n_proc: int,
              reynolds: float = RE, window: float = 1000, samples: int = 10,
              model: str = "sst", transient: bool = False, wall: str | None = None,
              family: str = REFINED) -> dict:
    """One point solved; in the fixed-wall family with its precursor's
    wall-function check first (task 0186), in ``<case>/precursor``."""
    case = work / point_name(config, q, k, reynolds, model, transient, wall, family)
    prepare_point(case, config, q, k, end_time, reynolds, window, samples, model, transient,
                  wall, family)
    pre = run_precursor(case / "precursor", k, reynolds) if family == FIXED else None
    if pre is not None:
        print(f"[{case.name}] precursor f {pre['f']:.5f}, McKeon {pre['f_mckeon']:.5f} "
              f"({pre['f_err_mckeon']:+.2%}), wall y+ {pre['yplus_first_mean']:.1f}, "
              f"converged {pre['converged']} in {pre['steps']}", flush=True)
    of.run_solver(case, "pimpleFoam" if transient else "simpleFoam", n_proc=n_proc)
    out = collect_point(case)
    return out if pre is None else {**out, "precursor": pre}


def _ta_case(steady: Path, case: Path) -> None:
    """The pimpleFoam case: the steady start's mesh and last fields as its
    time 0, the time-accurate schemes and solution."""
    (case / "0").mkdir(parents=True)
    shutil.copytree(steady / "constant", case / "constant")
    (case / "system").mkdir()
    t = of.latest_time(steady)
    for f in ("U", "p", "k", "omega", "nut"):
        text = (t / f).read_text(encoding="utf-8")
        (case / "0" / f).write_text(re.sub(r'location\s+"[^"]*";', 'location    "0";', text),
                                    encoding="utf-8")
    for name, text in (("fvSchemes", TA_SCHEMES), ("fvSolution", TA_SOLUTION)):
        (case / "system" / name).write_text(H("dictionary", name, "system") + text,
                                            encoding="utf-8")


def ta_steadiness(h: dict) -> dict:
    """Each coefficient's relative band over the last flow-through;
    ``converged`` once both are inside TA_BAND (never before one
    flow-through has run)."""
    t, ft = np.array(h["t"]), h["flow_through"]
    if len(t) == 0 or t[-1] < ft - 1e-9:
        return {"xi_PG_band": None, "xi_MGb_band": None, "converged": False}
    last = t >= t[-1] - ft - 1e-9
    bands = {f"{c}_band": float(np.ptp(np.array(h[c])[last]) / abs(h[c][-1]))
             for c in ("xi_PG", "xi_MGb")}
    return {**bands, "converged": all(b < TA_BAND for b in bands.values())}


def ta_time_mean(h: dict) -> dict:
    """The samples' mean and standard deviation per coefficient after
    TA_SETTLE flow-throughs, and the change between the window's halves:
    the time mean when the run doesn't settle (task 0186: level 1 cycles).
    The samples are 1/TA_SAMPLES of a flow-through apart, so a faster cycle
    aliases; the mean is still unbiased over many cycles."""
    t, ft = np.array(h["t"]), h["flow_through"]
    on = t > TA_SETTLE * ft + 1e-9
    if on.sum() < 4:
        return {}
    out = {"from_s": TA_SETTLE * ft, "samples": int(on.sum())}
    for c in ("xi_PG", "xi_MGb"):
        x = np.array(h[c])[on]
        n = len(x) // 2
        out[c] = {"mean": float(x.mean()), "std": float(x.std(ddof=1)),
                  "min": float(x.min()), "max": float(x.max()),
                  "halves_change": float(x[n:].mean() / x[:n].mean() - 1)}
    return out


def _times(case: Path) -> list[Path]:
    return sorted((d for d in case.iterdir() if d.is_dir() and re.fullmatch(r"[\d.e+-]+", d.name)),
                  key=lambda d: float(d.name))


def run_time_accurate(config: str, q: float, k: int, work: Path, n_proc: int,
                      reynolds: float = RE, family: str = FIXED) -> dict:
    """One point time-accurately with the convergence stop (task 0186; see
    TA_STEADY): the precursor's check, the steady start, then pimpleFoam
    chunks in ``<case>/transient`` until :func:`ta_steadiness` passes.
    Resumable: a run with ``transient/history.json`` carries on from its
    latest time."""
    total, _, flows_of = CONFIGS[config]
    flows = flows_of(q)
    root = work / point_name(config, q, k, reynolds, family=family, accurate=True)
    steady, case = root / "steady", root / "transient"
    hist_path = case / "history.json"
    if hist_path.exists():
        h = json.loads(hist_path.read_text(encoding="utf-8"))
        print(f"[{root.name}] resuming at t = {h['t'][-1] if h['t'] else 0:g} s", flush=True)
    else:
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        point = prepare_point(steady, config, q, k, TA_STEADY, reynolds, TA_STEADY, 1,
                              family=family)
        pre = run_precursor(root / "precursor", k, reynolds) if family == FIXED else None
        if pre is not None:
            print(f"[{root.name}] precursor f {pre['f']:.5f}, McKeon {pre['f_mckeon']:.5f} "
                  f"({pre['f_err_mckeon']:+.2%}), wall y+ {pre['yplus_first_mean']:.1f}",
                  flush=True)
        log = of.run_solver(steady, "simpleFoam", n_proc=n_proc)
        start = {"steps": len(re.findall(r"^Time = ", log, re.M)),
                 "converged": "solution converged in" in log}
        _ta_case(steady, case)
        shutil.rmtree(steady)
        h = {"point": point, "precursor": pre, "steady_start": start,
             "flow_through": flow_through(flows), "t": [], "xi_PG": [], "xi_MGb": [],
             "chunks": []}
        hist_path.write_text(json.dumps(h, indent=1), encoding="utf-8")
    ft = h["flow_through"]
    g = geometry(case)
    while True:
        st = ta_steadiness(h)
        t_end = h["t"][-1] if h["t"] else 0.0
        if st["converged"] or t_end >= TA_MAX * ft - 1e-9:
            break
        end = round(t_end + TA_CHUNK * ft, 9)
        (case / "system/controlDict").write_text(
            H("dictionary", "controlDict", "system")
            + TA_CONTROL.format(end_time=of.num(end), interval=of.num(ft / TA_SAMPLES)),
            encoding="utf-8")
        n = len(h["chunks"])
        log = of.run_solver(case, "pimpleFoam", n_proc=n_proc, log=f"log.pimpleFoam.{n}")
        new = [d for d in _times(case) if float(d.name) > t_end + 1e-9]
        if not new:
            raise SystemExit(f"[{root.name}] the chunk from t = {t_end:g} wrote no time; "
                             f"see {case.name}/log.pimpleFoam.{n}")
        for d in new:
            c = coefficients(g, of.read_internal(d / "p", 1).ravel(), flows, total, reynolds)
            h["t"].append(float(d.name))
            h["xi_PG"].append(c["xi_PG"])
            h["xi_MGb"].append(c["xi_MGb"])
        clock = re.findall(r"ClockTime = ([\d.e+-]+) s", log)
        h["chunks"].append({"end": float(new[-1].name),
                            "steps": len(re.findall(r"^Time = ", log, re.M)),
                            "clock_s": float(clock[-1]) if clock else None})
        for d in _times(case)[:-1]:                    # restart needs the latest only
            shutil.rmtree(d)
        hist_path.write_text(json.dumps(h, indent=1), encoding="utf-8")
        st = ta_steadiness(h)
        print(f"[{root.name}] t = {h['t'][-1]:g} s ({h['t'][-1] / ft:.2f} flow-throughs): "
              f"ξ_PG {h['xi_PG'][-1]:.6f}, ξ_MGb {h['xi_MGb'][-1]:.6f}, bands "
              f"{st['xi_PG_band']}, {st['xi_MGb_band']}", flush=True)
    last = _times(case)[-1]
    p = of.read_internal(last / "p", 1).ravel()
    point = {key: v for key, v in h["point"].items() if key != "window"}
    return {**point, "solver": "pimpleFoam", "method": "time_accurate",
            "ddt_corr": "default (on in v2406)", "steps": sum(c["steps"] for c in h["chunks"]),
            "end_time": float(last.name), "flow_through_s": ft,
            "flow_throughs": float(last.name) / ft, **st,
            **coefficients(g, p, flows, total, reynolds),
            "yplus": wall_yplus(case, g["cc"], reynolds),
            "time_mean": ta_time_mean(h),
            "steady_start": h["steady_start"], "chunks": h["chunks"],
            "history": {c: h[c] for c in ("t", "xi_PG", "xi_MGb")},
            "profile": profile(g, p, flows, reynolds),
            **({"precursor": h["precursor"]} if h["precursor"] else {})}


# --- the reference and the gates ---------------------------------------------------

#: the largest |CFD − measured| of the paper's own CFD per configuration and
#: coefficient at 90° (reference/stigler_2014.csv; task 0162 Q2)
def reference() -> list[dict]:
    rows = []
    for line in REFERENCE.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or line.startswith("figure,"):
            continue
        f = line.split(",")
        rows.append({"config": f[1].lower().replace(" ", "_"), "coefficient": f[2],
                     "gamma": float(f[3]), "q": float(f[4]), "measured": float(f[5]),
                     "u": float(f[6]), "cfd": float(f[7])})
    return rows


def tolerances(rows: list[dict]) -> dict:
    t = {}
    for r in rows:
        if r["gamma"] == GAMMA:
            key = (r["config"], r["coefficient"])
            t[key] = max(t.get(key, 0.0), abs(r["cfd"] - r["measured"]))
    return t


def _steady(level: dict) -> bool:
    """A steady level: the gated kind (a transient one is only reported)."""
    return level.get("solver", "simpleFoam") == "simpleFoam"


def _family(level: dict) -> str:
    return level.get("family", REFINED)


def recheck(data: dict) -> list[dict]:
    """Every gated value (task 0162, Q2): within u_measured + T of the
    measurement at the finest level that ran; the pass count per curve;
    Richardson / GCI at the convergence points."""
    rows, out = reference(), []
    tol = tolerances(rows)
    levels = data["levels"]
    for config in CONFIGS:
        for coef in ("xi_PG", "xi_MGb"):
            n_pass = n = 0
            for r in (r for r in rows if r["gamma"] == GAMMA and r["config"] == config
                      and r["coefficient"] == coef):
                got = [lv for lv in levels if lv["config"] == config and lv["re"] == RE
                       and lv.get("model", "sst") == "sst" and _steady(lv)
                       and _family(lv) == REFINED and abs(lv["q"] - r["q"]) < 1e-9]
                if not got:
                    continue
                lv = max(got, key=lambda x: x["k"])
                lim = r["u"] + tol[(config, coef)]
                ok = abs(lv[coef] - r["measured"]) <= lim
                n += 1
                n_pass += ok
                out.append(stored.row(f"{LABEL[config]} {coef} q {r['q']:.1f} (k = {lv['k']})",
                                      gate=f"within {lim:.3f} of {r['measured']:.3f}", ok=ok,
                                      value=f"{lv[coef]:.3f}",
                                      note=f"their CFD {r['cfd']:.3f}"))
            if n:
                out.append(stored.row(f"{LABEL[config]} {coef}: points passing",
                                      value=f"{n_pass} of {n}"))
    out += fixed_rows(levels, rows, tol)
    for name, rich in data.get("extra", {}).get("richardson", {}).items():
        for coef in ("xi_PG", "xi_MGb"):
            r = rich[coef]
            note = f"GCI {r['gci_fine']:.3f}" if r["status"] == "converging" else r["note"]
            out.append(stored.row(f"{name} {coef} (k = {', '.join(map(str, LEVELS))})",
                                  rich=r, gate="converging", ok=r["status"] == "converging",
                                  note=note))
    return out


def fixed_rows(levels: list[dict], rows: list[dict], tol: dict) -> list[dict]:
    """The fixed-wall family at FIXED_POINT (task 0186): its precursor's f
    per level (task 0049's gate), its coefficients against 0162's limits at
    its finest level, and their change between levels.  No GCI until a
    third level (the volunteer card's) is merged."""
    config, q = FIXED_POINT.split(":")
    q = float(q)
    fam = [lv for lv in levels if _family(lv) == FIXED and lv["config"] == config
           and abs(lv["q"] - q) < 1e-9 and lv["re"] == RE]
    # one method for every level (task 0186): time-accurate once any is
    accurate = [lv for lv in fam if lv.get("method") == "time_accurate"]
    fam = sorted(accurate or fam, key=lambda r: r["k"])
    out = []
    for lv in fam:
        pre = lv.get("precursor")
        if pre:
            out.append(stored.row(f"fixed wall k = {lv['k']}: precursor f against McKeon",
                                  gate=f"within {F_GATE:.0%}", ok=pre["f_ok"],
                                  value=f"{pre['f_err_mckeon']:+.2%}",
                                  note=f"wall cell y+ {pre['yplus_first_mean']:.1f}"))
    if not fam:
        return out
    top = fam[-1]
    for coef in ("xi_PG", "xi_MGb"):
        for r in rows:
            if (r["gamma"] == GAMMA and r["config"] == config and r["coefficient"] == coef
                    and abs(r["q"] - q) < 1e-9):
                lim = r["u"] + tol[(config, coef)]
                name = f"{LABEL[config]} {coef} q {q:.1f} (fixed wall, k = {top['k']})"
                mean = top.get("time_mean", {}).get(coef)
                note = (f"time mean {mean['mean']:.3f} ± {mean['std']:.3f}; " if mean else "")
                if top["k"] < FIXED_LEVELS[-1]:          # judged at level 2 (task 0186)
                    out.append(stored.row(name, value=f"{top[coef]:.3f}",
                                          note=note + f"gated at k = {FIXED_LEVELS[-1]}"))
                    continue
                out.append(stored.row(
                    name, gate=f"within {lim:.3f} of {r['measured']:.3f}",
                    ok=abs(top[coef] - r["measured"]) <= lim, value=f"{top[coef]:.3f}",
                    note=note + f"k = {top['k']} isn't the family's finest planned level"))
        if len(fam) > 1:
            a, b = fam[-2], fam[-1]
            out.append(stored.row(f"{LABEL[config]} {coef} q {q:.1f} (fixed wall): change "
                                  f"k = {a['k']} → {b['k']}",
                                  value=f"{b[coef] - a[coef]:+.4f}",
                                  note=f"{(b[coef] - a[coef]) / a[coef]:+.1%}"))
    return out


def analyse(levels: list[dict]) -> dict:
    """Richardson / GCI of both coefficients at the convergence points."""
    out = {}
    for spec in CONVERGENCE_POINTS:
        config, q = spec.split(":")
        rows = sorted((lv for lv in levels if lv["config"] == config and lv["re"] == RE
                       and lv.get("model", "sst") == "sst" and _steady(lv)
                       and _family(lv) == REFINED and abs(lv["q"] - float(q)) < 1e-9),
                      key=lambda r: r["k"])
        if [r["k"] for r in rows] != list(LEVELS):
            continue
        r21 = LEVELS[2] / LEVELS[1]
        r32 = LEVELS[1] / LEVELS[0]
        out[f"{LABEL[config]} q {float(q):.1f}"] = {
            coef: conv.richardson(*(r[coef] for r in rows), r21=r21, r32=r32, scale=1.0)
            for coef in ("xi_PG", "xi_MGb")}
    return out


def _parse_point(text: str) -> tuple[str, float]:
    config, q = text.split(":")
    if config not in CONFIGS:
        raise argparse.ArgumentTypeError(f"{config!r}: one of {list(CONFIGS)}")
    return config, float(q)


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--points", nargs="+", type=_parse_point, default=None,
                    help="config:q pairs, e.g. div_a:0.6 (default: every configuration at "
                         f"q = {', '.join(map(str, QS))})")
    ap.add_argument("--levels", nargs="+", type=int, default=[DEFAULT_LEVEL],
                    help="refined(k) levels (default %(default)s)")
    ap.add_argument("--re", type=float, default=RE,
                    help="the total branch's Reynolds number (default %(default)g)")
    ap.add_argument("--work", type=Path, default=HERE / "work",
                    help="folder for each point's OpenFOAM case (default: validation/junction_loss/work/, not committed); a point's case is deleted once its results are stored, unless --keep-work")
    ap.add_argument("--end-time", type=float, default=None,
                    help="the solver's last iteration (default 4000); it stops earlier once its "
                         f"residuals converge.  With --transient, seconds (default {TRANSIENT_END:g})")
    ap.add_argument("--window", type=float, default=None,
                    help="the coefficients are the mean over the solver's last WINDOW "
                         "iterations, their spread the standard deviation (default 1000).  With "
                         f"--transient, seconds of p's time average (default {TRANSIENT_WINDOW:g})")
    ap.add_argument("--samples", type=int, default=None,
                    help="pressure fields written across the window (default 10; with "
                         f"--transient {TRANSIENT_SAMPLES})")
    ap.add_argument("--wall", choices=sorted(NUT_WALL), default=None,
                    help="nut's wall function: spalding (nutUSpaldingWallFunction, the default "
                         "when steady) or nutk (nutkWallFunction, the default with --transient); "
                         "a level with the other one is named *_<wall>")
    ap.add_argument("--family", choices=(REFINED, FIXED), default=REFINED,
                    help="refined: refined(k) of k = 1, the wall cell split k ways (task 0162, "
                         f"the default); fixed_wall: the wall cell {FIXED_YPLUS} viscous units "
                         "high at every level, with the precursor's wall-function check "
                         "(task 0186); its levels are named fixed_*")
    ap.add_argument("--transient", action="store_true",
                    help="pimpleFoam from rest, as the paper's CFD (task 0162 Q3); never gated")
    ap.add_argument("--time-accurate", action="store_true",
                    help="the steady start, then pimpleFoam (SST, Spalding) with the convergence "
                         f"stop: both coefficients within {TA_BAND:g} relative over a "
                         "flow-through (task 0186); resumable; levels named transient_*")
    ap.add_argument("--np", type=int, default=1, dest="n_proc",
                    help="MPI processes per solve (check other runs first, CLAUDE.md)")
    ap.add_argument("--model", choices=sorted(MODELS), default="sst",
                    help="sst: k-ω SST, the gated model (default); rke: realizable k-ε, "
                         "for comparison with the paper's CFD (task 0162 step 4); "
                         "its levels are named *_rke and never gated")
    stored.add_arguments(ap, HERE)
    stored.add_openfoam_argument(ap, of.V2406)
    args = ap.parse_args(argv)
    steady = (4000, 1000, 10)
    transient = (TRANSIENT_END, TRANSIENT_WINDOW, TRANSIENT_SAMPLES)
    for name, default in zip(("end_time", "window", "samples"),
                             transient if args.transient else steady):
        if getattr(args, name) is None:
            setattr(args, name, default)
    if args.time_accurate and (args.transient or args.model != "sst" or args.wall):
        ap.error("--time-accurate runs SST with Spalding's wall: no --transient, --model, --wall")
    of.set_runner(args.openfoam)
    store = stored.Store(args.json, "junction_loss")
    store.put_extra("references", {
        "coefficients": "Štigler, Klas & Šperka (2014), figures 5, 6, 9-12, 15, 16, "
                        "digitised (reference/stigler_2014.csv, CC-BY 2.0)",
        "friction": "the solution's own gradient (the paper's §3); McKeon, Zagarola & "
                    "Smits (2005) eq. 3.5 for the *_mckeon variant"})
    points = args.points or [(c, q) for c in CONFIGS for q in QS]
    for config, q in points:
        for k in args.levels:
            name = point_name(config, q, k, args.re, args.model, args.transient, args.wall,
                              args.family, args.time_accurate)
            if args.time_accurate:
                run = (lambda c=config, q=q, k=k: run_time_accurate(
                    c, q, k, args.work, args.n_proc, args.re, args.family))
            else:
                run = (lambda c=config, q=q, k=k: run_point(
                    c, q, k, args.work, args.end_time, args.n_proc, args.re, args.window,
                    args.samples, args.model, args.transient, args.wall, args.family))
            r = stored.run_level(store, name, run, args.work / name, args.keep_work,
                                 cores=args.n_proc)
            print(f"[{name}] ξ_PG {r['xi_PG']:.4f} ± {r.get('xi_PG_spread') or 0:.4f} "
                  f"(McKeon {r['xi_PG_mckeon']:.4f}), ξ_MGb {r['xi_MGb']:.4f} "
                  f"± {r.get('xi_MGb_spread') or 0:.4f} (McKeon {r['xi_MGb_mckeon']:.4f}), "
                  f"steps {r['steps']}, converged {r['converged']}", flush=True)
    rich = analyse(store.levels())
    if rich:
        store.put_extra("richardson", rich)
    for row in recheck(store.data):
        print(json.dumps(row, ensure_ascii=False))
    return rich


if __name__ == "__main__":
    main()
