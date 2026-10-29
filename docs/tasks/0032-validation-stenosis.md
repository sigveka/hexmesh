# 0032 — Validation: smooth cosine constriction (Varghese et al.), Re = 500

- **Status:** ready (after 0031 and 0020's re-run)
- **Decision:** [0008 — Profiled sweep](../decisions/0008-profiled-sweep.md); [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md)
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

## Questions for design

_None._

## Outcome

_Not done._
