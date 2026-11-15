# 0050 — Validation: turbulent flow in a 90° bend (Sudo et al. 1998)

- **Status:** blocked (the paper's data: *Questions for design*)
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md) (its "Dean bend" case, turbulent); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) as amended
- **Category:** V3 (experiment: Sudo et al. 1998)
- **Features:** `section:circle`, `straight`, `bend`
- **Depends on:** 0049 (model setup, wall treatment, post-processing).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The first turbulent case with a fitting, and the basis for
turbulent loss-coefficient studies (decision 0025) and for installation
effects upstream of meters (decision 0021's showcase).  A bend is where
hexmesh's exact walls and conformal sweeps should show.

**Reference.**  [`sudo_and_sumida_etal_1998`]: smooth circular 90°
bend, Re = 6 × 10⁴, long straight pipes upstream and downstream;
rotating inclined hot-wire measurements of the mean velocity components
and Reynolds stresses at several stations through and after the bend.
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

_None yet._

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

## Outcome

_Not done._
