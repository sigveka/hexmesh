#!/usr/bin/env python3
"""
Heated multi-layer pipe with laminar flow, full conjugate heat transfer
(decision 0012, docs/tasks/0035): Poiseuille flow in a fluid core inside
a steel shell and an insulation shell, uniform heat flux into the outer
surface, against the exact developed solution.

    hexmesh Assembly (three materials) → write_openfoam → gmshToFoam
    → splitMeshRegions -cellZones → apply_boundary_roles_to_regions
    → checkMesh per region → topoSet (fluid planes) → parabolic inlet
    → chtMultiRegionSimpleFoam → Python post-processing

Exact, thermally and hydrodynamically developed, uniform flux: the bulk
temperature rises at q′/(ṁ c_p); the fluid side has Nu = 48/11; each
solid layer's temperature drop is q′/(2π k) ln(r_out/r_in).  Three
levels by ``Assembly.refined(k)``, k = 1 / 2 / 4.  Usage::

    python3 validation/heated_pipe/run.py [--levels 1 2 4] [--np N]
        [--end-time N] [--work DIR] [--json FILE]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import shutil
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

import sys                                                     # noqa: E402
sys.path.insert(0, str(ROOT))

from hexmesh import Assembly, PipeSpec, Session, Straight      # noqa: E402
from hexmesh.study import openfoam as of                       # noqa: E402

_spec = importlib.util.spec_from_file_location("poiseuille_run",
                                               ROOT / "validation/poiseuille/run.py")
pois = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pois)                  # richardson(), versions()

# --- physics -----------------------------------------------------------------
R1, R2, R3 = 0.010, 0.012, 0.020             # fluid, steel, insulation outer radii [m]
D = 2 * R1
K = {"steel": 50.0, "insulation": 0.05}      # solids, as task 0034 [W/(m K)]
CP_S, RHO_S = 500.0, 8000.0                  # solids; don't matter at steady state
RE, PR = 100, 1.0
RHO, CP, MU = 1000.0, 4000.0, 1.0e-3         # fluid, constant properties
K_F = MU * CP / PR                           # 4 W/(m K): Pr = 1
U_MEAN = RE * MU / (RHO * D)                 # 5e-3 m/s
Q_OUT = 800.0                                # q″₃ into the outer surface [W/m²]
T_IN = 300.0
NU_EXACT = 48 / 11
LENGTH = 30 * D
X_A, X_B = 20 * D, 25 * D                    # measurement planes; Nu at the middle
PLANES = {"planeA": X_A, "planeB": X_B}
SOLIDS = ("steel", "insulation")
REGIONS = ("fluid",) + SOLIDS


def exact() -> dict:
    qp = Q_OUT * 2 * math.pi * R3                                  # W/m
    mdot = RHO * U_MEAN * math.pi * R1**2
    return {"q_prime": qp, "mdot": mdot, "dtb_dx": qp / (mdot * CP),
            "nu": NU_EXACT,
            "tw_minus_tb": qp / (2 * math.pi * R1) * D / (K_F * NU_EXACT),
            "dt_steel": qp / (2 * math.pi * K["steel"]) * math.log(R2 / R1),
            "dt_insulation": qp / (2 * math.pi * K["insulation"]) * math.log(R3 / R2)}


# --- mesh --------------------------------------------------------------------
# One axial spacing throughout (0.625 D), so the planes at 20 D and 25 D are
# fitting interfaces with equal cells either side.
BASE = dict(nang=6, fluid=3, steel=2, insulation=3, n_layers=(32, 8, 8))   # 20, 5, 5 D


def assembly(k: int = 1) -> Assembly:
    spec = (PipeSpec(nang=BASE["nang"]).core("fluid", radius=R1, nrad=BASE["fluid"])
            .shell("steel", dR=R2 - R1, nrad=BASE["steel"])
            .shell("insulation", dR=R3 - R2, nrad=BASE["insulation"]))
    asm = Assembly(spec, position=[0, 0, 0], direction=[1, 0, 0], up=[0, 0, 1])
    lengths = (X_A, X_B - X_A, LENGTH - X_B)
    for i, (L, n) in enumerate(zip(lengths, BASE["n_layers"])):
        asm.add(Straight(L, n_layers=n), **({"names": ["outlet"]} if i == 2 else {}))
    return asm if k == 1 else asm.refined(k)


def meshes():
    """(label, caption, build) per mesh shown in README.md
    (``docs/gallery/build.py --validation``)."""
    return [(f"k{k}", f"k = {k}: nang {BASE['nang'] * k}, nrad {BASE['fluid'] * k} / "
                      f"{BASE['steel'] * k} / {BASE['insulation'] * k}, "
                      f"{sum(BASE['n_layers']) * k} axial layers",
             lambda k=k: assembly(k)) for k in (1, 2, 4)]


# --- case --------------------------------------------------------------------
H = of.header

CONTROL = """application     chtMultiRegionSimpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};
deltaT          1;
writeControl    timeStep;
writeInterval   {end_time};
writeFormat     ascii;
writePrecision  17;
writeCompression off;
timeFormat      general;
runTimeModifiable false;
"""

SOLID_SCHEMES = """ddtSchemes      { default steadyState; }
gradSchemes     { default Gauss linear; }
divSchemes      { default none; }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }
"""

FLUID_SCHEMES = """ddtSchemes      { default steadyState; }
gradSchemes     { default Gauss linear; }
divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss limitedLinearV 1;
    div(phi,h)      bounded Gauss limitedLinear 1;
    div(phi,K)      bounded Gauss linear;
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }
"""

SOLID_SOLUTION = """solvers
{
    h { solver PCG; preconditioner DIC; tolerance 1e-14; relTol 0; }
}
SIMPLE
{
    nNonOrthogonalCorrectors 2;
}
relaxationFactors { equations { h 1; } }
"""

FLUID_SOLUTION = """solvers
{
    p_rgh { solver GAMG; smoother GaussSeidel; tolerance 1e-12; relTol 0.01; }
    "(U|h)" { solver PBiCGStab; preconditioner DILU; tolerance 1e-14; relTol 0.01; }
}
SIMPLE
{
    nNonOrthogonalCorrectors 0;
}
relaxationFactors
{
    fields          { rho 1; p_rgh 0.3; }
    equations       { U 0.3; h 0.3; }
}
"""

SOLID_THERMO = """thermoType
{{
    type            heSolidThermo;
    mixture         pureMixture;
    transport       constIso;
    thermo          hConst;
    equationOfState rhoConst;
    specie          specie;
    energy          sensibleEnthalpy;
}}
mixture
{{
    specie          {{ molWeight 50; }}
    transport       {{ kappa {k}; }}
    thermodynamics  {{ Hf 0; Cp {cp}; }}
    equationOfState {{ rho {rho}; }}
}}
"""

FLUID_THERMO = f"""thermoType
{{
    type            heRhoThermo;
    mixture         pureMixture;
    transport       const;
    thermo          hConst;
    equationOfState rhoConst;
    specie          specie;
    energy          sensibleEnthalpy;
}}
mixture
{{
    specie          {{ molWeight 18; }}
    equationOfState {{ rho {RHO}; }}
    thermodynamics  {{ Hf 0; Cp {CP}; }}
    transport       {{ mu {MU}; Pr {PR}; }}
}}
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


