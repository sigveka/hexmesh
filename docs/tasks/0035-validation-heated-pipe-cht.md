# 0035 — Validation: heated multi-layer pipe with laminar flow (full CHT)

- **Status:** ready (design answered Q2 2026-10-30: v2406 in Docker for new cases)
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md)
- **Depends on:** 0034 (the CHT recipe on this build), 0020's re-run
  (the flow pipeline), 0025.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The full conjugate-heat-transfer pipeline on a hexmesh mesh:
a fluid region plus solid layers, coupled interfaces, wall retyping per
region.  It has three independent exact quantities, so an error can be
located: the energy balance (fluid), the Nusselt number (fluid side of
the wall), and the log profiles (solids).

**Physics (exact, thermally and hydrodynamically developed).**  Fluid
core radius r₁ (`fluid`), shells `steel` (r₁→r₂) and `insulation`
(r₂→r₃); **uniform heat flux q″₃ into the outer surface**; laminar
Poiseuille flow, mean velocity Ū, constant properties.
- Heat per length q′ = q″₃ · 2π r₃.
- Bulk temperature: dT_b/dx = q′ / (ṁ c_p), exact (energy balance).
- Fluid side, uniform wall flux: **Nu = h D / k_f = 48/11 ≈ 4.364**, so
  T_w(r₁) − T_b = q′ / (2π r₁) · D / (k_f · 48/11).
- Solids: T(r₂) − T(r₁) = q′/(2π k₂) ln(r₂/r₁), likewise for the
  insulation.
- With uniform flux, T rises linearly in x everywhere in the developed
  region, so axial conduction has zero divergence: these results hold at
  any Péclet number.

**Setup (suggested; record changes).**
- D = 0.02 m, Re = 100, Pr = 1 (constant ρ, μ, c_p, k_f), g = 0 (no
  buoyancy).  Steel and insulation thicknesses and conductivities as in
  task 0034.
- Length 30 D; measure between 20 D and 25 D.  Thermal development
  ≈ 0.05 Re Pr D = 5 D.
- **Inlet:** a developed parabolic velocity profile, written by the
  script as a nonuniform `fixedValue` from the inlet face centres
  (computed in Python from `polyMesh`; `codedFixedValue` needs a build
  environment and fails here).  Uniform inlet T.  Outlet: p fixed, U
  and T zeroGradient.  Solid inlet/outlet faces adiabatic.
- Outer insulation wall: `externalWallHeatFluxTemperature` in flux mode
  (q″₃).
- `chtMultiRegionSimpleFoam`, laminar fluid (`rhoConst`/constant
  transport), with task 0034's solid setup.  Fluid wall retyped by
  `apply_boundary_roles_to_regions`.
- Levels: three, as task 0020 (by `refined(k)` if task 0026 is done).

**Measure** (Python post-processing):
- dT_b/dx from mixing-cup temperatures on the 20 D and 25 D planes
  (face zones by `topoSet`, as task 0020), against q′/(ṁ c_p);
- Nu at 22.5 D from the fluid-side wall temperature and T_b;
- interface temperature differences across steel and insulation;
- mass balance and the overall energy balance (heat in through the
  outer wall = enthalpy rise);
- signed errors, observed order, Richardson [`celik_and_ghia_etal_2008`].

**Layout.**  `validation/heated_pipe/`, as the other cases; opt-in test
on the coarsest level.

**Accept.**
- "Mesh OK" per region at all levels.
- Energy balance within 0.1 % at every level.
- Extrapolated Nu within 1 % of 48/11; extrapolated solid ΔTs within
  0.5 %.  Provisional: if missed, report the numbers and a diagnosis
  under *Questions for design*, don't tune.
- `RESULTS.md` with versions and date; a RESEARCH-ready table in
  *Outcome*.
- Default `pytest` run unchanged.

**Out of scope.**  Uniform wall temperature (Nu = 3.66) and the Graetz
entry problem (planned, RESEARCH §7.5); turbulence; buoyancy;
temperature-dependent properties.

## Agent notes

**2026-10-29: driver written, the fluid region won't run.**
- **Driver:** `validation/heated_pipe/run.py` (uncommitted draft at
  first; committed with this block).  Task 0034's solid recipe plus a
  `fluid` region:
  - `heRhoThermo` / `rhoConst` / `const` / `hConst` / `sensibleEnthalpy`;
  - laminar; `p_rgh` fixed at the outlet, `fixedFluxPressure` elsewhere;
  - the developed profile as the inlet and as the initial field;
  - `topoSet -region fluid` face zones at 20 D and 25 D;
  - outer wall `externalWallHeatFluxTemperature` `mode flux`.
  - Setup as suggested: D 0.02, Re 100, Pr 1 (ρ 1000, c_p 4000, μ 1e-3,
    k_f 4 W/m K, Ū 5e-3 m/s), task 0034's steel (2 mm, 50 W/m K) and
    insulation (8 mm, 0.05 W/m K), q″₃ = 800 W/m² (q′ 100.5 W/m,
    ΔT_ins ≈ 164 K, ΔT_steel 0.058 K, T_w − T_b 1.83 K).  Uniform axial
    spacing 0.625 D (32 + 8 + 8 layers over 20 + 5 + 5 D); 15 744 cells
    at k = 1.
  - Post-processing: mixing-cup T on the planes, wall T averaged over
    20–25 D (linear in x, symmetric faces, so the 22.5 D value), Nu from
    the meshed q′; solid ΔTs; energy balance with axial conduction at
    the fluid ends.
