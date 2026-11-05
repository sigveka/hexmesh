# 0086 — H ports on duct junctions, and shells around an H core

- **Status:** done
- **Decision:** [0036 — Cartesian (H) rectangular section](../decisions/0036-cartesian-rectangular-section.md) (item 5, rollout step 3); [0026](../decisions/0026-layer-outlines.md) (layer outlines); DESIGN §7.1 ("Duct junctions and the H layout")
- **Depends on:** 0085 (the switch builder); 0060's split of the
  duct-tap front end out of `Tee`, if done by then.  Otherwise do that
  split first, as described in 0060's design note.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Before the default flips (0087), every rectangular fitting must
accept H ports.  Duct junctions keep their O-H blocks and embed the
switch in their legs, so users never place switches around them
(decision 0036 item 5).  Lagged ducts need shells around an H core.

**Where.**  `assembly/duct_tap.py` (and `tee.py`'s dispatch);
`sections/` (shells around `h`); `faces`/ring builders as moved by
0082; the conformance kit; the HVAC examples.

**Do.**
1. **Duct taps and duct tees on H mains and branches.**
   - When a duct junction's port is H, its leg next to that port
     includes the switch slab(s) from 0085.  The junction's internal
     blocks stay O-H.
   - The junction declares the class-1 strategy for those ports.
   - Cover round and rectangular branches, wide and narrow faces, and
     full-width taps.
   - The leg length grows by the switch's length rule; `validate()`
     reports it in the room checks.
2. **Shells around an H core** (lagged ducts, decision 0026):
   - The first shell's ring takes the H core's four corners as its
     inner corners.  The corner diagonals then lie in the shell (solid)
     and the fluid stays Cartesian (decision 0036, option B).
   - Support the outline combinations that rectangular O-H cores
     support today: rectangle in rectangle, rectangle in circle, and
     the kit's `_rect3` / `_in_rect` / `_rect_in_circle` cases.  Any
     other combination is rejected with a named error.
   - Measure the corner-cell quality of the first shell against the
     O-H equivalent.  Check it against the skewed-ring limit from task
     0047 (`limits.py`).
3. **`Transition` with shells and an H end**: lift 0085's rejection,
   once step 2 works.
4. **Junction blocks ask `sections.oh` for their inner square**
   (design answer to task 0082's Question 2, 2026-11-03).  The tee
   (`tee.py:340–341`), wye (`wye.py:374`) and duct tap
   (`duct_tap.py:229`) still compute `OH_RATIO · R` and the ring inset
   themselves.  Take the inner-square corners and the ring thickness
   from the layout instead, so the face and the junction blocks share
   one description (decision 0037).  Do this before step 1 adds H legs,
   so that work starts from the shared form.  Accept: no `OH_RATIO` in
   `assembly/`, and every existing junction mesh is unchanged (node
   coordinates to 1e-12, the 0065 method).
5. **The switch's loss defect, separated** (design, 2026-11-04, from
   task 0085's flow check; the user agreed).  0085 measured K = −0.073
   over a `Switch` (a/b 2, Re 100): the switch loses less than developed
   flow.  The likely cause is the change between the O-H and H
   discrete developed profiles, whose f·Re differ by 2.4 %.  Before
   switches go into every duct-junction leg, check that:
   - From the two plain runs' developed outlet planes (O-H and H, the
     counts of 0085's check), compute the momentum-flux coefficient
     β = ∫u² dA / (U² A) of each.  Also compute the kinetic-energy
     coefficient α = ∫u³ dA / (U³ A).
   - Predict the pressure-line shift from the momentum balance,
     Δp_shift = ρ U² (β_H − β_OH), and compare it with 0085's
     −0.12 D_h-equivalent defect.
   - Report both under *Outcome*.  If β accounts for the defect within
     about 20 %, say so: the switch itself adds no measurable loss.  If
     it doesn't, put the numbers under *Questions for design* before
     the junction flow work relies on switches.
   - Small: reuse 0085's setup, or a 2-D-equivalent short duct.  Delete
     the runs, keep the numbers.
6. **Examples:** build the HVAC examples (`hvac_supply`,
   `hvac_branched`) and `lagged_duct` with `layout="h"` explicitly, in
   a test (not in the examples yet; 0087 changes them).  Record cell
   counts and min SJ against the O-H versions.

**Accept.**
- The conformance kit passes for every duct-tap case in
  `tests/test_fitting_conformance.py` (`_duct_tap`), now with H ports,
  and for every layered duct spec with an H core.
- No fitting that takes rectangular ports rejects `layout="h"` any
  more.  List any exceptions under *Questions for design*.
- The H builds of the three examples mesh; *Outcome* has the cell-count
  and quality table against O-H.
- Every existing mesh unchanged (the default is still `"oh"`).
- Full suite: no new failures.

**Out of scope.**  Junction layouts native to the H face (a later
decision, only if these measure badly); the default flip (0087).

## Agent notes

**Order of work.**
1. 0060's split first: 0060 isn't done, and this task's *Depends on*
   says to do the split first in that case.
2. Then step 4, which the task says goes before step 1.
3. Then steps 1, 2, 3, 5 and 6.

Task 0094 (structured errors) shares `duct_tap.py` and `tee.py`, so it
goes between or after this task's commits, never mixed into one.

**Step 0, the split (0060's design note), done 2026-11-04.**
- The duct-tap front end leaves `Tee` for `duct_tap.TapTemplate`:
  resolve, check, ports, layout, quality, fill and `meshed_sj_check`.
  - `Tee._template(spec)` picks it on a non-round main, and `Tee`
    delegates.
  - `FULL_WIDTH_RUN` moves with it.
  - `thicknesses`, `branch_spec` and `tee_wall` stay public in `tee.py`.
- The template reads the branch and the main through the shape
  protocol: `corner(0)` for the half-extents (exact: the corner is ±1
  times them), `max_extent` for a round tap's radius, `is_round`, and
  `counts`.
- `SHAPE_SITES_CAP` goes from 15 to 7.  What's left is the pipe tee's
  radius reads in `tee.py`, which are round by definition.
- **No behaviour change** (task 0065's method).  21 test files that
  build tees were recorded before and after:
  - 334 of 334 distinct meshes are identical node for node;
  - 339 of 339 messages are identical;
  - 1262 tests passed.
- The one difference is on an error path that no test reaches.
  `check()` on a duct tee with no `branch` used to raise an
  `AttributeError`.  It now raises the named "needs branch=" message.

**Step 4, done 2026-11-04.**  The junction blocks ask `sections.oh`
for the inner square.
- New in `sections/oh.py`: `inner_radius(r)` (= OH_RATIO·r, the
  centre to an inner corner) and `inner_half_side(r)` (= OH_RATIO·r/√2).
  `oh.py`'s own copies of the expression use them too.
- The tee (`ci`, `si`), the wye (crotch corner F) and the round duct tap
  call them.  No `OH_RATIO` is left in `assembly/`.
- **Every existing junction mesh is unchanged, bit for bit.**  24 test
  files that build tees, wyes or duct taps were recorded before and
  after: 349 of 349 distinct meshes and 358 of 358 messages are
  identical, and 1320 tests passed.
- **Surprise:** the first try wrote the pipe tee's `ci` as
  `inner_half_side(r)`, which is OH_RATIO·r/√2 where the old code had
  OH_RATIO·(r/√2).  The values differ by 1 ulp (relative 1.3e-16).  At
  branch ratio 0.9 that grew to 6.9e-12 in the nodes (the kit's
  `tee-0.9` cases), which is over the 1e-12 acceptance.  `ci` is now
  `inner_radius(r/√2)`, the old order.
- `test_topology_invariance` shares meshes between its tests.  Its
  recording keys depend on xdist scheduling, so compare its meshes by
  content, not by key.

**Step 1, duct taps on H mains (2026-11-05).**
- `TapTemplate` on an H main: the O-H junction inside on
  `sections.h.pillowed(spec, nrad, mprg)`, and a `Switch` leg at each H
  port (both main ports, and a rectangular branch's).  A round branch
  stays O-H.  `Tee.strategies = {0, 1}`, `pillows = True`.
- **Refined: the legs' layers.**  Each main leg has `n_run` layers and a
  branch leg `n_branch`, so the legs refine with the tee
  (`refined_dict` scales both) and a uniform H main's refined count is
  exactly 8×.  A fixed `n_layers=1` did not refine.
- **Refined: leg length.**  Each leg is `switch.min_length` of its pair
  of faces, the Q2 answer's rule, not a fixed 1.25 t.  The branch leg
  needs the inner branch spec, which depends only on the tap's shape and
  face (`TapTemplate._branch_oh`).
- `Tee(nrad=, mprg=)` is checked before the ring is derived, so a bad
  override gets its own message, not a grading error.
- Graded H mains are checked after meshing (`Tee.meshed_sj_check`, the
  round taps' mechanism), because the legs' prediction is empirical.
- The kit's `tee-duct-h-*` cases cover rect, round and full-width taps,
  wide and narrow faces, aspect 1–3, uniform and graded, one oblique: 42
  tests pass.  Their three tier warnings (0.220, 0.229, 0.277) are the
  same as the O-H originals': the taps' own, not the H main's.

**Q2's measurements, widened (answer item 2, 2026-11-05).**  450 meshed
switches in two sweeps (`scratchpad rec0086/shear.json`, `core.json`):
a/b 1, 2 and 4; n 8, 16 and 24 per short side; first cell uniform, h/12.5,
h/25, h/50, h/100 and h/200; nrad derived (2–9) and 6; L/t 1.25 to 16.
OpenFOAM-exact metrics, 2 core layers.

Side shear Δ_max/L set by the length (L = max(1.25 t, Δ_max/shear)):

| target shear | rows | min SJ | where | max non-orth |
|---|---|---|---|---|
| 0.30 | 32 | 0.564 | a/b 1, n 8, h/200 | 77.3° |
| 0.35 | 32 | 0.547 | a/b 2, n 24, h/25 | 75.7° |
| 0.40 | 32 | 0.501 | a/b 2, n 24, h/25 (L/t 1.70) | 74.2° |
| 0.45 | 32 | 0.436 | the same | 72.9° |
| 0.50 | 30 | 0.353 | the same | 71.7° |

- **0.4 does not hold on its own.**  Where 1.25 t sets the length, the
  core block is only 0.25 t long and carries the same change of
  grading.  a/b 1, n 24, h/25 meshes at 0.481 with side shear 0.286.
- The core shear Δ_max/(L − t) separates the rows.  With side ≤ 0.4 and
  core ≤ 1.0, all 188 rows are ≥ 0.501.  Past core 1.0 the worst is
  0.479 (core 1.107) and 0.481 (1.432).
- **Implemented** (Q4 asks design to confirm):
  `L ≥ max(1.25 t, Δ_max/0.4, t + Δ_max/1.0)`, with
  `limits.SWITCH_MAX_CORE_SHEAR = 1.0`.  The core term binds for
  0.25 t < Δ_max < 0.67 t: 5 of the 36 measured cases.  The longest
  switch is unchanged (12 t).
- **Bound table** (`limits.SWITCH_SHEAR_SJ`, min SJ up to each side
  shear with the core term kept, rounded down): 0.1 → 0.577, 0.2 →
  0.550, 0.3 → 0.548, 0.35 → 0.546, 0.4 → 0.501.
- **Non-orthogonality** is the switch's own.  Plain graded H straights
  are at 0°, plain pillowed O-H ones at 44°.  At the steepest gradings
  the switch reaches 70–77° at any length, inside `OUTLINE_NONORTH_MAX`
  (80°) but past the 70° warning.  Nothing predicts or checks it (Q4).
- **The safety net fired** in the core sweep.  At 1.25 t with a/b 2–4,
  h/100, the meshed SJ was 0.039–0.085, and `mesh()` rejected it by
  name.  (The sweep bypassed `validate()` to reach those lengths.)

**Steps 2 and 3, shells around an H core and through a switch (2026-11-05).**
- `sections.h`: `levels`, `patches` and `node_grids` add one level and
  four ring patches per shell.  The first ring starts at the core's
  corners (option B), and every ring's sides take the core's wall
  grading, so lines across a thin shell stay straight.
- `sections.build_face` builds the rings with `build_ring`.  For an H
  core it passes a centre point (for arcs) and the per-side grading.
  `face_grading` covers the rings.  `bind_face` binds an H face's ring i
  from level i − 1.
- The spec's H shell rejection is gone.  `Reducer` stations keep the
  shells (`_with_layers` returned after the H core).
- **Refined step 3 to include `Switch` inside shells.**  Both faces'
  first shell starts at the rectangle's corners (O-H level 1, H level 0),
  so each shell adds four straight ring blocks.  The default H outlet
  copies the shells, and different shells at the two ends are rejected.
  `Transition`'s blend spec carries the H end's shells.  Without this,
  a lagged duct could not switch, and the acceptance item "no fitting
  that takes rectangular ports rejects H" would fail.
- `Wye`'s H check is gone: an H core is a rectangle, so the wye's
  circular-cores rule fires instead.
- Combinations: the same `ring_corners` path as rectangular O-H cores,
  so every outline stack they support works.  Stacks with unequal
  counts per side stay rejected, as on O-H.  No new error was needed.
- Duct taps stay single-layer on H mains, as on O-H mains.

*Corner quality of the shells* (predicted by `section_quality`, then
meshed as a straight; worst over n 8 and 16; `scratchpad
rec0086/shell_quality.json`).  Core half-height 0.05; for rect-in-rect,
a 0.003 wall and 0.03 lagging; for rect-in-circle, a casing of radius
1.6 × half-width.  Each cell gives min SJ / max non-orthogonality:

| stack | a/b | O-H | H uniform | H first cell 0.001 | H 0.00025 |
|---|---|---|---|---|---|
| rect in rect | 1–4 | 0.707 / 43.2° | 0.707 / 43.2° | 0.707 / 44.9° | 0.707 / 45.0° |
| rect in circle | 1 | 0.707 / 39.2° (mesh 24.9°) | 0.707 / 24.9° | 0.707 / 35.7° | 0.707 / 40.7° (37.9°) |
| rect in circle | 2 | 0.447 / 48.2° (37.2°) | 0.447 / 37.2° | 0.447 / 58.9° (50.7°) | 0.447 / 62.3° (59.4°) |
| rect in circle | 4 | 0.243 / 58.3° (48.5°) | 0.243 / 53.6° (48.5°) | 0.243 / 73.8° (64.5°) | 84.1°: rejected |

- Meshed and predicted SJ agree in every row.  Non-orthogonality: the
  prediction is equal or conservative.
- The skewed-ring tiers of 0047 hold.  The 4:1 casing at the steepest
  grading is rejected before GMSH (84.1° > `OUTLINE_NONORTH_MAX`).  At
  first cell 0.001 it warns (73.8° > 70°).
- The SJ is the casing's own corner, as on O-H.  The extra
  non-orthogonality comes from the core's wall grading copied onto the
  casing's arcs.  A proposed follow-up: relax a shape-changing shell's
  outer sides toward uniform.  Not needed for acceptance.
- The kit gains `outline-*-h`, the `2to1-circle-h` / `rrr-h` /
  `rrr-h-graded` stacks, `switch-lagged-oh-h`, `switch-in-circle-h-oh`
  and the two shelled H transitions: all pass.

## Questions for design

**Q1 (2026-11-04, step 1 waits on it): what `nrad` and ring grading do
a duct junction's internal O-H blocks get when its ports are H?**
- An H port has no `nrad` (decision 0036 item 4).  But the junction
  keeps O-H blocks inside (item 5), and so do the switch legs
  embedded at its ports.  Those need an `nrad` and an `mprg`.
- A round tap on an H main has the same gap.  Its branch port is a
  circle, so O-H, and today it takes the main's `nrad` and `mprg`.
- 0085's `Transition` H end had the other end's `nrad`.  A junction
  whose ports are all H has nothing to borrow from.
- Options:
  - **(a) Derived, no new field (proposed).**  `nrad` is the number of
    H cells across one ring thickness t on the H face's smaller side:
    `max(1, round(n_s · (1 − OH_RATIO) / 2))`, with n_s that side's
    count.  That gives 1 at n_s = 4–6, 2 at 8, 3 at 12 and 5 at 24.
    The ring's `mprg` is set so its first cell is the H face's wall
    cell on that side (`progression_for_first_cell`), so near-wall
    resolution doesn't jump across the switch.  The internal spec is
    stored resolved in the fitting, like the duct-tap tunables.
  - **(b) A `Tee(nrad=…, mprg=…)` field, required when the main is H.**
    Explicit, but it's an O-H parameter on an H network, against
    "users don't place switches" (item 5).
  - **(c) (a) as the default, with (b) as an override.**
- (a) or (c) also covers the round branch on an H main.
- I'm working steps 4, 2, 3 and 5 meanwhile; step 1 waits.

**Answer (design, 2026-11-04; the user agreed): (c), with (a) counted on
the real nodes.  Step 1 goes ahead.**
1. **Derived default.**
   - nrad is the number of H cells lying within one ring thickness t of
     the wall on the smaller side.  Count it on the H face's actual node
     positions (graded by `wall_bump` if any); at least 1.
   - The ring's `mprg` comes from `progression_for_first_cell`, so its
     first cell is the H face's wall cell on that side.
   - Warn, with the values, if that `mprg` is outside the limits or the
     predicted ring quality drops below `PREDICTED_SJ_WARN`.
2. **Store resolved.**  The derived nrad and mprg go into the fitting's
   `to_dict`.  `refined(k)` treats them like a spec's (nrad × k,
   mprg^(1/k)), so a series nests; never re-derive per level.
3. **Override:** an optional `Tee(nrad=, mprg=)`.
   - Used only when the junction's own O-H blocks have no O-H port to
     inherit from (an H main), and it then replaces the derived values.
   - `validate()` checks it before GMSH: nrad ≥ 1, mprg > 0, and the
     ring's predicted quality.
   - Plain numbers, documented in API.md (decision 0040's advisor will
     set them).
4. **A round tap on an H main:** the branch port is O-H with its own
   spec.  The derived or overridden values apply only to the junction's
   own blocks and the embedded switch legs on the main side.
5. **Tests:**
   - a uniform and a graded H main: the derived nrad matches a hand
     count, the first cell matches to 1e-9, and `to_dict` and refined
     nest;
   - the override, and its rejection when invalid;
   - a round tap on an H main.

**Q2 (2026-11-04; the switch legs of step 1 wait on it): 0085's switch
length rule doesn't hold on a graded H face.**

*What I found.*
- `L ≥ 1.25 t` (`limits.SWITCH_MIN_LENGTH`) came from 0085's rows with a
  uniform H end; its graded rows were all at L = 3t.
- On a graded H face, the meshed min SJ of a `Switch` falls with its
  length.  The number of core layers doesn't matter.
- `validate()` still predicts 1/√3 from straight-edge corners, so no
  tier fires.  A standalone `Switch` to a graded H outlet can therefore
  mesh at SJ ≈ 0.1 with no warning.  That is on main since 07c38de.
- Mechanism: in the four side blocks the wall edges go from uniform (the
  O-H face's sides) to `Bump`-graded (the H face's) over the length L,
  so the cells shear by about Δ/L.  Here Δ is the largest wall-node
  shift between the two distributions.  Δ can be computed before GMSH
  from the H spec alone.
- The derived ring's own grading is not the cause: mprg 1.0 and 0.39
  mesh the same.

*Measurements* (meshed in GMSH, OpenFOAM-exact metrics, 2 core layers;
`scratchpad rec0086/switch_grading.json`):

| a/b | n | first cell | L/t 1.25 | 1.5 | 2 | 3 | 4 |
|---|---|---|---|---|---|---|---|
| 1, 2 | 8 | uniform | 0.577 | 0.577 | 0.577 | 0.577 | 0.577 |
| 1 | 8 | 0.004 | 0.346 | 0.500 | 0.574 | 0.577 | 0.577 |
| 1 | 8 | 0.002 | 0.267 | 0.425 | 0.541 | 0.576 | 0.577 |
| 1 | 8 | 0.001 | 0.230 | 0.382 | 0.512 | 0.566 | 0.575 |
| 1 | 16 | 0.001 | 0.292 | 0.451 | 0.555 | 0.577 | 0.577 |
| 2 | 8 | 0.004 | 0.174 | 0.313 | 0.475 | 0.567 | 0.577 |
| 2 | 8 | 0.002 | 0.122 | 0.231 | 0.387 | 0.523 | 0.563 |
| 2 | 8 | 0.001 | 0.100 | 0.192 | 0.336 | 0.483 | 0.539 |
| 2 | 16 | 0.001 | 0.128 | 0.241 | 0.400 | 0.530 | 0.567 |

- The duct's half-height is 0.05 and t = 0.02.  Non-orthogonality
  reaches 79–81° at the worst lengths (the max limit is 80°).
- In Δ/L, the measured cases give:
  - Δ/L ≤ 0.4: min SJ ≥ 0.50 everywhere;
  - Δ/L 0.5–0.8: 0.23–0.52;
  - Δ/L > 1: 0.10–0.24.

*Options.*
- **(a) Proposed:** a second length rule, `L ≥ Δ_max / 0.4`.  Δ_max is
  the largest wall-node shift on any side.  Add it to
  `SWITCH_MIN_LENGTH`'s rule as `limits.SWITCH_MAX_SHEAR = 0.4`, pure,
  in `Switch.check`.  The `Transition` H end and the junction legs size
  their switch by the same rule.  A uniform H face keeps 1.25t.
- **(b)** Keep the rule.  Add a predicted SJ that sees the grading (a
  sheared-cell model of the side blocks) and apply the tiers.
- **(c)** (a) plus a meshed-SJ check in `Assembly.mesh()`, as for round
  duct taps.

Either way 0085's Outcome and RESEARCH §7.11 need the correction: the
1.25t rule holds only for a uniform H face.

**Answer (design, 2026-11-05; the user agreed): (c).**
1. **The rule:** `L ≥ max(1.25 t, Δ_max / SWITCH_MAX_SHEAR)`.
   - Applied in `Switch.check`, `Transition`'s H end and the junction
     legs' switch sizing.
   - Δ_max comes from the two wall-node distributions, before GMSH.
   - The message names Δ_max, the shear limit and the minimum length.
2. **Widen the measurements before fixing the constant:** a/b 4, n 24,
   nrad 6, and the steepest first cell expected in practice.  If 0.4
   doesn't hold min SJ ≥ 0.5 over the wider set, pick the constant that
   does and say so.  The full table goes under *Agent notes*.
3. **The prediction:** `validate()` stops reporting 1/√3 for a graded
   switch.  With the rule enforced, it reports the measured bound for
   the shear actually used, named as an empirical bound from the table,
   and the tiers apply to it.
4. **The meshed check:** after meshing, measure the min SJ of the switch
   and of the embedded legs, as for round taps, and apply the same
   tiers.  This is the safety net outside the measured range.
5. **Tests:** at least one graded case that the old rule accepted and
   the new rule rejects (or lengthens), and one at the limit that
   meshes ≥ 0.5.

Design is correcting RESEARCH §7.11 and decision 0036's amendment, and
adding a dated note to 0085's Outcome.

**Q3 (2026-11-05, step 5): β accounts for 65 % of the switch's defect, not
within 20 %; α accounts for 91 %.**  Nothing waits on it.  Step 5 says to
put the numbers here before the junction flow work relies on switches.

*Setup.*  Plain O-H and plain H runs at 0085's counts: a/b 2, 24 × 12
cells, O-H nrad 6, D_h/4 axial cells, 10 D_h long.  Laminar Re 100,
exact inlet, simpleFoam v2406.  Both converged (241 and 179
iterations).  β = Σ u² A / (U² A) and α = Σ u³ A / (U³ A) are face sums
on the planes, the discrete momentum and energy fluxes.

| | O-H | H | H − O-H |
|---|---|---|---|
| β at plane M (6 D_h) | 1.34869 | 1.32527 | −0.02342 |
| β at plane B (8 D_h) | 1.34894 | 1.32515 | −0.02379 |
| α at plane B | 2.04756 | 1.98130 | −0.06626 |
| exact profile on the same faces: β | 1.34470 | 1.33404 | −0.01067 |
| exact profile on the same faces: α | 2.03184 | 2.00802 | −0.02382 |

- 0085's measured defect: K = −0.0730 (−0.118 D_h).
- Momentum balance: K = 2 (β_H − β_OH) = −0.0476, which is **65 %** of
  the defect.
- Mechanical-energy balance: K = α_H − α_OH = −0.0663, which is **91 %**.
- The planes M and B agree to 2 %, so both profiles are developed.
- About 45 % of Δβ (and 36 % of Δα) is already in the exact profile
  summed on the two grids' faces.  That part is the plane quadrature
  (the H face's uniform cells against the O-H ring's graded ones), not a
  difference between the flows.

*Reading.*  The defect is the change between the two discrete developed
profiles.  The energy balance closes it to 9 %, and the switch shows no
loss of its own beyond that.  The momentum balance leaves 35 %.  It
leaves out the wall shear over the switch, which differs from the
developed value while the profile changes, so it is expected to close
less well.  Proposed: take α as the measure (no switch loss measurable
at 0085's counts), and note in RESEARCH §7.11 that the defect is a
discretisation effect, which shrinks with refinement as the two f·Re
converge.  If design wants β to close, the next check is the same pair
at 2× counts.  Both Δβ and the defect should fall roughly as the f·Re
gap (2.4 % here).

**Q4 (2026-11-05): confirm the switch rule's second term, and whether a
switch's non-orthogonality needs a tier.**  Nothing waits on it: (a)
below is implemented, and (b) is a constants change.
- **The term.**  The answer's form, `L ≥ max(1.25 t, Δ_max/SHEAR)`,
  holds min SJ ≥ 0.5 only with SHEAR ≤ 0.28.  That lengthens every
  graded switch by 1.43×, and the regime where 1.25 t binds is barely
  covered (the bad row is at 0.286).
  - **(a) Implemented:** add `t + Δ_max/1.0`, the core block's shear.
    It is ≥ 0.501 over 188 rows, and changes 5 of 36 cases.
  - **(b)** SHEAR = 0.28 alone.
- **Non-orthogonality.**  70–77° at the steepest gradings (h/100–h/200
  at a/b 4) at any length: past the 70° warning, inside the 80° limit.
  - **(a)** Add the meshed non-orthogonality to `mesh()`'s check, on the
    0047 tiers.
  - **(b)** Leave it, and document it in API.md.
  - Proposed: (a), the same safety net as for SJ.

## Outcome

*Done 2026-11-05.  Q3 and Q4 are open for design.  Neither blocks:
Q4's option (a) is implemented, and (b) is a constants change.*

**Files.**
- `sections/h.py`:
  - the pillowed O-H face (`wall_distances`, `pillow_ring`, `pillowed`);
  - shells: `levels`, `patches`, `node_grids`, `section_cells`,
    `side_fractions`.
- `sections/__init__.py` and `oh_gmsh.build_ring`: rings on an H core,
  with a centre point and per-side grading.
- `sections/oh.py`: `inner_radius`, `inner_half_side` (step 4).
- `assembly/duct_tap.py`:
  - `TapTemplate`, from 0060's split (step 0);
  - H ports: the O-H junction inside, switch legs, `_branch_oh`,
    `graded_legs`, `validate`, `cell_count`.
- `assembly/tee.py`: `nrad`/`mprg`, strategies {0, 1}, the meshed check
  on graded H mains.
- `assembly/switch.py`:
  - shells;
  - `wall_shift`, `min_length`, `length_rule`, `shear_sj`;
  - the predicted bound, `meshed_sj_check`.
- `assembly/limits.py`: `SWITCH_MAX_SHEAR`, `SWITCH_MAX_CORE_SHEAR`,
  `SWITCH_SHEAR_SJ`.
- `assembly/fittings.py`:
  - `Reducer` stations keep an H core's shells;
  - `Transition`: shells at an H end, the switch sized by `min_length`,
    the parts' warnings passed on, the meshed check, and an H↔H error
    that points to `Reducer`.
- `assembly/blocks.py` (`bind_face`: H rings) and `assembly/sweep.py`
  (`face_grading`: H rings).
- `assembly/assembler.py`: a per-fitting hint in the meshed check.
- `assembly/intent.py`: refinement of `nrad`/`mprg`.
- `assembly/wye.py`: the H check is dropped (circles only).
- `core/spec.py`: shells on an H core.
- Tests:
  - `test_duct_tap.py` (H mains: derived ring, JSON and refinement,
    override, round tap, legs);
  - `test_switch.py` (shells, shear rule, core term, at the limit,
    safety net, transition sizing);
  - `test_h_layout.py` (shells, wye);
  - `test_signature.py` (Tee's class 1);
  - `test_h_examples.py` (new);
  - the kit: `tee-duct-h-*` ×7, `outline-*-h` ×3, three H shell
    stacks, two shelled switches, two shelled H transitions.
- Docs: API.md (H shells, fittings on H, the switch's rule and
  quality, `Transition`'s H end, duct taps on H mains), GUIDE.md.

**Tests.**
- Full suite: 3157 passed, 15 skipped, 0 failed (2800 / 15 / 0 at 0085's
  end).
- Every existing mesh is unchanged, recorded over 0084's file list
  (1320 tests before, 1486 after):
  - 345 of 349 distinct meshes are identical; 912 recorded meshes are
    bit-identical.
  - The 4 lost meshes are the two kit cases the Q2 rule lengthens:
    `switch-4-h-oh-graded`, now L = 0.16 (it was 0.1 < 0.154), and
    `transition-circle-h2to1-graded`, whose embedded switch takes more
    layers.
  - Messages differ only by `Tee`'s repr, which now shows
    `nrad`/`mprg`.

**Measurements** (tables under *Agent notes* and Q2–Q4):
- **Switch rule:** 450 meshed switches.  The rule
  `L ≥ max(1.25 t, Δ/0.4, t + Δ/1.0)` gives min SJ ≥ 0.501 everywhere.
- **Shells around H:** rect-in-rect shells match O-H (0.707 / 43–45°).
  In circular casings the SJ is the same, and non-orthogonality rises
  with the core's grading (4:1 at h/200: 84°, rejected).
- **Examples** (cells, min SJ; meshed):

| example | O-H | H | H graded |
|---|---|---|---|
| `hvac_supply` | 15360, 0.627 | 6912, 0.577 | 6912, 0.566 (first cell 0.005) |
| `hvac_branched` | 33472, 0.421 | 24704, 0.421 | 24704, 0.421 (0.01) |
| `lagged_duct` | 10488, 0.690 | 7176, 0.690 | 7176, 0.690 (0.004) |

  - `hvac_supply`'s H minimum is its embedded switch.
  - Its terminal is a `Reducer` on H: a `Transition` with H at both
    ends is rejected and points there.
  - `hvac_branched` at first cell 0.005 is rejected: the side branch's
    0.4 is too short for the lengthened legs (0.25 at the main ports,
    0.11 at the branch), and the error names them.
- **Step 5:** 2Δβ explains 65 % of the switch's defect and Δα 91 % (Q3).

**Surprises.**
- 0085's switch rule was wrong on graded H faces (Q2): SJ about 0.1
  with no warning.  It was on main from 07c38de until this task.
- The shear limit alone misses a second, core-block limit (Q4).
- `Transition`'s H-end `validate` dropped its parts' warnings.
- `cell_count()` on an H↔H transition crashed on nrad 0 before
  `validate()` could reject it.

**Exceptions to "no rectangular-port fitting rejects H".**
- `Transition` with H at both ends: covered by `Reducer`.
- Duct taps are single-layer, on H mains as on O-H mains.

**Proposed follow-ups.**
- An mprg limit in `limits.py`.  A derived ring on a steep H face can
  grow by up to 8× per cell (nrad 3, mprg 0.12 at a/b 4, h/200).
- Relax a shape-changing shell's outer sides toward uniform (the casing
  non-orthogonality above).
- Q4(a): the switch's non-orthogonality in `mesh()`'s safety net.

**Disk.**  Recordings (about 145 MB) and the step 5 OpenFOAM runs
(18 MB) are deleted.  Kept in the scratchpad: the JSON tables.