def write_dicts(case: Path, end_time: int, n_proc: int) -> None:
    """The dictionaries splitMeshRegions and the solver need (no fields)."""
    files = {
        "system/controlDict": H("dictionary", "controlDict", "system")
        + CONTROL.format(end_time=end_time),
        "system/fvSchemes": H("dictionary", "fvSchemes", "system") + SOLID_SCHEMES,
        "system/fvSolution": H("dictionary", "fvSolution", "system") + "SIMPLE {}\n",
        "constant/g": H("uniformDimensionedVectorField", "g", "constant")
        + "dimensions [0 1 -2 0 0 0 0];\nvalue (0 0 0);\n",
        "constant/regionProperties": H("dictionary", "regionProperties", "constant")
        + f"regions\n(\n    fluid (fluid)\n    solid ({' '.join(SOLIDS)})\n);\n",
        "system/fluid/fvSchemes": H("dictionary", "fvSchemes", "system/fluid") + FLUID_SCHEMES,
        "system/fluid/fvSolution": H("dictionary", "fvSolution", "system/fluid")
        + FLUID_SOLUTION,
        "system/fluid/topoSetDict": H("dictionary", "topoSetDict", "system/fluid")
        + TOPOSET.format(actions="\n".join(
            ZONE.format(n=n, x0=x - 1e-3 * D, x1=x + 1e-3 * D) for n, x in PLANES.items())),
        "constant/fluid/thermophysicalProperties": H(
            "dictionary", "thermophysicalProperties", "constant/fluid") + FLUID_THERMO,
        "constant/fluid/turbulenceProperties": H(
            "dictionary", "turbulenceProperties", "constant/fluid") + "simulationType laminar;\n",
    }
    for r in SOLIDS:
        files[f"system/{r}/fvSchemes"] = H("dictionary", "fvSchemes", f"system/{r}") + SOLID_SCHEMES
        files[f"system/{r}/fvSolution"] = (H("dictionary", "fvSolution", f"system/{r}")
                                           + SOLID_SOLUTION)
        files[f"constant/{r}/thermophysicalProperties"] = (
            H("dictionary", "thermophysicalProperties", f"constant/{r}")
            + SOLID_THERMO.format(k=K[r], cp=CP_S, rho=RHO_S))
    if n_proc > 1:
        # slabs along the pipe: this build's Scotch is a dummy
        # (docs/integrations/openfoam.md)
        files["system/decomposeParDict"] = (
            H("dictionary", "decomposeParDict", "system")
            + f"numberOfSubdomains {n_proc};\nmethod          simple;\n"
              f"simpleCoeffs {{ n ({n_proc} 1 1); delta 0.001; }}\n")
    for name, text in files.items():
        (case / name).parent.mkdir(parents=True, exist_ok=True)
        (case / name).write_text(text)
    if n_proc > 1:
        for r in REGIONS:
            shutil.copy(case / "system/decomposeParDict", case / f"system/{r}/decomposeParDict")


