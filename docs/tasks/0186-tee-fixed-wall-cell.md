# 0186 — The tee benchmark with the wall cell fixed: is its order 1.9 a mesh convergence?

- **Status:** ready (after 0050's fixed-wall runs: they share the method
  and the machine)
- **Decision:** [0012](../decisions/0012-openfoam-validation-cases.md),
  judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md);
  follows task 0162
- **Depends on:** 0050 (its fixed-wall family, the way the levels are built).
- **Blocks:** none.  Not a 1.0 criterion: 0162 is reported, and the
  correction in RESEARCH §7.2 says what isn't shown.

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
     n_radial scaled, the wall cell fixed at k = 1's height (y⁺ ≈ 30 at
     McKeon's u_τ), axial counts × k;
   - share 0050's level builder if it generalises.  Otherwise say why in
     *Agent notes*.
   - The level names must differ from 0162's, which stay in
     `results.json` as they are.
2. **Record, per level:** the achieved first-cell y⁺ (mean and range on
   the walls), the precursor f against McKeon, ξ_PG and ξ_MGb with both
   pressure methods, and `wall_s` and `cores` (0185).
3. **Run k = 1 and 2 first**; k = 3 only if the machine allows (0162's
   k = 3 took 14 h on 3 processes).  With two levels, report the change
   and no GCI.
4. **Report** the orders, the GCI against 0162's, and whether the
   verdict changes.  Gates and verdict rules are unchanged: 0162's.
5. **Also check:** do any other turbulent drivers refine with
   `refined(k)` after setting `first_cell`?  Grep for `first_cell` with
   `refined(`.  List them in the *Outcome* for design, without
   rerunning.
6. Update RESULTS.md, README row, figure, summary and gallery as 0162
   did.  RESEARCH §7.2 is the design session's.

**Accept.**
- The fixed-wall levels reported, with y⁺ and f at each.
- The answer to "is the order a mesh convergence" stated, with the
  numbers.
- The list from step 5.

**Out of scope.**  Changing `refined(k)`'s behaviour (a library
question for design if step 5 finds it misleads users); the other 19
points of 0162's sweep.

## Agent notes

## Questions for design

## Outcome
