# 0180 — Validation (V2): turbulent rectangular ducts against the KTH DNS, with a volunteer card

- **Status:** ready (after 0176, which settles the card format;
  coordinate with 0179)
- **Decision:** [0012](../decisions/0012-openfoam-validation-cases.md)
  (V2); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md);
  [0044](../decisions/0044-volunteer-runs.md) and
  [0055](../decisions/0055-cards-for-every-case-ci-without-openfoam.md)
  (the card; CI without OpenFOAM)
- **Category:** V2 (DNS: Vinuesa et al., KTH; KIT's square duct,
  Pinelli et al. 2010, as the second reference at AR 1)
- **Features:** `section:rect`, `straight`; the H and O-H layouts
  (decision 0036)
- **Depends on:** 0176 (card format).  The periodic set-up of
  `validation/turbulent_pipe/` (cyclic and `meanVelocityForce`).
- **Blocks:** none.  Not a 1.0 criterion.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user (2026-11-18) asked for more high-fidelity
validations, with volunteer cards where data exist.  RESEARCH §7.16
(the survey) found the KTH duct DNS to be the open dataset that best fits
hexmesh: rectangular sections at six aspect ratios.  Its secondary flows
are set by the corner cells, so they test the duct mesh where RANS with
SST can't.

**Reference** (RESEARCH §7.16, and the KIT entry in §7.8).
- `https://www.mech.kth.se/~rvinuesa/DuctData/`: aspect ratios 1, 3, 5,
  7, 10, 14.4 at Re_τ 180 (1 and 3 also at 360).  Text `.prof` files of
  U, V, W and the six Reynolds stresses.  FTP, or the newer SharePoint
  folder.
- **Read first** and record in RESEARCH §7.16:
  - the papers the page names: the domain length, Re_b per case, the
    averaging time, and which quantities are on which coordinates;
  - the files' exact format, and how many are reachable today.  If the
    FTP and the SharePoint both fail, stop and write to *Questions for
    design*.
  - No licence is stated, so download at run time to
    `validation/kth_duct/data/` (git-ignored), as for the KIT data.
    Commit only a fetch script and checksums.

**Do.**
1. **The case** `validation/kth_duct/`, starting with **AR 1 and AR 3
   at Re_τ 180**:
   - a straight `section:rect` duct, periodic (cyclic inlet and outlet,
     `meanVelocityForce` at the DNS's Re_b), as turbulent_pipe;
   - the domain length from the paper;
   - the H layout (the rectangle's default), and the O-H layout at AR 1,
     as a mesh comparison.
2. **Level set A, here: Reynolds-stress RANS** (OpenFOAM v2406 `SSG`
   or `LRR`; say which, and why).  It is cheap, and a mesh test as far
   as the model allows:
   - three meshes with `refined(k)`, wall-resolved (y⁺ < 1), GCI on the
     friction factor and the secondary-flow peak;
   - SST on the finest mesh as a baseline.  It should show no secondary
     flow; say whether it does;
   - reported, not gated: RANS's own limits dominate.
3. **Level set B, volunteer: wall-resolved LES** at AR 1, Re_τ 180,
   and AR 3 if the card's numbers allow:
   - resolution from the literature for wall-resolved LES (Δx⁺, Δy⁺,
     Δz⁺, stated), two levels;
   - a timing run here: enough steps for seconds per step, the time
     step, and the averaging time to converge the secondary flow.
     Measure peak memory and disk; delete the run;
   - run the coarser LES level here if it fits in about 12 h.  Otherwise
     the card's requirements are *estimated* from the timing run.
4. **Proposed gates for B**, under *Questions for design*: which
   quantities, and which band.  Design fixes them before the card is
   offered (as 0120).  For example:
   - U along the wall bisector and the diagonal;
   - the secondary-flow peak (V, W);
   - u_rms along the bisector;
   - a band from the two DNS (KTH against KIT at AR 1) and the
     statistics' uncertainty.
5. **The card** (`card.json`, decision 0055):
   - set A's levels are "run here", and reproducible with
     `python3 -m validation run kth_duct`;
   - set B's levels are volunteer levels;
   - the hooks are `prepare`/`run`/`collect`;
   - a dry run through `check` on set A's coarsest level.
6. `case.json` (V2; tags `rans:SSG` or `rans:LRR` for set A, `les` for
   set B, `section:rect`, `straight`), RESULTS.md, and the *Outcome*
   table for RESEARCH §7.16.
7. **Later aspect ratios** (5, 7, 10, 14.4): only if A and B at AR 1 and
   3 go well.  List them as follow-ups with their estimated cost.  Don't
   run them here.

**Accept.**
- The data fetched and its provenance recorded.
- Set A run and reported, with GCI.
- The LES timing measured and the card written, its requirements labelled.
- Proposed gates under *Questions for design*.
- `python3 -m validation run kth_duct` reproduces set A's coarsest level.
- No OpenFOAM in CI (decision 0055).
- Disk freed.

**Out of scope.**  The ducts' entrance development (the DNS are
periodic); heat transfer; the KIT Reynolds-number sweep beyond its AR 1
check.

## Agent notes

## Questions for design

## Outcome
