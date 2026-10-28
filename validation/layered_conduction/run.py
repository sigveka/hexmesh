#!/usr/bin/env python3
"""
Conduction through a heated, multi-layer cylinder (decision 0012,
docs/tasks/0034): a rod with uniform heat generation in a steel shell
and an insulation shell, solids only, against the exact solution.

    hexmesh Assembly (three materials) → write_openfoam → gmshToFoam
    → splitMeshRegions -cellZones → apply_boundary_roles_to_regions
    → checkMesh per region → chtMultiRegionSimpleFoam → Python post-processing

Two variants: the outer surface held at T₃ (``fixed``), and convection to
T∞ (``convection``).  Three levels, ``nang`` 6 / 12 / 24 with every
``nrad`` scaled (``Assembly.refined``; the axial count stays at 2: the
problem is axially uniform).  Usage::

    python3 validation/layered_conduction/run.py [--levels 1 2 4]
        [--variants fixed convection] [--work DIR] [--json FILE]
"""

from __future__ import annotations

import argparse
import datetime
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

import gmsh                                                    # noqa: E402

from hexmesh import Assembly, PipeSpec, Session, Straight      # noqa: E402
from hexmesh.assembly import intent                            # noqa: E402
from hexmesh.study import openfoam as of                       # noqa: E402

_spec = importlib.util.spec_from_file_location("poiseuille_run",
                                               ROOT / "validation/poiseuille/run.py")
pois = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pois)                  # richardson(), versions()

# --- physics -----------------------------------------------------------------
R1, R2, R3 = 0.010, 0.012, 0.020             # rod, steel, insulation outer radii [m]
K = {"rod": 20.0, "steel": 50.0, "insulation": 0.05}    # W/(m K)
Q3 = 1.0e6                                   # q''' in the rod [W/m³]
T_OUT = 300.0                                # fixed: T₃; convection: T∞ [K]
H_CONV = 20.0                                # convection coefficient [W/(m² K)]
LENGTH = 0.004
REGIONS = ("rod", "steel", "insulation")
CP, RHO = 500.0, 8000.0                      # don't matter at steady state


def exact(variant: str) -> dict:
    """Exact radii temperatures and the profile T(r)."""
    qp = Q3 * math.pi * R1**2                                  # W/m
    t3 = T_OUT if variant == "fixed" else T_OUT + qp / (2 * math.pi * R3 * H_CONV)
    t2 = t3 + qp / (2 * math.pi * K["insulation"]) * math.log(R3 / R2)
    t1 = t2 + qp / (2 * math.pi * K["steel"]) * math.log(R2 / R1)
    t0 = t1 + Q3 * R1**2 / (4 * K["rod"])

    def profile(r):
        r = np.asarray(r, float)
        return np.where(
            r <= R1, t1 + Q3 * (R1**2 - r**2) / (4 * K["rod"]),
            np.where(r <= R2, t2 + qp / (2 * math.pi * K["steel"]) * np.log(R2 / np.maximum(r, 1e-30)),
                     t3 + qp / (2 * math.pi * K["insulation"]) * np.log(R3 / np.maximum(r, 1e-30))))
    return {"q_prime": qp, "t0": t0, "t1": t1, "t2": t2, "t3": t3, "rise": t0 - T_OUT,
            "profile": profile}


# --- mesh --------------------------------------------------------------------
BASE = dict(nang=6, rod=3, steel=2, insulation=3, n_layers=2)


def assembly(k: int) -> Assembly:
    spec = (PipeSpec(nang=BASE["nang"]).core("rod", radius=R1, nrad=BASE["rod"])
            .shell("steel", dR=R2 - R1, nrad=BASE["steel"])
            .shell("insulation", dR=R3 - R2, nrad=BASE["insulation"]))
    asm = Assembly(spec, position=[0, 0, 0], direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(LENGTH, n_layers=BASE["n_layers"]), names=["outlet"])
    d = intent.refined_dict(asm.to_dict(), k)
    for e in d["edges"]:
        e["fitting"]["n_layers"] = BASE["n_layers"]
    return Assembly.from_dict(d)


