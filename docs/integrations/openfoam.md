# OpenFOAM

## Role

**Consumer.**  hexmesh writes a gmsh mesh, and OpenFOAM converts it with
`gmshToFoam`.  For multi-material (CHT) meshes, `splitMeshRegions` then
splits it into one region per material.

Possible future **peer** use: coupling hexmesh output to separately meshed
regions (snappyHexMesh drums, density breaks) through AMI.  This is
decision 0003, option C (proposed).

## Versions

| OpenFOAM | Source | Status |
|---|---|---|
| v1912 (ESI/openfoam.com line), build patch 200626 | Debian `openfoam` 1912.200626-2build3 | Installed; hexmesh output converts, splits and passes `checkMesh` (task 0005, 2026-10-25, gmsh 4.12.1) |

The utilities need the OpenFOAM environment:

```bash
source /usr/share/openfoam/etc/bashrc
gmshToFoam -help
```

Without it, `gmshToFoam` aborts: `Could not find mandatory etc entry
'controlDict'`.  *Verified* 2026-10-24.

The ESI (openfoam.com, vYYMM) and Foundation (openfoam.org, version
numbers) lines differ in utilities and options.  Record which line every
finding applies to.

## Features used

Write the mesh with `Assembly.write_openfoam("case.msh")`: MSH 2.2 ASCII,
without the material-interface groups by default, plus the role manifest
`case.roles.json` (task 0023).

**Single material:**

```bash
source /usr/share/openfoam/etc/bashrc
gmshToFoam -case case case.msh
python3 -c "from hexmesh.io.writers.openfoam_boundary import apply_boundary_roles; \
            apply_boundary_roles('case', 'case.roles.json')"
checkMesh -case case
```

**Multi-material (CHT):**

```bash
gmshToFoam -case case case.msh
splitMeshRegions -case case -cellZones -overwrite
python3 -c "from hexmesh.io.writers.openfoam_boundary import apply_boundary_roles_to_regions; \
            apply_boundary_roles_to_regions('case', 'case.roles.json')"
checkMesh -case case -region fluid      # and each other material
```

The retyping step is plain Python; it edits only the typing lines of
`constant[/<region>]/polyMesh/boundary`.  *Verified* on v1912, 2026-10-26,
in `tests/test_openfoam_boundary.py` (tee, with and without per-fitting
walls; three-material pipe after the split).

All *verified* on v1912, 2026-10-25, on `examples/insulated_pipe`
(fluid / steel / insulation) and `examples/tee`, and in the test
`tests/test_openfoam_output.py::test_openfoam_cht_split`.
`splitMeshRegions` needs a `system/fvSchemes` with real scheme entries
(it reads `divSchemes`); an empty dictionary aborts it.

- **cellZones:** each physical volume becomes a cellZone named after its
  material (`fluid`, `steel`, `insulation`).  *Verified.*
