# 0034 — Validation: conduction through a heated, multi-layer cylinder (CHT, solids only)

- **Status:** ready (after 0025 and 0033)
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md)
- **Depends on:** 0025 (exact straight walls **and material
  interfaces**: before it, interfaces sag up to 0.7 % of R, which biases
  the layer resistances), 0033 (`laplacianFoam` + `fvOptions` setup).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The first check of hexmesh's multi-material output in a
coupled solve: the layer stack, exact layer thicknesses, material
interfaces through `splitMeshRegions` → `mappedWall`, radial grading per
layer, and the role manifest (task 0023).  Solids only, so it isolates
interface coupling from flow.

**Physics (exact).**  A heated rod with cladding (like a fuel pin):
core radius r₁ with heat generation q‴ and conductivity k₁; shells
`steel` (r₁→r₂, k₂) and `insulation` (r₂→r₃, k₃); outer surface at T₃
(variant 2: convection h to T_∞).
- Heat per length q′ = q‴ π r₁².
- Shells: T(r) = T_out,i + q′/(2π kᵢ) · ln(r_out,i / r).
- Core: T(r) = T(r₁) + q‴ (r₁² − r²)/(4k₁).
- Variant 2: T₃ = T_∞ + q′/(2π r₃ h).
- Interface temperatures T(r₁), T(r₂) follow exactly.
- Choose conductivities that differ strongly (e.g. k₁ = 20, k₂ = 50,
  k₃ = 0.05 W/m K), so a coupling error shows.

**Setup (suggested).**
- Spec: `.core("rod", …)`, `.shell("steel", …)`, `.shell("insulation",
  …)`, short `Straight` (2 axial layers), ends adiabatic (zeroGradient).
- `write_openfoam` → `gmshToFoam` → `splitMeshRegions -cellZones
  -overwrite` → `apply_boundary_roles_to_regions`.
- Solver: `chtMultiRegionSimpleFoam` with three solid regions and no
  fluid region; coupled interfaces with
  `compressible::turbulentTemperatureCoupledBaffleMixed`
  (`kappaMethod solidThermo`); constant-property `heSolidThermo`.
- **Step 0: check the solver runs on this build** (the `pipeCyclic`
  tutorial didn't, and function objects abort).  Run a shipped
  `chtMultiRegionSimpleFoam` tutorial or a minimal two-solid case first,
  and record the outcome in `docs/integrations/openfoam.md`.  If it
  can't run, set `blocked` with the error.
- Levels: `nang` 6 / 12 / 24 with every `nrad` scaled.

**Measure.**
- T at r₁ and r₂ (interface faces, area-averaged), centre T, outer T
  (variant 2): signed errors against exact.
- Heat flux through each interface and the outer wall vs q′ (energy
  balance per region).
- Volume-weighted L2 error of T per region.
- Signed errors, observed order, Richardson [`celik_and_ghia_etal_2008`].
- `mappedWall` pairs: equal face counts on each side (as task 0022).

**Layout.**  `validation/layered_conduction/`, as task 0033; opt-in
test on the coarsest level.

**Accept.**
- "Mesh OK" per region at all levels.
- Energy balance through every interface to solver tolerance.
- Extrapolated interface and centre temperatures within 0.1 % of exact
  (of the total temperature rise); L2 order ≈ 2 per region.  If missed,
  report under *Questions for design*, don't tune.
- Both variants (fixed T₃, convection).
- `docs/integrations/openfoam.md` gains the CHT recipe that worked.
- Default `pytest` run unchanged.

**Out of scope.**  Fluid regions (task 0035); contact resistance;
temperature-dependent properties.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