def patches(case: Path, region: str) -> list[str]:
    text = (case / f"constant/{region}/polyMesh/boundary").read_text()
    return re.findall(r"^\s{4}(\w+)\s*\n\s*\{", text, re.M)


COUPLED = ("type compressible::turbulentTemperatureCoupledBaffleMixed; Tnbr T; "
           "kappaMethod {m}; value uniform {t};")


def write_fields(case: Path) -> None:
    def field(region, name, cls, dims, internal, bcs):
        body = "\n".join(f"    {p} {{ {b} }}" for p, b in bcs.items())
        (case / f"0/{region}").mkdir(parents=True, exist_ok=True)
        (case / f"0/{region}/{name}").write_text(
            H(cls, name, f"0/{region}") + f"dimensions {dims};\ninternalField {internal};\n"
            f"boundaryField\n{{\n{body}\n}}\n")

    fp = patches(case, "fluid")
    wall = [p for p in fp if "_to_" in p]
    t_bc = {}
    for p in fp:
        if p == "fluid_inlet":
            t_bc[p] = f"type fixedValue; value uniform {T_IN};"
        elif p == "fluid_outlet":
            t_bc[p] = f"type inletOutlet; inletValue uniform {T_IN}; value uniform {T_IN};"
        else:
            t_bc[p] = COUPLED.format(m="fluidThermo", t=T_IN)
    field("fluid", "T", "volScalarField", "[0 0 0 1 0 0 0]", f"uniform {T_IN}", t_bc)
    field("fluid", "U", "volVectorField", "[0 1 -1 0 0 0 0]", "uniform (0 0 0)",
          {p: ("type fixedValue; value uniform (0 0 0);" if p == "fluid_inlet" else
               "type zeroGradient;" if p == "fluid_outlet" else "type noSlip;") for p in fp})
    field("fluid", "p_rgh", "volScalarField", "[1 -1 -2 0 0 0 0]", "uniform 1e5",
          {p: ("type fixedValue; value uniform 1e5;" if p == "fluid_outlet" else
               "type fixedFluxPressure; value uniform 1e5;") for p in fp})
    field("fluid", "p", "volScalarField", "[1 -1 -2 0 0 0 0]", "uniform 1e5",
          {p: "type calculated; value uniform 1e5;" for p in fp})
    assert wall, fp
    for r in SOLIDS:
        bc = {}
        for p in patches(case, r):
            if "_to_" in p:
                bc[p] = COUPLED.format(m="solidThermo", t=T_IN)
            elif p == f"{r}_wall":
                # flux mode: q″ into the region (positive heats it)
                bc[p] = (f"type externalWallHeatFluxTemperature; mode flux; q uniform {Q_OUT}; "
                         f"kappaMethod solidThermo; value uniform {T_IN};")
            else:
                bc[p] = "type zeroGradient;"           # pipe ends: adiabatic
        field(r, "T", "volScalarField", "[0 0 0 1 0 0 0]", f"uniform {T_IN}", bc)
        field(r, "p", "volScalarField", "[1 -1 -2 0 0 0 0]", "uniform 1e5",
              {'".*"': "type calculated; value uniform 1e5;"})


