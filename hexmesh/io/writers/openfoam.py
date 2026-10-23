"""
OpenFOAM case scaffolding writer.

Generates a minimal OpenFOAM case directory structure from a Network's
regions and material graph.  The caller still needs to populate boundary
condition files (``0/`` directory) with appropriate values, but the
directory structure, ``controlDict``, ``fvSchemes``, and ``fvSolution``
stubs are created ready to edit.

For multi-region cases (``chtMultiRegionFoam``, ``multiRegionFoam``),
``splitMeshRegions -cellZones`` is the expected workflow after meshing:

    1. Run ``gmshToFoam mesh.msh`` to create ``constant/polyMesh``.
    2. Run ``splitMeshRegions -cellZones -overwrite`` to split by Physical
       Volume into per-region polyMesh directories.
    3. The interface patches are auto-named by OpenFOAM as
       ``{regionA}_to_{regionB}`` — matching the hexmesh interface labels.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Sequence


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_openfoam_case(
    path:        str | Path,
    regions:     Sequence[str],
    solver:      str = "chtMultiRegionFoam",
    end_time:    float = 1.0,
    delta_t:     float = 0.01,
    write_interval: int = 10,
    fluid_regions:  Sequence[str] | None = None,
    solid_regions:  Sequence[str] | None = None,
) -> None:
    """Write an OpenFOAM case directory for a multi-region simulation.

    Parameters
    ----------
    path : str or Path
        Root directory for the case.  Created if it does not exist.
    regions : list[str]
        All material region names (Physical Volume names from hexmesh).
    solver : str
        OpenFOAM solver name.  Default ``"chtMultiRegionFoam"``.
    end_time : float
        ``controlDict`` endTime.
    delta_t : float
        ``controlDict`` deltaT.
    write_interval : int
        ``controlDict`` writeInterval.
    fluid_regions : list[str], optional
        Subset of *regions* that are fluid (used for ``regionProperties``).
        If None, all regions are treated as fluid.
    solid_regions : list[str], optional
        Subset of *regions* that are solid.  If None, empty list.
    """
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)

    fluid  = list(fluid_regions or regions)
    solid  = list(solid_regions or [])

    _write_control_dict(root, solver, end_time, delta_t, write_interval)
    _write_fv_schemes(root)
    _write_fv_solution(root)
    _write_region_properties(root, fluid, solid)

    # Create per-region constant/ subdirectories (populated by splitMeshRegions)
    (root / "constant" / "polyMesh").mkdir(parents=True, exist_ok=True)
    for region in regions:
        (root / "constant" / region).mkdir(exist_ok=True)
        (root / "0"        / region).mkdir(parents=True, exist_ok=True)
        _write_region_fv_schemes(root, region)
        _write_region_fv_solution(root, region)

    _write_all_run(root, solver)

    print(f"OpenFOAM case written to: {root.resolve()}")
    print(f"  Regions : {regions}")
    print(f"  Solver  : {solver}")
    print(f"  Next steps:")
    print(f"    gmshToFoam mesh.msh -case {root}")
    print(f"    splitMeshRegions -cellZones -overwrite -case {root}")
    print(f"    {solver} -case {root}")


# ---------------------------------------------------------------------------
# File writers
# ---------------------------------------------------------------------------

def _foam_header(cls: str, obj: str, location: str = "system") -> str:
    return textwrap.dedent(f"""\
        FoamFile
        {{
            version     2.0;
            format      ascii;
            class       {cls};
            location    "{location}";
            object      {obj};
        }}
        // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
    """)


def _write_control_dict(
    root: Path,
    solver: str,
    end_time: float,
    delta_t: float,
    write_interval: int,
) -> None:
    (root / "system").mkdir(exist_ok=True)
    content = _foam_header("dictionary", "controlDict") + textwrap.dedent(f"""
        application     {solver};

        startFrom       latestTime;
        startTime       0;
        stopAt          endTime;
        endTime         {end_time};

        deltaT          {delta_t};

        writeControl    timeStep;
        writeInterval   {write_interval};
        purgeWrite      0;

        writeFormat     ascii;
        writePrecision  8;

        runTimeModifiable true;
    """)
    (root / "system" / "controlDict").write_text(content)


def _write_fv_schemes(root: Path) -> None:
    content = _foam_header("dictionary", "fvSchemes") + textwrap.dedent("""
        ddtSchemes      { default Euler; }
        gradSchemes     { default Gauss linear; }
        divSchemes      { default none; }
        laplacianSchemes{ default Gauss linear corrected; }
        interpolationSchemes { default linear; }
        snGradSchemes   { default corrected; }
    """)
    (root / "system" / "fvSchemes").write_text(content)


def _write_fv_solution(root: Path) -> None:
    content = _foam_header("dictionary", "fvSolution") + textwrap.dedent("""
        solvers
        {
            p_rgh
            {
                solver          PCG;
                preconditioner  DIC;
                tolerance       1e-8;
                relTol          0.01;
            }
            "(U|T|k|epsilon)"
            {
                solver          PBiCG;
                preconditioner  DILU;
                tolerance       1e-7;
                relTol          0.1;
            }
        }
        PIMPLE { nOuterCorrectors 1; nCorrectors 2; nNonOrthogonalCorrectors 1; }
    """)
    (root / "system" / "fvSolution").write_text(content)


def _write_region_properties(
    root: Path,
    fluid: list[str],
    solid: list[str],
) -> None:
    def _fmt(names):
        return "( " + " ".join(names) + " )" if names else "( )"

    content = _foam_header("dictionary", "regionProperties") + textwrap.dedent(f"""
        regions
        (
            fluid  {_fmt(fluid)}
            solid  {_fmt(solid)}
        );
    """)
    (root / "constant" / "regionProperties").write_text(content)


def _write_region_fv_schemes(root: Path, region: str) -> None:
    dst = root / "system" / region
    dst.mkdir(exist_ok=True)
    content = _foam_header("dictionary", "fvSchemes",
                            location=f"system/{region}") + textwrap.dedent("""
        ddtSchemes      { default Euler; }
        gradSchemes     { default Gauss linear; }
        divSchemes      { default none; }
        laplacianSchemes{ default Gauss linear corrected; }
        interpolationSchemes { default linear; }
        snGradSchemes   { default corrected; }
    """)
    (dst / "fvSchemes").write_text(content)


def _write_region_fv_solution(root: Path, region: str) -> None:
    dst = root / "system" / region
    dst.mkdir(exist_ok=True)
    content = _foam_header("dictionary", "fvSolution",
                            location=f"system/{region}") + textwrap.dedent("""
        solvers
        {
            T
            {
                solver          PCG;
                preconditioner  DIC;
                tolerance       1e-8;
                relTol          0.01;
            }
        }
        PIMPLE { nOuterCorrectors 1; nCorrectors 2; nNonOrthogonalCorrectors 1; }
    """)
    (dst / "fvSolution").write_text(content)


def _write_all_run(root: Path, solver: str) -> None:
    script = textwrap.dedent(f"""\
        #!/bin/sh
        cd "${{0%/*}}" || exit 1
        . "${{WM_PROJECT_DIR:?}}/bin/tools/RunFunctions"

        runApplication gmshToFoam mesh.msh
        runApplication splitMeshRegions -cellZones -overwrite
        runApplication {solver}
    """)
    p = root / "Allrun"
    p.write_text(script)
    p.chmod(0o755)
