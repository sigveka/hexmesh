# 0020 — Validation: laminar Hagen–Poiseuille pipe, three refinement levels

- **Status:** done
- **Decision:** [0012 — OpenFOAM verification and validation cases](../decisions/0012-openfoam-validation-cases.md)
- **Category:** V1 (exact)
- **Features:** `section:circle`, `straight`
- **Depends on:** 0005 (done 2026-10-25), 0009's fix to `write_openfoam`
  for single-material meshes (see step 1), and **0023** (boundary
  retyping).  Decision 0013: use 0023's `apply_boundary_roles` for the
  wall type instead of retyping by hand, so this validation exercises
  the real pipeline.
- **Re-run depends on:** **0025** (ruled straight slabs).  0026
  (`refined(k)`) is optional: use it if done.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  This is the simplest exact check that a hexmesh mesh gives a
correct, converging CFD answer.  Steady laminar flow in a straight pipe
has an analytic solution, so any error is mesh and discretisation error.
Three refinement levels show whether the error shrinks at the expected
rate.

**Physics (exact, for the checks).**
- Fully developed laminar flow, pipe diameter D, mean velocity Ū,
  kinematic viscosity ν (OpenFOAM's incompressible `p` is kinematic,
  p/ρ).
- Kinematic pressure drop over a length L_m:
  **Δp = 32 · ν · Ū · L_m / D²**.  This is the same as
  ΔP = 128 μ L Q / (π D⁴).
- Centreline velocity **u_max = 2 Ū**.  Profile
  u(r) = 2 Ū (1 − r²/R²).
- Development length ≈ 0.06 · Re · D.

**Setup (suggested values; record any change under Agent notes).**
- D = 0.02 m, ν = 1e-6 m²/s (as in `pipeCyclic`), Re = Ū D / ν = 100,
  so Ū = 5e-3 m/s.
- Pipe length 30 D, so development ≈ 6 D.  Measure between x = 15 D and
  x = 25 D (L_m = 10 D), well inside the developed region.
- Inlet uniform `fixedValue` U = Ū; outlet `p` `fixedValue` 0, U
  `zeroGradient`; wall `noSlip`.
- **Mesh:** one or more `Straight` fittings in an `Assembly`, single
  layer `PipeSpec(nang=…).core("fluid", radius=D/2, nrad=…)`.  Put
  interfaces at the measurement planes (x = 15 D and 25 D), so pressure
  can be sampled on existing mesh faces.  Patches come out as
  `fluid_inlet`, `fluid_outlet`, `fluid_wall` (check the names actually
  written).
- **Refinement:** three levels, doubling `nang`, `nrad` and every
  `n_layers` per level (8× cells per level).  Coarse level about 5–10 k
  cells.  hexmesh has no global refinement factor (the legacy
  `refinement` went with decision 0004).  Scale the parameters in the
  script, and **record under *Questions for design*** whether a
  `refine(factor)` API is wanted.  Don't build one here.
- Use `Assembly.cell_count()` before meshing, and log it.

**Case setup from `pipeCyclic`.**  Source:
`/usr/share/doc/openfoam-examples/examples/incompressible/simpleFoam/pipeCyclic`
(read-only; copy).
- Take `system/fvSchemes`, `system/fvSolution` and `system/controlDict`
  as the base.  Drop its function-object `#include`s
  (`coordinateTransform`, `momentum`, `timeInfo`).
- Keep `constant/transportProperties` (Newtonian, ν = 1e-6).
- **Changes required for this case:**
  - `constant/turbulenceProperties`: `simulationType laminar;`
    (pipeCyclic is RAS realizableKE).
  - `fvSchemes`: remove the k/epsilon/R/nuTilda entries.  Second-order
    schemes throughout; keep `div(phi,U) bounded Gauss limitedLinearV 1`,
    or use `linearUpwind grad(U)` and record which.
  - `fvSolution`: tighten `residualControl` well below pipeCyclic's
    (`p 1e-2` is far too loose for a 1 % pressure check), e.g. p 1e-6,
    U 1e-7.  Raise `endTime` until converged.  Record the iterations
    needed.
  - Not used: pipeCyclic's coded swirl inlet, `topoSet`/`refineHexMesh`,
    and parallel decomposition.  Run serial.
  - Write `0/U` and `0/p` from scratch for the patch names above.
