# 0034 — Validation: conduction through a heated, multi-layer cylinder (CHT, solids only)

- **Status:** done
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

- **Step 0.**  `chtMultiRegionSimpleFoam` runs with three solid regions
  and no fluid.  The working recipe is in `docs/integrations/openfoam.md`.
  Three quirks needed handling:
  - `constant/g` must exist.
  - `splitMeshRegions` needs a `divSchemes` entry.
  - **`residualControl` is ignored for solid regions**, so the solver
    runs to `endTime`.  The driver judges convergence itself: the
    largest initial residual of `h` < 1e-10 at the last step.
- **Iterations.**  The segregated coupling across the 1000:1
  conductivity ratio converges slowly: about 47 000 / 59 000 iterations
  at the coarse level (fixed / convection), doubling per level.  Each
  level runs 75 000 · k iterations.  The full study takes about 45 min,
  with the two variants in parallel.  No initial guess from the exact
  solution and no mapping from coarser levels: the converged result
  doesn't depend on them.
- **Built on 0043's `hexmesh.study.openfoam`.**  Two fixes there:
  - `read_patch_values` matched the substring `value` and so read a
    mixed condition's `valueFraction`; it now matches the keyword.  It
    also takes a face count, for `uniform` values.
  - `check_mesh` takes a region.
- **Fix:** the Poiseuille script's `versions()` ran `git status --
  hexmesh` from its own directory, so it never reported `+local`.  This
  task's runs are stamped `91c897a`, clean; `RESULTS.md` says so.
- Material values: k as suggested; q‴ = 10⁶ W/m³; h = 20 W/(m² K) for
  the convection variant.

## Questions for design

_None._

## Outcome

**All gates met, both variants** (`validation/layered_conduction/RESULTS.md`):
- "Mesh OK" in every region at every level (`nang` 6 / 12 / 24; 456 /
  1 824 / 7 296 cells).  The `mappedWall` pairs have equal face counts.
- Energy balance through each interface and the outer wall: ≤ 5e-12
  (fixed) and ≤ 1.2e-9 (convection).
- Extrapolated T₀, T(r₁), T(r₂) (and T₃, convection) within
  0.0007 % of the total rise; the gate was 0.1 %.  Observed orders are
  2.00–2.01.
- L2 order per region 1.99–2.01.
- The errors are negative and the same at every radius at a given level
  (−0.95 % coarse, −0.059 % fine).  They are the insulation's
  discretisation error: the insulation holds 99.7 % of the rise.

**Files.**
- New: `validation/layered_conduction/run.py`, `README.md` and
  `RESULTS.md`.
- `tests/test_validation.py`: an opt-in coarse-level test, both
  variants, about 4 min.
- `hexmesh/study/openfoam.py`: the reader fixes and `check_mesh(region)`.
- `validation/poiseuille/run.py`: the `versions()` fix.
- `docs/integrations/openfoam.md`: the CHT recipe and quirks.

**Meshes** (the design session's new convention): `meshes()` returns
the three levels.  `docs/gallery/build.py --validation
layered_conduction` rendered `img/` and the README's "Mesh" section.
- It also updated `docs/gallery/metrics.json` and `docs/GALLERY.md`.
  Those have the other session's uncommitted edits, so I left them out
  of this commit.
- **For design:** the k = 4 section image shows grey patches in the
  steel ring at 0°/90°/180°/270°.
  - The mesh is complete: every inlet patch has the expected face count
    (rod 1 728, steel 768, insulation 1 152) and there is no default
    patch.
  - So it looks like a rendering artefact of thin rings in the section
    view, not missing groups.

**Suite:** 1805 passed, 5 skipped (default; unchanged).  Opt-in: the
layered tests (2) and the study test (1) passed.

**Follow-ups.**
- 0035 (heated pipe with flow) can reuse this case's solid side and its
  convergence criterion.  A fluid region should converge faster, but
  check it.
- RESEARCH: move this table in as a §7 entry.