def parabolic_inlet(case: Path) -> float:
    """The developed profile u = 2Ū(1 − r²/R1²): at the inlet face centres,
    scaled so the discrete flow rate is Ū · A_mesh, and, with the same
    scale, as the initial field in every cell (the flow is developed
    throughout, so the coupling starts from the exact flow).  Returns the
    scale."""
    mesh = case / "constant/fluid/polyMesh"
    pts, faces = of.read_points(mesh / "points"), of.read_faces(mesh / "faces")
    owner, neigh = of.read_labels(mesh / "owner"), of.read_labels(mesh / "neighbour")
    ids = of.read_patch_faces(mesh / "boundary", "fluid_inlet")
    c, sf = of.face_geometry(pts, [faces[i] for i in ids])
    a = np.linalg.norm(sf, axis=1)

    def profile(x):
        return 2 * U_MEAN * np.clip(1 - (np.hypot(x[:, 1], x[:, 2]) / R1) ** 2, 0, None)
    u = profile(c)
    scale = U_MEAN * a.sum() / float((u * a).sum())
    u *= scale
    fc, fsf = of.face_geometry(pts, faces)
    cc, _ = of.cell_geometry(fc, fsf, owner, neigh, int(owner.max()) + 1)
    uc = scale * profile(cc)

    def vectors(v):
        return f"nonuniform List<vector>\n{len(v)}\n(\n" + "\n".join(
            f"({x:.15g} 0 0)" for x in v) + "\n)"
    path = case / "0/fluid/U"
    text = re.sub(r"fluid_inlet\s*\{[^}]*\}",
                  f"fluid_inlet {{ type fixedValue; value {vectors(u)}; }}", path.read_text())
    text = text.replace("internalField uniform (0 0 0);", f"internalField {vectors(uc)};")
    path.write_text(text)
    return scale


# --- post-processing ---------------------------------------------------------

def region(case: Path, name: str) -> dict:
    mesh = case / f"constant/{name}/polyMesh"
    pts, faces = of.read_points(mesh / "points"), of.read_faces(mesh / "faces")
    owner, neigh = of.read_labels(mesh / "owner"), of.read_labels(mesh / "neighbour")
    t = of.latest_time(case)
    T = of.read_internal(t / name / "T", 1)
    fc, sf = of.face_geometry(pts, faces)
    cc, vol = of.cell_geometry(fc, sf, owner, neigh, len(T))
    return dict(mesh=mesh, t=t, T=T, fc=fc, sf=sf, cc=cc, vol=vol, owner=owner,
                neigh=neigh, name=name)


def patch(f: dict, name: str, k: float) -> dict:
    """Face values, areas, x and the conducted heat leaving the region
    through each face [W] (from the wall cells)."""
    ids = of.read_patch_faces(f["mesh"] / "boundary", name)
    tf = of.read_patch_values(f["t"] / f["name"] / "T", name, n=len(ids))
    a = np.linalg.norm(f["sf"][ids], axis=1)
    n = f["sf"][ids] / a[:, None]
    cell = f["owner"][ids]
    d = np.einsum("ij,ij->i", f["fc"][ids] - f["cc"][cell], n)
    return dict(T=tf, a=a, x=f["fc"][ids, 0], q=k * (f["T"][cell] - tf) / d * a, ids=ids)