- `hexmesh.io.writers.openfoam.write_openfoam_case` targets multi-region
  CHT cases and still mentions the deleted `Network` in its docstring.
  Use it only if it fits a single-region case.  Otherwise write the
  dictionaries in the script, and note the gap under *Agent notes*.

**Pipeline per level (script `validation/poiseuille/run.py`).**
1. Build the mesh with hexmesh and write it with
   **`Assembly.write_openfoam(path)`** (task 0005: MSH 2.2 ASCII; v1912
   reads 2.2 and 4.1 alike).  This is a **single-material** mesh, the
   case where 0005's `write_openfoam` emptied every physical group.  Make
   sure 0009's guard is present (regression test
   `test_single_material_keeps_every_group`), and check that the patches
   come out as `fluid_inlet`, `fluid_outlet` and `fluid_wall`, not
   `patch0`.  Recipe and quirks: `docs/integrations/openfoam.md`.
2. Under the OpenFOAM environment
   (`source /usr/share/openfoam/etc/bashrc`):
   - run `gmshToFoam`;
   - set wall patch types with task 0023's `apply_boundary_roles`, using
     the `.roles.json` that `write_openfoam` writes (`gmshToFoam` writes
     every patch as `patch`);
   - run `checkMesh` and save its log, then `simpleFoam`.
3. Post-process with `postProcess -func` or a function object.
   - Area-averaged `p` on the planes at 15 D and 25 D → Δp.
   - Flow rate through the outlet → check Ū.
   - `u` along the centreline at 20 D → u_max.
   - Also sample the radial profile u(r) at 20 D.
4. Compute errors against the exact values above.

**Convergence report.**
- e_k = |Δp_k − Δp_exact| / Δp_exact for k = coarse, medium, fine.
- Observed order p = log₂(e_coarse / e_medium) and log₂(e_medium /
  e_fine).
- The same for u_max.
- Write `validation/poiseuille/RESULTS.md` with a table: level, cells,
  min scaled Jacobian (task 0004 report), checkMesh non-orthogonality
  and skewness maxima, iterations, Δp, e, u_max, e.  Include versions
  (hexmesh git hash, gmsh, OpenFOAM) and the date.  Optionally include
  one profile plot (PNG) per level against the exact parabola.

**Layout (decision 0012).**
- `validation/poiseuille/run.py`, `README.md`, `RESULTS.md`.
- Work directory `validation/poiseuille/work/`, git-ignored (add to
  `.gitignore`).
- `tests/test_validation.py` with `@pytest.mark.openfoam`, skipped when
  `gmshToFoam` is not on PATH, and excluded from the default `pytest`
  run (register the marker; default `-m "not openfoam"`).  It runs the
  script and asserts the acceptance criteria below.

**Accept.**  *Revised 2026-10-26 by decision 0015; the original
criteria are kept below, struck, for the record.*
- `checkMesh` reports "Mesh OK" at all three levels.
- **Signed errors**, Δp and u_max, against two references:
  - the exact circle (as before);
  - the **meshed geometry**: Poiseuille for the equivalent circle of the
    mesh's own cross-section, Δp_ref = 8 π ν L_m Q / A², with A the
    summed face area of the inlet patch and Q the flow measured through
    the outlet.
- **Richardson extrapolation** of the three levels for Δp and u_max,
  following [`celik_and_ghia_etal_2008`] (RESEARCH §7.4): observed
  order, extrapolated value, and GCI on the fine level.
