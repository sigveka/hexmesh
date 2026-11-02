# 0079 — Validation (V3): a Taylor bubble rising in stagnant liquid (VOF)

- **Status:** ready (on the v2406 runner)
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md) (V3; `multiphase` tag, amendment 2026-11-01); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) as amended
- **Category:** V3 (experiment: Nogueira et al. 2004; V4 correlation, Viana et al. 2003, secondary)
- **Features:** `section:circle`, `straight`
- **Depends on:** the shared OpenFOAM helpers and the Docker runner.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  This is hexmesh's first multiphase case.  It is
interface-resolving (VOF, `interFoam`), so there are no closure models
and the result tests the mesh.  Structured hexes aligned with the pipe
should keep the interface sharp, and the falling film between bubble
and wall is thin.  This is where hexmesh should show.

**References** (RESEARCH §7.10; PDFs in `docs/papers/`).
- **Primary, V3:** [`nogueira_and_riethmuller_etal_2004`], Table 1.
  - 32 mm tube, aqueous glycerol, stagnant liquid.
  - Rise velocity UB timed by photocells; film thickness δ.
- **Secondary, V4:** [`viana_and_pardo_etal_2003`].  The universal
  correlation Fr(R, Eo), with its constants in RESEARCH §7.10.
  Implement it in the driver and check it against the paper's limiting
  forms.
- **Known discrepancy:** at μ = 1.5 Pa s the two references differ by
  40 %.  Run that case, report it, and don't gate on it.

**Where.**  `validation/taylor_bubble/` (`run.py`, `README.md`,
`RESULTS.md`, `case.json`, `meshes()`), v2406.  Add the `multiphase`
physics tag and the `vof` regime tag to `validation/case.schema.json`.

**Do.**
1. **Geometry and mesh.**
   - A vertical `Straight` of diameter 32 mm and length about 20 D,
     both ends closed (wall patches).
   - Grade the radial cells to the wall (`first_cell`).  The film is
     δ/D = 0.075–0.161 in the gated cases: put at least **8 cells
     across the film** at the finest level, and state the count at
     each level.
   - Axial cells uniform over the bubble's path.
2. **Cases** (Table 1, stagnant):
   - **gated:** μ = 0.200 and 0.043 Pa s (Re_UB 37 and 177: laminar,
     axisymmetric);
   - **reported:** μ = 1.5 Pa s (the discrepancy) and μ = 0.109.
   - Not water (μ = 0.001): its wake is turbulent and 3-D.  A follow-up
     with LES, if wanted.
   - Densities and viscosities from Table 1.
   - **Surface tension:** take it for the glycerol fraction that gives
     each viscosity (from property tables; state the source).  Then
     show the result is insensitive: one run at ±10 % σ.  At Eo ≈ 190
     it should change UB by ≪ 1 %.
3. **Initial state.**
   - Gas: a cylinder of length 3 D with a hemispherical cap, its
     radius leaving a film of roughly the expected δ, near the bottom.
     Liquid elsewhere.  Use `setFields` or a field written by Python.
   - Check that the result doesn't depend on bubble length: one run at
     5 D.
4. **Solver.**
   - `interFoam`, laminar, gravity along the axis.
   - MULES with `cAlpha 1`; maxCo and maxAlphaCo of about 0.2 (say
     which).
   - Record the settings, and any version quirk, in
     `docs/integrations/openfoam.md`.
5. **Measure** once the rise is steady (the nose velocity constant
   within 0.5 % over 2 D of travel):
   - **UB** from the nose position (the α = 0.5 crossing on the axis)
     against time;
   - **δ**: the α = 0.5 radius in the developed film (where the film
     thickness has stopped changing), as D/2 − r;
   - the **bubble shape** (the α = 0.5 contour of the nose), compared
     with Dumitrescu's inviscid profile as plotted by Nogueira et al.
     (qualitative);
   - **axisymmetry:** the spread of the α = 0.5 radius around the
     circumference.
6. **Convergence:** three levels; GCI on UB and δ for the two gated
   cases.

**Accept** (V3 gates, provisional; report and don't tune if missed):
- **UB** within **5 %** of Nogueira's measured value for μ = 0.200 and
  0.043 Pa s, at the finest level, with GCI reported.  Viana's
  prediction shown beside it.
- **δ** within **10 %** of the measured value for the same cases.
- The bubble stays axisymmetric: the α = 0.5 radius spread is below one
  cell at the finest level.
- `case.json` (V3; tags `laminar`, `transient`, `vof`, `multiphase`,
  `section:circle`, `straight`); RESULTS.md; *Outcome* table for
  RESEARCH §7.10.

**Out of scope.**
- The co-current cases (the next step: an inlet flow, UB = c·UL + Fr√(gD));
- water and turbulent wakes;
- Bugg & Saad's local PIV (paywalled, digitising needed);
- Euler–Euler bubbly flow (planned separately).

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
