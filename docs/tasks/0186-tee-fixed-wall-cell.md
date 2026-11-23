# 0186 — The tee benchmark with the wall cell fixed: is its order 1.9 a mesh convergence?

- **Status:** ready (revised 2026-11-23 with 0050's lessons; level 3 moves
  to the volunteer card, task 0168)
- **Decision:** [0012](../decisions/0012-openfoam-validation-cases.md),
  judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md);
  follows task 0162
- **Depends on:** 0050 (its fixed-wall family, the way the levels are built).
- **Blocks:** 0187; 1.0 (decision 0058, 2026-11-21: it is the tee's
  ladder step 1).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0050 found that `validation/junction_loss` doesn't hold its
wall cell fixed across levels.  `assembly()` sets `first_cell` at k = 1
and `refined(k)` splits the wall cell into k.  So y⁺ falls about 30 → 15
→ 10, and the wall function works in a different layer at each level.
The tee's "converges at order 1.9, so the mesh isn't the cause" (0162,
RESEARCH §7.2) mixes mesh refinement with a change of model.  The bend
at the same settings drifted its precursor f by +9 %.  The design
session's answer to 0050 Q2 wrongly cited the tee as already fixing the
wall cell.

**Do.**
1. **A fixed-wall family for the tee** at Div a, q 0.6, SST with Spalding
   (0162's main point):
   - build each level's section directly, as 0050 does: n_arc and
     n_radial scaled, the wall cell fixed at k = 1's height, axial counts
     × k;
   - **the wall cell's centre at y⁺ ≳ 20** (0050 Q4: at y⁺ 8–12, f is
     6–9 % high).  Check the precursor's f within 0049's 5 % at every
     level.  If k = 1's height puts the centre lower, fix it at 50
     viscous units as the bend did, and say so.
   - share 0050's level builder if it generalises.  Otherwise say why in
     *Agent notes*.
   - The level names must differ from 0162's, which stay in
     `results.json` as they are.
   - **The precursor on one process** (0050: decomposed, its residuals
     floor above residualControl).
2. **Record, per level:** the achieved first-cell y⁺ (mean and range on
   the walls), the precursor f against McKeon, ξ_PG and ξ_MGb with both
   pressure methods, and `wall_s` and `cores` (0185).
3. **Levels 1 and 2 here; level 3 goes to volunteers** (the user,
   2026-11-23).
   - **Method, as 0050 learned:** steady simpleFoam first, starting from
     rest, not potentialFoam.  If a level plateaus (residualControl not
     met, K moving with the start), switch to 0050's time-accurate run
     with its convergence stop (Q5's answer): ξ within 10⁻⁴ relative
     over one flow-through.  Use **one method for both levels**: if
     either needs it, both run time-accurately.  `ddtCorr` stays at
     its default; record it.
   - Report levels 1 and 2 with the change and no GCI, as the bend was
     reported.
   - **Level 3** isn't run here.  Task 0168's card offers it, with
     the method settled here, resumable and started from level 2 by
     `mapFields` (0190's machinery).
4. **Report** the change from level 1 to 2 against 0162's `refined(k)`
   levels, and whether the verdict changes.  Gates and verdict rules are
   unchanged: 0162's, judged at level 2, and the report says plainly
   that level 2 isn't the finest planned level.  The GCI comes when a
   volunteer's level 3 is merged.
5. **Also check:** do any other turbulent drivers refine with
   `refined(k)` after setting `first_cell`?  Grep for `first_cell` with
   `refined(`.  List them in the *Outcome* for design, without
   rerunning.
6. Update RESULTS.md, README row, figure, summary and gallery as 0162
   did.  RESEARCH §7.2 is the design session's.

**Accept.**
- Levels 1 and 2 of the fixed-wall family reported, with y⁺, f, the
  method and its convergence at each.
- The answer to "is the order a mesh convergence" stated, with the
  numbers.
- The list from step 5.

**Out of scope.**  Changing `refined(k)`'s behaviour (a library
question for design if step 5 finds it misleads users); level 3 and the
other 19 points of 0162's sweep (both in task 0168's card).

## Agent notes

## Questions for design

## Outcome