def meshes():
    """(label, caption, build) per mesh shown in README.md
    (``docs/gallery/build.py --validation``)."""
    return [(f"k{k}", f"k = {k}: nang {BASE['nang'] * k}, nrad "
                      f"{BASE['rod'] * k} / {BASE['steel'] * k} / {BASE['insulation'] * k}",
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

SCHEMES = """ddtSchemes      { default steadyState; }
gradSchemes     { default Gauss linear; }
divSchemes      { default none; }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }
"""

REGION_SOLUTION = """solvers
{
    h { solver PCG; preconditioner DIC; tolerance 1e-14; relTol 0; }
}
SIMPLE
{
    nNonOrthogonalCorrectors 2;
    residualControl { h 1e-11; }
}
relaxationFactors { equations { h 1; } }
"""

THERMO = """thermoType
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

FVOPTIONS = f"""heat
{{
    type            scalarSemiImplicitSource;
    active          true;
    selectionMode   all;
    volumeMode      specific;
    injectionRateSuSp {{ h ({Q3} 0); }}
}}
"""


def write_dicts(case: Path, end_time: int) -> None:
    """The dictionaries splitMeshRegions and the solver need (no fields)."""
    files = {
        "system/controlDict": H("dictionary", "controlDict", "system")
        + CONTROL.format(end_time=end_time),
        "system/fvSchemes": H("dictionary", "fvSchemes", "system") + SCHEMES,
        "system/fvSolution": H("dictionary", "fvSolution", "system") + "SIMPLE {}\n",
        # read even with no fluid region (v1912)
        "constant/g": H("uniformDimensionedVectorField", "g", "constant")
        + "dimensions [0 1 -2 0 0 0 0];\nvalue (0 0 0);\n",
        "constant/regionProperties": H("dictionary", "regionProperties", "constant")
        + f"regions\n(\n    fluid ()\n    solid ({' '.join(REGIONS)})\n);\n",
    }
    for r in REGIONS:
        files[f"system/{r}/fvSchemes"] = H("dictionary", "fvSchemes", f"system/{r}") + SCHEMES
        files[f"system/{r}/fvSolution"] = (H("dictionary", "fvSolution", f"system/{r}")
                                           + REGION_SOLUTION)
        files[f"constant/{r}/thermophysicalProperties"] = (
            H("dictionary", "thermophysicalProperties", f"constant/{r}")
            + THERMO.format(k=K[r], cp=CP, rho=RHO))
    files["system/rod/fvOptions"] = H("dictionary", "fvOptions", "system/rod") + FVOPTIONS
    for name, text in files.items():
        (case / name).parent.mkdir(parents=True, exist_ok=True)
        (case / name).write_text(text)


def patches(case: Path, region: str) -> list[str]:
    text = (case / f"constant/{region}/polyMesh/boundary").read_text()
    return re.findall(r"^\s{4}(\w+)\s*\n\s*\{", text, re.M)


def write_fields(case: Path, variant: str) -> None:
    for r in REGIONS:
        bc = []
        for p in patches(case, r):
            if "_to_" in p:
                b = ("type compressible::turbulentTemperatureCoupledBaffleMixed; Tnbr T; "
                     f"kappaMethod solidThermo; value uniform {T_OUT};")
            elif p.endswith("_wall") and variant == "fixed":
                b = f"type fixedValue; value uniform {T_OUT};"
            elif p.endswith("_wall"):
                b = (f"type externalWallHeatFluxTemperature; mode coefficient; "
                     f"Ta constant {T_OUT}; h uniform {H_CONV}; kappaMethod solidThermo; "
                     f"value uniform {T_OUT};")
            else:
                b = "type zeroGradient;"
            bc.append(f"    {p} {{ {b} }}")
        body = "\n".join(bc)
        (case / f"0/{r}").mkdir(parents=True, exist_ok=True)
        (case / f"0/{r}/T").write_text(
            H("volScalarField", "T", f"0/{r}")
            + f"dimensions [0 0 0 1 0 0 0];\ninternalField uniform {T_OUT};\n"
              f"boundaryField\n{{\n{body}\n}}\n")
        (case / f"0/{r}/p").write_text(
            H("volScalarField", "p", f"0/{r}")
            + "dimensions [1 -1 -2 0 0 0 0];\ninternalField uniform 1e5;\n"
              "boundaryField\n{\n    \".*\" { type calculated; value uniform 1e5; }\n}\n")


# --- post-processing ---------------------------------------------------------

def region_fields(case: Path, region: str):
    mesh = case / f"constant/{region}/polyMesh"
    pts, faces = of.read_points(mesh / "points"), of.read_faces(mesh / "faces")
    owner, neigh = of.read_labels(mesh / "owner"), of.read_labels(mesh / "neighbour")
    t = of.latest_time(case)
    T = of.read_internal(t / region / "T", 1)
    fc, sf = of.face_geometry(pts, faces)
    cc, vol = of.cell_geometry(fc, sf, owner, neigh, len(T))
    return dict(mesh=mesh, t=t, T=T, fc=fc, sf=sf, cc=cc, vol=vol, owner=owner)


def patch_heat(f: dict, region: str, patch: str) -> tuple[float, float, int]:
    """(area-averaged face T, heat leaving the region through *patch* [W],
    number of faces) from the face values and the wall cells."""
    ids = of.read_patch_faces(f["mesh"] / "boundary", patch)
    tf = of.read_patch_values(f["t"] / region / "T", patch, n=len(ids))
    a = np.linalg.norm(f["sf"][ids], axis=1)
    n = f["sf"][ids] / a[:, None]
    cell = f["owner"][ids]
    d = np.einsum("ij,ij->i", f["fc"][ids] - f["cc"][cell], n)
    q = float((K[region] * (f["T"][cell] - tf) / d * a).sum())
    return float((tf * a).sum() / a.sum()), q, len(ids)


def results(case: Path, variant: str) -> dict:
    ex = exact(variant)
    rise = ex["rise"]
    f = {r: region_fields(case, r) for r in REGIONS}
    out = {"exact": {k: v for k, v in ex.items() if k != "profile"}}
    heat_in = Q3 * float(f["rod"]["vol"].sum())
    pairs = {}
    for name, region, patch in (("t1", "rod", "rod_to_steel"),
                                ("t1_steel", "steel", "steel_to_rod"),
                                ("t2", "steel", "steel_to_insulation"),
                                ("t2_insulation", "insulation", "insulation_to_steel"),
                                ("t3", "insulation", "insulation_wall")):
        t, q, n = patch_heat(f[region], region, patch)
        out[name], out[f"q_{name}"], pairs[patch] = t, q, n
    # heat leaving each region outward, against q''' V_rod (energy balance)
    out["heat_in"] = heat_in
    out["balance_rod"] = (out["q_t1"] - heat_in) / heat_in
    out["balance_steel"] = (out["q_t2"] - heat_in) / heat_in
    out["balance_outer"] = (out["q_t3"] - heat_in) / heat_in
    out["mapped_pairs_equal"] = (pairs["rod_to_steel"] == pairs["steel_to_rod"]
                                 and pairs["steel_to_insulation"] == pairs["insulation_to_steel"])
    # centre: T = c0 + c2 r² fitted to the rod cells within R1/3
    rod = f["rod"]
    r = np.hypot(rod["cc"][:, 1], rod["cc"][:, 2])
    fit = r < R1 / 3
    c0 = np.linalg.lstsq(np.column_stack([np.ones(fit.sum()), r[fit] ** 2]),
                         rod["T"][fit], rcond=None)[0][0]
    out["t0"], out["t0_fit_cells"] = float(c0), int(fit.sum())
    for key in ("t0", "t1", "t2", "t3"):
        out[f"{key}_err"] = (out[key] - ex[key]) / rise
    out["l2"] = {}
    for reg in REGIONS:
        g = f[reg]
        rr = np.hypot(g["cc"][:, 1], g["cc"][:, 2])
        e = (g["T"] - ex["profile"](rr)) / rise
        out["l2"][reg] = float(np.sqrt((e**2 * g["vol"]).sum() / g["vol"].sum()))
    return out


# --- driver ------------------------------------------------------------------

TOL = 1e-10      # largest initial h residual, over the regions, of a converged step


def residual_history(log: str) -> list[tuple[int, float]]:
    """(step, largest initial residual of h over the regions' solves)."""
    parts = re.split(r"\nTime = (\d+)\n", log)
    out = []
    for i in range(1, len(parts), 2):
        res = re.findall(r"Solving for h, Initial residual = ([\d.e+-]+)", parts[i + 1])
        if res:
            out.append((int(parts[i]), max(map(float, res))))
    return out


def run_level(variant: str, k: int, work: Path, end_time: int) -> dict:
    case = work / f"{variant}-{k}"
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    with Session(f"layered-{variant}-{k}"):
        asm = assembly(k)
        cells = asm.cell_count()
        msh = case / "layers.msh"
        asm.write_openfoam(str(msh))
        sj = asm.check_quality("scaled_jacobian").worst
    write_dicts(case, end_time)
    retyped = of.convert(case, msh, split_regions=True)
    checks = {r: of.check_mesh(case, r) for r in REGIONS}
    write_fields(case, variant)
    solve = of.foam("chtMultiRegionSimpleFoam", case, "log.chtMultiRegionSimpleFoam")
    times = re.findall(r"^Time = (\d+)$", solve, re.M)
    # v1912 ignores residualControl for solid regions (it runs to endTime;
    # docs/integrations/openfoam.md): judge convergence from the residuals
    history = residual_history(solve)
    first = next((t for t, r in history if r < TOL), None)
    out = {
        "variant": variant, "k": k, "nang": BASE["nang"] * k, "cells": cells,
        "cells_foam": sum(c["cells_foam"] for c in checks.values()),
        "mesh_ok": all(c["mesh_ok"] for c in checks.values()), "checks": checks,
        "retyped": retyped, "min_scaled_jacobian": sj,
        "converged": history[-1][1] < TOL, "iterations": int(times[-1]),
        "converged_at": first, "last_residual": history[-1][1],
    }
    out.update(results(case, variant))
    return out


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--levels", nargs="+", type=int, default=[1, 2, 4])
    ap.add_argument("--variants", nargs="+", default=["fixed", "convection"],
                    choices=["fixed", "convection"])
    ap.add_argument("--work", type=Path, default=HERE / "work")
    ap.add_argument("--end-time", type=int, default=75000,
                    help="iterations at level 1; level k runs k times as many (the "
                         "coupling's iteration count doubles per level)")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    data = {"versions": pois.versions(), "variants": {}}
    for variant in args.variants:
        rows = []
        for k in args.levels:
            r = run_level(variant, k, args.work, args.end_time * k)
            print(json.dumps({key: v for key, v in r.items() if key != "checks"}), flush=True)
            rows.append(r)
        rich = {}
        if len(rows) == 3:
            for key in ("t0", "t1", "t2") + (("t3",) if variant == "convection" else ()):
                try:
                    rich[key] = pois.richardson(*(r[key] for r in rows))
                except (ValueError, ZeroDivisionError) as e:
                    rich[key] = {"error": str(e)}
        data["variants"][variant] = {"levels": rows, "richardson": rich}
    if args.json:
        args.json.write_text(json.dumps(data, indent=1, default=float))
    return data


if __name__ == "__main__":
    main()