def band(p: dict) -> float:
    """Area average over X_A < x < X_B: T is linear in x there and the
    faces are symmetric about the middle, so this is T at (X_A + X_B)/2."""
    m = (p["x"] > X_A) & (p["x"] < X_B)
    return float((p["T"][m] * p["a"][m]).sum() / p["a"][m].sum())


def results(case: Path) -> dict:
    ex = exact()
    fl = region(case, "fluid")
    so = {r: region(case, r) for r in SOLIDS}
    t = fl["t"]
    U = of.read_internal(t / "fluid/U", 3)

    # mixing-cup temperature on each plane: equal cells either side, so
    # face values are the owner/neighbour means
    tb = {}
    for name in PLANES:
        ids = of.read_zone(fl["mesh"] / "faceZones", name)
        a = np.linalg.norm(fl["sf"][ids], axis=1)
        o, nb = fl["owner"][ids], fl["neigh"][ids]
        u = 0.5 * (U[o, 0] + U[nb, 0])
        T = 0.5 * (fl["T"][o] + fl["T"][nb])
        tb[name] = float((u * T * a).sum() / (u * a).sum())
    phi_in = of.read_patch_values(t / "fluid/phi", "fluid_inlet")
    phi_out = of.read_patch_values(t / "fluid/phi", "fluid_outlet")
    mdot = float(phi_out.sum())
    mass_err = abs(mdot + float(phi_in.sum())) / mdot

    # heat into the outer surface (the mesh's own area), and the enthalpy
    # rise plus axial conduction out through the fluid ends
    outer = patch(so["insulation"], "insulation_wall", K["insulation"])
    heat_in = Q_OUT * float(outer["a"].sum())
    ends = {e: patch(fl, f"fluid_{e}", K_F) for e in ("inlet", "outlet")}
    rise = CP * (float((phi_out * ends["outlet"]["T"]).sum())
                 + float((phi_in * ends["inlet"]["T"]).sum()))
    conduction = float(ends["inlet"]["q"].sum() + ends["outlet"]["q"].sum())
    energy_err = (rise + conduction - heat_in) / heat_in

    # the meshed reference: q′ from the mesh's outer area per length, ṁ
    # measured (decision 0015)
    qp_mesh = heat_in / LENGTH
    dtb_dx = (tb["planeB"] - tb["planeA"]) / (X_B - X_A)
    tb_mid = 0.5 * (tb["planeA"] + tb["planeB"])
    walls = {"fluid": patch(fl, "fluid_to_steel", K_F),
             "steel_in": patch(so["steel"], "steel_to_fluid", K["steel"]),
             "steel_out": patch(so["steel"], "steel_to_insulation", K["steel"]),
             "insulation_in": patch(so["insulation"], "insulation_to_steel", K["insulation"]),
             "insulation_out": outer}
    tw = {k: band(v) for k, v in walls.items()}
    nu = qp_mesh / (2 * math.pi * R1) * D / (K_F * (tw["fluid"] - tb_mid))
    dt_steel = tw["steel_out"] - tw["steel_in"]
    dt_ins = tw["insulation_out"] - tw["insulation_in"]
    ex_mesh = {"dtb_dx": qp_mesh / (mdot * CP),
               "dt_steel": qp_mesh / (2 * math.pi * K["steel"]) * math.log(R2 / R1),
               "dt_insulation": qp_mesh / (2 * math.pi * K["insulation"]) * math.log(R3 / R2)}
    return {
        "exact": ex, "exact_mesh": ex_mesh, "q_prime_mesh": qp_mesh, "mdot": mdot,
        "mdot_err": (mdot - ex["mdot"]) / ex["mdot"], "mass_err": mass_err,
        "heat_in": heat_in, "enthalpy_rise": rise, "end_conduction": conduction,
        "energy_err": energy_err,
        "tb_planeA": tb["planeA"], "tb_planeB": tb["planeB"], "dtb_dx": dtb_dx,
        "dtb_dx_err": (dtb_dx - ex_mesh["dtb_dx"]) / ex_mesh["dtb_dx"],
        "t_wall": tw, "nu": nu, "nu_err": (nu - NU_EXACT) / NU_EXACT,
        "interface_match": {"steel_fluid": tw["steel_in"] - tw["fluid"],
                            "insulation_steel": tw["insulation_in"] - tw["steel_out"]},
        "dt_steel": dt_steel, "dt_steel_err": (dt_steel - ex_mesh["dt_steel"]) / ex_mesh["dt_steel"],
        "dt_insulation": dt_ins,
        "dt_insulation_err": (dt_ins - ex_mesh["dt_insulation"]) / ex_mesh["dt_insulation"],
    }


