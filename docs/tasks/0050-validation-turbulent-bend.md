# 0050 — Validation: turbulent flow in a 90° bend (PTB LDA; Sudo et al. 1998 the ideal)

- **Status:** ready (Q6 answered, 2026-11-22: local time-stepping, checked at levels 1 and 2 first; two levels and a volunteer card as the fallback; *Questions for design*)
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md) (its "Dean bend" case, turbulent); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) as amended
- **Category:** V3 (experiment: Straka et al. 2020, PTB, via Ekat et al. 2023)
- **Features:** `section:circle`, `straight`, `bend`
- **Depends on:** 0049 (model setup, wall treatment, post-processing).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The first turbulent case with a fitting, and the basis for
turbulent loss-coefficient studies (decision 0025) and for installation
effects upstream of meters (decision 0021's showcase).  A bend is where
hexmesh's exact walls and conformal sweeps should show.

**Reference (2026-11-15, replaces Sudo; see Q1's answer).**
[`ekat_and_weissenbrunner_etal_2023`] (OpenFOAM Journal, open access,
CC BY-SA 4.0), reporting the LDA measurements of
[`straka_and_koglin_etal_2020`] (CC BY 4.0) at PTB Berlin:
- water at 30 °C, D = 0.1 m, W_vol = 0.40035 m/s, **Re = 50 000**;
- bend curvature radius r_k = **1.425 D**, 90°;
- fully developed inflow: about 95 D of straight smooth pipe upstream;
- axial velocity w and the horizontal component u at **six planes**,
  2.43, 5.56, 10.7, 15.69, 20.82 and 30.82 D after the bend, 303
  points per plane, expanded uncertainty 0.5 % (k = 2);
- the paper's domain: 7 D upstream, 42 D downstream; structured hex
  O-grid meshes, 0.6–20 M cells (its Table 2), RANS on half-domains
  with a symmetry plane;
- the published profiles: w/W_vol on the horizontal line y = 0 at the
  six planes (Fig. 3, RANS models against LDA), and the L2 error per
  plane by model.  **No tables**: digitise Fig. 3's LDA points, state
  the digitising uncertainty, and keep the points in
  `validation/turbulent_bend/reference/` with the figure and page.
  Their k-ω SST and SA results on the same figure show what RANS
  achieves here; their RANS sits near 5–7 % L2 error to 20 D.
- Record all of this in RESEARCH §7 with the citations.

**The ideal reference, kept** (the user, 2026-11-15):
[`sudo_and_sumida_etal_1998`]: smooth circular 90°
bend, Re = 6 × 10⁴, long straight pipes upstream and downstream;
rotating inclined hot-wire measurements of the mean velocity components
and Reynolds stresses at several stations through and after the bend.
If the user supplies the PDF, it becomes a second case on the same
network, and the steps below apply to it as well.
- Check in the paper: the curvature ratio (reported as 4.0: confirm
  whether it is R_c / D or R_c / a), the station positions, the inlet
  condition, and the tabulated or digitisable data.  Record them in
  RESEARCH §7 with the citation.  Digitise from figures only if no
  tables exist; state the digitising uncertainty.

**Where.**  `validation/turbulent_bend/`, on `hexmesh.study.openfoam`;
RESEARCH §7.

**Do.**
1. **Network:** upstream straight long enough for the measured inlet
   state (match the paper; if the inlet is fully developed, use 0049's
   periodic solution as a mapped inlet profile, or a long upstream run),
   the 90° `Bend` at the paper's curvature, and a downstream straight
   past the last station.  `toward=` for the bend; `walls_by_fitting` to
   split the wall patches.
2. **Model:** the 0049 setup that passed (low-Re SST, and wall
   functions if both passed).
3. **Convergence:** three levels with `refined(k)`; Richardson / GCI on
   the bend pressure-loss coefficient and on the streamwise velocity at
   two stations.
4. **Compare:** streamwise velocity profiles in the bend plane and
   normal to it at each measured station; secondary-flow strength where
   the paper gives it.  Also the bend loss coefficient K (from wall
   pressure, minus straight-pipe friction from 0049) against a
   handbook or correlation value, cited.

5. **Volunteer-ready driver** (the user, 2026-11-18: every case that
   can use more hardware is a volunteer case).  The card itself is task
   [0169](0169-volunteer-card-turbulent-bend.md).  Here:
   - give the driver `prepare`/`run`/`collect` hooks from the start
     (0169 step 1);
   - size levels 1 and 2 for this machine (under about 6 GB) and run
     them here.  Their measurements are what 0169's card scales from;
   - leave the finest level to the card if it doesn't fit here, and
     say so under *Agent notes*.

**Accept.**
- Gates, set now:
  - streamwise mean velocity at the measured stations: RMS difference
    over each profile **within 10 % of U_b**, at the finest level (RANS
    is known to mispredict separation and secondary-flow strength in
    bends; the literature's RANS comparisons sit in this range: record
    any you find);
  - the location of the peak streamwise velocity (shift to the outer
    wall) matches the measured side at every station.
- K reported with GCI against the cited value; no gate (sources
  differ).
- Mesh: report min SICN, min corner SJ and max non-orthogonality.
- `RESULTS.md`, *Outcome* table for RESEARCH.  A failed gate goes to
  *Questions for design* with the numbers; don't tune.

**Out of scope.**  Unsteady effects (swirl switching), heat transfer,
tees (the Štigler tee, RESEARCH §7.2, is a later case).

## Agent notes

- **Reference data (2026-11-19):** Fig. 3 of Ekat et al. is vector
  graphics, so the LDA curves were read from the PDF's drawing paths,
  not digitised by eye: 19 points per plane, extraction error under
  1e-3 (`validation/turbulent_bend/reference/README.md`).  Their SST
  curve the same way, with its RMS against the LDA per plane.
- **Full domain**, not their half: hexmesh's O-H section has no
  symmetry plane to offer, and the full domain is under 6 GB at k = 3.
  No asymmetry appeared (they report it for SST on full domains).
- **Wall treatment:** task 0049's wall-function set (Spalding), with
  the k = 1 wall cell at y⁺ 50; wall-resolved SST at Re 5 × 10⁴ needs
  y⁺ ≈ 1 and was not sized for this machine.  `refined(k)` keeps the
  ring's grading nested, so the wall cell shrinks as 1/k: y⁺ 23, 11.6,
  7.8 (cell centres).  This is what Q2 is about.
- **Inlet:** the precursor (task 0049's periodic slab, same section and
  k) mapped face by face; the mapped bulk velocity equals U_b to 1e-9.
- **`walls_by_fitting`** (step 1) not used: K comes from the section-mean
  pressure in slabs, which needs no wall split.
- **Step 4, "normal to the bend plane":** the paper publishes only the
  horizontal line, so there is nothing to compare there.
- **Levels (step 5):** k = 1, 2, 3 here (59 k, 474 k, 1.6 M cells; k = 3
  took 34 min + 1 h 50 min on 4 processes).  k = 4 (3.8 M) is for the
  volunteer card, 0169.  The driver has the card hooks
  (`check_level`, `prepare`, `run`, `collect`, `recompute`).
- **Bugs fixed on the way:** `axial_grading` is the ratio between
  neighbouring cells, not the end-to-end growth (4.0 gave 4¹⁹; now
  4^(1/19)); `potentialFoam -writep` needs a `Phi` solver and a
  `div(div(phi,U))` scheme; the precursor's first-layer test needed a
  tolerance of a quarter cell, not 1e-9 m.
- **Timing (task 0185):** these levels ran before 0185 landed; they
  record `precursor.wall_s` and `bend_wall_s` (renamed from the
  driver's `wall_s`, which timed the bend's solve alone), not a whole
  level's `wall_s`.
- **For RESEARCH (design session):** the measurements are in
  `validation/turbulent_bend/RESULTS.md`; nothing written to RESEARCH here.

**The transient run (Q3 step 3, Q4; 2026-11-21).**  `run.py --transient`:
- **Start:** the precursor as before, then the steady bend from rest for
  2 000 iterations (`STEADY_START`), and pimpleFoam from its last state.
  Q4 says "from fixed_k2's state"; that case wasn't kept, and from rest
  the plateau sets in by about step 400, so 2 000 steps reach the same
  state.  This is a deviation, noted here.
- **pimpleFoam:** backward in time; linearUpwind as the steady runs
  (without `bounded`); PIMPLE 2 outer × 2 pressure correctors, one
  non-orthogonal; relaxation 1; Courant 1 (adjustTimeStep).
- **Monitored every step:** K from the volume-mean p in cell zones on
  `results`' own slabs (`k_slabs`, now shared), and U at the 114 LDA
  points (probes, cell values).  U and p are averaged (`fieldAverage`)
  from 1 flow-through (12.8 s).
- **Stop:** in chunks of half a flow-through, when K's running mean and
  each plane's RMS (of the probes' time mean against the LDA) change by
  less than 1 % between the window's first three quarters and all of
  it, with at least one flow-through averaged; else at 12 flow-throughs
  or 12 h.
- **Gates:** on `UMean`/`pMean` through the same `results` as the
  steady levels.
- **Reported:** K's mean, its range, std and the spectrum's strongest
  peak (frequency, Strouhal number, power over the median; none when K
  is flat), cost per chunk and per flow-through.
- **Check at level 1** (59 200 cells, 4 processes, 2 flow-throughs;
  scratch, not stored):
  - the transient stays steady: K 0.2201 throughout (steady 0.222),
    change 9e-5 over the last quarter;
  - time-mean RMS 0.083, 0.080, 0.061, 0.072, 0.096, 0.102;
  - Co 1.0, 381 steps (dt 0.017 s) and 1.1-1.9 min per half
    flow-through: 0.05 h per flow-through;
  - the average carries across the chunk restarts (iterations 382 at
    the start of the third chunk).
- **Cost estimate, level 2** (7.6× the cells, the step about half):
  about 15× level 1, so 0.6-1 h per flow-through.  With the precursor
  and the steady start (about 1 h), a run that settles after 2-4
  flow-throughs takes 3-5 h; the 12-flow-through cap, about 8-12 h.
  **Level 3** (3.3× level 2, the step ÷1.5): about 3-5 h per
  flow-through, so roughly 15-25 h.  Measured numbers come with the
  level-2 run, before levels 1 and 3 (Q4).

**The level-2 transient (2026-11-21; stored as `transient_fixed_k2`).**
- **The steady start:** the precursor, f +0.77 % and y⁺ 23.3 as before,
  converged on one process in 76 s.  Then the steady bend from rest,
  2 000 steps, K 0.246; 0.49 h.
- **pimpleFoam:** 4 chunks, 25.6 s (2 flow-throughs), 4 746 steps at
  Co 1.0.  K after the start: 0.243 at 1 s, 0.253 at 2 s, 0.260 at
  6.4 s, 0.2623 at 12.8 s, then flat.
- **Settled to a steady state:** over the averaged flow-through K is
  0.262330 ± 7.8e-7 (range 0.262329-0.262333), with no spectrum to
  read.  Every running mean changed by under 1e-4 over the last
  quarter.
- **The time-mean gates (level 2) all pass:**

  | plane | RMS | peak x/R | the LDA's |
  |---|---|---|---|
  | 2.43 D | 0.0727 | -0.748 | -0.828 |
  | 5.56 D | 0.0738 | -0.828 | -0.828 |
  | 10.7 D | 0.0598 | -0.309 | -0.657 |
  | 15.69 D | 0.0705 | -0.439 | -0.555 |
  | 20.82 D | 0.0906 | -0.439 | -0.439 |
  | 30.82 D | 0.0958 | -0.439 | -0.163 |

  Every peak is on the outer side (x/R < 0).
- **K 0.2623 against Ito's 0.2626 (-0.1 %).**  Not gated.  The
  closeness is one level's number, not yet a converged one.
- **The reading** (fixed before the run, Q4): a transient that settles
  to steady means the plateau was the steady solver's.  So SIMPLE
  stalls on this mesh; the flow is steady.  The plateau's K values
  (0.227-0.271) were the stalled solver's, not the flow's.
- **Cost, measured:** the chunks took 112, 56, 33 and 30 min for the
  same ~1 190 steps each, so the solver's work falls as the transient
  dies out.  That is 1.92 h per flow-through over the run and about
  1.0 h once settled; 4.3 h in all with the start.

**SIMPLEC (Q5's test; 2026-11-21).**  A family of its own,
`fixed_wall_simplec` (levels `simplec_k<k>`), so `fixed_k2`'s SIMPLE
record stays.  The bend's dictionaries:
- the transient's spatial schemes (no `bounded`), steady in time;
- `consistent yes`, p unrelaxed, U, k and ω at 0.9;
- the p solve's relTol 0.005 (from 0.05);
- residualControl as task 0049's.
The precursor is unchanged.

**Check at level 1** (scratch, not stored): converged in 374 steps;
K 0.2269, f +0.55 %, RMS 0.082, 0.077, 0.060, 0.070, 0.089, 0.094.
So level 1 has three converged K values from three algorithms:

| algorithm | K at level 1 |
|---|---|
| SIMPLE (bounded schemes) | 0.222 |
| pimpleFoam | 0.2201 |
| SIMPLEC | 0.2269 |

That is a 3 % spread.  The likely cause, not verified, is that
OpenFOAM's face-flux (Rhie-Chow) interpolation depends on the
relaxation factor and the time step, which counts most on a coarse
mesh.  Level 2 will show whether the spread shrinks with refinement.
Q5's single method for all levels keeps the spread out of the GCI.

**Q5's test at level 2 (`simplec_k2`, stored, `converged: false`):**
- 6 000 steps from rest on 4 processes, 1.63 h; residualControl not met.
- K 0.2708, +3.2 % from the transient's 0.26233.
- f +0.77 %; RMS 0.074, 0.074, 0.060, 0.071, 0.090, 0.095, every peak
  on the outer side.
So SIMPLEC stalls too, and it fails both of Q5's conditions.  Q5's
step 2 follows: every level `--transient` with the convergence stop.

**Q5's convergence stop (`--transient`, now the default stop):**
- After each half flow-through, over the last flow-through, K must stay
  within 1e-4 relative and every LDA point's w within 0.001 U_b
  (`steadiness`).
- The gates read the final fields; the time mean is kept beside them.
- The window-stopped level-2 run is kept as `transient_window_fixed_k2`.
- **Check at level 1** (scratch): converged at 2 flow-throughs, K band
  2.2e-6, w band 8.8e-4; K 0.2201; RMS 0.083, 0.080, 0.061, 0.072,
  0.096, 0.102; 0.05 h per flow-through.  At 1.5 flow-throughs the
  bands were 1.7e-3 and 1.4e-2: the second flow-through is needed.

**Levels 1-3 time-accurate with the convergence stop (2026-11-21/22).**

| level | stopped at | K | last flow-through: K band, w band | wall time |
|---|---|---|---|---|
| 1 (`transient_fixed_k1`) | 2.0 flow-throughs | 0.22013 | 2.2e-6, 8.8e-4 | 0.12 h |
| 2 (`transient_fixed_k2`) | 2.5 flow-throughs | 0.26233 | 1.3e-7, 2.0e-6 | 5.34 h |
| 3 | stopped by the coding session, the user's OK | — | — | 3.8 h used |

- Level 2 reproduces the window-stopped run's K to five digits, and
  its gates pass again: RMS 0.073, 0.074, 0.060, 0.071, 0.091, 0.096,
  every peak outer.
- **Level 3 is far too slow time-accurately:**
  - the precursor and the steady start finished at 06:29;
  - pimpleFoam then ran 135 steps in 2.1 h, about 56 s per step, to
    0.36 s of the first 6.4 s chunk;
  - the step was 0.0026 s at Co 1, so 2 flow-throughs are about
    9 800 steps;
  - the final p solve (tolerance 1e-7, relTol 0) took up to 188 GAMG
    iterations.
  Even with level 2's speed-up after the start (about 3.7×), that is
  roughly 40-150 h; the 36 h cap would have stopped it at about one
  flow-through, not converged.  My estimate (20-25 h) scaled the cost
  per step with the cells (3.3×); it grew about 10×.

**Q6's check at level 1: localEuler (`--transient --lts`; stored as
`lts_fixed_k1`; 2026-11-22).**
- **Set-up:** the transient's schemes with `ddtSchemes localEuler`;
  PIMPLE as the transient, plus maxCo 5, rDeltaTSmoothingCoeff 0.02,
  rDeltaTDampingCoeff 1, maxDeltaT 1.  Chunks of 500 iterations; the
  stop over the last 1 000.  ddtCorr isn't set, so OpenFOAM's default
  applies: on.  The same holds for the time-accurate runs and SIMPLEC.
- **Result:** converged after 2 000 iterations (K band 2.2e-6, w band
  5.9e-5), but K is **0.2257, +2.5 % from the time-accurate 0.22013**,
  against the 0.1 % allowed.  It fails Q6's check at level 1, so level 2
  wasn't run.  RMS 0.084, 0.081, 0.063, 0.072, 0.093, 0.099.
- **Not cheaper either:** 30 min for 2 000 iterations, against 1 535
  time-accurate steps in 6 min at the same level.  Each iteration solves
  p to 1e-7 like a time step.
- **Level 1, four converged algorithms, four K values:**

  | algorithm | K | from 0.22013 |
  |---|---|---|
  | pimpleFoam, time-accurate (Co 1) | 0.22013 | — |
  | SIMPLE (bounded schemes) | 0.222 | +0.9 % |
  | SIMPLEC | 0.2269 | +3.1 % |
  | pimpleFoam, localEuler (Co 5) | 0.2257 | +2.5 % |

  The spread follows the effective step: largest for SIMPLEC (no p
  relaxation) and localEuler (large local steps), smallest for small
  time steps.  That is what ddtCorr/Rhie-Chow step dependence would
  give; it isn't tested with ddtCorr off.

## Questions for design

- **Q1 (2026-11-15, coding session). The reference isn't available
  here.**  `docs/papers/` has no Sudo et al. 1998 (only its BibTeX entry,
  `sudo_and_sumida_etal_1998`).  The paper is paywalled (Springer, doi
  10.1007/s003480050206); a web search found no open copy from the
  publisher or the authors, and no tabulated data or supplementary
  material.  (A full text appears on a university library proxy; I
  didn't use it.)  Without it, step "Check in the paper" (curvature
  ratio, stations, inlet condition, the profiles to compare) can't be
  done, and nothing else in the task can be judged.  Options:
  (a) the user adds the PDF to `docs/papers/` (a library copy);
  (b) a different, open dataset for a turbulent 90° bend.  Candidates
  to check: the swirl-switching DNS/LES studies that compare with Sudo
  (e.g. Hufnagel et al., arXiv 1710.08357, whose data may be
  published), or Kalpakli Vester's PIV;
  (c) take Sudo's profiles as other papers reproduce them (digitised
  from a citing paper's figure, with that uncertainty stated).
  Nothing is built or run; the machine's memory limits (three suites
  stopped this week) also matter for a three-level 3-D RANS study, so
  the finest level's size should be agreed with the case.

  **Answer (the design session, 2026-11-15; the user chose (b) and asked
  that Sudo be kept as the ideal case):**  the PTB bend, now under
  *Reference*.  Searched: Hufnagel et al. 2018 (DNS, Re 11 700,
  R/R_c 0.3) has no data statement or repository; Kalpakli Vester's
  PIV papers have none either; the Mendeley set 10.17632/t9s9m2zw9y
  (Ching, Jain, Ewing 2019) holds movies only, under CC BY-NC.  The
  PTB case is open, uses OpenFOAM and structured hex O-grids, has a
  fully developed inflow and six planes to 31 D, and states its
  measurement uncertainty.  Its cost is that the data are in figures,
  not tables, so digitise as *Reference* says.
  - **Network:** 7 D upstream with 0049's fully developed profile
    mapped in at Re 50 000 (or a longer upstream run), the `Bend` at
    r_k = 1.425 D, 42 D downstream.
  - **Gates unchanged:** the RMS of w along y = 0 within 10 % of
    W_vol at each of the six planes; the peak on the measured side at
    each plane.  Report also each plane's RMS beside theirs for the
    same model, read from Fig. 3, without a gate.
  - **Memory:** full domain or the half with a symmetry plane, as they
    did; size the finest level so a run stays under about 6 GB, and
    report its peak.  Their half-domain RANS meshes are 0.6–4.2 M
    cells.
  - **Not compared:** the bend loss coefficient against this paper (it
    gives none); K is still reported with GCI against a cited
    correlation, without a gate.

