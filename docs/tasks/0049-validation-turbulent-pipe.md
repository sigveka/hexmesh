# 0049 — Validation: fully developed turbulent pipe flow (RANS, k-ω SST)

- **Status:** blocked (gates fail: questions Q1–Q3; results complete)
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md) (its "turbulent pipe DNS" case); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) as amended
- **Category:** V2 (DNS profiles; V4 friction-factor correlation as secondary)
- **Features:** `section:circle`, `straight`
- **Depends on:** 0043 (shared OpenFOAM helpers).  Uses `first_cell`
  wall grading and `refined(k)`.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Every validated case so far is laminar.  Loss coefficients,
flow meters and most plant flows are turbulent, and a study's turbulent
results (decision 0025) are only as good as this case.  It is the
simplest turbulent check: a straight pipe, where the friction factor and
the mean-velocity profile are known precisely.  The RANS literature
(RESEARCH §10.2) sets realistic expectations: errors of a few per cent
are the model's, not the mesh's.

**References.**
- Friction factor: [`mckeon_and_zagarola_etal_2005`] (Princeton
  Superpipe; their relation fits all data within 1.4 %, Blasius within
  2 % at low Re).
- Mean profile and wall shear: DNS of [`el_khoury_and_schlatter_etal_2013`],
  Re_τ = 180, 360, 550, 1000 (the paper's tabulated profiles; the PDF
  is linked in RESEARCH once added; don't commit the data if its licence
  doesn't allow it).

**Where.**  `validation/turbulent_pipe/` (`run.py`, `README.md`,
`RESULTS.md`), on `hexmesh.study.openfoam` (task 0043);
`docs/integrations/openfoam.md`; RESEARCH §7.

**Do.**
1. **Domain.**  Prefer a short **periodic** pipe (e.g. 2π R long) with
   cyclic ends and a mean-velocity driving force (`meanVelocityForce` in
   `constant/fvOptions`).  hexmesh's inlet and outlet faces have
   identical node layouts, so `createPatch` can pair them as a
   translational cyclic.
   - Neither `meanVelocityForce` nor a hexmesh cyclic pair has been
     tried on this OpenFOAM build.  If either fails, record it in
     `openfoam.md` and fall back to a long inlet-outlet pipe (e.g. 80 D,
     results from the last quarter), saying why.
2. **Cases.**  Re_b chosen to match two DNS cases (Re_τ = 550 and 1000;
   compute Re_b from the paper), plus one Superpipe point near
   Re_b = 10⁵ (friction factor only).
3. **Model.**  `kOmegaSST`, steady `simpleFoam`.
   - **Low-Re variant:** wall-resolved, first cell y⁺ ≤ 1 via
     `first_cell` (check the achieved y⁺ in post-processing, not only
     the design value).
   - **Wall-function variant:** first cell centre at y⁺ 30–100, wall
     functions on k and ω.
4. **Convergence.**  Three levels with `refined(k)` for the low-Re
   variant at Re_τ = 550 (axial resolution matters little in a periodic
   pipe: say what you scaled).  Richardson and GCI on the friction factor
   and the centreline velocity.
5. **Post-processing** in Python (function objects abort on this
   build): wall shear stress from the near-wall velocity gradient (or
   from the driving force in the periodic case, which is exact by the
   momentum balance), friction factor f = 8 τ_w / (ρ U_b²), u⁺(y⁺) on a
   radial line, U_c / U_b.

**Accept.**
- Gates, set now (RANS, not DNS, accuracy):
  - **friction factor** within **3 %** of McKeon et al. (low-Re
    variant) and within **5 %** (wall functions), at the finest level;
  - **U_c / U_b** within 3 % of the DNS value at the matching Re_τ;
  - **u⁺(y⁺)** reported against the DNS (plot and table at y⁺ = 1, 10,
    30, 100 and the centre); no gate, it shows the model's known
    deviations.
- GCI reported for f and U_c (fine level), with observed orders
  (reported, not gated: decision 0015 as amended).
- Achieved first-cell y⁺ reported for each variant.
- `RESULTS.md` with versions and date, and a RESEARCH-ready table in
  *Outcome*.  If a gate fails, report under *Questions for design* with
  the numbers; don't tune the model constants.
- Default `pytest` run unchanged (OpenFOAM tests opt-in).

**Out of scope.**  Rough walls; LES; heat transfer; bends (task 0050).

## Agent notes

- **Data (2026-11-05):** the DNS profiles are on Zenodo
  ([10.5281/zenodo.7352880](https://doi.org/10.5281/zenodo.7352880)),
  CC-BY-4.0, so they are committed with attribution:
  `validation/turbulent_pipe/data/` (the 550 and 1000 mean-profile files,
  unmodified, with a README).  Their headers give Re_b = 19 000 (Re_τ
  550.06, u_τ/U_b 0.05790) and 37 700 (Re_τ 999.03, 0.05300).  Bib:
  `el_khoury_and_schlatter_etal_2013_data`.
- **Reference f:** McKeon et al. eq. 3.5, which they state predicts all
  data within 1.4 % and Blasius within 2 % at low Re.  It gives 0.02651,
  0.02249 and 0.01818 at Re_b 19 000, 37 700 and 10⁵.  The DNS f =
  8(u_τ/U_b)² is 0.02682 and 0.02247; Blasius gives 0.02695, 0.02271
  and 0.01779.
- **Domain:** the periodic pipe works on v2406 (`openfoam.md`).  Its
  length is R and it has 2 axial layers at k = 1: the solution doesn't
  vary along the axis.  `refined(k)` scales the axial count with the
  rest.  τ_w comes from the momentum balance, (dp/dx) V / A_wall, with
  dp/dx the force `meanVelocityForce` applied; it is exact for the mesh.
  **Pipeline check:** laminar Re 100 on the same set-up gives f within
  0.1 % of 64/Re, and U_c/U_b = 1.990.
- **Wall distance:** the meshed wall is faceted, inside R between nodes
  by R(1 − cos(45°/nang)), which is 1.15 viscous units at nang 12 and
  Re_τ 550.  That is more than the wall-resolved first cell, so the
  profile uses each cell's distance to the nearest wall face, not R − r.
  With R − r, u⁺(10) read 7.1 instead of 8.5.
- **Wall functions, sensitivity (wf_550, k = 1, trials):**
  - f against McKeon: −7.3 % with OpenFOAM's standard `nutkWallFunction`,
    −5.3 % with `nutUWallFunction`, −0.4 % with
    `nutUSpaldingWallFunction`;
  - U_c/U_b is 7–7.5 % low with all three;
  - neither nang 12–48 nor nrad 3–12 moved f by more than 0.3 %.
  The gated variant is the standard pairing (kqR/omega/nutk), chosen
  before seeing the results.  The other two are reported as
  `wfu_*`/`wfs_*`, not gated, so as not to pick whichever passes.
- **Residual control** loosened to p 1e-6, U/k/ω 1e-7.  With tighter
  values the Uy/Uz residuals stalled for 20 000 steps, while dp/dx had
  stopped changing at the 12th digit by step 6000.
  `dpdx_drift_50` (the relative change over the last 50 steps) is
  stored per level as the convergence measure.

## Questions for design

The gates are not met.  Per the task, the numbers are reported and the
model constants are not tuned.  Evidence: `validation/turbulent_pipe/RESULTS.md`.

- **Q1. U_c/U_b, wall-resolved:**
  - Lowre_550 converges to 1.2129, −3.9 % from the DNS (fine GCI 0.1 %,
    so not the mesh).  Lowre_1000 at k = 2 is −4.7 %.
  - The gate is 3 %.
  - The deficit is k-ω SST's weak wake: u⁺ at the centre is about 1
    below the DNS, while the sublayer matches (u⁺(1) = 1.00, u⁺(10) 8.29
    against 8.47).
  - Accept a ~4 % gate for U_c/U_b as the model's, or keep 3 % and leave
    the case rejected for SST?
- **Q2. f, wall-resolved:**
  - The finest level passes: +2.41 % from McKeon at k = 4 (+1.22 % from
    the DNS's f).
  - But f converges slowly from below (order 0.84), and its Richardson
    extrapolation is +4.6 % from McKeon (+3.4 % from the DNS), with a
    2.7 % fine-level GCI.
  - Does the gate apply to the finest level (as written) or to the
    extrapolation?
- **Q3. Wall functions:**
  - With OpenFOAM's standard pairing (kqR / omega / nutk), f is −7.1 to
    −7.3 % at all three Re (gate 5 %) and U_c/U_b is −6.7 to −7.6 %.
  - The nut wall function alone moves f by up to 7 points: Spalding's
    law gives −0.4 / −2.0 / −3.3 %.
  - The ring resolution and nang don't matter (≤ 0.3 %).
  - Which wall-function set should the validated wall-function variant
    be, and should the CFD guidance warn that the standard `nutk` set
    under-predicts f by ~7 % in fully developed pipe flow at y⁺ ≈ 45?

## Outcome

_Blocked on Q1–Q3; the runs and results are complete._

- **Files:**
  - `validation/turbulent_pipe/`: `run.py`, `README.md`, `RESULTS.md`,
    `case.json`, `results.json`, and `data/` (2 DNS files with a README,
    CC-BY-4.0);
  - `docs/references.bib` (the dataset);
  - `docs/integrations/openfoam.md` (the periodic pipe).
- **For RESEARCH §7 (k-ω SST, v2406, periodic pipe):**

  | Re_b (Re_τ) | variant | f vs McKeon | f vs DNS | U_c/U_b vs DNS | first-cell y⁺ |
  |---|---|---|---|---|---|
  | 19 000 (550) | wall-resolved, k = 4 | +2.41 % (extrap. +4.6 %) | +1.22 % | −3.98 % | 0.12 |
  | 37 700 (1000) | wall-resolved, k = 2 | −0.55 % | −0.48 % | −4.68 % | 0.24 |
  | 10⁵ | wall-resolved, k = 2 | −1.60 % | — | — | 0.24 |
  | 19 000 / 37 700 / 10⁵ | nutk wall functions | −7.26 / −7.08 / −7.22 % | −8.3 / −7.0 % | −7.6 / −6.7 % | 46–48 |
  | same | Spalding | −0.37 / −2.04 / −3.27 % | | −7.2 / −6.4 % | 48 |

- **Run times (4 MPI processes):** the whole set took 2 h 50 min.
  lowre_550 at k = 4 (184k cells) took 15 400 SIMPLE steps and most of
  that.
- **Surprises:**
  - the faceted wall: with R − r as the wall distance, the wall-resolved
    u⁺ read wrong by about a viscous unit at nang 12;
  - the nut wall function's large effect.
- **Follow-ups:** the turbulent bend (0050) needs Q3's answer for its
  wall treatment.
