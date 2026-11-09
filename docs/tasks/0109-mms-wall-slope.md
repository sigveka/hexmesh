# 0109 — MMS: does the order track the wall slope?

- **Status:** done
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md); follow-up of task 0074 (RESEARCH §7.14)
- **Depends on:** 0074, 0108.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  In 0074 the reducer, transition and tees converge at about
first order, and the least-squares gradient doesn't recover them.  What
they share is a wall-face non-orthogonality that refinement doesn't
shrink (reducer 21–24°, transition 12–14°, tee 9°), which OpenFOAM's
`fixedValue` snGrad doesn't correct.  Design has taken it as a scheme
property (RESEARCH §7.14), but not as verified to be the only cause.  If
it is, the order should rise as the wall slope falls.  If not, the
fittings' near-wall grid may need changing, which would be a decision.

**Where.**  `validation/mms/run.py` (a new series); `validation/mms/`
(`RESULTS.md`, `results.json`); RESEARCH numbers go in *Outcome* (design
moves them).

**Do.**
1. **A reducer slope series:** the cosine reducer at three or four
   constrictions, so the wall's maximum slope spans about 5° to the
   0074 case's (e.g. outlet radii 0.95, 0.9, 0.8 and 0074's R).  Same
   manufactured T, schemes and k levels (at least k 1, 2, 4) as 0074.
   Use `keep_orientation` as 0108 sets it.
