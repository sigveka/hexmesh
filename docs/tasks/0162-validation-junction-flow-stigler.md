# 0162 — Validation: loss coefficients of equal-diameter tees and laterals (Štigler et al. 2014)

- **Status:** done (missed: ξ_MGb passes, ξ_PG misses, grid-converged)
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

- **2026-11-17, k = 2 and the k–ε comparison (Div a, q = 0.6):**
  - The convergence run's driver was stopped twice for low memory
    (Claude Code's background-job reaper, not the run).  `run.py` is now
    split into `prepare_point` and `collect_point` (972d9cb), so a solved
    case can be collected afterwards.  k = 2 was collected that way: the
    solver reached 8000 steps, the piped log ends at 7440, so
    `converged` is unknown.
  - 14 GB free before k = 3; a k = 3 case is about 5 GB.

    | k, model | cells | ξ_PG (fit) | ξ_MGb (fit) | slope / McKeon a, b, c |
    |---|---|---|---|---|
    | 1, SST | 65 792 | 0.724 ± 0.008 (0.672) | 0.461 ± 0.004 | |
    | 2, SST | 526 336 | 0.672 ± 0.010 (0.616) | 0.469 ± 0.008 (0.449) | 1.14, 1.09, 1.30 |
    | 2, realizable k–ε | 526 336 | 0.667 ± 0.00001 (0.575) | 0.472 (0.432) | 1.22, 1.50, 1.45 |

  - **k–ε is steady:** over the last 2400 steps its coefficients move by
    about 10⁻⁵ (SST oscillates by about 0.01).  `converged` is false
    only because the residuals stay above the tolerance.  It agrees with
    SST within SST's spread: the turbulence model doesn't put ξ_PG high.
  - **Fixed method vs fit, checked (the design session's point b):**
    the difference is exactly the excess slope carried back over the
    stations' mean distance (14 D).  At SST k = 2: a's centre pressure
    moves by −0.018, b's by +0.002 and c's by +0.015, so relative to a
    Δp_b = 0.020 and Δp_c = 0.033, and Δξ_PG = −2 (0.4 · 0.020 + 0.6 ·
    0.033) = −0.056, the computed 0.672 − 0.616.  The k = 1 estimate of
    "about 0.04 at most" was low for two reasons.  It took branch a at
    10 %, where the fit over the stations sees 13–14 %.  And c's excess
    grew from about 25 % at k = 1 to 30 % at k = 2.  a counts twice,
    because every pressure is taken relative to it.  With k–ε the slopes
    are 22–50 % above McKeon's, and the difference is 0.092.
  - **What the paper's CFD does** (§3, after eq. 14): the friction
    gradients Δp₁ "were measured before the measurement of the
    T-junction" for the experiment; "in case of numerical solution they
    are evaluated from the numerical solution".  So the paper's CFD
    carries its pressures with the model's own gradient, as our fit
    variant does.  The experiment uses its measured gradient; McKeon
    stands in for that.  §5: branches 25 D from the junction's border,
    velocity inlet and "outflow" outlets, about 2.3 M hex cells (worst
    skewness 0.51), realizable k–ε with non-equilibrium wall functions,
    solved unsteady; no Re given.
  - SST k = 3 started 11:46, alone.

- **2026-11-17, correction: the compared value is the solution's own
  gradient** (the design session's decision, after the note above).
  - Step 5 asks for the coefficients "as the paper's definition
    requires".  The paper's §3: the friction gradients Δp₁ "can be
    obtained either by experimental way or by using some empirical
    formula … They were measured before the measurement of the T-junction
    started.  In case of numerical solution they are evaluated from the
    numerical solution."  The McKeon gradient was the experiment's way
    applied to CFD: a misreading of the definition, not a choice.
  - **Made after seeing results**, and it moves ξ_PG toward the
    measurement.  It is a correction anyway: the definition fixes the
    method, and the paper's own CFD, whose error sets T, used it.  The
    gates, the stations (10-18 D) and the line through them are
    unchanged; the McKeon value stays in results.json beside it.
  - `run.py`: `xi_PG`/`xi_MGb` are now the line-fit values (the earlier
    `*_fit`); `xi_PG_mckeon`/`xi_MGb_mckeon` hold the McKeon ones, with
    their own spread and drift.  `case.json`'s first gate names the
    method.  Results stored before this (k = 1, 2, and the k = 3 run,
    which uses the code frozen at its start) have the old keys and are
    mapped when analysed.

    | Div a, q = 0.6 | ξ_PG own gradient | ξ_PG McKeon | ξ_MGb own gradient | ξ_MGb McKeon |
    |---|---|---|---|---|
    | k = 1, SST | 0.672 | 0.724 | 0.438 | 0.461 |
    | k = 2, SST | 0.616 | 0.672 | 0.449 | 0.469 |
    | k = 2, realizable k–ε | 0.575 | 0.667 | 0.432 | 0.472 |

  - The k = 3 reading (band 0.44-0.56 for ξ_PG, 0.387-0.487 for ξ_MGb)
    is applied to the own-gradient values.

- **2026-11-18, k = 3 (SST, Div a, q = 0.6): not close; stopped.**
  - The run: 1 776 384 cells, 8000 steps, 14:11 at np 3 (11:46 to
    01:57).  Peak memory wasn't logged.  checkMesh OK
    (non-orthogonality 50.3, skewness 2.37).  `converged` false, as at
    k = 1 and 2: the residuals stay above the tolerance while the
    coefficients oscillate within the window.  The case folder was
    deleted by the run; the numbers are in the scratchpad's
    `jl/conv3/results.json` (old keys, mapped below).
  - The three levels, own gradient (the old `*_fit` keys) and McKeon,
    mean over the last 2400 steps ± their standard deviation (that
    spread is for the McKeon values, the only ones the window samples):

    | k | cells | ξ_PG own | ξ_PG McKeon | ξ_MGb own | ξ_MGb McKeon | own slope / McKeon a, b, c |
    |---|---|---|---|---|---|---|
    | 1 | 65 792 | 0.672 | 0.724 ± 0.008 | 0.438 | 0.461 ± 0.004 | |
    | 2 | 526 336 | 0.616 | 0.672 ± 0.010 | 0.449 | 0.469 ± 0.008 | 1.14, 1.09, 1.30 |
    | 3 | 1 776 384 | 0.605 | 0.635 ± 0.005 | 0.459 | 0.469 ± 0.002 | 1.08, 0.99, 1.17 |

  - **Richardson / GCI** (Celik et al. 2008, h ∝ 1/k, so r = 2 and 1.5):
    both coefficients converge monotonically.
    - ξ_PG: observed order 1.90, extrapolated **0.596**, GCI at k = 3
      1.9 % (0.012).
    - ξ_MGb: observed order 1.93, extrapolated **0.468**, GCI at k = 3
      2.3 % (0.011).
  - **The reading:** ξ_MGb's 0.468 is inside its band (0.387-0.487).
    ξ_PG's 0.596 is outside its band (0.44-0.56), 0.096 above the
    measured 0.50.  So "close" fails, and per the user's rule the 20
    points at k = 2 aren't run.  Against the gates at k = 3: ξ_MGb 0.459
    passes (0.022 from 0.437, gate 0.025); ξ_PG 0.605 fails (0.105 from
    0.50, gate 0.03).
  - **What the levels show:** the grid error is now small (GCI about
    0.01) against the gap (about 0.1), so refinement won't close it.
    The own gradients approach McKeon's as k rises (c from 1.30 to 1.17,
    b to 0.99), so the two methods are converging too.  Realizable k–ε
    at k = 2 gave 0.575, 0.04 below SST at the same level.  Their 2.3 M
    cell k–ε gave 0.48.

- **2026-11-18, Q3 part 1: the report.**
  - `validation/junction_loss/`: `results.json` (the four levels, their
    old keys mapped: `xi_*` ← `xi_*_fit`, `xi_*_mckeon` ← `xi_*`, `nang`
    → `n_arc` etc.; `keys_mapped` says so in each level), `RESULTS.md`,
    `README.md`, `figure.png` (the coefficients against h, with the
    measurement, its gate, their CFD, the McKeon variant and k–ε).
    `recheck` and `plots` know the case.
  - **Status `missed`** (decision 0012's note, aebace9): added to
    `case.schema.json` in place of `rejected`; the gallery marks it ⚠ /
    ⚠️; `test_validation_meta` checks that a missed case misses a gate
    and that its RESULTS.md names each miss.  The README's validation
    table and the gallery pages regenerated (`--markdown-only`).
  - **Found while writing it:** ξ_MGb's extrapolated value, 0.468, is
    0.006 outside its gate's band (0.412-0.462).  It passes at k = 3
    (0.459), the level the gate names, and drifts away as h falls.
    RESULTS.md says so.
  - `environment.hexmesh` is 972d9cb for k = 3 and k–ε (the frozen copy
    matches every commit from 972d9cb to 4951278 file for file); k = 1
    and 2 ran from the tree of 2026-11-16, commit not recorded (None).
  - RESEARCH §7.2: left to the design session (its message of
    2026-11-18).
  - Part 2, the transient k–ε run, is next.

- **2026-11-18, Q3 part 2: the transient run, estimated: far over budget.**
  - Set up in `run.py --transient` (4c1698e), as fixed before any run:
    pimpleFoam from rest, realizable k–ε, `nutkWallFunction` (the nearest
    v2406 has to Fluent's non-equilibrium wall functions: the log law with
    the velocity scale C_μ^¼ k^½, ε and G set in the wall cell, no
    pressure-gradient term; both switch to the laminar law below y⁺ ≈ 11,
    and the wall cell is near y⁺ 14 at k = 2), `backward`, `maxCo` 1,
    settle 20 s (three flow-throughs of the slowest branch, b at 0.4 m/s
    over 25 D), then p time-averaged over 12 s by `fieldAverage`, 12
    samples.  A k = 1 smoke run (0.05 s) wrote `pMean` and gave
    coefficients.
  - **Trials at k = 2, np 3** (both deleted):
    - `pFinal` at relTol 0 stalls at a residual of 1.3e-6 for its 1000
      iterations every step: 48 s a step.  Now relTol 0.01.
    - Then about 200 GAMG iterations a step (two correctors, one
      non-orthogonal corrector, so four p solves), about 0.2 s each:
      **41 s a step**.  The step settles near Δt = 0.4-0.5 ms at Co 1.
  - **Estimate:** 32 s simulated is about 70 000 steps, about 800 h.  The
    budget is 16 h.  Even a step ten times cheaper would be 80 h.  Not
    started; see Q4.

- **2026-11-18, Q4: the steady k–ε run with `nutkWallFunction`.**
  `run.py --wall {spalding,nutk}` (1d5902c); level
  `div_a_q0.6_k2_rke_nutk`, Div a, q = 0.6, k = 2 (526 336 cells), np 3,
  8000 iterations, the last 2400 sampled 12 times, as the Spalding run.
  3 h 46 min.  **ξ_PG 0.567** (McKeon 0.650), **ξ_MGb 0.433** (McKeon
  0.468); spreads below 10⁻⁵, so it settles.  Spalding gave 0.575 and
  0.432: the wall treatment's share of ξ_PG is 0.008.  Outside
  0.45–0.51, so our meshes with their model and the nearest wall
  function don't reproduce their CFD's 0.48.  The work directory is
  deleted.
  - `results.json` stamped the level with hexmesh ffbf6cd, the commit
    checked out when the run wrote it, not the code it ran
    (`environment()` is called at the end).  Set by hand to 1d5902c:
    `hexmesh/` is the same at 7972972 and 1d5902c, and the merge of
    0173 came after meshing.  Follow-up below.

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

- **Q3 (2026-11-18, coding session). ξ_PG converges to 0.60, 0.1 above
  the measurement; the "close" check fails.**  Numbers in *Agent notes*,
  2026-11-18.  Grid-converged (GCI 0.012) at Div a, q = 0.6: ξ_PG 0.596,
  measured 0.50 ± 0.01, their CFD 0.48; ξ_MGb 0.468, measured 0.437,
  inside its band.  The user's rule says stop here.  Options:
  - (a) **Report it as a fail, with the convergence study, and run no
    more points** (my recommendation).  The case's verdict is "fail" at
    Div a ξ_PG, with the grid error shown to be a tenth of the gap.
    That is a finding about the setup (steady SST and wall functions,
    the uniform inlet at 25 D, sharp edges), not about the mesh's
    convergence.  It costs nothing further.
  - (b) **Look for the cause first, at k = 2 (about 4 h a run):** a
    developed inlet profile in place of the uniform one (a's slope still
    rises toward the inlet, 1.08 to 1.4); a transient run as theirs was;
    or low-Re wall treatment (y⁺ ≈ 1, which needs a new mesh grading
    and more cells).  Any of these chosen after seeing the result needs
    the gates left as they are.
  - (c) Run the 20 points at k = 2 anyway (about 80 h at the rate
    measured), to show the curves' shape against q.  It would report
    ξ_MGb passes and ξ_PG fails across q, which (a) already predicts
    for this point.
  Which, and does the user's 60 h budget still stand for (b) or (c)?

**Answer to Q3 (the design session, 2026-11-18; the user chose "Report +
one run like theirs").**
1. **Report now.**  The single point is the case's result for 1.0.
   - ξ_MGb passes; ξ_PG misses at Div a, q = 0.6.
   - The convergence study (k = 1, 2, 3; Richardson and GCI) goes in,
     with both methods (own gradient, the compared value, and McKeon
     beside it).
   - k–ε at k = 2 goes in as the comparison, with their CFD's 0.48 and
     the measured 0.50.
   - The README's verdict table says plainly: grid-converged, so the gap
     is the model and setup, not the mesh's resolution.
   - `case.json`'s status: reported, with the miss.
   - The 20 points and Div c / Com a / Com c are not run; say so, with
     the cost (about 80 h at k = 2), as the way to extend it.
   - Move the numbers into RESEARCH §7.2 (or leave them for the design
     session, saying so).
2. **One more run, set up as their CFD was, reported beside it (not in
   place of it):**
   - realizable k–ε, **transient** (`pimpleFoam`), at k = 2, Div a,
     q = 0.6;
   - their inlet: uniform, 25 D upstream, which ours already is.  This
     corrects the "developed inlet" in the user's option text: copy
     their setup, don't improve on it;
   - their wall treatment as near as OpenFOAM v2406 has it.  Fluent's
     non-equilibrium wall functions have no exact match, so say which
     function is used and why;
   - coefficients time-averaged over a window you fix before the run,
     with its length and spread;
   - the same stations and the own-gradient method.
   Budget about 8–12 h; give the estimate before starting, and stop and
   say so if it runs past 16 h.
   - **Reading, fixed now:** within ±0.03 of their 0.48 (0.45–0.51)
     means the meshes reproduce a published CFD of this geometry.  The
     gap to the experiment is then the RANS model's, as it is for theirs
     at 45°.  Outside it, report the value and the difference.
   - Either way the gates and the verdict above don't change.
3. **0168** (the volunteer card for the 20 points) stays *ready*, but
   its trigger "after 0162's level-3 point" now reads: only if the user
   asks for the 20 points.
4. Order: the run can go beside the 0.8.0 release prep (memory: one CFD
   job at a time, as before).  Report (1) first.


- **Q4 (2026-11-18, coding session). The transient run as set up costs
  about 800 h, against a 16 h budget.**  Numbers in *Agent notes*.  Its
  purpose was to see whether our meshes reproduce their CFD's 0.48.
  Options:
  - (a) **Don't run it; report the steady k–ε as the comparison**
    (my recommendation).  Our steady k–ε at k = 2 settles: its samples
    agree to 10⁻⁵ over 2400 iterations.  A RANS flow that settles in a
    steady solve has that steady state as the transient solve's limit,
    so a transient run from rest would end where the steady one did
    (0.575), unless the flow has a RANS-scale unsteadiness that the
    steady solver damps.  Add one steady k–ε run at k = 2 with the
    transient set-up's wall function (`nutkWallFunction`), about 4 h,
    to separate the wall treatment from the solver.  Then the reading
    0.45–0.51 applies to that run.
  - (b) Transient from the steady k–ε solution, with large steps (PIMPLE
    at Co 10, three outer correctors) for about two flow-throughs of b
    (15 s), to check that it stays steady: about 3300 steps at about
    120 s, so about 100 h.
  - (c) Transient at k = 1, as specified: 8 times fewer cells (about 5 s
    a step) and twice the step (about 35 000 steps): about 50 h.
  Which, and the budget?


**Answer to Q4 (the design session, 2026-11-18; the user chose "Steady
k-ε, other wall fn").**  (a), as you recommend:
- **One steady realizable k–ε run at k = 2, Div a, q = 0.6, with
  `nutkWallFunction`** in place of Spalding.  Everything else is as the
  k = 2 k–ε run: the stations, the own gradient, the same window.
  About 4 h; stop and say so past 8 h.
- **Reading, unchanged:** 0.45–0.51 means the meshes reproduce their
  CFD.  Report the value beside 0.575 (Spalding) either way.  The
  difference between the two is the wall treatment's share.
- **The transient run is reported as not run**, in RESULTS.md's *Not
  run*.  Give its measured cost (41 s a step, Δt 0.4–0.5 ms at Co 1,
  about 70 000 steps, about 800 h at k = 2) and the reason it was
  dropped: the steady k–ε solve settles, so a transient from rest would
  most likely end there.
- Record the pFinal relTol stall (relTol 0 stalls at 1.3e-6) in
  `docs/integrations/openfoam.md` if it isn't there.
- Gates and verdict unchanged.

## Outcome

**Missed** (decision 0012's note): at Div a, q = 0.6, ξ_MGb passes its
gate (0.459 against 0.437 ± 0.025) and ξ_PG misses it (0.605 against
0.500 ± 0.030).  The mesh is not the cause: k = 1, 2, 3 converge at
order 1.9, extrapolated 0.596, GCI 0.012.

- **Files:** `validation/junction_loss/` (run.py, case.json,
  results.json with five levels, RESULTS.md, README.md, figure.png,
  reference/), `validation/tools/plots.py` (`junction_loss`),
  `validation/tools/recheck.py`; the "missed" status in
  `validation/case.schema.json`, the gallery and
  `tests/test_validation_meta.py`; `docs/integrations/openfoam.md`
  (fieldAverage on v2406, `pFinal` relTol 0 stall).
- **Comparisons, not gated, at k = 2:** realizable k–ε 0.575 with
  Spalding's wall function and 0.567 with `nutkWallFunction`.  Neither
  the model (−0.04 from SST) nor the wall function (−0.008) closes the
  gap to their CFD's 0.48.
- **Not run:** the 20 points, the Com a convergence point and the
  Reynolds check (about 80 h at k = 2; task 0168 on hold), and the
  transient run (about 800 h).
- **Run cost:** k = 1 33 min, k = 2 about 4 h, k = 3 14 h 11 min, each
  k–ε run about 4 h, on 3 processes.
- **Follow-ups:**
  1. `validation/tools/results.py`'s `environment()` is read when a
     driver writes `results.json`, at the end of a long run, so a commit
     made meanwhile is stamped as the run's.  Take it at the start of
     the run (or stamp the start commit beside it).
  2. If ξ_PG matters again: their mesh size (2.3 M cells, k = 3 is
     1.8 M), or a transient run at k = 1 (option (c) of Q4, about 50 h),
     as a volunteer card.
