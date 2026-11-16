# 0162 — Validation: loss coefficients of equal-diameter tees and laterals (Štigler et al. 2014)

- **Status:** in progress
- **Decision:** [0042](../decisions/0042-road-to-1-0.md) criterion 4
  ("a junction-flow benchmark (Štigler's T-junction, on equal tees)"),
  milestone 0.7; [0012](../decisions/0012-openfoam-validation-cases.md);
  judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md)
  as amended.  The user, 2026-11-14: "add junction-flow benchmark".
- **Category:** V3 (experiment: Štigler et al. 2014)
- **Features:** `section:circle`, `straight`, `tee`
- **Depends on:** 0049 (the turbulent model setup and post-processing).
  The square equal tee is done (0122, 0127).  Equal laterals below 90°
  are deferred (decisions 0031 and 0043, `EQUAL_LATERAL_ANGLE_MIN`):
  *corrected 2026-11-15*, this line first said they were done.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  It is the 1.0 validation of the junction family, and the
only fitting family without a flow case.  A loss coefficient is what a
user of a tee mesh wants right, and it tests the junction's cells where
the flow turns and separates.

**Reference** (`stigler_and_klas_etal_2014`, in `docs/papers/`, open
access CC-BY; RESEARCH §7.2):
- **Rig:** water; three branches of equal diameter, **50 mm**, drilled
  in a plastic block (so the walls meet **sharp**, as hexmesh's do;
  decision 0045).  Adjacent-branch angle γ = 30°, 45°, 60°, 75°, 90°.
- **Six configurations** per angle (three dividing, three combining,
  their figure 3), **11 flow-rate ratios** each.  Flow rates by magnetic
  flow meters, pressure differences by differential and U-tube
  manometers.
- **Their CFD:** GAMBIT, all hex, about 2.3 M cells, worst skewness
  0.51; realizable k–ε with non-equilibrium wall functions; branches
  25 D long from the junction; velocity inlets, outflow outlets; solved
  unsteady; 21 flow ratios per configuration.
- **Results are figures only** (their figures 5–16): their "geometry"
  coefficients against the flow-rate ratio q, points measured, lines
  computed.
- **Not given in the paper** (read 2026-11-14): the Reynolds number or
  the flow rates' magnitude, and any uncertainty.  Step 1 deals with
  both.

**Where.**  `validation/junction_loss/` (a new case), on
`hexmesh.study.openfoam`; RESEARCH §7.2.

**Do.**
1. **The reference, before any run.**
   - Read the paper fully; record in RESEARCH §7.2 the coefficient
     definitions you compare (their model's coefficients, and Miller's
     loss coefficient, their eq. for $K_{31}$), and the configurations'
     branch labels (a, b, c) against hexmesh's `Tee` ports.
   - Digitise the measured points for the chosen subset (step 2) from
     the figures, with the digitising uncertainty stated, into
     `validation/junction_loss/reference/` (CC-BY: credit in the
     README and the data file).
   - **The Reynolds number:** ask the authors' later papers (search
     Štigler, Klas, Brno, T-junction) for the rig's flow rates.  If
     none gives it, choose Re = 10⁵ on the combined branch (fully
     turbulent, where loss coefficients depend weakly on Re), say so in
     the README, and add a check of that dependence: one point at Re
     5 × 10⁴ and 2 × 10⁵.
   - **Fix the gates before running** (decision 0015): the tolerance on
     each coefficient, set from the digitised scatter and the paper's
     CFD-to-experiment spread at the same points.  Write them in
     `case.json`.
2. **The subset** (the full matrix is 30 configurations × 11 ratios):
   γ = **90°** and **45°** (a tee and a lateral); configurations **Div
   a** and **Com a** (one dividing, one combining); **five** flow-rate
   ratios each, spanning the measured range.  20 points.  Add others
   only if the subset passes and the cost is reported.
