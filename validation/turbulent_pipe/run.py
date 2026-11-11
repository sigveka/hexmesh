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
Fully developed turbulent pipe flow, RANS k-ω SST (decision 0012, task 0049).

    python3 validation/turbulent_pipe/run.py                 # every case
    python3 validation/turbulent_pipe/run.py --cases lowre_550 --np 4

A periodic pipe: hexmesh's inlet and outlet faces become a translational
cyclic pair (``createPatch``), and ``meanVelocityForce`` drives the bulk
velocity to U_b.  Steady ``simpleFoam``; post-processing in Python.

**Cases.**  Re_b of the El Khoury et al. DNS at Re_τ = 550 (19 000) and
1000 (37 700), and 10⁵ (friction factor only), each with

- **lowre**: wall-resolved, the wall cell 1 viscous unit high at the
  design u_τ (``first_cell``; the achieved y⁺ is measured);
- **wf**: wall functions (``kqRWallFunction``, ``omegaWallFunction``,
  ``nutkWallFunction``: OpenFOAM's standard pairing, reported), the wall
  cell 100 viscous units high (its centre near y⁺ 50);
- **wfu**, **wfs**: the same with ``nutUWallFunction`` (reported) and
  ``nutUSpaldingWallFunction`` (the gated wall-function variant, task
  0049's design answer Q3).

lowre_550 runs at k = 1, 2, 4 (``refined(k)``: nang, nrad and the axial
layers ×k, the radial growth its k-th root, so the wall cell shrinks too).
The flow is axially uniform, so the axial count matters only through cell
aspect; it is scaled with the rest.  The other cases run at one level.

**Quantities.**  The wall shear stress follows exactly from the momentum
balance of the periodic pipe, τ_w = (dp/dx) V / A_wall, with dp/dx the
force ``meanVelocityForce`` applied; f = 8 τ_w / U_b².  U_c / U_b and
u⁺(y⁺) are interpolated from the cell centres of one cross-section along
the 45° radius.  References: McKeon et al. (2005) eq. 3.5 for f, the DNS
(``data/``, CC-BY-4.0) for U_c / U_b and u⁺.

OpenFOAM v2406 in Docker by default.
"""

from __future__ import annotations

import argparse
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

from hexmesh import Assembly, PipeSpec, Session, Straight      # noqa: E402
from hexmesh.study import openfoam as of                       # noqa: E402

_spec = importlib.util.spec_from_file_location("convergence",
                                               ROOT / "validation/tools/convergence.py")
conv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conv)       # richardson() (task 0089)
_spec = importlib.util.spec_from_file_location("stored", ROOT / "validation/tools/results.py")
stored = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stored)                # results.json (task 0093)

# --- physics -----------------------------------------------------------------
R = 0.05                  # pipe radius [m]
D = 2 * R
U_B = 1.0                 # bulk velocity [m/s]
LENGTH = R                # the periodic pipe; the flow doesn't vary along it
NANG, N_LAYERS = 12, 2    # at k = 1
GROWTH_MAX = 1.15         # radial growth ratio of the wall-resolved ring
YPLUS_SAMPLES = (1, 10, 30, 100)

#: DNS mean profiles [el_khoury_and_schlatter_etal_2013], Zenodo 10.5281/zenodo.7352880
DNS = {550: HERE / "data/550_Re_1.dat", 1000: HERE / "data/1000_Re_1.dat"}

#: name → Re_b, the DNS case it matches (None: f only), wall cell height
#: [viscous units at the design u_τ], wall treatment, levels
CASES = {
    "lowre_550": dict(re_b=19000, dns=550, wall_yplus=1, wall="lowre", levels=(1, 2, 4)),
    "lowre_1000": dict(re_b=37700, dns=1000, wall_yplus=1, wall="lowre", levels=(2,)),
    "lowre_1e5": dict(re_b=1e5, dns=None, wall_yplus=1, wall="lowre", levels=(2,)),
    "wf_550": dict(re_b=19000, dns=550, wall_yplus=100, wall="wf", levels=(1,)),
    "wf_1000": dict(re_b=37700, dns=1000, wall_yplus=100, wall="wf", levels=(1,)),
    "wf_1e5": dict(re_b=1e5, dns=None, wall_yplus=100, wall="wf", levels=(1,)),
}
# the same meshes with the velocity-based nutU and Spalding's continuous
# law (nutUSpalding, the gated variant) in place of nutk
for _re in ("550", "1000", "1e5"):
    for _w in ("wfu", "wfs"):
        CASES[f"{_w}_{_re}"] = dict(CASES[f"wf_{_re}"], wall=_w)


# --- references ----------------------------------------------------------------

def mckeon(re_b: float) -> float:
    """f from McKeon, Zagarola & Smits (2005) eq. 3.5 (fixed point):
    1/√f = 1.920 log10(Re √f) − 0.475 − 7.04 / (Re √f)^0.55."""
    f = 0.02
    for _ in range(200):
        s = re_b * math.sqrt(f)
        f = (1.920 * math.log10(s) - 0.475 - 7.04 / s ** 0.55) ** -2
    return f


def blasius(re_b: float) -> float:
    return 0.3164 * re_b ** -0.25


def read_dns(path: Path) -> dict:
    """Re_τ, u_τ/U_b and the profile columns (y⁺ ascending)."""
    text = path.read_text(encoding="utf-8")
    re_tau = float(re.search(r"Re_tau\s*=\s*([\d.E+-]+)", text).group(1))
    ratio = float(re.search(r"u_tau/U_b\s*=\s*([\d.E+-]+)", text).group(1))
    rows = np.array([line.split() for line in text.splitlines()
                     if re.match(r"\s*[\d.]+E[+-]\d+\s", line)], float)
    rows = rows[np.argsort(rows[:, 1])]
    return {"re_tau": re_tau, "u_tau_over_ub": ratio, "y_plus": rows[:, 1],
            "u_plus": rows[:, 2], "uc_over_ub": float(rows[-1, 3]),
            "f": 8 * ratio ** 2}


def design_u_tau(re_b: float) -> float:
    """u_τ from McKeon's f, for sizing the wall cell."""
    return U_B * math.sqrt(mckeon(re_b) / 8)


# --- the mesh -----------------------------------------------------------------

def wall_ring(first: float, nang: int = NANG) -> int:
    """The smallest nrad whose ring growth toward the centre is at most
    GROWTH_MAX with a wall cell of *first*."""
    for n in range(2, 200):
        try:
            spec = PipeSpec(nang=nang).core("fluid", radius=R, nrad=n, first_cell=first)
        except Exception:                          # first cell too large for n cells
            continue
        if 1 / spec.to_dict()["core"]["mprg"] <= GROWTH_MAX:
            return n
    raise ValueError(f"no ring for a first cell of {first}")


def assembly(name: str, k: int = 1) -> Assembly:
    c = CASES[name]
    nu = U_B * D / c["re_b"]
    first = c["wall_yplus"] * nu / design_u_tau(c["re_b"])
    nang = c.get("nang", NANG)
    spec = PipeSpec(nang=nang).core("fluid", radius=R, nrad=wall_ring(first, nang),
                                    first_cell=first)
    asm = Assembly(spec, position=[0, 0, 0], direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(LENGTH, n_layers=N_LAYERS))
    return asm if k == 1 else asm.refined(k)


def meshes():
    """(label, caption, build) per mesh shown in README.md."""
    return [(name, f"{name}, k = {CASES[name]['levels'][0]}",
             lambda n=name: assembly(n, CASES[n]["levels"][0])) for name in CASES]


# --- OpenFOAM dictionaries ---------------------------------------------------

H = of.header

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
    div(phi,k)      bounded Gauss linearUpwind grad(k);
    div(phi,omega)  bounded Gauss linearUpwind grad(omega);
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }
wallDist        { method meshWave; }
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
    "(U|k|omega)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-12;
        relTol          0.1;
    }
}
SIMPLE
{
    nNonOrthogonalCorrectors 0;
    pRefCell        0;
    pRefValue       0;
    residualControl
    {
        p               1e-6;
        U               1e-7;
        "(k|omega)"     1e-7;
    }
}
relaxationFactors
{
    fields          { p 0.3; }
    equations       { U 0.7; "(k|omega)" 0.7; }
}
"""

TURBULENCE = """simulationType  RAS;
RAS
{
    RASModel        kOmegaSST;
    turbulence      on;
    printCoeffs     on;
}
"""

FVOPTIONS = """momentumSource
{{
    type            meanVelocityForce;
    active          true;
    selectionMode   all;
    fields          (U);
    Ubar            ({u} 0 0);
}}
"""

CREATE_PATCH = """pointSync       false;
patches
(
    {{
        name            cyc_in;
        patchInfo
        {{
            type            cyclic;
            neighbourPatch  cyc_out;
            transform       translational;
            separationVector ({L} 0 0);
        }}
        constructFrom   patches;
        patches         (fluid_inlet);
    }}
    {{
        name            cyc_out;
        patchInfo
        {{
            type            cyclic;
            neighbourPatch  cyc_in;
            transform       translational;
            separationVector (-{L} 0 0);
        }}
        constructFrom   patches;
        patches         (fluid_outlet);
    }}
);
"""

#: wall boundary condition per field and wall treatment
WALL = {
    "lowre": {"U": "type noSlip;", "p": "type zeroGradient;",
              "k": "type fixedValue; value uniform 0;",
              "omega": "type omegaWallFunction; value uniform {omega};",
              "nut": "type nutLowReWallFunction; value uniform 0;"},
    "wf": {"U": "type noSlip;", "p": "type zeroGradient;",
           "k": "type kqRWallFunction; value uniform {k};",
           "omega": "type omegaWallFunction; value uniform {omega};",
           "nut": "type nutkWallFunction; value uniform 0;"},
}
WALL["wfu"] = dict(WALL["wf"], nut="type nutUWallFunction; value uniform 0;")
WALL["wfs"] = dict(WALL["wf"], nut="type nutUSpaldingWallFunction; value uniform 0;")
DIMS = {"U": "[0 1 -1 0 0 0 0]", "p": "[0 2 -2 0 0 0 0]", "k": "[0 2 -2 0 0 0 0]",
        "omega": "[0 0 -1 0 0 0 0]", "nut": "[0 2 -1 0 0 0 0]"}


def write_system(case: Path, end_time: int, nu: float) -> None:
    for d in ("0", "constant", "system"):
        (case / d).mkdir(parents=True, exist_ok=True)
    files = {
        "system/controlDict": H("dictionary", "controlDict", "system")
        + CONTROL.format(end_time=end_time),
        "system/fvSchemes": H("dictionary", "fvSchemes", "system") + SCHEMES,
        "system/fvSolution": H("dictionary", "fvSolution", "system") + SOLUTION,
        "system/createPatchDict": H("dictionary", "createPatchDict", "system")
        + CREATE_PATCH.format(L=repr(LENGTH)),
        "constant/transportProperties": H("dictionary", "transportProperties", "constant")
        + f"transportModel  Newtonian;\nnu              {nu!r};\n",
        "constant/turbulenceProperties": H("dictionary", "turbulenceProperties", "constant")
        + TURBULENCE,
        "constant/fvOptions": H("dictionary", "fvOptions", "constant")
        + FVOPTIONS.format(u=repr(U_B)),
    }
    for name, text in files.items():
        (case / name).write_text(text, encoding="utf-8")


def write_fields(case: Path, wall: str) -> None:
    """Initial fields: U_b everywhere, 5 % intensity, a 0.07 D mixing length."""
    k = 1.5 * (0.05 * U_B) ** 2
    omega = math.sqrt(k) / (0.09 ** 0.25 * 0.07 * D)
    internal = {"U": f"uniform ({U_B!r} 0 0)", "p": "uniform 0", "k": f"uniform {k!r}",
                "omega": f"uniform {omega!r}", "nut": "uniform 0"}
    for f, dims in DIMS.items():
        cls = "volVectorField" if f == "U" else "volScalarField"
        w = WALL[wall][f].format(k=repr(k), omega=repr(omega))
        text = (H(cls, f, "0") + f"dimensions      {dims};\ninternalField   {internal[f]};\n"
                "boundaryField\n{\n    cyc_in      { type cyclic; }\n"
                f"    cyc_out     {{ type cyclic; }}\n    fluid_wall  {{ {w} }}\n}}\n")
        (case / "0" / f).write_text(text, encoding="utf-8")


# --- post-processing -----------------------------------------------------------

def wall_distance(cc: np.ndarray, fc: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Each cell centre's distance to the nearest of the wall faces (centres
    *fc*, unit normals *n*), along that face's normal.  The meshed wall is
    faceted: between nodes it lies inside R, by about a viscous unit at
    k = 1, so R − r is not the wall distance near the wall."""
    from scipy.spatial import cKDTree
    _, near = cKDTree(fc).query(cc, k=4)
    d = np.abs(np.einsum("ijk,ijk->ij", cc[:, None, :] - fc[near], n[near]))
    return d.min(axis=1)