2. **Measure** per constriction: the L2 order in the fitting (k 2→4,
   §7.12's rule), the median and maximum wall-face non-orthogonality,
   and the error's location (near the wall or in the interior).
3. **One control** that removes the boundary effect without changing the
   mesh: impose T through a boundary condition that corrects for
   non-orthogonality, if v2406 has one that fits (check
   `docs/integrations/openfoam.md` first; record what you find).  If
   none fits, say so and skip it.
4. **Plot** order against wall non-orthogonality (one PNG beside
   RESULTS.md).

**Accept.**
- The table and plot are in RESULTS.md; *Outcome* states plainly
  whether the order tracks the slope, and how closely.
- No gate: this is a measurement.  Its interpretation is for design.
- Meshes and case directories deleted after the run; results.json keeps
  the numbers.  Check `df -h .` before starting and note it here.

**Out of scope.**  Changing the reducer's or transition's grid.

## Agent notes

- **Disk:** 29 GB free before the run (`df -h .`, 2026-11-09).  The
  levels are small (83k cells at k = 4); each case directory was deleted
  once stored, and none is left.
- **The constrictions, refined (step 1).**  The cosine form over
  L = 4 R has its largest wall slope at atan(π s0 / 2).  The task's
  example radii (0.95, 0.9, 0.8) would start at about 2°, so I chose s0
  by slope instead: 0.05, 0.1, 0.2 and 0074's 0.4, which give 4.5°, 8.9°,
  17.4° and 32.1°, roughly doubling each step.  0074's case throats at
  1 − 2·0.4 = 0.2 R.  The driver's comment said 60 %; it's corrected.
- **s0 = 0.4 runs again as `reducer_s040`.**  Stored levels are reused,
  so 0074's `reducer` rows would never gain the wall measurements.  The
  rerun gives the same L2 to 13 digits (k = 4: 0.0026516971743004 vs
  …3014).
- **Wall non-orthogonality (step 2)** is measured in `results()` for
  every new level, over the focus fitting's faces on `*_wall` patches.
  It uses OpenFOAM's geometry, as in `of.cell_geometry`.  I can't
  reproduce 0074's reducer numbers (median 21–24°): the script that
  produced them isn't in the repository.  Mine, on 0074's mesh: 13.7°,
  15.6°, 15.3°.  Per face, the angle isn't the wall slope.  Away from the
  throat it is below the slope; at the throat it is above (14° slope,
  35° angle at k = 1), where the near-wall cells are thin and sheared.
- **The error's location (step 2)** is split into the fitting's cells
  with a wall face and the rest (`focus_wall_cells`,
  `focus_off_wall_cells`).
- **The control (step 3).**  `docs/integrations/openfoam.md` had nothing
  on this, so I read v2406's source in the Docker image.  No boundary
  condition corrects a `fixedValue` wall for non-orthogonality: the
  correction vectors are zeroed on every non-coupled patch, in the
  geometry scheme, before any condition is applied.  What fits the
  step's purpose, removing the boundary effect without changing the
  mesh, is the exact *flux* at the wall: `uniformFixedGradient` with
  n·∇T_m as an expression of `normal()`.  A Neumann wall's Laplacian flux
  is exact, so the uncorrected snGrad never enters it.  The ends stay at
  T_m.  Recorded in `openfoam.md`.  The applied condition is read back
  from the solved `T` and stored per level (`wall_bc_applied`).
- **Not gated:** the series is left out of `recheck()` (task: "no
  gate"), and out of the README's mesh gallery.
- **The plot** is `validation/mms/img/slope.png`, where the other cases'
  extra graphs live, drawn by `validation/tools/plots.py` (`mms_slope`)
  and hash-checked like them.  The task said "beside RESULTS.md"; `img/`
  is the repository's place for it.

## Outcome

**Done** (2026-11-09).  **The order tracks the wall non-orthogonality,
and the wall's value condition is the cause.**

| s0 | max slope | wall non-orth. median, k = 4 | order k 2 → 4 | control (exact wall flux) |
|---|---|---|---|---|
| 0.05 | 4.5° | 3.1° | 1.27 | 1.80 |
| 0.1 | 8.9° | 5.8° | 1.17 | 1.85 |
| 0.2 | 17.4° | 10.9° | 0.99 | 1.68 |
| 0.4 (0074's) | 32.1° | 15.3° | 0.95 | 1.84 |

The straight's order, k 2 → 4, is 1.60.  The full table, with k 1 → 2,
the maxima, and the error at the wall and off it, is in
`validation/mms/RESULTS.md`.

- **How closely:** monotonically, at every step.  The order falls by
  0.3 from 3° to 15° median wall angle, and the two largest constrictions
  sit at first order.  Even 3° costs 0.5 against the control.  Any
  nonzero angle leaves a first-order term, with a coefficient that grows
  with tan θ, so at these levels the order is a blend.
- **The control, on the same meshes, gives 1.68–1.85 at every slope**,
  with no trend.  Nothing else in the reducer's near-wall grid holds the
  order down.  RESEARCH §7.14's reading, a scheme property of
  `fixedValue` at a non-orthogonal wall, is confirmed for the reducer.
  Its wall angle doesn't need a grid change.
- **The wall's error spreads inward:** off the wall the order falls with
  the angle too (1.20 → 0.98).
- **Cause, in v2406's source:** the non-orthogonal correction vectors are
  zero on non-coupled patches, and the patch delta is normal.  So a
  `fixedValue` wall's snGrad ignores the cell centre's tangential offset
  (`docs/integrations/openfoam.md`).

**For RESEARCH (§7.14):** the table above, the control, and the source
reference.

**Surprises.**
- The wall angle isn't the slope (notes).  At the throat, thin sheared
  cells push it above the slope; elsewhere it is below.
- The control's absolute errors are 1.7–5.6× larger.  A Neumann wall
  fixes the flux, not the level.  It is a check on the order, not a
  remedy.
- 0074's wall-angle numbers can't be reproduced from the repository.

**Files.**  `validation/mms/run.py`: the series, the control, the wall
measurements, `slope_series`, `slope_table` and `--slope`.
`validation/mms/results.json` (24 new levels), `RESULTS.md`, `figure.png`
(redrawn: its source hash changed), `img/slope.png`.
`validation/tools/plots.py` (`mms_slope`), `docs/integrations/openfoam.md`.

**Tests:** `test_validation_meta.py` (69), `test_validation_counts.py` and
`test_validation_drivers_import.py` (23) pass.  `recheck mms` passes.  No
library code changed.

**Proposed follow-ups (for design).**
- The transition and the tee were flagged with the reducer.  The same
  control on them would show whether their first order is all wall too.
  The tee also has interior kinks, so it may not be.
- Users solving on a sloped wall with a fixed value see first order near
  it.  Whether the user guide should say so, and what to recommend, is
  design's call.
