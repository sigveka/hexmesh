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

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