def _along_radius(cc: np.ndarray, yw: np.ndarray, u: np.ndarray, y: np.ndarray) -> np.ndarray:
    """u at wall distances *y* along the 45° radius of the first
    cross-section's cell centres, linear in (wall distance *yw*, angle).
    The centre (y = R) and the core (y ≥ R/2) are interpolated in
    Cartesian coordinates; NaN outside the cell centres (below the first)."""
    from scipy.interpolate import LinearNDInterpolator
    layers = np.unique(np.round(cc[:, 0] / LENGTH, 6)).size
    first = cc[:, 0] < cc[:, 0].min() + 0.5 * LENGTH / layers
    yz, v, w = cc[first][:, 1:], u[first], yw[first]
    y = np.asarray(y, float)
    out = np.full(len(y), np.nan)
    th = np.arctan2(yz[:, 1], yz[:, 0])
    ring = (w < 0.6 * R) & (np.abs(th - math.pi / 4) < math.pi / 4)
    rest = y < 0.5 * R
    polar = LinearNDInterpolator(np.c_[w[ring] / R, th[ring]], v[ring])
    out[rest] = polar(np.c_[y[rest] / R, np.full(int(rest.sum()), math.pi / 4)])
    s = (R - y[~rest]) / math.sqrt(2)
    out[~rest] = LinearNDInterpolator(yz, v)(np.c_[s, s])
    return out


