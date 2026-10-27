# 0022 — Convergence order of the O-H section, and a self-similar core square

- **Status:** proposed (no tasks; recorded at the user's request, 2026-10-27)
- **Date:** 2026-10-27
- **Tasks:** none.  Related: task 0033 (finding), decision 0015 (amended
  the same day: order reported, not gated, for O-H sections).

## Context

Two verification cases converge more slowly than second order, and
both point at the O-H core:

- **Poiseuille** (task 0020, RESEARCH §7.4): Δp order 1.25 (a competing
  polygon-area error explained part of it); u_max order 1.91.
- **Heated rod** (task 0033, RESEARCH §7.6): pure diffusion, no p–U
  coupling.  L2 order of T **1.77 → 1.57 → 1.34**, still falling;
  ΔT₀ 1.58 → 1.38 → 1.22.  Extrapolated ΔT₀ is within 0.026 % of exact
  (gate 0.1 %), so the case passes on its values.
  - Slowest convergence inside the **core square** (order 1.23; ring
    1.41–1.73).
  - Max non-orthogonality grows with refinement (23.5° → 41.9°),
    approaching the ~45° of the core-square corner (angles 90° / 135° /
    135°), and the worst faces converge onto those corners.  The mesh
    family does not refine self-similarly there.
  - The error is a near-uniform negative bias, as a local error in an
    elliptic problem would give.

This is a correlation, not a proven cause.

## Options

### A. Accept the O-H order; judge on extrapolated values
Already the rule for gating (decision 0015, as amended).  No change to
any fitting.  Cost: more levels, or a finer finest level, for a given
GCI; Richardson extrapolation with a non-asymptotic order is less
reliable, which GCI's safety factor covers.

### B. A corner-free control mesh (establishes cause)
Solve the heated rod on a mesh with the same resolution but no
core-square corner kinks (e.g. an elliptically smoothed O-H, or a mesh
whose inner-square sides bulge so grid lines cross the core/ring
boundary smoothly).  If the order returns to ≈ 2, the corners are the
cause.  Needs a section that hexmesh can't build today, made by hand
for the test only.

### C. A core square that refines self-similarly
Change the section so the grid stays smooth under refinement: bulged
(curved) inner-square sides, an inner-square size (`OH_RATIO`, 0.6
today) that depends on `nang`/`nrad`, or smoothing of the transfinite
core.  This changes the cross-section of every fitting: every face
builder, the tee/wye/drum block layouts, port signatures (decision
0011: a geometry change, still class 0 if counts are unchanged), and
every mesh.

## Decision (recommended)

**A now** (decision 0015 amendment; task 0033 accepted on extrapolated
values, with one extra level to see whether the order levels off).
**B before C**: C is considered only if B shows the corners cause the
loss *and* a case needs the order (e.g. GCI too large at affordable
cost).  Neither is tasked.

To settle before any task: the task 0033 k = 16 level (does the order
level off near 1.3, or fall toward 1?), and whether any validation case
fails its gate because of it.

## Consequences

- None now.  If C is chosen: DESIGN §5 (section topology) amended; every
  mesh changes; conformance kit and examples re-measured.
- **Effect on future expansions:**
  - 0018 (vascular): wall shear stress depends on the ring, not the
    core; a smoother core helps centreline quantities only.  C would
    apply to vascular sections unchanged.
  - 0019 (agent SDK): none (no API change; `OH_RATIO` is internal).
  - 0021 (flow restrictions): the two-fluid-layer orifice section has
    the same core square.  C must stay behind the one section-geometry
    abstraction (0021, constraint 4) so eccentric and contour cores can
    join.

## Verified vs. assumed

- **Verified:** the orders, the regional errors and the
  non-orthogonality trend (task 0033 RESULTS, 2026-10-27; task 0020).
- **Assumed:** that the core-square corners cause the loss of order;
  that option C would restore it.