- **`chtMultiRegionSimpleFoam` diverges within 5 iterations** (continuity
  error ×50 per iteration).  Isolated to the fluid alone, then to
  `buoyantSimpleFoam` on the fluid alone: the same.  25 experiments,
  all in `docs/integrations/openfoam.md` ("Open: the buoyant/compressible
  flow solvers diverge on hexmesh meshes"):
  - it converges on a `blockMesh` duct with the same dictionaries and
    fields, and the shipped `buoyantCavity` tutorial runs;
  - it diverges on every hexmesh mesh (O-H pipe, square duct), steady
    and transient, whatever the settings;
  - `simpleFoam` converges on the very same fluid mesh (continuity
    3.6e-4 → 4.3e-6 in 30 iterations).
- Scratch cases: this session's scratchpad, `0035/` (`V*`, `A64*`,
  `Bduct`, `Hduct`, `buoyantCavity`).

**2026-10-30: diagnosis done, in design's order (about 2 h).**
Fluid-only `buoyantSimpleFoam` pipe with the driver's fluid
dictionaries; details in `docs/integrations/openfoam.md`.
1. **Non-orthogonal correctors 1 and 2; `limited corrected 0.33`;
   `uncorrected`:** all still diverge in 4–5 iterations.
2. **`blockMesh` O-grid** (`validation/tools/blockmesh_ogrid.py`, same
   topology and counts): diverges.  So not hexmesh or `gmshToFoam`.
   - **Skewed `blockMesh` duct:** diverges at every shear tried, 1° to
     35°; unsheared converges.  So not the O-H topology either.
   - **The shipped `buoyantCavity` tutorial, box sheared 1°:**
     floating-point exception at iteration 6.  The v1912 build's buoyant
     solvers fail on any non-orthogonal mesh.
3. **OpenFOAM v2406** (`opencfd/openfoam-default:2406` Docker image,
   pulled for this; 1.5 GB): the sheared tutorial, our O-H pipe and the
   23° duct all converge.
   - **The full CHT case on v2406**, k = 1 (10 944 cells; mesh,
     conversion and setup by the driver on v1912, only
     `chtMultiRegionSimpleFoam` in the container): converged in 3000
     iterations, residuals ≤ 2e-6; energy balance −6e-8, mass 2e-9.

     | Quantity | k = 1 | exact (mesh-based where it applies) | error |
     |---|---|---|---|
     | Nu | 4.469 | 48/11 = 4.364 | +2.4 % |
     | dT_b/dx (K/m) | 16.133 | 16.138 | −0.03 % |
     | ΔT steel (K) | 0.05796 | 0.05818 | −0.37 % |
     | ΔT insulation (K) | 163.31 | 163.00 | +0.19 % |

     Steel–fluid interface temperatures match to 1e-11.  So the
     driver, the regions and the coupled baffles work; only the solver
     build was in the way.
- Scratch: this session's scratchpad, `0035d/` (`make.py`, the
  fluid-only reproducer; `cht2406.py`, the driver with the solver in the
  container; the cases).

## Questions for design

**Q1. The compressible/buoyant solvers diverge on hexmesh meshes in this
build; how to proceed?**  Not explained yet (*Agent notes*;
`docs/integrations/openfoam.md`).  It blocks every case with a fluid
region in `chtMultiRegion*Foam`, so this task, and any CHT study.
Options:
- (a) **Diagnose further** (coding, time-boxed, about half a day): a
  `blockMesh` O-grid pipe tells topology from hexmesh/`gmshToFoam`
  specifics; a skewed `blockMesh` duct tests non-orthogonality alone;
  then bisect between the two meshes.  If it is a hexmesh mesh property,
  it's a hexmesh bug, worth a task of its own.
- (b) **Another OpenFOAM build** (a newer ESI or Foundation release, e.g.
  in a container) to see whether v1912's buoyant solvers are the issue.
  Changes the validated toolchain, so it's yours to decide.
- (c) **Split the physics:** incompressible flow (`simpleFoam`) frozen,
  then energy alone with a passive scalar (`scalarTransportFoam` with
  per-region conductivity isn't available; a fluid-only constant-q″
  wall would test Nu, and task 0034 already tests the solids).  Loses
  the coupled CHT check, which is the point of this task.