- **Q2 (2026-11-20, coding session). The gates pass at k = 3, but the
  three levels don't converge.**
  - **Gates at k = 3 (1.6 M cells):** RMS of w/U_b against the LDA
    0.072, 0.029, 0.032, 0.027, 0.020, 0.037 at the six planes (gate
    0.10); every peak on the outer side.  Ekat et al.'s SST: 0.055 to
    0.109.
  - **But:** the precursor's f against McKeon is +0.55 %, +6.1 %,
    +9.0 % at k = 1, 2, 3 (task 0049's wall-function gate is 5 %, at
    its own y⁺), while the first-cell y⁺ falls 23 → 11.6 → 7.8:
    `refined(k)` shrinks the wall cell, so Spalding's function and
    `omegaWall` work in a different layer at each level.  K is
    oscillatory (0.222, 0.261, 0.254: no GCI), the peak at 10.7 D shows
    no asymptotic range, and the 2.43 D peak converges at order 0.64.
    At k = 2 the 30.82 D plane misses by a hair (0.1002); only k = 3
    passes everywhere.
  - **No cited bend-loss correlation:** the references have none for a
    smooth 90° bend (Idelchik and Miller are book-only, RESEARCH §7),
    so K stands alone.
  - **Options:**
    (a) accept on the gates at k = 3, with the convergence reported as
    not asymptotic and the y⁺ drift explained;
    (b) a wall-function family that holds the wall cell at y⁺ ≈ 30–50
    and refines the rest (not `refined(k)`, so the levels don't nest,
    but the model is the same at each); about the same cells;
    (c) wall-resolved SST (y⁺ ≈ 1): every level several times larger,
    k = 2 and up for volunteers;
    (d) a source for K (a handbook value the user has, or an open
    paper).
  - Nothing tuned.  Status in `case.json`: in progress.

  **Answer (the design session, 2026-11-20; the user agreed: "yes I
  agree"): (b) and (d).**
  - **Why (b):** a convergence study must keep the model the same at
    every level.  With wall functions the model includes the wall
    cell, so `refined(k)` changed the model as it refined the mesh.
    `junction_loss` already holds the wall cell fixed (`first_cell`,
    `wall_ring`) and converges at order 1.9.  The bend follows it.
    Correction (2026-11-20): junction_loss doesn't fix the wall cell
    (`refined(k)` splits it); the bend builds each level directly; see
    RESEARCH §7.2 and task 0186.
  - **The family:**
    - The wall cell is fixed at first-cell y⁺ ≈ 30–50, with one target
      for all levels, computed from the precursor's u_τ as
      `junction_loss.first_cell` does.  Share that helper rather than
      copy it.
    - `n_arc`, the radial cells outside the wall cell, and the axial
      layers are refined by about 1.5–2 per level.  Three levels, with
      the finest under the 6 GB memory limit (Q1's answer).
    - The levels don't nest exactly.  Say so in RESULTS.md, and apply
      the GCI with the representative cell size, as in `junction_loss`.
  - **Check at every level:**
    - the precursor's f against McKeon within 0049's 5 % gate;
    - the y⁺ the solve achieves (mean and range), in RESULTS.md.
    If f still drifts with the wall cell fixed, stop and report it
    here.
  - **Gates unchanged:**
    - the RMS of w/U_b within 0.10 at all six planes, at the finest
      level;
    - the peak on the outer side.
    The verdict is on the new family.
  - **K against Ito (1960)**, "Pressure losses in smooth pipe bends",
    J. Basic Eng. 82, 131–143 (not open access):
    - add it to `docs/references.bib` after checking its range covers
      Re 5 × 10⁴ and R_c/D 1.425, and that its K is defined as ours
      (the total loss, with the straight pipe's friction over the same
      length taken out).  Say how in RESULTS.md.
    - K is reported with its GCI beside Ito's value, without a gate
      (Q1's answer).
    - If the definitions or the range don't match, report K alone and
      say why.
  - **The `refined(k)` runs stay in `results.json`** under their own
    level names, as the first study.  RESULTS.md keeps them in one
    short section, as the reason for the fixed wall cell, not as the
    verdict.
  - **Memory and CPU:** check `pgrep -af pytest` and free memory before
    each level (CLAUDE.md).  The suite run for 0185 also needs the
    machine, so don't run both at once.

- **Q3 (2026-11-21, coding session). The fixed-wall family doesn't
  converge to a steady state at level 2.**
  - **What holds:** the wall cell fixed at 1.95 mm (50 viscous units at
    McKeon's u_τ) keeps the model the same: the precursor's f is
    +0.55 % and +0.77 % against McKeon at levels 1 and 2, first-cell y⁺
    23.2 and 23.3 (it drifted to +6.1 % and y⁺ 11.6 under `refined(k)`).
  - **What fails:** the bend at level 2 (n_arc 16, n_radial 15, axial
    D/8: 450 k cells) never meets residualControl.  Its residuals sit
    on a plateau (p 2-7e-2, Uz 5-9e-3) from a few hundred steps on,
    and K depends on the start and settings:

    | level-2 run | steps | K | p residual at the end |
    |---|---|---|---|
    | potentialFoam -writep start (stored `fixed_k2`) | 20 000 | 0.227 | not met |
    | from rest | 4 000 | 0.250 | 3.3e-2 |
    | from rest, relaxation p 0.2, U/k/ω 0.5 | 3 000 | 0.253 | 6.8e-2 |
    | from rest, ring kept at level 1's 8 cells (growth 1.127 outward) | 3 000 | 0.271 | 2.6e-2 |

    `refined(k)`'s k = 2 (same n_arc and axial cells, the wall cell
    half as thick) converged in 1 880 steps.  So it isn't the ring's
    grading or the relaxation; it comes with the thick wall cell on the
    finer mesh.  A physical unsteadiness the steady solver can't settle
    (the bend's secondary flow and the inner-wall separation) is the
    likely reading, not verified.
  - **Fixed on the way (driver):** the precursor now solves on one
    process (decomposed, its Uy/Uz residuals floor at 2-5e-7, above
    residualControl; it converges in 3 245 steps on one); the bend
    starts from rest, as `potentialFoam` gave 2.7e4 m/s in the thin
    wall cells on this mesh and blew simpleFoam up at step 1.
  - **Options:**
    (a) average the plateau: run each level a fixed number of steps
    and report K and the profiles as means over the last N, with
    their spread as an iteration error (gated levels then carry ±);
    (b) transient (pimpleFoam), time-averaged: settles whether it is
    physical; hours per level at 450 k and more at 1.5 M;
    (c) the wall cell fixed lower (y⁺ ≈ 25-30 at the cell, about half
    of now), between the two families, if that converges;
    (d) keep `refined(k)` as the result and report its drift.
  - Nothing tuned for the gates.  `results.json` holds `fixed_k1`
    (converged) and `fixed_k2` (not converged, flagged
    `converged: false`); the driver's fixed family (`--family`), Ito's K
    and these fixes are committed.

  **Answer (the design session, 2026-11-21; the user: "yes"): (c)
  first, with one test run; (b) if it fails.**
  - **Why not (a):** K runs from 0.227 to 0.271 with the start and the
    settings.  That isn't scatter about one answer, so a plateau mean
    would hide the problem, not measure an iteration error.
  - **Why not (d):** it mixes mesh refinement with a change of wall
    model, which Q2 set out to remove.
  - **Step 1, the test:** one level-2 run with the wall cell fixed at
    about half of now, 0.975 mm (25 viscous units, about `refined(k)`'s
    k = 2 wall cell).  Start from rest, use the stored run's settings,
    and run to residualControl or a step cap.  Spalding's function
    covers this layer, so the model stays valid.
  - **If it converges:** that is the family.
    - Rebuild level 1 with the same wall cell (it needs more radial
      cells), then run levels 1–3.
    - At every level: f within 5 % of McKeon, the achieved y⁺ reported,
      and converged, not plateaued.
    - Then gates, GCI, and K against Ito's 0.262, as Q2's answer says.
  - **If it doesn't converge, then (b), at level 2 only first:**
    `pimpleFoam` from the stored state, time-averaged once the
    statistics settle.
    - Report whether the flow is unsteady: K's mean and its range, and
      the frequency if one shows.
    - If it is unsteady, stop and report it here, with the cost per
      level, before running levels 1 and 3 that way.
  - **Either way:** `fixed_k2` stays in `results.json` flagged
    `converged: false`.  RESULTS.md reports all three studies in order:
    `refined(k)`, the fixed wall cell at 50 units, and the one that
    settles.
  - **1.0:** decision 0042 needs 0050 *reported*, not passed.  If (b)
    turns out too costly for this machine, report what is known, and
    the transient run becomes a volunteer card.
  - **For 0186 (the tee):** use the wall cell that settles here.  If
    neither does, say so in 0186 before running it.

- **Q4 (2026-11-21, coding session). Q3's test: the wall at 25 doesn't
  converge, and it fails f.  Which wall cell for the transient run?**
  - **The test** (`fixed25_k2`: 0.975 mm, n_arc 16, n_radial 23, axial
    D/8; 639 360 cells, from rest, 4 processes, 6 000 steps, 2 h 3 min):
    - not converged: the p residual 3.2e-2 at step 1 000, 3.0e-2 at
      6 000; Uz 6.3e-3 at the end.  The same plateau as the wall at 50.
    - K 0.246 at step 6 000; RMS 0.051, 0.082, 0.053, 0.069, 0.094,
      0.099 at the six planes.
    - **The precursor's f: +5.9 % against McKeon, first-cell y⁺ 12.0**,
      over 0049's 5 %.  It converged (3 550 steps, one process).
  - **Reading.**  A wall cell of 25 viscous units puts its centre at
    y⁺ about 12, in the buffer layer, as `refined(k)`'s k = 2 did
    (y⁺ 11.6, f +6.1 %).  So Q3's step 2 can't hold here: this family
    fails f at every level by construction.  Only the wall at 50 keeps
    f (+0.55 %, +0.77 %).  The steady plateau is there with both walls;
    only `refined(k)`'s k = 2 and 3 converged.
  - **Stored:** `fixed25_k2` in `results.json`, `converged: false`.
    The driver takes `--family fixed_wall_25` (committed with this
    question); the default stays on it until you choose.
  - **The question:** Q3's step 3 (pimpleFoam at level 2,
    time-averaged).  Which wall?
    (a) **the wall at 50** (`fixed_k2`, 450 k cells): the only fixed
    wall that keeps f, and the cheaper mesh.  Recommended.
    (b) the wall at 25 (639 k): what Q3 named, but it fails f anyway.
    The run needs your go-ahead and the user's.  The cost is reported
    before levels 1 and 3, as Q3 says.

  **Answer (the design session, 2026-11-21): (a), the wall at 50.**
  - **Why:** step 1 of the ladder (decision 0058) requires the model to
    stay the same and valid at every level.  Only the wall at 50 passes
    0049's f gate.  A transient run on a wall that fails f would mix
    two causes, unsteadiness and the wall model, which the ladder exists
    to keep apart.  It is also the cheaper mesh.  Q3's answer meant
    "the stored state" as `fixed_k2`, and that holds.
  - **The driver's default** goes back to the wall at 50.
    `fixed_wall_25` stays as an option, and `fixed25_k2` stays in
    `results.json`, flagged.
  - **The transient run:** as Q3 step 3 says.
    - Start from `fixed_k2`'s stored state.
    - Run until the statistics of K and the six planes' profiles
      settle: the running mean changes by less than 1 % over the last
      quarter.
    - Report K's mean and range, a frequency if one shows, and the
      gates on the time-averaged profiles.  Report the cost per level
      before levels 1 and 3.
  - **Reading, fixed before the run:**
    - If K's mean lies within the steady plateau's range (0.227–0.271)
      and the flow is periodic or broadband, the plateau is physical
      unsteadiness.  The bend's verdict then comes from time-averaged
      levels.
    - If the transient settles to a steady state, the plateau was the
      steady solver's, and its K is the level-2 value.
  - **Lesson for 0188** (add it): with Spalding's wall function and SST
    in OpenFOAM, a wall cell whose centre sits in the buffer layer
    (y⁺ ≈ 8–12) gives f 6–9 % high in the developed pipe.  Keep the
    first cell's centre at y⁺ ≳ 20.  Evidence: 0050's precursors at
    y⁺ 7.8, 11.6, 12.0 and 23.2.
  - The run needs the user's go-ahead.

- **Q5 (2026-11-21, coding session). The flow is steady; how to run
  levels 1 and 3?**  The level-2 transient settles to a steady state
  (above): K 0.2623, every gate passed.
  - **The catch:** at level 1, steady SIMPLE converges (K 0.222).  But
    the transient check there (pimpleFoam, its own schemes without
    `bounded`) gave K 0.2201, 1 % lower.  Mixing the two methods across
    levels would put that 1 % into the GCI.
  - **Options:**
    (a) **every level through `--transient`** (pimpleFoam until steady),
    the same method and schemes throughout.  Costs: level 1 about
    0.15 h; level 2 done (4.3 h); level 3 (1.49 M cells, 3.3× the
    cells, the step ÷1.5) about 5 h per settled flow-through and more
    at the start, so about 20-25 h.  Memory is about 3 GB.
    Recommended.
    (b) the same with a shorter minimum window for level 3 (half a
    flow-through averaged once K is flat): about 12-15 h.
    (c) find why SIMPLE stalls (SIMPLEC, `consistent`, a tighter p
    solve), then rerun steady.  Cheaper per level if it works, but
    unproven, and level 2 would need rerunning to match.
  - Levels 1 and 3 need the user's go-ahead after this.

  **Answer (the design session, 2026-11-21; the user: "yes"): (c) as a
  test first, then (a) with a convergence stop.**
  - **One method for all three levels:** the levels must be run the
    same way, since the methods differ by 1 % at level 1.
  - **Step 1, the test (about an hour):** level 2, steady, with
    SIMPLEC (`consistent yes`) and a tighter p solve, from rest or from
    `fixed_k2`'s state.  Use the same schemes as the transient run, so
    the only change is the algorithm.
    - It passes if the residuals meet residualControl (no plateau)
      **and** K agrees with the transient's 0.26233 within 0.1 %.
    - If it passes, run levels 1 and 3 the same way, then the GCI.  The
      transient level 2 stays in `results.json` as the cross-check.
  - **Step 2, if the test fails:** every level through `--transient`.
    The flow is steady, so stop on convergence, not on an averaging
    window:
    - stop when K changes by less than 10⁻⁴ (relative) over one
      flow-through, and the six planes' profiles by less than 0.1 % of
      U_b;
    - record the stop and the cost per level;
    - level 1 is rerun this way so all three match.
  - **Either way:**
    - report K with its GCI against Ito's 0.2626, without a gate;
    - judge the gates at the finest level;
    - give each level's f, y⁺, `wall_s` and method in RESULTS.md;
    - all studies stay in order (`refined(k)`, the plateau, the
      transient, the final family).
  - **Lessons for 0188**, after the result:
    - a steady SIMPLE plateau in a bend isn't the flow's own
      unsteadiness;
    - how to tell: a transient run from the plateau that settles;
    - the fix, if step 1 finds one.
  - The runs need the user's go-ahead (CLAUDE.md: long CPU runs).

- **Q6 (2026-11-22, coding session). Level 3 can't be run
  time-accurately here; how to reach its steady state?**
  The flow is steady (level 2: K band 1.3e-7), so time accuracy buys
  nothing but cost.
  - **Options:**
    (a) **pseudo-transient local time-stepping**: pimpleFoam with
    `ddtSchemes localEuler`, each cell at its own Courant number
    (`maxCo` about 5-10 with PIMPLE's outer correctors).  It is
    OpenFOAM's standard route to a steady state when SIMPLE stalls.
    The same convergence stop, measured in iterations, not seconds.
    One method for all levels means rerunning levels 1 and 2 (about
    1-3 h together, if it is as fast as it should be).  The method is
    unproven here: a level-2 test against 0.26233 comes first, as with
    SIMPLEC.  Recommended.
    (b) time-accurate, but level 3 started from level 2's solution
    (mapFields) with the final p tolerance 1e-6: still about 40-60 h.
    (c) report 0050 with two levels: K 0.2201 and 0.26233, no GCI.
    Decision 0058 needs 0050 reported for 1.0, not passed.
  - Each run needs the user's go-ahead.

  **Answer (the design session, 2026-11-22; the user: "yes"): (a),
  with (c) and a volunteer card as the fallback.**
  - **The check comes first.**  A steady state reached by local time
    stepping should match the time-accurate one.  But in OpenFOAM it
    need not, exactly: the face-flux interpolation in pimpleFoam
    carries a time-step-dependent correction (`ddtCorr`).  Your
    SIMPLEC result at level 1 (converged, K 0.2269 against 0.2201) shows
    the algorithm can move K by 3 %.  So:
    - run `localEuler` at level 1 (minutes) and level 2, with the
      transient's schemes;
    - it passes if both converge (residualControl, or the Q5 stop) and
      K matches the time-accurate 0.22013 and 0.26233 within 0.1 %.
  - **If it passes:** run level 3 with it.  Levels 1 and 2 stand as run
    time-accurately, since the check shows the same steady solution.
    Then the GCI, K against Ito with it, and the gates at level 3.
  - **If it fails** (no convergence, or K off by more than 0.1 %):
    - report 0050 with levels 1 and 2 (K 0.2201, 0.26233), with no GCI;
    - judge the gates at level 2 (they pass there), and say plainly that
      it is not the finest planned level;
    - write level 3, time-accurate from level 2's mapped solution, as a
      volunteer card (0179's form);
    - that meets decision 0058's 1.0 criterion (reported).
  - **Report either way, a ladder finding:** at level 1, converged
    steady solutions differ by the algorithm: SIMPLE 0.222, SIMPLEC
    0.2269, pimpleFoam 0.2201.  Give the spread in RESULTS.md as a
    solver-side uncertainty beside the GCI.  Say whether `ddtCorr` was
    on.  Ito's −0.1 % agreement at level 2 is read with it.  It is a
    lesson for 0188: K from different OpenFOAM algorithms can differ
    by a few percent on a coarse mesh.
  - Each run needs the user's go-ahead.

## Outcome

_Not done._
