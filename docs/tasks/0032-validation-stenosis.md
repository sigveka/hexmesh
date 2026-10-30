# 0032 — Validation: smooth cosine constriction (Varghese et al.), Re = 500

- **Status:** done
- **Decision:** [0008 — Profiled sweep](../decisions/0008-profiled-sweep.md); [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md)
- **Category:** V2 (DNS: Varghese et al. Part 1)
- **Features:** `section:circle`, `straight`, `profiled-reducer`
- **Depends on:** 0031 (profiled `Reducer`), 0020 (re-run: the
  validation pipeline), 0025 (exact straight walls)

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The second validation case, and the first with a
non-trivial flow: a jet through a smooth 75 %-area constriction with
public DNS data (RESEARCH §7.3).  It tests a profiled fitting, axial
resolution through a throat, and steady laminar separation.

**Geometry** (RESEARCH §7.3).  Straight pipe of diameter D with
R(x) = D/2 · [1 − s0 (1 + cos(2π(x − x0)/L))], s0 = 0.25.
- **Check L against the paper first**
  [`varghese_and_frankel_etal_2007`]: the Purdue page gives L = 2D,
  `../geometry_valve/` used L = D.  Record the source (page, equation)
  under *Agent notes*; the paper is not in `docs/papers/` (add it if you
  can get it).
- Upstream and downstream lengths from the paper's domain (record them).
  Use `extend_open_ends` or explicit `Straight`s.

**Case.**  Steady laminar `simpleFoam`, Re = 500 based on D and the
mean inlet velocity, inlet profile as in the paper (parabolic if so).
Reuse task 0020's pipeline (`validation/poiseuille/run.py`): the case
writer, `apply_boundary_roles`, Python post-processing (function
objects abort on this OpenFOAM build, `docs/integrations/openfoam.md`).

**Pipeline.**  `validation/stenosis/run.py`, `README.md`, `RESULTS.md`;
work directory git-ignored.  Three levels, by `Assembly.refined(k)` if
task 0026 is done, otherwise by scaling as in 0020.

**Compare** with the paper / Purdue data:
- centreline axial velocity along x;
- the recirculation length downstream of the throat (reattachment
  point of the wall shear stress);
- wall shear stress along x, if the data has it;
- signed errors, Richardson extrapolation and observed order
  (decision 0015; [`celik_and_ghia_etal_2008`]).