# --- driver ------------------------------------------------------------------

def residual_history(log: str) -> list[tuple[int, dict]]:
    """(step, {field: largest initial residual over the regions' solves})."""
    parts = re.split(r"\nTime = (\d+)\n", log)
    out = []
    for i in range(1, len(parts), 2):
        res: dict[str, float] = {}
        for f, v in re.findall(r"Solving for (\w+), Initial residual = ([\d.e+-]+)",
                               parts[i + 1]):
            res[f] = max(res.get(f, 0.0), float(v))
        if res:
            out.append((int(parts[i]), res))
    return out


def run_level(k: int, work: Path, end_time: int, n_proc: int) -> dict:
    case = work / f"k{k}"
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    with Session(f"heated-pipe-{k}"):
        asm = assembly(k)
        cells = asm.cell_count()
        print(f"[k{k}] predicted cells: {cells}", flush=True)
        msh = case / "pipe.msh"
        asm.write_openfoam(str(msh))
        sj = asm.check_quality("scaled_jacobian").worst
    write_dicts(case, end_time, n_proc)
    retyped = of.convert(case, msh, split_regions=True)
    checks = {r: of.check_mesh(case, r) for r in REGIONS}
    write_fields(case)
    of.foam("topoSet -region fluid", case, "log.topoSet")
    scale = parabolic_inlet(case)
    if n_proc > 1:
        of.foam("decomposePar -allRegions -force", case, "log.decomposePar")
        solve = of.foam(f"mpirun -np {n_proc} chtMultiRegionSimpleFoam -parallel", case,
                        "log.chtMultiRegionSimpleFoam")
        of.foam("reconstructPar -allRegions -latestTime", case, "log.reconstructPar")
    else:
        solve = of.foam("chtMultiRegionSimpleFoam", case, "log.chtMultiRegionSimpleFoam")
    history = residual_history(solve)
    out = {
        "k": k, "nang": BASE["nang"] * k, "cells": cells,
        "cells_foam": sum(c["cells_foam"] for c in checks.values()),
        "mesh_ok": all(c["mesh_ok"] for c in checks.values()), "checks": checks,
        "patches": {r: patches(case, r) for r in REGIONS},
        "retyped": retyped, "min_scaled_jacobian": sj, "inlet_scale": scale,
        "iterations": history[-1][0], "last_residuals": history[-1][1],
        "residual_history": history[::max(1, len(history) // 200)], "n_proc": n_proc,
    }
    out.update(results(case))
    return out


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--levels", nargs="+", type=int, default=[1, 2, 4])
    ap.add_argument("--work", type=Path, default=HERE / "work")
    ap.add_argument("--end-time", type=int, default=20000)
    ap.add_argument("--np", type=int, default=1, dest="n_proc",
                    help="MPI processes (levels above 1)")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    rows = []
    for k in args.levels:
        r = run_level(k, args.work, args.end_time, 1 if k == 1 else args.n_proc)
        print(json.dumps({key: v for key, v in r.items()
                          if key not in ("checks", "residual_history")}, default=float),
              flush=True)
        rows.append(r)
    rich = {}
    if len(rows) == 3:
        for key in ("nu", "dt_steel", "dt_insulation", "dtb_dx"):
            try:
                rich[key] = pois.richardson(*(r[key] for r in rows))
            except (ValueError, ZeroDivisionError) as e:
                rich[key] = {"error": str(e)}
    data = {"versions": pois.versions(), "levels": rows, "richardson": rich}
    if args.json:
        args.json.write_text(json.dumps(data, indent=1, default=float))
    return data


if __name__ == "__main__":
    main()
