# 0186 — The tee benchmark with the wall cell fixed: is its order 1.9 a mesh convergence?

- **Status:** ready (Q1 answered 2026-11-28, the user: "I agree": option
  A, after a check of the cycle; level 2 time-accurate, about 30–40 h here;
  revised 2026-11-23 with 0050's lessons; level 3 moves to the volunteer
  card, task 0168)
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

- **The wall cell (step 1):** k = 1's height, `WALL_YPLUS` 30 viscous
  units, puts its centre at y⁺ 15, below 0050 Q4's ≳ 20.  So the family
  fixes it at **50 units** (`FIXED_YPLUS`), centre at y⁺ 25, as the bend
  did; both at McKeon's u_τ in the total branch.  Ring 8 cells (growth
  ≤ 1.3); level 1 54 848 cells, level 2 398 656 (0162's refined k = 1, 2:
  65 792, 526 336; unchanged by the refactor).
- **The builder:** `fixed_spec(k)` applies the bend's rule (n_arc and the
  radial cells outside the wall cell × k, axial × k) over the tee's own
  `wall_ring`.  Not shared with the bend: its `spec` is bound to the
  bend's ν and design u_τ, and the rule is two lines over each driver's
  ring search.  `assembly(k, re, family)`; `--family fixed_wall`; levels
  `fixed_*` (steady) and `transient_fixed_*` (time-accurate), so 0162's
  names stay.  0162's gates and GCI read only the refined levels
  (`_family`); `fixed_rows` reports the family's.
- **The precursor:** a periodic pipe R long on the level's section, at
  the total branch's U and Re, with the tee's own schemes, solution
  (plus `pRefCell`) and Spalding wall; one process; f against
  `turbulent_pipe.mckeon` (0049's 5 %).  Scratch check: k = 1 f +1.91 %,
  wall-cell y⁺ 23.5 (max 25.0), converged in 249; k = 2 +2.66 %, y⁺
  23.7, converged in 1 394.
- **The tee's own y⁺** (`wall_yplus`, as OpenFOAM's yPlus with ν_t from
  the wall function), per wall patch and overall, area-weighted.  At
  fixed k = 1 (steady): inlet straight 24.2 (20.7-33.9), tee 22.6
  (4.9-52.8), branch c 18.7, main outlet b 12.6 (2.3-27.9).  The 50 units
  are the total branch's; b carries 0.4 of the flow, so its wall cell
  sits near y⁺ 12, where 0050 Q4 found f 6-9 % high.  Reported, not
  changed: the task fixes the height by the total branch.
- **Steady first (step 3):** `fixed_div_a_q0.6_k1`, simpleFoam from rest,
  0162's settings (8 000 iterations, mean of the last 2 400, 12
  samples), 4 processes, 1 185 s: **plateau**.  U's initial residual
  flat at 5-7e-4 from iteration 800 to 8 000 (residualControl 1e-6);
  ξ_PG 0.6704 ± 0.0013, ξ_MGb 0.4483 ± 0.0003.  So both levels run
  time-accurately; the steady k = 1 is kept as the plateau's record, and
  level 2 isn't run steady.
