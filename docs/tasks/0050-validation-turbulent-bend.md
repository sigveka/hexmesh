# 0050 — Validation: turbulent flow in a 90° bend (PTB LDA; Sudo et al. 1998 the ideal)

- **Status:** blocked (Q2, 2026-11-20: the gates pass at k = 3, but the levels don't converge; *Questions for design*)
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

## Outcome

_Not done._
