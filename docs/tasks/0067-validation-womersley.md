# 0067 — Validation: Womersley flow (pulsatile laminar pipe flow, exact solution)

- **Status:** ready (after 0032's Re 500 level is done: same machine time)
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) as amended
- **Category:** V1 (exact: Womersley)
- **Depends on:** the shared OpenFOAM helpers (0043); the Poiseuille
  setup (0020).  0068 (pulsatile stenosis) builds on it.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The first time-dependent case.  Fully developed pulsatile flow
in a straight pipe has an exact solution (Womersley 1955), so it checks
the transient solver path and, above all, **the time-varying,
spatially varying inlet** that the pulsatile stenosis (0068) needs,
without a jet on top.

**Physics** (the stenosis paper's inlet, RESEARCH §7.3,
[`varghese_and_frankel_etal_2007b`] eq. 2.1, read with the imaginary
part):

u/u_c = (1 − (r/R)²) + A·Im{[1 − J₀(i^{3/2} α r/R)/J₀(i^{3/2} α)] e^{iωt}}

- α = (D/2)√(ω/ν) = 7.5, A = 0.667, Re = u_c D/ν = 600 (centreline
  velocity), D = u_c = 1, so ν = 1/600, ω = 0.375, T ≈ 16.76.
- The matching exact pressure gradient follows from the same solution
  (steady Poiseuille part plus the oscillatory part); derive it in the
  driver, with the formula in README.md.

**Where.**  `validation/womersley/` (`run.py`, `README.md`,
`RESULTS.md`, `meshes()` for the gallery), on `hexmesh.study.openfoam`;
`docs/integrations/openfoam.md`.

**Do.**
1. **Inlet without coded BCs** (they fail on this build): write the
   profile with Python into `constant/boundaryData/fluid_inlet/points`
   and `…/<time>/U` at enough times per period (e.g. 48), for enough
   periods, and use `timeVaryingMappedFixedValue`.  Check that v1912
   interpolates in time as expected (compare the applied face values at
   a few times with the formula).  Record what works in `openfoam.md`.
2. **Pipe:** a straight pipe long enough for the profile to stay fully
   developed (e.g. 10 D; check the mid-length profile against the
   inlet's).  Uniform axial spacing; O-H section with `first_cell` or
   uniform (say which).
3. **Solver:** `pimpleFoam`, laminar, second-order time scheme
   (`backward`, or `CrankNicolson` with a coefficient: say which), Courant
   number ≤ 0.5.  Run until periodic: the phase values change by less
   than 0.1 % between consecutive periods.
4. **Compare at mid-length,** at the six phases t/T = 0.09 + k/6 (the
   stenosis data's phases) and at the peak and minimum:
   - the velocity profile u(r) against the exact solution (max and RMS
     error as % of u_c);
   - the axial pressure gradient against the exact one (amplitude and
     phase).
5. **Convergence:** three mesh levels (`refined(k)`), and the finest
   also with Δt halved, to separate space and time errors.  Richardson /
   GCI on the centreline velocity at peak flow and on the
   pressure-gradient amplitude.

**Accept** (gates set now, laminar and exact):
- Velocity: max profile error at the finest level **≤ 1 % of u_c** at
  every phase; extrapolated within 0.3 %.
- Pressure gradient: amplitude within 1 %, phase within 2°, at the
  finest level.
- The time-step study shows the time error is below the space error at
  the finest level (or report the split).
- Periodicity reached and reported (periods needed).
- `RESULTS.md`, *Outcome* table for RESEARCH; the default pytest run
  unchanged (opt-in test for the coarse level only).

**Out of scope.**  Non-sinusoidal (physiological) waveforms; elastic
walls.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