- **The time-accurate run** (`--time-accurate`, the bend's Q5 method):
  simpleFoam from rest 2 000 iterations, then pimpleFoam from its fields
  (backward, the steady spatial schemes without `bounded`, PIMPLE 2 × 2,
  one non-orthogonal corrector, relaxation 1, Co 1, `ddtCorr` at v2406's
  default, on); SST with Spalding as the steady levels.  Chunks of half a
  flow-through (8.75 s: 25 D at 1 m/s in a, then 25 D at 0.4 m/s in b),
  p written 10 times a flow-through and both coefficients read from
  each; stop when both stay within 1e-4 relative over the last
  flow-through, else at 12.  Resumable from `transient/history.json`.
  The coefficients are the final fields'.
- **Step 5** (`first_cell` with `refined(`): only `turbulent_pipe` among
  the other RAS drivers, and only `lowre_550` (k = 1, 2, 4) refines: a
  wall-resolved cell at y⁺ 1, which splitting keeps in the viscous
  sublayer, so the model doesn't change.  Its wall-function cases run
  one level.  `turbulent_bend` already has its fixed-wall families
  (its `refined` family is kept as the first study).  `rect_duct`,
  `square_bend` and `heated_rod` set `first_cell` but are laminar.
- **Time-accurate level 1** (`transient_fixed_div_a_q0.6_k1`, stored
  with `converged: false`): the steady start (2 000 iterations, not
  converged), then 24 chunks to the 12-flow-through cap (105 s), 44 790
  steps, 1 865 a chunk; **6.1 h** on 4 processes (`wall_s` 21 862),
  13-20 min a chunk.  My estimate before the run (under 1 h) assumed it
  would settle in 2-4 flow-throughs, as the bend did.
- **It doesn't settle: it cycles.**  From the first flow-through on, both
  coefficients swing with a steady amplitude: ξ_PG 0.6503-0.6558 (band
  0.6-0.8 % a flow-through, no trend over 12), ξ_MGb 0.4498-0.4531 (band
  0.55-0.7 %).  The samples (0.875 s apart) peak at 0.377 Hz (2.65 s);
  that may be an alias of a faster cycle.  The 1e-4 stop is two orders
  away and doesn't approach it.
- **Its time mean is stable** (`time_mean`, samples after 2
  flow-throughs): ξ_PG 0.65315 ± 0.0016 (std), from 4 or 6
  flow-throughs 0.65310, 0.65305; halves -3.0e-4 apart.  ξ_MGb 0.45143
  ± 0.0011, halves -2.8e-4.  So 2 flow-throughs of settling and about 2
  of averaging fix the mean to ~3e-4.
- **Against the steady plateau at the same mesh** (`fixed_…_k1`):
  ξ_PG 0.6704 vs 0.6531 (steady +2.6 %); ξ_MGb 0.4483 vs 0.4514 (steady
  -0.7 %).  Unlike the bend, the plateau isn't the time-accurate flow's
  value: the steady solver averages a cycling flow differently.
- **Against 0162's refined k = 1** (wall cell at 30, centre y⁺ 15):
  ξ_PG 0.6718 (fixed steady -0.2 %), ξ_MGb 0.4383 (fixed steady +2.3 %).
- **Gates** (0162's, judged at level 2): level 1 is reported, not gated
  (`fixed_rows`).  For reference: ξ_PG 0.653 against 0.500 ± 0.030 would
  miss, as every SST level does; ξ_MGb 0.451 against 0.437 ± 0.025
  would pass.
- **Figure:** `plots.junction_loss` took every Div a SST level into the
  refined curve; it now takes only the refined steady ones and plots the
  fixed family as its own points (steady plateau, time mean ± std).
- **Stored here** (`results.json`): `fixed_div_a_q0.6_k1`,
  `transient_fixed_div_a_q0.6_k1` (with its ξ history, chunks and time
  mean); 0162's levels unchanged.  Figure and summary regenerated.  The
  run directories are deleted.

## Questions for design

- **Q1 (2026-11-28, coding session).  Level 1's time-accurate run cycles,
  so 0050 Q5's stop (ξ within 1e-4 over a flow-through) can't be met.
  How should the family's levels be run and read?**  Numbers in *Agent
  notes*.  Cost per flow-through: 0.5 h at level 1; level 2 about 7 h
  (7.3× the cells, half the step; an estimate, the level-1 one was off),
  so its 12-flow-through cap would be ~85 h on 4 cores.  Options:
  - **A. Time-accurate, time mean with a stop on the mean** (my
    recommendation): settle 2 flow-throughs, then average p every step
    (`fieldAverage`, no aliasing) and read the coefficients from pMean;
    stop when the running mean changes by under, say, 1e-3 relative over
    the last flow-through (level 1 meets that by ~4 flow-throughs), cap
    at 8.  Level 2: ~4-6 flow-throughs, ~30-40 h on 4 cores.  Level 3 for
    volunteers: roughly 30+ h a flow-through on 4 cores, so 16 cores and
    still days.  The gate reads the time mean.
  - **B. Steady, 0162's way:** the plateau's window mean at both levels
    (level 2 steady ~4-6 h).  Cheap, but at level 1 it sits 2.6 % above
    the time mean of ξ_PG, so it reads a solver artefact into the
    convergence study.
  - **C. Steady for the study, time-accurate level 1 as the bias
    estimate:** B, with the 2.6 % / 0.7 % reported as the steady
    method's uncertainty.
  - In every option, is the cycle physical (separation at the branch
    corner shedding at Re 10⁵) or numerical?  Not tested here.  A faster
    probe (p at the stations every step) would give its true frequency
    and a Strouhal number to compare.
  The task is blocked until this is answered; nothing else in it waits
  on a run.

  **Answer (the design session, 2026-11-28; the user: "I agree").  A,
  after a check of the cycle.**
  1. **First, the cycle, at level 1 (about 2 h):**
     - restart from the stored level 1's last state.  Write p at the
       stations every step, for one flow-through, for the true frequency
       and amplitude (no aliasing) and a Strouhal number on the branch
       diameter and U in a;
     - then the same with Δt halved (Co 0.5), for one flow-through after
       half a flow-through to adjust;
     - **physical** (in the URANS sense) if the frequency and the band
       change by under about 10 %.  Then go on.  **Numerical** if they
       move with Δt: stop and write it here, before level 2;
     - record the Strouhal number and both runs in *Agent notes*.
  2. **The levels:**
     - time-accurate as level 1, with `fieldAverage` of p every step
       from 2 flow-throughs;
     - the coefficients from pMean;
     - the stop: both running means change by under 1e-3 relative over
       the last flow-through, with a cap at 8 flow-throughs;
     - stored with the mean's statistical uncertainty (batch means over
       flow-throughs) beside the GCI, and `converged` read as "the mean
       met the stop".
     - Level 1 is rerun this way only if its stored time mean, taken from
       the sampled p, differs.  Its samples are 0.875 s apart over 10
       flow-throughs, so recompute from the check's every-step p if
       that's simpler.
  3. **Level 2:** the user accepts about 30–40 h on 4 cores here.
     - Resumable per chunk, as now.
     - Measure the first chunk and update the estimate in *Agent notes*.
       If it projects above 60 h, say so before going on.
  4. **The gate** reads the time mean.  The steady levels stay stored as
     the plateau's record, with the bias reported: ξ_PG +2.6 %, ξ_MGb
     −0.7 % at level 1.
  5. **The rule for the cases** (for 0188's hints, and RESEARCH §7.2):
     with SST on separated flow, the answer is the time-accurate mean.
     A steady plateau stands in for it only where a case shows the two
     agree, as the bend did (K 0.2623 against 0.2626).  The tee shows
     they can differ by 2–3 % with no warning from the residuals.
  6. **0168** (level 3 for volunteers) uses this method.  Its card
     states the cost as days on 16 cores, measured from level 2.

## Outcome