- **Patches** come from the physical surfaces on the boundary:
  - open interfaces as `{layer}_{patch}` (`fluid_inlet`,
    `steel_outlet`, …);
  - the outer wall as `{outer}_wall`.

  `gmshToFoam` writes all of them as type `patch`.
  `apply_boundary_roles` retypes the walls (role `wall` in the manifest)
  to the form OpenFOAM's own tools write: `type wall;` followed by
  `inGroups 1(wall);`, with keywords padded to 16 columns (checked
  against `blockMesh` on the `pipeCyclic` tutorial, v1912).  It also sets
  `gmshToFoam`'s `physicalType` line to `wall`.  `foamDictionary
  constant/polyMesh/boundary -entry entry0/<patch>/type -value` reads a
  patch's type: v1912 reads the boundary list as `entry0`.
- **CHT interfaces:** after the split, each material interface is a
  `mappedWall` pair with equal face counts, `fluid_to_steel` ↔
  `steel_to_fluid` and `steel_to_insulation` ↔ `insulation_to_steel`.
  *Verified.*  The outer `insulation_wall` stays a `patch`.

## Known quirks

All v1912, gmsh 4.12.1, 2026-10-25.

- **MSH 4.1 is read too.**  `gmshToFoam` v1912 reads MSH 4.1 ASCII as well
  as 2.2.  For both the tee and the insulated pipe, the cells, patches,
  face counts and `checkMesh` output were identical.  hexmesh still writes
  2.2, which every OpenFOAM line reads.
- **"Found N undefined faces … adding to default patch defaultFaces"** is
  harmless.  `gmshToFoam` first assigns every boundary face to
  `defaultFaces`, then moves them to the named patches.  For the tee,
  N = 1608 = the total boundary faces.  The empty `defaultFaces` patch is
  then dropped, and `checkMesh` lists only the named patches.
- **Internal physical surfaces** (material interfaces) become:
  - an **empty `patch`**, 0 faces, with the group's name;
  - a **faceZone**, here 864 faces;
  - one warning per face: "Not using gmsh face … since zero vertex is not
    on boundary of polyMesh".
- **Name clash with `splitMeshRegions`.**  hexmesh names its interface
  groups `<a>_to_<b>`, which is exactly the name `splitMeshRegions` gives
  its interface patches.  When those empty patches exist, the split reuses
  them instead of adding `mappedWall` pairs.  For the insulated pipe, the
  log shows the fluid/steel interface mapped to patches 6
  (`fluid_to_steel`) and 7 (`steel_to_insulation`), and the
  steel/insulation interface to 7 and 8 (`insulation_wall`).  The result:
  - `steel_to_insulation` held 1728 faces (both steel interfaces);
  - `insulation_wall` held the wall and the interface together;
  - every patch had type `patch`.

  Each region still passed `checkMesh`, so only the patch list shows the
  error.  `write_openfoam` therefore leaves these groups out by default
  (`interfaces=True` keeps them).
- **`simpleFoam` doesn't converge on the steady laminar stenosis jet; it
  isn't the mesh or the convection scheme** (v1912, design session
  2026-10-29, task 0032).  Medium level (122 688 cells, Re 500, cosine
  stenosis s0 = 0.25), 1500 SIMPLE iterations on 4 cores, relaxation
  p 0.3 / U 0.7:
  - `div(phi,U)` = `bounded Gauss limitedLinearV 1`, `linearUpwind
    grad(U)` and `linear`: all plateau within about 100 iterations (p
    residual 0.35–0.47), with reattachment 4.7–5.5 D against the DNS
    database's 11.0 D.  Not limiter chatter.
  - An independent `blockMesh` O-grid with the same topology, counts and
    axial stations (1420 blocks; non-orthogonality 31.0°, skewness 0.69)
    plateaus the same way (p 0.39–0.42, reattachment 5.2 D).  Not the
    hexmesh mesh or its `gmshToFoam` route.
  - The coding session (task 0032) found that SIMPLE, SIMPLEC and heavier
    relaxation all plateau, and that SIMPLE started on the converged
    steady state leaves it.  Transient `pimpleFoam` reaches the steady
    state.
  - Reading: SIMPLE's iteration is unstable around this steady solution
    (a confined jet near its instability threshold), an algorithmic
    limit, not a defect.  Not reported upstream.  To take it further:
    a current OpenFOAM release, then a CFD Online question if it
    persists.
  - Scripts: the design session's scratchpad (`simple_check/`).
  - **What works: `pimpleFoam` from rest to a steady state** (coding
    session, 2026-10-30, task 0032; `validation/stenosis/run.py`).
    Euler, `adjustTimeStep` at `maxCo` 0.8, `nOuterCorrectors` 1,
    `nCorrectors` 2, no relaxation, the Poiseuille case's solvers for
    `p|pFinal` and `U|UFinal`.  Run in 5-time-unit chunks (restart with
    `startFrom latestTime`), steady when the quantities of interest
    change < 0.1 % over a chunk.  Steady by t = 10–15 D/U at every
    level; 760 s (123k cells), 5647 s (414k), 17 705 s (982k) on 4 cores.
  - **Not the v1912 defect (2026-10-30):** on OpenFOAM v2406 (Docker,
    `opencfd/openfoam-default:2406`), the same k2 case files and
    SIMPLE settings, 3000 iterations on 4 cores, behave as on v1912.
    From the converged `pimpleFoam` state the residuals climb from
    Ux 1.8e-6 to 1.5e-2 by iteration 200 (v1912: 1.2e-8 to 1.5e-2), then
    plateau at p ≈ 0.4; from rest, plateau at p ≈ 0.38.  So SIMPLE's
    instability here is algorithmic, as read above, not the build's
    non-orthogonality defect (task 0035).
  - **`purgeWrite` counts one run's writes only:** with chunked restarts
    each run writes once, so nothing is purged, in the case or in the
    `processor*` directories.  The driver deletes old times itself.
- **`checkMesh` thresholds** (v1912, design session 2026-10-28, task
  0047).  On a circle-in-3:1-rectangle ring (max non-orthogonality
  81.3°): "*Number of severely non-orthogonal (> 70 degrees) faces:
  256", then "Non-orthogonality check OK" and "Mesh OK".  So 70° is a
  warning count only; the check fails above 90°.  Max skewness 1.39 to
  2.36 on the task's rings was reported "OK".  Needs the OpenFOAM
  environment (`source /usr/share/openfoam/etc/bashrc`); without it,
  every utility fails with "Could not find mandatory etc entry
  'controlDict'".
- **Non-orthogonality is reproducible in Python** (2026-10-28, task
  0047).  `checkMesh`'s "Mesh non-orthogonality Max" is the angle
  between an interior face's area vector and the owner → neighbour
  centre line, with OpenFOAM's `primitiveMesh` construction:
  - faces: triangle fans about the point average, centre weighted by
    triangle area;
  - cells: pyramids from the face-centre average, centre weighted by
    pyramid volume.

  `benchmarks/outline_quality.py` does this and matched `checkMesh` to
  four decimals: 80.2544° and 54.1026° on two ring meshes.  Plain vertex
  averages for the centres gave 52.15° for the second, 2° low on
  trapezoidal cells.
  - `checkMesh` also needs `system/fvSchemes` and `system/fvSolution` to
    exist ("cannot find file …/fvSchemes"), not only `controlDict`.
    Minimal entries are enough.
- **Orientation:** `checkMesh` reports "Mesh OK" for hexmesh hexes both
  without and with `gmshToFoam -keepOrientation`, so the option is not
  needed.
- **Function objects abort on this build.**  Any entry under
  `functions` in `controlDict`, and `postProcess -func …`, stops with
  `FOAM FATAL IO ERROR: error in IOstream "sha1" for operation
  Foam::Ostream& Foam::operator<<(Ostream&, const word&)`.
  - Stack (`FOAM_ABORT=1`): `primitiveEntry::write` ←
    `dictionary::digest()` ← `functionObjectList::read()`.  So it fails
    while hashing the function's dictionary, before any function runs.
  - It fails for every type tried: `surfaceFieldValue` (patch and
    faceZone), `sets`, and pipeCyclic's own `timeInfo`.  An empty
    `functions {}` runs.
  - Not caused by the case: `writePrecision` and `runTimeModifiable`
    make no difference.
  - Solvers and mesh utilities are unaffected: `simpleFoam`, `topoSet`,
    `checkMesh`, `gmshToFoam` and `splitMeshRegions`.
  - **Workaround:** post-process in Python from the ASCII case files
    (`validation/poiseuille/run.py`).  `topoSet` (`boxToFace` +
    `setToFaceZone`) still makes face zones to sample on.
  - Probably the distribution's rebuild (`2build3`, GCC 13.3, Ubuntu
    24.04) of the 2020 sources: the SHA1 stream state fails.  Not checked
    against an upstream build.
  - *Verified* 2026-10-26 (task 0020), `openfoam` 1912.200626-2build3.
- **Tutorial `pipeCyclic` does not run as shipped here.**  Its coded
  swirl inlet fails with `Unknown variable 'WM_OPTIONS'` (no build
  environment).  Its dictionaries are still a sound base: task 0020 uses
  its `fvSchemes`, `fvSolution` and `controlDict` without the coded BC.
  *Verified* 2026-10-26.
- **`laplacianFoam` reads `constant/fvOptions`; `scalarSemiImplicitSource`
  works.**  A uniform heat source on T needs no coded source:
  `type scalarSemiImplicitSource; selectionMode all; volumeMode specific;
  injectionRateSuSp { T (Su 0); }`, coefficients at the top level of the
  entry (no `…Coeffs` subdictionary needed).  The log shows "Creating
  finite volume options from "constant/fvOptions"" and the selected cell
  count and volume.  Steady runs: `ddtSchemes steadyState`; each time step
  repeats the `SIMPLE` non-orthogonal correctors from the last T, and
  `SIMPLE { residualControl { T 1e-11; } }` stops at the first converged
  step.  Three correctors in one step leave an initial residual of 1e-4 on
  a 24° non-orthogonal O-H rod; 10 correctors and up to 3 steps reach
  1e-15.  *Verified* 2026-10-27 (task 0033), `openfoam`
  1912.200626-2build3.
- **`chtMultiRegionSimpleFoam` with solid regions only runs; the recipe**
  (task 0034, *verified* 2026-10-28, `openfoam` 1912.200626-2build3).
  `validation/layered_conduction/run.py` is the working case.
  - **Mesh:** `gmshToFoam`, then `splitMeshRegions -cellZones -overwrite`
    (it needs `system/fvSchemes` with a `divSchemes` entry, else "Entry
    'divSchemes' not found"), then `apply_boundary_roles_to_regions`.
    The interfaces come out as `mappedWall` pairs `<a>_to_<b>` /
    `<b>_to_<a>` with equal face counts.
  - **`constant/regionProperties`:** `regions ( fluid () solid (rod steel
    insulation) );`.
  - **`constant/g`** must exist even with no fluid region ("cannot find
    file …/constant/g").  `value (0 0 0);` is enough.
  - **Per region:**
    - `constant/<r>/thermophysicalProperties`: `heSolidThermo`,
      `pureMixture`, `constIso`, `hConst`, `rhoConst`,
      `sensibleEnthalpy`.
    - `system/<r>/fvSchemes`, and `system/<r>/fvSolution` with a solver
      for `h` and `SIMPLE { nNonOrthogonalCorrectors …; }`.
    - `0/<r>/T` and `0/<r>/p` (`calculated`).
    - The top-level `system/fvSolution` needs only `SIMPLE {}`.
  - **Heat source:** `system/<r>/fvOptions`, `scalarSemiImplicitSource`
    on **`h`** (`injectionRateSuSp { h (q‴ 0); }`, `volumeMode
    specific`, in W/m³).
  - **Interfaces:** `compressible::turbulentTemperatureCoupledBaffleMixed;
    Tnbr T; kappaMethod solidThermo;`.
  - **Outer convection:** `externalWallHeatFluxTemperature; mode
    coefficient; Ta constant T∞; h uniform h; kappaMethod solidThermo;`.
  - **`residualControl` is ignored for solid regions**, both in
    `system/<r>/fvSolution` and in the top-level `SIMPLE`.  The solver
    runs to `endTime` and never prints "converged", so judge convergence
    from the log's initial residuals.
  - **The segregated coupling converges slowly with a large conductivity
    ratio.**
    - Rod 20, steel 50, insulation 0.05 W/m K: the largest initial
      residual of `h` falls about 100× per 10 000 iterations.
    - It is below 1e-10 at iteration 47 076 (456 cells) and 91 960
      (1 824 cells): the count doubles per refinement level.
    - The energy balance then closes to 1e-11.
  - **Patch values of a mixed condition:** the field file's
    `valueFraction` comes before `value`, so a reader must match the
    keyword `value` exactly (`hexmesh.study.openfoam.read_patch_values`).

- **No Scotch: `decomposePar` with `method scotch` fails** (v1912 Ubuntu
  package, 2026-10-29, task 0032).  The library linked is
  `dummyScotchDecomp`: "FOAM exiting … scotchDecomp::decompose …
  dummyScotchDecomp.C at line 112".  `method simple` works
  (`simpleCoeffs { n (N 1 1); delta 0.001; }`, slabs along a pipe's x
  axis), and needs no graph partitioner.

- **v1912's buoyant solvers fail on any non-orthogonal mesh** (Ubuntu
  package `1912.200626-2build3`, gmsh 4.12.1, found 2026-10-29, cause
  isolated 2026-10-30, task 0035).  Not a hexmesh problem: the shipped
  `buoyantCavity` tutorial with its box sheared by 1° crashes too.
  OpenFOAM v2406 (the `opencfd/openfoam-default:2406` Docker image)
  runs all of it.  Incompressible `simpleFoam`/`pimpleFoam` on the same
  meshes are fine (tasks 0020, 0032).
  - **Symptom:** `buoyantSimpleFoam`, `chtMultiRegionSimpleFoam` (fluid
    region) and the transient `buoyantPimpleFoam` (Co 0.5) all blow up
    within 5 iterations or steps: continuity error grows 50–1000× per
    pressure correction, transverse velocity appears first in the inlet
    cells near the O-H core corners (r ≈ 0.46–0.53 R), then h, and the
    run aborts with "Negative initial temperature T0".
  - **Converges, same dictionaries and fields:** a `blockMesh` square
    duct (64 × 10 × 10, orthogonal), 300 iterations to continuity 1.6e-9;
    and the shipped `buoyantSimpleFoam/buoyantCavity` tutorial unchanged.
  - **Diverges:** every hexmesh mesh tried, via `gmshToFoam` +
    `apply_boundary_roles`: the circular O-H pipe (cell aspect 12 or
    1.6), and a hexmesh square duct (`RectShape`, planar faces, non-orth.
    ≈ 23°).
  - **Ruled out** (each changed alone, still diverges): `rhoConst` vs
    `perfectGas`; p level 0 vs 1e5; water-like vs air-like fluid at the
    same Re; g = 0 vs −9.81; `momentumPredictor` on/off; relaxation
    (0.3/0.3, 0.7/0.3, the tutorials'); upwind vs limitedLinear;
    `fixedFluxPressure` vs `zeroGradient` p_rgh; velocity vs pressure
    inlet; GAMG vs PCG; cell/face/point zones removed; `renumberMesh`;
    developed vs zero initial velocity.
  - **Mesh checks pass:** `checkMesh -allGeometry -allTopology` OK; every
    internal face points owner → neighbour and every boundary face
    outward; `fvc::reconstruct`'s Σ Sf⊗Sf/|Sf| has condition ≤ 6 and
    reconstructs a uniform field to 1e-17.
  - **The cause, 2026-10-30** (fluid-only pipe, the heated-pipe
    driver's fluid dictionaries, rhoConst, Re 100, g = 0, 300
    iterations):
    - `nNonOrthogonalCorrectors` 1 or 2, `snGrad` `limited corrected
      0.33` or `uncorrected`: still diverges (4–5 iterations).
    - A `blockMesh` O-grid with hexmesh's topology and counts
      (`validation/tools/blockmesh_ogrid.py`, non-orth. 18°): diverges.
      So it isn't hexmesh or `gmshToFoam`.
    - A `blockMesh` square duct whose section is sheared by 1°, 3°, 6°,
      12°, 23° or 35°: diverges at every angle.  Unsheared: converges.
      So it isn't the O-H topology or the size of the angle: any
      non-orthogonality at all.
    - **The shipped `buoyantCavity` tutorial, its box sheared by 1°**
      (non-orth. 1°), otherwise unchanged: floating-point exception at
      iteration 6.  Unsheared: 100 iterations, fine.
    - **OpenFOAM v2406** (`opencfd/openfoam-default:2406`, 1.5 GB):
      v2406's own `buoyantCavity` sheared 1°, and our hexmesh O-H pipe
      and 23° duct with the v1912 case files unchanged, all converge
      (300 iterations, continuity 1.4e-6 and 2.1e-6).
  - **So:** a defect of this v1912 build's buoyant/compressible pressure
    equation on non-orthogonal meshes, fixed (or absent) in v2406.
    Whether it's v1912 itself or the Ubuntu build isn't known.  Every
    hexmesh mesh is non-orthogonal (O-H corners), so CHT with a fluid
    region needs another OpenFOAM build.
  - Scripts: the coding session's scratchpad, `0035d/` (`make.py`,
    `cht2406.py`).



## Gaps in hexmesh's OpenFOAM support

- **`hexmesh/io/writers/openfoam.py` (`write_openfoam_case`)** — noted
  2026-10-25:
  - It targets **multi-region CHT** cases (`chtMultiRegionFoam`,
    `regionProperties`, per-region `fvSchemes`/`fvSolution`).  There is
    no single-region path (e.g. `simpleFoam` for the Poiseuille case,
    task 0020).
  - Its module docstring still says it builds the case "from a Network's
    regions": `Network` is the legacy API deleted by decision 0004.
  - No test calls it.
  - It writes no `0/` boundary-condition files.  Wall patch types are
    now set by `apply_boundary_roles` (task 0023), which it doesn't
    call.
  Task 0020 records what a single-region case needs.  A follow-up task
  should come from that outcome.

## Open questions

Settled in task 0005 (2026-10-25): the MSH version (2.2 and 4.1 both
read), cellZones (yes, by material), internal surfaces (empty patch plus
faceZone; see Known quirks), and orientation (no `-keepOrientation`
needed).

- **AMI coupling** between a hexmesh pipe and a separately meshed region
  (decision 0003): untested.