- **Gates:**
  - extrapolated Δp and u_max within **0.1 %** of exact;
  - fine-level |error| against the circle < 1 % for both;
  - |error| against the circle decreases monotonically for both;
  - u_max observed order ≥ 1.5.
  - Δp's observed order is **reported, not gated**: the polygon's
    geometric error competes with it (RESEARCH §7.4).
- **Non-orthogonality trend:** `checkMesh` only (no solve) on a short
  pipe (e.g. 2 D, few axial layers) with the same cross-section at
  `nang` 48 and 96 (`nrad` scaled with it).  Report max
  non-orthogonality and skewness for `nang` 6–96.  Expected: they level
  off near the 135° corner kink's limit (about 45°).  If they keep
  growing, report it under *Questions for design*; it does not block.
- Remove the `xfail` marks for criteria that now pass.
- `RESULTS.md` replaced with the new run; keep the sagged-wall table as
  "before task 0025" history.
- Default `pytest` run unchanged.

~~Original criteria:~~
- ~~`checkMesh` reports "Mesh OK" at all three levels.~~
- ~~Errors in Δp and u_max decrease monotonically from coarse to fine.~~
- ~~Fine-level Δp error < 1 %, and fine-level u_max error < 1 %.~~
- ~~Mass balance: outlet flow rate matches the inlet to < 0.1 %.~~ (kept;
  it passes at 1e-10)
- ~~Observed order ≥ 1.5 for both.~~  Still: **if a gate is missed, do
  not tune the case to pass**; report under *Questions for design*, set
  `blocked`, and stop.

**Out of scope.**  Cyclic or periodic setups, turbulence, heat transfer,
other fittings, a `refine()` API, and fixing `write_openfoam_case`
beyond what this case needs.

## Agent notes

- **Setup as suggested**, with these specifics:
  - D = 0.02, ν = 1e-6, Re = 100, length 30 D;
  - three `Straight`s of 15 D, 10 D and 5 D, so interfaces lie at the
    measurement planes;
  - levels: `nang` 6/12/24, `nrad` 3/6/12, axial 48/96/192, giving
    5 184 / 41 472 / 331 776 cells.  Predicted = meshed = `gmshToFoam`;
  - axial spacing is uniform (12.5 mm coarse) in all three fittings.