I'd do (a) first: whether it's hexmesh's fault decides everything else.

### Design answer (2026-10-29): (a), time-boxed to half a day, in this order

1. **Non-orthogonal correctors first** (not in your list).  hexmesh's
   O-H corners are 23–35° non-orthogonal; the converging `blockMesh` duct
   is orthogonal; the transverse velocity starts at r ≈ 0.46–0.53 R, at
   the corners.  Compressible pressure equations are more sensitive to
   that than `simpleFoam`'s.  Try `nNonOrthogonalCorrectors` 1 and 2 on
   the hexmesh pipe.
2. **A `blockMesh` O-grid pipe** with the same topology, counts and
   stations: `validation/tools/blockmesh_ogrid.py` (written by the
   design session for the stenosis SIMPLE check;
   `stations_from_case(your hexmesh case)`, then `block_mesh_dict(xs,
   radius=lambda x: R, nang, nrad)`).  Then your skewed `blockMesh` duct
   at 23°.
   - **The O-grid diverges too:** it's the O-H topology (corner
     non-orthogonality) in v1912's buoyant solvers.  Not a hexmesh bug;
     record it, and the fix is in the solver settings (correctors,
     `limited corrected` snGrad) or the O-H corner design (decision
     0022's self-similar core).
   - **The O-grid converges:** it's hexmesh/`gmshToFoam`-specific.
     Bisect (point and face order, patch types after
     `apply_boundary_roles`, zones, `physicalType` lines) and report it
     as a hexmesh bug under *Questions for design*: that gets a task of
     its own, ahead of this one.
3. **(b) for diagnosis only:** a current OpenFOAM release in a
   container, to see whether v1912's buoyant solvers are the issue.
   Switching the validated toolchain needs a decision.
4. **(c) is not the task's goal**, but if (a) and (b) end without a fix,
   report what a split (frozen flow + energy) would and wouldn't validate.

Record everything in `docs/integrations/openfoam.md` (your "Open" entry).

**Q2. v1912 can't run any case with a fluid region in a buoyant or CHT
solver on a hexmesh mesh (every one is non-orthogonal).  Which
toolchain for CHT?**
- (a) **v2406 in Docker for the solver only**, as `cht2406.py` did: a
  `--openfoam docker:opencfd/openfoam-default:2406` option in
  `hexmesh.study.openfoam` (`foam()` runs solvers in the container,
  conversion stays on v1912).  Small; validated toolchain becomes
  mixed, so version records must name both.
- (b) **v2406 for every validation case** (re-run 0020, 0032, 0034 on
  it).  One toolchain, but re-validation cost (0032's k4 alone is 5 h).
- (c) **Install v2406 natively** instead of Docker; same as (a)/(b)
  without the container, but it's a system change for you.
- Also worth deciding: report the v1912 defect upstream?  It reproduces
  on their own tutorial with a 1° shear, so the report is short.
- I'd take (a) now (it unblocks 0035 with three levels at about the cost
  measured) and (b) only if a case shows the two builds disagree.

### Design answer to Q2 (2026-10-30): v2406 for new cases, one toolchain per case

Excellent diagnosis.  It clears hexmesh and pins the cause on v1912's
buoyant solvers.
- **Runner option:** `hexmesh.study.openfoam` gains a selectable runner
  (`native`, or `docker:<image>`).  `foam()` runs utilities and solvers
  through it, and every result records the runner and image.
- **One toolchain per case:** run conversion *and* solvers in the same
  version for a case, not v1912 conversion with a v2406 solver, so each
  result names one toolchain.  Check that v2406's `gmshToFoam` gives the
  same mesh (cell count and patches; it should).
- **v2406 (`opencfd/openfoam-default:2406`) is the default for new
  validation cases:** this task, and 0049, 0050, 0067, 0068.
- **Finished cases** (0020, 0032, 0033, 0034) keep their v1912 results
  and recorded versions.  Cross-check on v2406 at their coarsest level
  (0032 at k = 2), once.  If a key quantity moves by more than its
  GCI, report it under *Questions for design*; otherwise record the
  agreement in each RESULTS.md.
- **No upstream report:** v1912 is unsupported and the defect is absent
  in v2406.
- **Users:** add to `README.md` (limitations / OpenFOAM) that buoyant
  and CHT solvers need OpenFOAM v2406 or later on non-orthogonal meshes,
  which includes every hexmesh mesh, with the 1° sheared-tutorial
  evidence in `openfoam.md`.
- **Shared machine:** container processes appear in `/proc`, so
  `other_runs()` sees them.  Check that it does, and record it.
- **Then finish 0035** on v2406, three levels as planned.

Decision 0012 is amended to match (toolchain).

## Outcome

_Not done._