def results(case: Path, nu: float, log: str, c: dict) -> dict:
    mesh = case / "constant/polyMesh"
    pts, faces = of.read_points(mesh / "points"), of.read_faces(mesh / "faces")
    owner, neigh = of.read_labels(mesh / "owner"), of.read_labels(mesh / "neighbour")
    t = of.latest_time(case)
    U = of.read_internal(t / "U", 3)
    fc, sf = of.face_geometry(pts, faces)
    cc, vol = of.cell_geometry(fc, sf, owner, neigh, len(U))
    wall = of.read_patch_faces(mesh / "boundary", "fluid_wall")
    a_wall = float(np.linalg.norm(sf[wall], axis=1).sum())
    grads = [float(v) for v in re.findall(r"pressure gradient = ([-\d.eE+]+)", log)]
    dpdx = grads[-1]
    tau = dpdx * vol.sum() / a_wall
    u_tau = math.sqrt(tau)
    ub = float(np.sum(vol * U[:, 0]) / vol.sum())
    n = sf[wall] / np.linalg.norm(sf[wall], axis=1)[:, None]
    d = np.abs(np.einsum("ij,ij->i", cc[owner[wall]] - fc[wall], n))
    yplus = u_tau * d / nu
    f = 8 * tau / ub ** 2
    ys = np.array(YPLUS_SAMPLES, float) * nu / u_tau
    line_y = R * (1 - np.r_[np.geomspace(1e-4, 0.5, 40), np.linspace(0.55, 1.0, 10)])
    # the last 50 steps' pressure-gradient drift: a convergence measure
    drift = abs(grads[-1] - grads[-51]) / abs(grads[-1]) if len(grads) > 51 else None
    yw = wall_distance(cc, fc[wall], n)
    up = _along_radius(cc, yw, U[:, 0], np.r_[ys, R, R - line_y]) / u_tau
    out = {
        "dpdx": dpdx, "dpdx_drift_50": drift, "tau_w": tau, "u_tau": u_tau, "u_b": ub,
        "re_tau": u_tau * R / nu, "f": f,
        "f_mckeon": mckeon(c["re_b"]), "f_blasius": blasius(c["re_b"]),
        "f_err_mckeon": f / mckeon(c["re_b"]) - 1,
        "yplus_first_max": float(yplus.max()), "yplus_first_mean": float(yplus.mean()),
        "uc_over_ub": float(up[len(ys)] * u_tau / ub),
        "u_plus_at": dict(zip(map(str, YPLUS_SAMPLES), map(_num, up[:len(ys)]))),
        "u_plus_centre": _num(up[len(ys)]),
        "profile": {"y_plus": (u_tau * (R - line_y) / nu).tolist(),
                    "u_plus": [_num(v) for v in up[len(ys) + 1:]]},
    }
    if c["dns"]:
        ref = read_dns(DNS[c["dns"]])
        out.update(
            dns_re_tau=ref["re_tau"], dns_f=ref["f"], f_err_dns=f / ref["f"] - 1,
            dns_uc_over_ub=ref["uc_over_ub"],
            uc_err=out["uc_over_ub"] / ref["uc_over_ub"] - 1,
            dns_u_plus_at={str(y): float(np.interp(y, ref["y_plus"], ref["u_plus"]))
                           for y in YPLUS_SAMPLES},
            dns_u_plus_centre=float(ref["u_plus"][-1]))
    return out


