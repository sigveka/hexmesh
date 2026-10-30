# 0067 — Validation: Womersley flow (pulsatile laminar pipe flow, exact solution)

- **Status:** done
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) as amended
- **Category:** V1 (exact: Womersley)
- **Features:** `section:circle`, `straight`
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

- **Runner (built here, for 0035 too).**  `hexmesh.study.openfoam` runs
  OpenFOAM natively (v1912) or in Docker (`docker:<image>`; default for
  this case `opencfd/openfoam-default:2406`, decision 0012's toolchain),
  via `set_runner`, `--openfoam` or `HEXMESH_OPENFOAM`.  Each command runs
  in a fresh container as the calling user, the case mounted at its own
  path.  `read_zone` now reads v2406's `faceZones` format too.  Details
  and the v1912 ↔ v2406 mesh comparison in `docs/integrations/openfoam.md`.
- **Step 1 refined.**  `boundaryData` is written at **every solver time
  step**, not 48 per period, so the BC's linear time interpolation is
  exact at each step; applied inlet error 2e-10.  Checked on v2406 (the
  case's toolchain), not v1912.
- **Initial state** is the exact profile at the first phase, so the run
  is periodic after 2–3 periods.
- **Steps 2–3:** 10 D, uniform axial spacing, the O-H section graded
  toward the wall (`mprg` 0.85^(1/k), not `first_cell`); `backward`;
  Co ≈ 0.47.
- **Step 5 refined: the time-step study is at k2, not k4.**  On 4
  physical cores, k4 takes about 2.5 h per period, so a halved-Δt k4 run
  would add about 10 h.  The halved run is warm-started from the level's
  periodic state, which separates the time error from the start-up.
- **Bug found and fixed before the results:** the first halved-step run
  had Δt *doubled* (step count divided by the factor); its numbers are
  not used.

## Questions for design

_None._

## Outcome

**Accepted:** every gate passes at k4.  Run 2026-10-30, OpenFOAM v2406
(Docker), gmsh 4.12.1; details in `validation/womersley/RESULTS.md`.

| Quantity (for RESEARCH) | k1 | k2 | k4 | gate |
|---|---|---|---|---|
| cells | 7 680 | 61 440 | 491 520 | |
| max profile error, all phases (% u_c) | 2.11 | 0.65 | **0.31** | ≤ 1 |
| RMS profile error, worst phase (% u_c) | 1.03 | 0.27 | 0.07 | |
| centreline error at peak (u_c) | 5.3e-3 | 1.4e-3 | 3.6e-4 | |
| extrapolated (order 1.89) | | | **−2.9e-5** | within 0.3 % |
| dp/dx amplitude error | 0.29 % | 0.081 % | **0.020 %** | 1 % |
| dp/dx phase (°) | 0.35 | 0.089 | **0.022** | 2° |
| amplitude extrapolated (order 1.79) | | | −0.005 % | |
| periods to periodic (< 0.1 %) | 3 | 3 | 2 | reported |
| time error at k2 (Δt halved): centreline / amplitude | | 2.8e-5 / 0.0055 % | | below space error (1.4e-3 / 0.081 %) |

**Files.**
- `hexmesh/study/openfoam.py`: the runner (`set_runner`, `runner`,
  `V2406`, `HEXMESH_OPENFOAM`, `foam(…, mounts=)`); `read_zone` reads
  v2406's `faceZones`.
- `validation/womersley/`: `run.py`, `README.md`, `RESULTS.md`,
  `case.json` (V1, accepted), `img/` (gallery).
- `tests/test_openfoam_runner.py` (7: 6 default, 1 `openfoam`);
  `tests/test_validation.py::test_womersley_coarse` (opt-in, ~2 min).
- `docs/integrations/openfoam.md`: v2406 in Docker; the `faceZones`
  format; `timeVaryingMappedFixedValue` with boundaryData at every step.
- `docs/GALLERY.md`, regenerated.

**Tests.**  Full suite: 2144 passed, 14 skipped (2138 before, plus 6
runner tests).  Opt-in: `test_womersley_coarse` and the Docker runner
test pass.

**Surprises.**
- The **max** profile error converges more slowly than the RMS error (max
  orders 1.7 then 1.1; RMS 1.8–2.1 at every phase), and its worst phase
  moves (0.42 at k2, 0.59 at k4).  The error is local; where it sits
  isn't recorded.  Candidate: `mprg^(1/k)` grading, so near-wall cells
  don't halve exactly.  It's within the gate at k4 (0.31 %).
- The centreline value must be extrapolated as an error against the exact
  value at the same sampling points.  Extrapolating the raw velocity gave
  a spurious 0.04 %, because the four faces nearest the axis move with
  the level.
- Open MPI counts physical cores: `-np 6` failed on this 8-thread,
  4-core machine.
- A restarted (warm) run takes `deltaT` from `<time>/uniform/time`, not
  `controlDict`; the driver rewrites it.

**Proposed follow-ups.**
- Record where the max profile error sits (r, θ) per phase, and test a
  level series with fixed-ratio grading (`first_cell` halved per
  level), to tell grading from a corner or near-wall effect.
- 0068 can reuse `write_inlet`/boundaryData-every-step and the runner
  as-is.
