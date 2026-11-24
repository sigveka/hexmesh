#!/usr/bin/env python3
"""
The animated hero's run (task 0192): a hot front through
``sections.insulated_network``, with conjugate heat transfer through the
fluid, the steel and the insulation.  An illustration, not a validation
case.

    python3 docs/gallery/hero_run.py --work DIR [--np N] [--openfoam RUNNER]
        [--probe STEPS]

Laminar, constant properties, no gravity.  Everything starts at the
ambient temperature and still; at t = 0 the inlet's flow and a hot step
switch on.  The outer surfaces lose heat to the ambient air, so the
insulation's job shows: the bare branch's steel runs hot, the insulated
jacket stays cool.

    hexmesh Assembly → write_openfoam → gmshToFoam → splitMeshRegions
    → chtMultiRegionFoam (transient) → time directories for the renderer

Two phases, written at two rates: the front (dense writes), then the soak
into the steel and the insulation (sparse).  The case stays in ``--work``;
``build.py --hero-anim`` reads its time directories.  Delete it once the
animation is rendered (CLAUDE.md: disk is limited).
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import re
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from hexmesh import Session                                    # noqa: E402
from hexmesh.study import openfoam as of                       # noqa: E402

HERO = "sections.insulated_network"
REGIONS = ("fluid", "steel", "insulation")
SOLIDS = REGIONS[1:]
H = of.header

# --- physics: water-like, laminar --------------------------------------------
RHO, CP, MU, PR = 1000.0, 4000.0, 1.0e-3, 7.0
K_F = MU * CP / PR
RE = 300                                     # on the header's diameter
R_HEADER = 0.1                               # the example's header radius [m]
U_MEAN = RE * MU / (RHO * 2 * R_HEADER)      # 1.5 mm/s
SOLID = {"steel": dict(k=50.0, rho=8000.0, cp=500.0),
         "insulation": dict(k=0.04, rho=50.0, cp=1000.0)}
T_AMB, T_HOT = 293.15, 353.15                # 20 °C everywhere, a 80 °C step
H_OUT = 10.0                                 # outer surfaces to still air [W/(m² K)]
DT = 2.0                                     # fixed step [s]
#: (end time, write interval) per phase [s]: the front, then the soak
PHASES = ((1500, 20), (6000, 250))


# --- case --------------------------------------------------------------------
CONTROL = """application     chtMultiRegionFoam;
startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         {end};
deltaT          {dt};
writeControl    runTime;
writeInterval   {write};
purgeWrite      0;
writeFormat     ascii;
writePrecision  8;
writeCompression off;
timeFormat      general;
timePrecision   8;
runTimeModifiable false;
adjustTimeStep  no;
"""

SOLID_SCHEMES = """ddtSchemes      { default Euler; }
gradSchemes     { default Gauss linear; }
divSchemes      { default none; }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }
"""

FLUID_SCHEMES = """ddtSchemes      { default Euler; }
gradSchemes     { default Gauss linear; }
divSchemes
{
    default         none;
    div(phi,U)      Gauss limitedLinearV 1;
    div(phi,h)      Gauss limitedLinear 1;
    div(phi,K)      Gauss linear;
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }
"""

SOLID_SOLUTION = """solvers
{
    "h.*" { solver PCG; preconditioner DIC; tolerance 1e-8; relTol 0; }
}
PIMPLE { nNonOrthogonalCorrectors 1; }
"""

FLUID_SOLUTION = """solvers
{
    "rho.*" { solver diagonal; }
    "p_rgh.*" { solver GAMG; smoother GaussSeidel; tolerance 1e-8; relTol 0.01; }
    "(U|h).*" { solver PBiCGStab; preconditioner DILU; tolerance 1e-8; relTol 0; }
}
PIMPLE
{
    momentumPredictor yes;
    nCorrectors 2;
    nNonOrthogonalCorrectors 1;
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


def set_control(case: Path, end: float, write: float) -> None:
    (case / "system/controlDict").write_text(
        H("dictionary", "controlDict", "system")
        + CONTROL.format(end=end, dt=DT, write=write), encoding="utf-8")


def write_dicts(case: Path) -> None:
    """The dictionaries splitMeshRegions and the solver need (no fields)."""
    files = {
        "system/fvSchemes": H("dictionary", "fvSchemes", "system") + SOLID_SCHEMES,
        "system/fvSolution": H("dictionary", "fvSolution", "system")
        + "PIMPLE { nOuterCorrectors 1; }\n",
        "constant/g": H("uniformDimensionedVectorField", "g", "constant")
        + "dimensions [0 1 -2 0 0 0 0];\nvalue (0 0 0);\n",
        "constant/regionProperties": H("dictionary", "regionProperties", "constant")
        + f"regions\n(\n    fluid (fluid)\n    solid ({' '.join(SOLIDS)})\n);\n",
        "system/fluid/fvSchemes": H("dictionary", "fvSchemes", "system/fluid") + FLUID_SCHEMES,
        "system/fluid/fvSolution": H("dictionary", "fvSolution", "system/fluid")
        + FLUID_SOLUTION,
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
            + SOLID_THERMO.format(**SOLID[r]))
    for name, text in files.items():
        (case / name).parent.mkdir(parents=True, exist_ok=True)
        (case / name).write_text(text, encoding="utf-8")
    set_control(case, *PHASES[0])


def patches(case: Path, region: str) -> list[str]:
    text = (case / f"constant/{region}/polyMesh/boundary").read_text(encoding="utf-8")
    return re.findall(r"^\s{4}(\w+)\s*\n\s*\{", text, re.M)


COUPLED = ("type compressible::turbulentTemperatureCoupledBaffleMixed; Tnbr T; "
           f"kappaMethod {{m}}; value uniform {T_AMB};")
LOSS = ("type externalWallHeatFluxTemperature; mode coefficient; "
        f"h uniform {H_OUT}; Ta constant {T_AMB}; kappaMethod solidThermo; "
        f"value uniform {T_AMB};")


def write_fields(case: Path) -> dict:
    """Initial and boundary fields; returns each patch's role, for the record."""
    def field(region, name, cls, dims, internal, bcs):
        body = "\n".join(f"    {p} {{ {b} }}" for p, b in bcs.items())
        (case / f"0/{region}").mkdir(parents=True, exist_ok=True)
        (case / f"0/{region}/{name}").write_text(
            H(cls, name, f"0/{region}") + f"dimensions {dims};\ninternalField {internal};\n"
            f"boundaryField\n{{\n{body}\n}}\n", encoding="utf-8")

    fp = patches(case, "fluid")
    inlet = [p for p in fp if p.endswith("inlet")]
    outlets = [p for p in fp if "_to_" not in p and p not in inlet]
    assert len(inlet) == 1 and outlets, fp
    q = U_MEAN * math.pi * R_HEADER**2
    t_bc, u_bc, p_bc = {}, {}, {}
    for p in fp:
        if p in inlet:
            t_bc[p] = f"type fixedValue; value uniform {T_HOT};"
            u_bc[p] = f"type flowRateInletVelocity; volumetricFlowRate constant {q!r}; value uniform (0 0 0);"
            p_bc[p] = "type fixedFluxPressure; value uniform 1e5;"
        elif p in outlets:
            t_bc[p] = f"type inletOutlet; inletValue uniform {T_AMB}; value uniform {T_AMB};"
            u_bc[p] = "type pressureInletOutletVelocity; value uniform (0 0 0);"
            p_bc[p] = "type fixedValue; value uniform 1e5;"
        else:
            t_bc[p] = COUPLED.format(m="fluidThermo")
            u_bc[p] = "type noSlip;"
            p_bc[p] = "type fixedFluxPressure; value uniform 1e5;"
    field("fluid", "T", "volScalarField", "[0 0 0 1 0 0 0]", f"uniform {T_AMB}", t_bc)
    field("fluid", "U", "volVectorField", "[0 1 -1 0 0 0 0]", "uniform (0 0 0)", u_bc)
    field("fluid", "p_rgh", "volScalarField", "[1 -1 -2 0 0 0 0]", "uniform 1e5", p_bc)
    field("fluid", "p", "volScalarField", "[1 -1 -2 0 0 0 0]", "uniform 1e5",
          {p: "type calculated; value uniform 1e5;" for p in fp})
    roles = {"fluid": {"inlet": inlet, "outlets": outlets}}
    for r in SOLIDS:
        bc, losing = {}, []
        for p in patches(case, r):
            if "_to_" in p:
                bc[p] = COUPLED.format(m="solidThermo")
            elif p.endswith("_wall"):
                bc[p] = LOSS
                losing.append(p)
            else:
                bc[p] = "type zeroGradient;"           # pipe ends, the insulation's end
        field(r, "T", "volScalarField", "[0 0 0 1 0 0 0]", f"uniform {T_AMB}", bc)
        field(r, "p", "volScalarField", "[1 -1 -2 0 0 0 0]", "uniform 1e5",
              {'".*"': "type calculated; value uniform 1e5;"})
        roles[r] = {"outer": losing}
    return roles


def mesh(case: Path) -> dict:
    """The hero network as ``build()`` gives it, converted and split."""
    module = importlib.import_module(f"hexmesh.examples.{HERO}")
    case.mkdir(parents=True, exist_ok=True)
    msh = case / "hero.msh"
    with Session("hero-run"):
        asm = module.build()
        cells = asm.cell_count()
        asm.write_openfoam(str(msh))
        sj = asm.check_quality("scaled_jacobian").worst
    write_dicts(case)
    retyped = of.convert(case, msh, split_regions=True, keep_orientation=sj > 0)
    return {"cells": cells, "min_scaled_jacobian": sj, "retyped": retyped}


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--work", type=Path, required=True, help="the case directory")
    ap.add_argument("--np", type=int, default=1, help="MPI processes (default: %(default)s)")
    ap.add_argument("--probe", type=int, default=0,
                    help="run only this many steps and report the time per step")
    ap.add_argument("--openfoam", default="docker:opencfd/openfoam-default:2406",
                    help="OpenFOAM runner (default: %(default)s)")
    args = ap.parse_args(argv)
    of.set_runner(args.openfoam)
    case = args.work
    info = {"re": RE, "u_mean": U_MEAN, "pr": PR, "t_amb": T_AMB, "t_hot": T_HOT,
            "h_out": H_OUT, "dt": DT, "phases": PHASES}
    if not (case / "constant/fluid/polyMesh").exists():
        info.update(mesh(case))
        info["roles"] = write_fields(case)
        info["checks"] = {r: of.check_mesh(case, r) for r in REGIONS}
    t0 = time.monotonic()
    if args.probe:
        set_control(case, args.probe * DT, args.probe * DT)
        of.run_solver(case, "chtMultiRegionFoam", n_proc=args.np, log="log.probe",
                      regions=REGIONS)
        info["probe_s_per_step"] = (time.monotonic() - t0) / args.probe
    else:
        done = max((float(d.name) for d in case.iterdir()
                    if d.is_dir() and d.name.replace(".", "", 1).isdigit()), default=0.0)
        for end, write in PHASES:
            if end <= done:  # resumed: this phase is already written
                continue
            set_control(case, end, write)
            of.run_solver(case, "chtMultiRegionFoam", n_proc=args.np,
                          log=f"log.chtMultiRegionFoam.{end}", regions=REGIONS)
        info["wall_s"] = time.monotonic() - t0
    info["peak_rss_gb_children"] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1e6
    (case / "hero_run.json").write_text(json.dumps(info, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in info.items() if k != "checks"}, indent=1, default=str))
    return info


if __name__ == "__main__":
    main()