**Accept.**
- `checkMesh` "Mesh OK" at all levels.
- The comparison plots/tables in `RESULTS.md`, with versions and date.
- Gates (provisional; if missed, report under *Questions for design*,
  don't tune): extrapolated recirculation length within 5 % of the
  reference; centreline velocity within 2 % of the reference peak.
- If task 0031 kept `core="fixed"` (D2), run the finest level with both
  core modes and report the difference.
- `tests/test_validation.py`: an opt-in `-m openfoam` test that runs the
  coarse level and checks it completes with "Mesh OK".
- Default `pytest` run unchanged.

**Out of scope.**  Pulsatile flow (Part 2), the eccentric model,
turbulence, Re = 750 and 1000 (follow-ups if Re = 500 passes).

## Agent notes

- **Paused 2026-10-28** for the design order (0032 last, built on
  0043's `hexmesh.study.openfoam`).  A draft driver,
  `validation/stenosis/run.py`, is in the working tree, uncommitted.  It
  reuses the Poiseuille and heated-rod helpers by import, so redo it on
  0043's module.
  - Driver: D = 1, U = 1, ν = 1/500, and a parabolic fixed-value inlet
    written per face and scaled to the discrete flow rate.  The
    centreline value is a quadratic fit near the axis, per slab.
    Separation and reattachment are sign changes of the wall shear
    stress.
  - It used 22 D downstream, from the database figure's axis; **the
    paper says 16 D** (design note below).
- **Purdue database, Re = 500** (`Axi_stdy/Re500/vel.dat`, fetched
  2026-10-28): radial profiles of (u, v, w) on D = 1 at x/D = −2 … 15
  (1 D apart, 101 points across), normalised by u_i = 0.5.
  - Inlet parabolic: centreline 1.000 / 0.5 at −2 D.
  - Peak centreline 4.596 u_m (at x = 0).  The design note's ">4 u_m"
    agrees.
  - **No wall shear stress in the database**, only velocities.  The
    near-wall axial velocity at r = 0.48 changes sign between 11 D
    (−0.00015) and 12 D (+0.0041): **reattachment ≈ 11.0 D** by linear
    interpolation, against the paper's "≈ 10 D".
- **Coarse level, first run** (11 664 cells, `nang` 6, `nrad` 3,
  108 layers).
  - Mesh OK: max non-orthogonality 24.8°, min SJ 0.77.
  - **Not converged after 20 000 SIMPLE iterations** (430 s).
  - Reattachment 5.0 D, separation 0.43 D, peak 4.31 u_m.  Max
    centreline error 18 % of the DNS peak, at 10 D.
  - Too coarse to judge yet, and not converged: try the medium level,
    and check convergence (residual history) before reading anything
    into the 5 D.

**Note from design (2026-10-28): the paper is now in `docs/papers/`**
(`varghese_and_frankel_etal_2007.pdf`).
It is the 2005 preprint ("Under consideration for publication in J.
Fluid Mech.", received 28 January 2005), not the published 2007 version:
cite the published one, but check any number you take against the
Purdue database if you can.  What it settles (page numbers of the
preprint):
- **L = 2D** (eq. 2.1, p. 5; fig. 1).  `../geometry_valve/`'s L = D
  does not match the reference.  s₀ = 0.25, x₀ the stenosis centre.
- **Domain:** 3 D upstream and 16 D downstream of the throat (p. 5).
- **Inlet:** parabolic Poiseuille profile u/u_m = 2(1 − r²) (eq. 2.3);
  **Re = 500 and 1000** on D and the mean inlet velocity (p. 6).  Not
  750 (RESEARCH §7.3 had it wrong; corrected).
- **Outlet:** they add an outflow "nozzle" divergence for stability
  (§2.2.1); a steady laminar `simpleFoam` run at Re 500 shouldn't need
  it, but say if the outlet misbehaves.
- **Reference results, axisymmetric, Re = 500** (§3.1): steady,
  laminar, axisymmetric; peak velocity just downstream of the throat
  **more than 4 u_m**; **reattachment at x ≈ 10 D** from the throat;
  at 15 D the peak is still **more than 3 u_m**.  Axial profiles at
  x/D = −2 … 15 (fig. 4); comparison with Ahmed & Giddens (1983a) at 1,
  2.5, 4, 5, 6 D (fig. 6).  Re = 1000 axisymmetric is "qualitatively
  similar" (not shown).
- **Compare with the DNS, not the experiment.**  The experiment
  reattaches between 4 D and 6 D, which the authors attribute to the
  flow not being fully laminar (p. 9).
- **The paper gives figures, not tables.**  "≈ 10 D" can't carry a 5 %
  gate.
  - **Revised gates:** use numbers from the Purdue database where it
    has them (centreline velocity, wall shear stress), with the 5 % /
    2 % gates as written.
  - Otherwise digitise fig. 4 (profiles at each x/D) and fig. 5(a), and
    state the digitising uncertainty.  Gate on the profile RMS
    difference within 5 % of u_m at x = 1–6 D, and report reattachment
    against "≈ 10 D" without a gate.
- **Eccentric model** (eq. 2.2): the stenosis centre is offset by
  E(x) = (s₀/10)(1 + cos(2π(x − x₀)/L)), so 0.05 D at the throat.
  - At Re 500 it stays laminar but asymmetric, reattaching at about
    14 D (§3.2).
  - At Re 1000 it transitions: the jet breaks down after 6 D and
    reattaches by about 10 D.
  - Out of scope here.  It is the validation case for an eccentric core
    (decision 0021, stage 3) and for non-centred outlines (decision
    0026).
- **Griffith et al. (2008) is not a second source for this geometry**
  (read 2026-10-28; RESEARCH §7.3 corrected).  Their blockage is
  semicircular, not the cosine.  They do measure the recirculation
  length where the wall shear stress is zero, which is the method to use
  here too.

**Resumed 2026-10-29** (after 0043).  Driver redone on
`hexmesh.study.openfoam`.
- **Driver changes:**
  - OpenFOAM is run and read through `hexmesh.study.openfoam`; the
    heated-rod import is gone.  The Poiseuille script is still loaded
    for its simpleFoam dictionaries, `richardson` and `versions`.
  - Its own case writer.
  - The paper's domain: 3 D upstream, 16 D downstream (was 22 D).
  - Both runs next to the constriction are graded to meet its axial
    spacing, L/36 = 0.056 D: upstream 16 layers (ratio 1/1.100), 1–13 D
    80 layers (ratio 1.022, so about 0.2 D at 10 D), then 10 uniform
    layers to 16 D.  The draft's 6 layers upstream and 48 uniform ones
    downstream jumped 4.5–6× in cell length at the constriction.
  - The reference is downloaded into the work directory (it carries no
    licence, so it isn't committed); `--reference` takes a local copy,
    `--no-reference` skips it.
  - Residual history in the JSON; `meshes()` for the gallery.
  - **Bug fixes:** `decomposePar` used `method scotch`, but this build's
    Scotch is a dummy (`docs/integrations/openfoam.md`), so it's now
    `method simple`, slabs along x.  The centreline grouped cells by
    exact x, which splits tapering slabs (a centroid's x shifts with
    radius) and crashed on the medium mesh; it now clusters the
    near-axis cells, split at gaps above 1e-3 D.
- **Coarse level (15 336 cells): no steady solution.**
  - SIMPLE, 20 000 iterations (463 s): the residuals plateau after about
    300 iterations, p 0.33 and Ux 0.013, so the iteration oscillates,
    not slowly converges.  SIMPLEC (U 0.9, p 1) plateaus at about 1e-2;
    relaxation p 0.2 / U 0.5 at about 0.4.  No outlet backflow.
  - Transient `pimpleFoam` from that state, 100 time units (Co 0.8,
    378 s): it settles within 10 units (peak 4.403, mass 1e-8), then the
    jet leaves the axis slowly.  Offset at 6 D: 0.021 → 0.032 D from
    t = 10 to 100, growing about 0.5 % per time unit; reattachment
    6.58 → 6.41 D.  So the axisymmetric state is weakly unstable on the
    coarse mesh, which a steady iteration can't converge to.
  - And even before the drift it is far off: reattachment 6.6 D against
    11.0 D; centreline 13 % of the DNS peak low at 9 D.
- **Medium level (122 688 cells), transient, 60 time units (4 cores,
  2795 s): steady and axisymmetric.**
  - Jet offset 0.0000 D; every quantity constant from t = 10 to 60
    (mass balance 5e-13).
  - Reattachment 11.12 D against the DNS's 11.02 D (+0.9 %);
    separation 0.23 D; centreline peak 4.704 (DNS station max 4.596);
    largest centreline error 2.2 % of the DNS peak, at x = 2 D.
  - So the coarse level's instability is a resolution artefact.

- **SIMPLE fails at the medium level too** (driver, 4 cores, 20 000
  iterations, 2188 s): the same plateau (p 0.40, Ux 0.012), and the
  result is wrong (reattachment 5.0 D, centreline 56 % low at 7 D).
  - **Restarted from the converged transient state** (2 cores, 1500
    iterations), SIMPLE leaves it: the residuals grow from 1e-8 (Ux) at
    iteration 1 to 1.5e-2 by iteration 200, onto the same plateau.  The
    steady solution exists, but SIMPLE's iteration is unstable around
    it.
  - SIMPLEC (`consistent yes`, U 0.9, p 1) from rest: plateau at about
    0.1, 4000 iterations.
- **Opt-in test:** `tests/test_validation.py::test_stenosis_coarse` runs
  the coarse level for 200 SIMPLE iterations (18 s) and checks the
  pipeline: Mesh OK, 15 336 cells both ways, a jet forms.  It is no flow
  check, since nothing converges.
- Scratch cases and logs: this session's scratchpad, `0032x/` (T coarse
  transient, M medium transient, S1/S2 the SIMPLE tests).

**Resumed 2026-10-29 after the design answer: `pimpleFoam` to steady,
k = 2, 3, 4.**
- **Driver:**
  - `pimpleFoam` from rest: Euler, Co 0.8, 2 correctors, the Poiseuille
    solvers, no relaxation.
  - 5-time-unit chunks, restarted from the latest time; steady when the
    centreline (largest change, of the peak) and both reattachment
    measures change < 0.1 % over a chunk.
  - Reattachment both ways: τ_w = 0, and u(0.48 D) = 0, continuous and
    sampled at the 1 D stations.
  - Celik's non-constant-ratio Richardson (fixed-point q(p)); checked
    on synthetic data (recovers p = 2 and the exact value).
  - Mesh geometry computed once per case (982k cells at k4); `--repost`
    re-measures saved fields.
  - Old time directories pruned by the driver, case and processors:
    `purgeWrite` counts only one run's writes (integration note).
- **The centreline measure was biased.**  The quadratic fit over
  0.35 R(x) overestimates the axis value past the throat, where the jet
  is a flat core with a shear layer: +0.06 U at 2 D on k3, which made
  k3 look worse than k2 (2.85 % against 2.17 %).  0.2 R and 0.12 R agree
  to 0.004 U, so the window is now 0.2 R.  All levels re-measured from
  the saved fields.
- **Results (RESULTS.md):** all three gates pass.
  - Reattachment, database measure: 10.98 / 11.02 / 10.97 D (k2/k3/k4)
    against 11.03 D; k4 −0.5 %.
  - τ_w = 0: 11.12 / 11.41 / 11.40 D, converged (k3–k4 0.03 %), +3.4 %.
    The two measures differ by 0.43 D: the velocity 0.02 D from the wall
    turns positive before the wall shear stress does.
  - Centreline: 0.93 % of the DNS peak at most (k4, x = 3 D).  The jet
    is slightly faster than the DNS past the throat at every level.
  - Convergence is oscillatory for most quantities (k3 overshoots), so
    Richardson extrapolation is reported but used only where defined
    (the separation point; 3 centreline stations).
- **Time to steady:** t = 10 (k2), 15 (k3, k4).
- Scratch: this session's scratchpad, `0032/` (logs, `results.json`,
  re-measured `final.json`); the cases in `validation/stenosis/work/`.

**Check after task 0035 (2026-10-30): SIMPLE on OpenFOAM v2406.**
Task 0035 found v1912's buoyant solvers fail on any non-orthogonal mesh,
so SIMPLE's plateau here might have been the same build's fault.  It
isn't: on v2406 (Docker), k2, the same files, SIMPLE leaves the
converged state (Ux 1.8e-6 → 1.5e-2 by iteration 200) and plateaus at
p ≈ 0.4, as on v1912; from rest, p ≈ 0.38.  `pimpleFoam` to steady
stands.  Details in `docs/integrations/openfoam.md`.

## Questions for design

**Q1. `simpleFoam` doesn't converge on this case; which solver and
levels?**  Measured (*Agent notes*):
- SIMPLE (and SIMPLEC, and heavier relaxation) plateaus at every level
  tried, and leaves the steady state when started on it.
- Transient `pimpleFoam` (Euler, Co 0.8, no relaxation) reaches a steady
  state at the medium level within 10–20 time units.
- The coarse level (k = 1) has no steady axisymmetric state at all: the
  jet drifts off the axis, growing about 0.5 % per time unit.  So it
  can't be the coarsest of three levels.
- The medium transient already sits near the gates: reattachment +0.9 %
  (gate 5 %), centreline worst 2.2 % of the DNS peak (gate 2 %), at
  x = 2 D.

Options:
- (a) **`pimpleFoam` to a steady state** (stop when the centreline and
  reattachment change less than a tolerance over 5 time units), levels
  **k = 2, 3, 4**: 123k, 414k and 981k cells, refinement ratios 1.5 and
  1.33, so Richardson with non-constant ratio (Celik et al. 2008 allow
  it).  Estimated cost on 4 cores: about 15 min, 1.5 h and 4 h.  This
  is a change from the task's "steady laminar simpleFoam", so it's
  yours to decide.
- (b) As (a), but k = 2, 4 only (no Richardson, two levels) to halve
  the cost, with the finest level judged against the gates directly.
- (c) Keep `simpleFoam`, and search its settings further (smaller
  relaxation, upwind start, local time stepping with `LTSFoam`-style
  pseudo-time; v1912 has no laminar LTS solver).  I don't expect it to
  work: S1 shows the instability around the fixed point itself.
- (d) A coarser-level fix for k = 1 (higher `nang` / `nrad` base), then
  any of (a)–(c).

I'd take (a).  Shared-machine note: the fine level would occupy 4 of the
8 cores for about 4 hours.

### Design answer (2026-10-29): (a), with three additions

**`pimpleFoam` to a steady state, levels k = 2, 3, 4,** with Richardson
at the non-constant ratio [`celik_and_ghia_etal_2008`].  The task's
"steady laminar `simpleFoam`" is replaced: the reference flow is steady
(the DNS), and pseudo-transient marching is a legitimate way to reach
it when SIMPLE's iteration is unstable around the fixed point.
- **Steady criterion:** the centreline profile and the reattachment
  change by less than 0.1 % over 5 time units, residuals reported.
  Record the time to steady per level.
- **k = 1 is out:** its flow has no steady axisymmetric state (your
  drift measurement).  Report that in RESULTS as a finding: a minimum
  resolution for this case, not a solver failure.
- **Reattachment both ways:** wall shear stress = 0, *and* the database's
  method (near-wall axial velocity at r = 0.48 D changing sign), so the
  comparison with the database's 11.0 D is like with like.  Gate on the
  database's 11.0 D, not the paper's rough "≈ 10 D".
- **Gates unchanged** (reattachment 5 %, centreline 2 % of the DNS peak),
  on the extrapolated values where Richardson works, else the finest
  level.
- **Shared machine:** the fine level uses 4 cores for about 4 h.  Check
  for other sessions' runs first (CLAUDE.md), and run it when the
  machine is otherwise idle.
- Record in `docs/integrations/openfoam.md`: SIMPLE/SIMPLEC plateau on
  this jet at every relaxation tried and leave the converged state, while
  `pimpleFoam` converges.  It matters for every separated laminar case
  (bulges too, task 0055).
- **For the surrogate study** (planned): note the cost per variant at
  the medium level (about 15 min on 4 cores) in *Outcome*; it sets the
  study's budget.

**Design-session checks (2026-10-29):** SIMPLE's plateau is neither
the convection scheme (limitedLinearV, linearUpwind and linear all
plateau) nor the hexmesh mesh (a `blockMesh` O-grid with the same
topology plateaus the same way).  Details in
`docs/integrations/openfoam.md`.  `pimpleFoam` to steady stands.

**Follow-up step (design, 2026-10-29): Re 750 and Re 1000.**  After
Re 500 passes its gates, run the same driver at Re 750 and Re 1000.  The
Purdue database has both (`Axi_stdy/Re750/vel.dat`, `Re1000/vel.dat`;
r, z, u, v, w, 501 radial points per station, x/D −2…15; RESEARCH §7.3).
- **Same geometry, mesh levels and `pimpleFoam`-to-steady route;** only ν
  changes.  The paper reports both as laminar and axisymmetric.
- **Same gates.**  Reattachment from the database's near-wall velocity
  (as for Re 500), and the centreline against the DNS peak.
- **Report the time to steady per Re.**  Re 1000 may need a finer level
  or longer runs; if the coarsest level drifts off-axis as at Re 500,
  say so.
- **Why:** a three-point Re sweep on one mesh topology: a first study-
  runner case and the anchor range of a stenosis surrogate.
- It may also be done as a study (`hexmesh.study`, decision 0025) with
  Re as the parameter, if that's simpler than three driver runs.

## Outcome

**Done (2026-10-30).**  Accepted: every gate passes (RESULTS.md).
- **Files:** `validation/stenosis/run.py` (`pimpleFoam` to steady,
  both reattachment measures, non-constant-ratio Richardson,
  `--repost`), `README.md`, `RESULTS.md`; `tests/test_validation.py`
  (opt-in: the coarse level for 10 time units, 51 s);
  `docs/integrations/openfoam.md` (the `pimpleFoam` recipe and costs,
  `purgeWrite` with restarts, under design's SIMPLE entry).
- **Measurements:**

  | Level | Cells | steady from t | wall time, 4 cores | reattachment (database measure) | τ_w = 0 | max centreline err. |
  |---|---|---|---|---|---|---|
  | k2 | 122 688 | 10 | 760 s | 10.981 D | 11.123 D | 1.32 % |
  | k3 | 414 072 | 15 | 5647 s | 11.019 D | 11.405 D | 1.25 % |
  | k4 | 981 504 | 15 | 17 705 s | 10.970 D | 11.402 D | 0.93 % |

  DNS (database): reattachment 11.025 D.  Mass balance ≤ 1.5e-10.
- **Cost per variant for the surrogate study:** k2, 13 min on 4 cores
  from rest, is the cheapest steady level.  k = 1 has no steady
  axisymmetric state, so it isn't an option.
- **Surprises:**
  - The 0.35 R centreline fit was biased by up to 1.3 % of the peak
    past the throat; a measure, not a flow, problem.
  - Oscillatory grid convergence at ratios 4/3, 3/2: the observed
    orders mean little except for the separation point (3.5).
  - The two reattachment measures differ by 0.43 D, consistently at
    every level.
- **Not applicable:** the D2 (`core="fixed"`) comparison: task 0031
  measured it but didn't keep it as an option.
- **Follow-ups (proposed):**
  - The surrogate study could start each variant from its neighbour's
    steady state (`mapFields`), probably well under 13 min; not
    measured.
  - Re = 750/1000, the eccentric model (out of scope here).