def _num(v) -> float | None:
    return None if v is None or not np.isfinite(v) else float(v)


def run_level(name: str, k: int, work: Path, end_time: int, n_proc: int) -> dict:
    c = CASES[name]
    nu = U_B * D / c["re_b"]
    case = work / f"{name}_k{k}"
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    asm = assembly(name, k)
    with Session(f"turbulent-pipe-{name}-{k}"):
        cells = asm.cell_count()
        print(f"[{name} k={k}] predicted cells: {cells}", flush=True)
        msh = case / "mesh.msh"
        asm.write_openfoam(str(msh))
        sj = asm.check_quality("scaled_jacobian").worst
    write_system(case, end_time, nu)
    # every hex right-handed: skip gmshToFoam's orientation test (task 0108)
    of.convert(case, msh, keep_orientation=sj > 0)
    of.foam("createPatch -overwrite", case, "log.createPatch")
    write_fields(case, c["wall"])
    check = of.check_mesh(case)
    log = of.run_solver(case, "simpleFoam", n_proc=n_proc)
    steps = re.findall(r"^Time = (\d+)", log, re.M)
    out = {"case": name, "k": k, "cells": cells, "re_b": c["re_b"], "nu": nu,
           "wall": c["wall"], "design_wall_yplus": c["wall_yplus"],
           **{f"check_{key}": v for key, v in check.items()}, **stored.counts(asm),
           "steps": int(steps[-1]) if steps else 0,
           "converged": "solution converged in" in log}
    out.update(results(case, nu, log, c))
    return out