- **Schemes:** pipeCyclic's, kept as `div(phi,U) bounded Gauss
  limitedLinearV 1`.
- **Solvers:** pipeCyclic's, with tolerances tightened (p 1e-9, U 1e-10)
  and residual control p 1e-6, U 1e-7.
  - Converged in 107 / 327 / 941 iterations.
  - Checked: forcing 2 000 iterations with residual targets of 1e-12
    changes Δp by 1 part in 10¹⁰.
- **Case files written by the script.**  `write_openfoam_case` targets
  multi-region CHT (as the integrations file notes), so it was not used.
  A single-region `simpleFoam` case needs:
  - `controlDict`, `fvSchemes`, `fvSolution`;
  - `transportProperties`;
  - `turbulenceProperties` (`laminar`);
  - `0/U` and `0/p` for the three patch names;
  - optionally `topoSetDict`.
- **Function objects abort on this OpenFOAM build** (`dictionary::digest`,
  IOstream "sha1"), both in `controlDict` and through `postProcess
  -func`.  Recorded in `docs/integrations/openfoam.md`.
  - Workaround: post-processing in Python from the ASCII files.
  - `topoSet` (`boxToFace` + `setToFaceZone`) makes the face zones at
    15 D, 25 D and 20 D.
  - p is area-averaged on the zone faces; face values are ½(owner +
    neighbour), exact for the uniform axial spacing.
  - Flow rates come from `phi` on the patches.
- **u_max is the centreline value from a fit.**
  - No face centre lies on the axis.  The four nearest are 0.12 R off
    it at the coarse level, a 1.46 % offset in the exact profile alone.
  - So the value is c₀ of u = c₀ − c₂r², fitted to the 20 D faces within
    R/3 (12 / 52 / 200 faces).
  - The four-face mean and the exact profile at those faces are reported
    beside it in `RESULTS.md`.
- **Pipeline checks:**
  - patches come out as `fluid_inlet`, `fluid_outlet` and `fluid_wall`;
  - `apply_boundary_roles` retypes `fluid_wall`;
  - 0009's single-material guard is in place;
  - "Mesh OK" at all levels.
- **The `pipeCyclic` tutorial doesn't run as shipped here.**  Its coded
  inlet needs `WM_OPTIONS`.  Recorded.

## Questions for design

The acceptance targets are missed.  Per the task, the case was not tuned;
here are the numbers and the diagnosis.  Full tables are in
`validation/poiseuille/RESULTS.md`.

1. **`Straight` walls are not cylindrical between interfaces (mesh
   finding, breaks DESIGN §6 exactness).**

   | Level | e(Δp) | e(u_max) |
   |---|---|---|
   | coarse | 2.59 % | 0.14 % |
   | medium | 2.63 % | 0.93 % |
   | fine | 2.60 % | 1.14 % |

   - The Δp error does not converge, and the u_max error grows.
   - **Cause:** a `Straight` is one slab with `n_layers` axial layers.
     Its outer side surfaces are `addSurfaceFilling` plates, and GMSH
     puts the interior wall nodes on them.
   - The plate sags up to **1.08 % of R** inside the circle (at ~30° from
     a corner), the same at `nang` 6, 12 and 24.  Interface faces are
     exact.
   - **Confirmation:** for medium and fine, the sagged cross-section
     predicts the measured Δp (Δp ∝ 1/A² at fixed Q) within 0.1 %:
     1.0262 vs 1.0263, and 1.0246 vs 1.0260.
   - **Not in DESIGN's deviations table.**  §6 says interior nodes
     "follow from transfinite interpolation of those exact boundaries";
     in GMSH they are projected onto the filled surface.  Bend, Reducer
     and Closure are unaffected: they have one layer per slab.
   - **Two exact options**, both measured (16 layers, `nang` 6 and 24):
     - **(a) ruled side surfaces** for straight slabs
       (`addBSplineFilling(type="Stretch")`, already `sweep._ruled` for
       miter slabs).  Wall nodes are on the cylinder to 4e-16 R, min SICN
       unchanged.  Cheap.
     - **(b) one station per axial layer**, like the Reducer.  Equally
       exact, with more OCC entities.

     Which one, and should DESIGN §6 say "straight slabs use ruled side
     surfaces"?  Other multi-layer slabs with plate sides should be
     checked too: SplinePipe and Closure use one layer per slab, but the
     tee's run slabs are already in the deviations table.
2. **With exact walls (diagnostic only, (a) patched in at run time):**

   | Level | e(Δp) | e(u_max) |
   |---|---|---|
   | coarse | 0.45 % | 0.93 % |
   | medium | 0.21 % | 0.25 % |
   | fine | 0.10 % | 0.07 % |

   - Monotonic, and both fine errors are < 1 %.
   - Observed order: u_max 1.88, 1.80; **Δp 1.12, 0.99**, below the 1.5
     threshold.
   - Max non-orthogonality (23 → 33 → 39°) and skewness (0.42 → 0.52)
     **grow with refinement**.  A smooth mapped mesh would level off, so
     the O-grid core corners are the first suspect for the first-order
     Δp.  Not investigated further.
   - **Question:** is first-order Δp convergence acceptable on the O-H
     section, or should the core corner topology / inner-square sizing be
     revisited (a design topic)?
3. **`refine(factor)` API?**  The script scales `nang`, `nrad` and every
   `n_layers` by hand (`assembly(factor)`), in 6 lines.  A
   `refine(factor)` would mainly help networks with many fittings.  Is it
   wanted?

### Design answers (2026-10-26, decision 0015)

1. **Option (a), ruled side surfaces**, now a DESIGN §6 rule.  Task
   0025, which also adds a wall-exactness check to the conformance kit
   (it also covers material interfaces: the design session measured the
   same sag on a fluid/steel interface).
2. **First-order Δp is an artefact of the reference, not the O-H
   section.**  The mesh's cross-section is the inscribed 4·`nang`-gon.
   Your inlet-flow deficit (1.138 / 0.285 / 0.071 %) equals its area
   deficit to four digits.  At fixed inlet velocity that adds
   +1.151 / +0.286 / +0.071 % to Δp, a second-order error of the opposite
   sign to the discretisation error (remainder −0.692 / −0.079 /
   +0.033 %).  Richardson extrapolation of your three levels: Δp
   +0.030 % from exact (order 1.25), u_max −0.007 % (order 1.91).  So
   the solution converges; acceptance is revised above.  The topology is
   not revisited now; the non-orthogonality check above settles whether
   it levels off.  Details: RESEARCH §7.4.
3. **Yes**, as `Assembly.refined(k)`, integer k: task 0026.

## Outcome

**Re-run after 0025 (2026-10-26):** every revised gate passes; see
`validation/poiseuille/RESULTS.md`.
- `run.py`:
  - signed errors against both references, the circle and the meshed
    section (inlet area A, measured Q);
  - `richardson()` (Celik 2008);
  - `nonorth_trend()` (checkMesh only, `nang` 6–96; `--no-trend`).
- **Δp:** extrapolated +0.030 % from exact, observed order 1.25 (not
  gated), GCI 0.093 %; the fine level is +0.104 % off.
- **u_max:** extrapolated −0.007 %, order 1.91, GCI 0.083 %; the fine
  level is −0.073 % off.
- Non-orthogonality levels off: 23.5 → 33.2 → 38.9 → 41.9 → 43.4°.  No
  design question.
- `tests/test_validation.py`: the `xfail` marks are removed, and the
  gates are rewritten to decision 0015.  `-m openfoam
  tests/test_validation.py`: 11 passed (22 min).  The default run is
  unchanged: the module is opt-in.
- Task 0026 was not done, so the script still scales density by hand.


*First run (2026-10-26):* blocked (see *Questions for design*); acceptance not met.

- **Files:**
  - `validation/poiseuille/run.py` (the pipeline and Python
    post-processing);
  - `validation/poiseuille/README.md`;
  - `validation/poiseuille/RESULTS.md` (both tables, versions, date);
  - `validation/poiseuille/diagnostic_ruled_walls.py` (the exact-wall
    diagnostic; not a fix);
  - `tests/test_validation.py`: 8 tests, opt-in `-m openfoam`, deselected
    by default.  The convergence and 1 % checks are `xfail` (non-strict)
    pointing at this block.  The pytest wrapper itself was not run
    end-to-end (22 min); the script it runs was, twice;
  - `.gitignore` (`validation/*/work/`);
  - `docs/integrations/openfoam.md` (function objects, pipeCyclic) and
    `docs/integrations/gmsh.md` (plate-surface interior nodes); both
    untracked.
- **Met:**
  - "Mesh OK" at all levels;
  - mass balance < 1e-10;
  - patch names and retyping;
  - predicted cells = converted cells;
  - default pytest run unchanged.
- **Not met:** monotonic decrease, fine < 1 % (Δp 2.60 %, u_max 1.14 %),
  and observed order ≥ 1.5.
- **Runtime:** about 22 minutes for all three levels, serial; fine level
  332 k cells and 941 iterations.
- **Proposed follow-ups:**
  - ruled side surfaces for straight slabs, plus a wall-exactness check
    in the conformance kit (every wall node at radius R for straight and
    curved sweeps);
  - then rerun this validation;
  - a single-region case writer, or a fix for `write_openfoam_case`.