3. **Network:** an equal `Tee` (90°) and an equal lateral (45°), each
   branch 25 D from the junction as in their CFD (or longer, if the
   outlet's recirculation reaches the boundary: check).  `walls_by_
   fitting` for the wall patches.  Sharp intersections (the default).
4. **Model:** the 0049 setup that passed (k–ω SST); also realizable
   k–ε with wall functions at one level, for comparison with their CFD.
   Steady `simpleFoam`; if a point won't converge steadily, say so and
   run it transient, as they did.
5. **Pressure:** area-averaged static pressure at stations in each
   branch, extrapolated back to the junction centre along the fully
   developed friction gradient, as the paper's definition requires
   (their section 3; the friction from 0049's validated straight pipe).
6. **Convergence:** three levels with `refined(k)` at one point per
   angle (q ≈ 0.5); Richardson / GCI on the loss coefficient.  The
   other points at the finest level that the budget allows.
7. **Report:** `results.json`, the README's verdict table and graphs
   (coefficient against q, measured points, their CFD line, ours),
   `case.json`'s status.  The gallery's validation page picks it up.
   Cell counts, wall time and peak memory per level.
8. **Resources** (CLAUDE.md): check `pgrep -af pytest` and free memory
   before runs; delete each level's OpenFOAM case once its numbers are
   stored; say in the task if a run needs more than ~1 GB of disk.

**Accept.**
- The gates fixed in `case.json` before the first run (its git history
  shows it).
- 20 points run, each pass or fail reported, whether it passes or not.
- GCI reported at both angles.
- `tests/test_validation_meta.py` passes; a quick check (`-m
  openfoam`), if a coarse point runs in under a few minutes.

**Out of scope.**  Unequal branches (Miller's and the BHRA data: a later
V4 comparison); the Vattenfall thermal-mixing case (0120, LES); rounded
intersections (decision 0045).

## Agent notes

- **2026-11-15, step 1 (in part).**  Read the paper in full.
  - **Branches against `Tee`:** `a` is the inlet port, `b` is `main`,
    `c` is `branch`, and γ is `Tee.angle`.  In both Div a and Com a,
    `a` carries the total flow.
  - **What is compared:** ξ_PG (eq. 15) and ξ_MGb (eq. 16, p_a = 0)
    against q_ca.  Miller's K₃₁ (eq. 1) isn't plotted; it can be
    computed from our runs but has no measured counterpart in this
    paper.
  - **Digitised:** 40 points (both angles, both configurations, both
    coefficients, q = 0.2, 0.4, 0.6, 0.8, 1.0), each with their CFD
    line at the same q.  They are in
    `validation/junction_loss/reference/`, with the method and the
    CC-BY credit in its README.  The reading uncertainty is 0.01 for
    isolated markers, and up to 0.05 where they cluster (q ≤ 0.4).
  - **Their CFD against their experiment**, the largest |F − E| over
    the five q:

    | configuration | coefficient | 90° | 45° |
    |---|---|---|---|
    | Div a | ξ_PG | 0.02 | 0.13 |
    | Div a | ξ_MGb | 0.015 | 0.03 |
    | Com a | ξ_PG | 0.055 | 0.16 |
    | Com a | ξ_MGb | 0.035 | 0.04 |

    At 45°, their CFD's ξ_PG is below the measurement by a third to a
    half at q ≥ 0.6.  The text says so for 30° and 45° (section 6.1).
  - **Reynolds number:** not found.
    - The group's 2011 Engineering Mechanics paper (their ref. 12):
      the proceedings link returns 404.
    - The 2012 Procedia Engineering paper (their ref. 11, doi
      10.1016/j.proeng.2012.07.003): the publisher returns 403 here.
    - The university repository record is behind a bot check.
    - So the fallback in step 1 applies: Re = 10⁵ on the combined
      branch, with the check at 5 × 10⁴ and 2 × 10⁵.
  - **Not done:** RESEARCH §7.2 (waiting on Q1, which changes the
    subset) and `case.json` with its gates.  No run.
- **2026-11-15, step 1 done** (after the answers):
  - **Digitised at 90°:** figures 9, 10, 15 and 16 (Div c, Com c), five
    q each.  The reference is now `reference/stigler_2014.csv`, 60
    values: the 40 at 90° and the 20 at 45°.  For c, q = q_ac and
    p_c = 0.
  - **RESEARCH §7.2:** the coefficient definitions, the reference
    pressure, the branch mapping, what isn't given, and the spread of
    their CFD.
  - **`case.json` written with the gates,** before any run: T per
    configuration and coefficient (Q2), every value to pass, and the
    count per curve reported.
    - Convergence at q = 0.6, in Div a and Com a.  With one angle left,
      I took two configurations in place of "one point per angle".
    - The Re check at Div a, q = 0.6.
  - **Div c's ξ_PG gate is loose: T = 0.30** (their CFD's miss at
    q = 0.4).  Their CFD's curve sits near 0.7 and the measurements near
    1.0.  So a value anywhere between about 0.69 and 1.31 passes there.
    That is what the rule gives, so I applied it unchanged.  The
    results will show which side of the measurement we land on.

- **2026-11-16, first two runs (Div a, q = 0.6), before the full set:**
  - `run.py` (k-ω SST, wall functions at y⁺ ≈ 30, the pressures taken
    to the junction centre along the McKeon friction gradient), not yet
    committed.

    | k | cells | steps | ξ_PG (fit) | ξ_MGb (fit) | drift, last 400 steps | wall time, np | memory peak |
    |---|---|---|---|---|---|---|---|
    | 1 | 65 792 | 4000 | 0.714 (0.660) | 0.455 (0.432) | −0.015, −0.006 | 14:53, 2 | 117 MiB (Docker) |
    | 2 | 526 336 | 6000 | 0.658 (0.604) | 0.456 (0.436) | −0.019, −0.016 | 3:10:52, 3 | 761 MiB (Docker) |

  - Measured: ξ_PG 0.50, ξ_MGb 0.437.  ξ_MGb passes at both levels.
    ξ_PG is 0.16 above the measurement at k = 2, against a gate of
    u + 0.02, and it falls with k.
  - Neither run is converged; the drift hasn't shrunk with the steps.
  - The fitted pressure slopes sit 13–27 % above McKeon's.
  - checkMesh at k = 2: OK, non-orthogonality 49.5, skewness 2.22.
  - At about 3 h a point, the 20 points at k = 2 take about 60 h on this
    machine, and the convergence points at k = 3 (1.78 M cells) about
    10 h each.  I'm asking the user about the budget before the full
    run.

- **2026-11-16, the user's budget:** "yes, 60 h is fine if level 3 is
  close".
  - **"Close":** for both ξ_PG and ξ_MGb at Div a, q = 0.6, the
    extrapolated value lies within twice the gate's tolerance of the
    measurement.  If the levels don't converge monotonically, the k = 3
    value is used instead.
    - The gate's tolerance is u_measured + T.  So for ξ_PG the band is
      0.50 ± 2 × (0.01 + 0.02) = 0.44 to 0.56.  For ξ_MGb it is
      0.437 ± 2 × (0.01 + 0.015) = 0.387 to 0.487.
  - **If close:** the 20 points at k = 2 in the background (about
    60 h), with the cost reported.
  - **If not:** stop, with the numbers under Questions.
  - Before that, following the design session's order:
    - a steady solve whose drift doesn't shrink is step 4's case.  The
      coefficient is the mean over the last iterations (`--window`,
      `--samples`), with the samples' standard deviation as its spread.
      A transient run follows only if the spread exceeds the gate.
    - The local pressure slope per branch, over McKeon's (`profile` in
      the results), shows whether the stations at 10-18 D lie in
      developed flow.

- **2026-11-16, the k = 1 check (8000 steps, a sample every 200):**
  - **The drift is an oscillation, not a creep.**  Period about 1200
    steps, steady in amplitude from step 200 to 8000: ξ_PG between 0.715
    and 0.736, ξ_MGb between 0.455 and 0.468.  It is step 4's case (a
    steady solve that won't settle).  Over the run: ξ_PG 0.7235 ± 0.0064
    and ξ_MGb 0.4600 ± 0.0034 (mean ± standard deviation).  The spread
    is under the gates' T (0.02 and 0.015), so no transient run.
    32:53 at np 3, Docker peak 148 MiB.
  - **The slope profile** (local slope over McKeon's, 3 to 23 D from
    the centre, the run's mean field):

    | s/D | 3 | 6 | 8 | 10 | 12 | 14 | 16 | 18 | 20 | 23 |
    |---|---|---|---|---|---|---|---|---|---|---|
    | a (in) | 1.07 | 1.06 | 1.07 | 1.08 | 1.10 | 1.12 | 1.16 | 1.20 | 1.26 | 1.48 |
    | b (out) | −13.2 | −1.64 | 0.49 | 1.09 | 1.24 | 1.26 | 1.25 | 1.23 | 1.22 | 1.19 |
    | c (out) | −17.3 | −3.84 | −0.08 | 0.97 | 1.22 | 1.27 | 1.26 | 1.24 | 1.22 | 1.23 |

    - b and c recover pressure for about 8 D, then reach a plateau from
      about 12 D at 1.2-1.27 times McKeon's slope.  It doesn't fall to
      1 before the outlets.  So the excess is mostly the model's own
      friction on this mesh (wall functions), not flow still
      redeveloping.  The stations at 10-11 D sit just before the plateau.
    - a is still developing from its uniform inlet: 1.06 near the
      junction, rising to 1.48 near the inlet.  Stations further out
      would be worse there, not better.
    - **Size of the effect:** carrying the plateau's extra 20-27 % back
      over the stations' mean distance (14 D) moves the centre
      pressures by about 0.005 (b), 0.012 (c) and 0.013 (a, at 10 %).
      That changes ξ_PG by about 0.04 at most.  The gap to the
      measurement is 0.16-0.22, so the stations don't explain it.  The
      fit variant (the model's own slopes) gives ξ_PG 0.672 here, still
      far off.
    - **Kept as fixed:** the stations (10-18 D) and the McKeon gradient.
      Moving b and c to 12-20 D would be a choice made after seeing the
      results.  So it is not made.
  - **The convergence run, started 2026-11-16:** Div a, q = 0.6, at k = 1,
    2 and 3.  Each runs 8000 steps, and the coefficients are averaged
    over the last 2400 steps (two periods) from 12 samples.  The same
    method at every level, so k = 2 is rerun.
    - Expected: about 0.5 h, 4 h and 14 h at np 3.  k = 3 runs longer
      than the 10 h first estimated: 8000 steps, against 6000 at k = 2.
    - Disk: about 4-5 GB for k = 3's 13 kept writes (18 GB free).  The
      work folder is deleted once the numbers are stored.

## Questions for design

- **Q1 (2026-11-15, coding session). hexmesh can't mesh the 45° equal
  lateral.**  Step 2's subset needs γ = 45° and step 3 "an equal lateral
  (45°)".  But `Tee` rejects every equal branch below 90°
  (`equal_lateral_angle_below_min`, `limits.EQUAL_LATERAL_ANGLE_MIN` =
  90°, `hexmesh/assembly/cube.py:296`).  The limit's comment gives the
  measurement: equal laterals fold as `nang` rises, and at 45° they fail
  `checkMesh` skewness (6.2) already at `nang` 8.  The "Depends on" line
  ("equal tees and laterals are done") is therefore true for the square
  tee only.  Options:
  - (a) **90° only, four configurations** (my recommendation).  Div a,
    Com a, Div c and Com c at five q each, still 20 points.  Div c and
    Com c (flow into or out of the branch alone) are where their CFD
    and experiment differ most (figures 9, 15), so they test the
    junction's cells more.  The 45° points stay in `reference/` for
    when equal laterals exist.
  - (b) 90°, Div a and Com a only: 10 points.
  - (c) 45° with a reduced branch (r/R ≤ `TEE_MAX_RATIO`).  This isn't
    Štigler's geometry, so it has no reference.  I don't recommend it.

  If (a): I'd digitise figures 9, 10, 15 and 16 at 90°.
- **Q2. Proposed gates**, for `case.json` once Q1 is settled, following
  step 1 ("from the digitised scatter and the paper's CFD-to-experiment
  spread"): at each point, |ours − measured| ≤ u_measured + the largest
  |F − E| of their CFD for that configuration, coefficient and angle
  (the table above).  At 90° this gives about 0.03 (Div a ξ_PG),
  0.025 (Div a ξ_MGb), 0.065 (Com a ξ_PG) and 0.045 (Com a ξ_MGb).
  That is: agree with the experiment as well as their 2.3 M-cell
  k–ε did.  Is a per-point gate right, or a pass count (for example
  4 of 5 per curve)?

**Answers (the design session, 2026-11-15):**
- **Q1: (a).**  90° only, Div a, Com a, Div c and Com c, five q each
  (20 points); digitise figures 9, 10, 15 and 16 at 90°.  The 45°
  points stay in `reference/` for when equal laterals are built.  Step
  2's subset and step 3's lateral are replaced by this.  The design
  error was mine: equal laterals were deferred with the user's yes
  (decision 0031's note of 2026-11-10).
- **Q2: per-point gates, as proposed**: |ours − measured| ≤
  u_measured + the largest |F − E| of their CFD for that configuration,
  coefficient and angle.  **The case passes when every point passes**;
  report the count per curve as well, so a near miss is visible.  It
  reads as "as close to the experiment as their 2.3 M-cell k–ε", which
  is the claim worth making.  Write the gates in `case.json` before the
  first run, as step 1 says.
- **Memory** (the 0050 question applies here too): size the finest
  level so that one run stays under about 6 GB; report its peak.

## Outcome
