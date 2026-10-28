# 0049 — Validation: fully developed turbulent pipe flow (RANS, k-ω SST)

- **Status:** ready (after 0043)
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md) (its "turbulent pipe DNS" case); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) as amended
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

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