# --- analysis -----------------------------------------------------------------

def analyse(levels: list[dict]) -> dict:
    """lowre_550's Richardson / GCI on f and U_c / U_b (k = 1, 2, 4)."""
    rows = sorted((lv for lv in levels if lv["case"] == "lowre_550"), key=lambda r: r["k"])
    if [r["k"] for r in rows] != [1, 2, 4]:
        return {}
    return {q: conv.richardson(*(r[q] for r in rows)) for q in ("f", "uc_over_ub")}


def table(levels: list[dict]) -> str:
    lines = ["| case | k | cells | y⁺ first (max) | Re_τ | f | f vs McKeon | U_c/U_b | "
             "U_c vs DNS | steps |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in levels:
        uc = f"{100 * r['uc_err']:+.2f} %" if "uc_err" in r else "—"
        lines.append(f"| {r['case']} | {r['k']} | {r['cells']} | {r['yplus_first_max']:.2f} | "
                     f"{r['re_tau']:.0f} | {r['f']:.5f} | {100 * r['f_err_mckeon']:+.2f} % | "
                     f"{r['uc_over_ub']:.4f} | {uc} | {r['steps']} |")
    return "\n".join(lines)


# The gated wall treatments (task 0049, design answers 2026-11-06): the
# mesh's part is gated, the turbulence model's reported.  The validated
# wall-function variant is Spalding's law; nutk and nutU are reported.
F_GATE = {"lowre": 0.03, "wfs": 0.05}
UC_LIMIT = 0.03                 # U_c/U_b against the DNS: reported (SST's wake)


def recheck(data: dict) -> list[dict]:
    """The gates from ``results.json`` (task 0049, design answers Q1-Q3):
    f within 3 % of McKeon (wall-resolved, finest level) and 5 %
    (Spalding wall functions); lowre_550's f and U_c/U_b converging under
    refinement (GCI reported).  U_c/U_b against the DNS, and the nutk and
    nutU wall functions, are reported."""
    rich = analyse(data["levels"])
    out = []
    for q in ("f", "uc_over_ub"):
        if q in rich:
            r = rich[q]
            note = f"GCI {r['gci_fine']:.2%}" if r["status"] == "converging" else r["note"]
            if q == "f" and r["status"] == "converging":
                ext = r["extrapolated"] / mckeon(CASES["lowre_550"]["re_b"]) - 1
                note += f"; extrapolated {ext:+.2%} from McKeon (converging slowly)"
            out.append(stored.row(f"lowre_550 {q} (k = 1, 2, 4)", rich=r,
                                  gate="converging", ok=r["status"] == "converging",
                                  note=note))
    for name in sorted({lv["case"] for lv in data["levels"]}):
        c = CASES[name]
        lv = max((x for x in data["levels"] if x["case"] == name), key=lambda x: x["k"])
        lim = F_GATE.get(c["wall"])
        out.append(stored.row(f"{name} f (k = {lv['k']})",
                              gate=f"within {lim:.0%} of McKeon" if lim else None,
                              ok=abs(lv["f_err_mckeon"]) <= lim if lim else None,
                              value=f"{lv['f_err_mckeon']:+.2%}",
                              note=f"y+ first {lv['yplus_first_max']:.2f}"))
        if "uc_err" in lv:
            within = abs(lv["uc_err"]) <= UC_LIMIT
            out.append(stored.row(f"{name} U_c/U_b (k = {lv['k']})",
                                  value=f"{lv['uc_err']:+.2%}",
                                  note=f"3 % comparison with the DNS: "
                                       f"{'within' if within else 'missed'}"))
    return out


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--cases", nargs="+", choices=list(CASES), default=list(CASES),
                    help="cases to run: 'lowre' resolves the wall (first cell at y+ 1), 'wf' uses wall functions (y+ 100), 'wfu' and 'wfs' the velocity-based nutU and Spalding's law (nutUSpalding: the gated variant); 550 and 1000 are the DNS friction Reynolds numbers, 1e5 a bulk Reynolds number without DNS (default: all of %(choices)s)")
    ap.add_argument("--levels", nargs="+", type=int, default=None,
                    help="override every case's levels")
    ap.add_argument("--work", type=Path, default=HERE / "work",
                    help="folder for each level's OpenFOAM case (default: validation/turbulent_pipe/work/, not committed); a level's case is deleted once its results are stored, unless --keep-work")
    ap.add_argument("--end-time", type=int, default=20000,
                    help="the solver's last iteration (default %(default)s); the solve stops earlier once its residuals converge")
    ap.add_argument("--np", type=int, default=1, dest="n_proc",
                    help="MPI processes per solve (check other runs first, CLAUDE.md)")
    stored.add_arguments(ap, HERE)
    stored.add_openfoam_argument(ap, of.V2406)
    args = ap.parse_args(argv)
    of.set_runner(args.openfoam)
    store = stored.Store(args.json, "turbulent_pipe")
    store.put_extra("references", {
        "f": "McKeon, Zagarola & Smits (2005) eq. 3.5",
        "profiles": "El Khoury et al. (2013), Zenodo 10.5281/zenodo.7352880, CC-BY-4.0"})
    for name in args.cases:
        for k in args.levels or CASES[name]["levels"]:
            r = stored.run_level(store, f"{name}_k{k}",
                                 lambda name=name, k=k: run_level(name, k, args.work,
                                                                  args.end_time, args.n_proc),
                                 args.work / f"{name}_k{k}", args.keep_work)
            print(f"[{name} k={k}] f {r['f']:.5f} ({100 * r['f_err_mckeon']:+.2f} % McKeon), "
                  f"U_c/U_b {r['uc_over_ub']:.4f}, y+ {r['yplus_first_max']:.2f}, "
                  f"steps {r['steps']}", flush=True)
    rich = analyse(store.levels())
    if rich:
        store.put_extra("richardson_lowre_550", rich)
    print(table(sorted(store.levels(), key=lambda r: (r["case"], r["k"]))))
    return rich


if __name__ == "__main__":
    main()
