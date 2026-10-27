# 0015 — Exact walls in straight slabs, and how convergence is judged

- **Status:** accepted
- **Date:** 2026-10-26 (accepted 2026-10-26 by the user: "write them up")
- **Tasks:** 0025, 0026, and the revised 0020

## Context

Task 0020 (laminar Hagen–Poiseuille, three levels) was blocked with
three questions.  Evidence: `validation/poiseuille/RESULTS.md`, task
0020's *Questions for design*, `docs/integrations/gmsh.md`, and the
design session's checks (RESEARCH §7.4).

1. **Straight walls are not exact.**  A `Straight` is one slab with
   `n_layers` axial layers.  Its side surfaces are OCC plate fillings
   (`addSurfaceFilling`), and gmsh puts the interior nodes on them.
   - Single-layer pipe (agent): nodes up to 1.08 % of R inside the
     circle.
   - Two-layer pipe (design session, 16 layers): nodes from −0.15 % to
     +0.69 % of R off the circle, on the outer wall **and** on the
     fluid/steel interface.  The same at `nang` 6 and 24.
   - Consequence: Δp stuck at +2.6 % at every level.  The sagged
     cross-section's area explains it within 0.1 %.
   - DESIGN §6 says interior nodes follow from the exact boundaries.
     This is not true for multi-layer plate-sided slabs, and the case is
     not in the deviations table (only the tee's is).
   - Affected: every `Straight`, so every `extend_open_ends` run, and the
     material interfaces of CHT meshes.  `Bend`, `Reducer`, `SplinePipe`
     and `Closure` place one layer per slab and are exact.  `MiterBend`
     slabs are already ruled (`sweep._ruled`).
2. **"Δp converges at first order"** with exact walls (diagnostic run).
   The errors measured against the circle mix two errors of opposite
   sign:
   - the mesh's cross-section is the inscribed 4·`nang`-gon, not the
     circle.  The inlet-flow deficit, 1.138 / 0.285 / 0.071 %, equals the
     polygon's area deficit exactly.  This geometric error is second
     order and pushes Δp up;
   - the discretisation error pushes it down at the coarse levels.

   Separated (RESEARCH §7.4), the remainder is −0.69 / −0.08 / +0.03 %
   and changes sign.  Richardson extrapolation of the three levels gives
   Δp within +0.03 % and u_max within −0.007 % of exact; u_max's observed
   order is 1.91.  An order computed from |e| against the circle has no
   meaning here.
3. **No global refinement.**  The validation script scales `nang`,
   `nrad` and every `n_layers` by hand.  Every convergence study on a
   real network would repeat that.

## Options

### Q1. Exact walls in straight slabs
- **A. Ruled side surfaces** (`addBSplineFilling(type="Stretch")`) for
  straight slabs, as miter slabs already have.  Between two identical,
  parallel arcs a ruled surface is the exact cylinder.  Measured: wall
  nodes on the cylinder to 4e-16 R, min SICN unchanged.  No new
  entities.
- **B. One station per axial layer**, like `Reducer`.  Equally exact,
  with n_layers × more OCC entities, so slower to build and mesh.
- **C. List it as a deviation.**  Rejected: it biases every straight run,
  and DESIGN forbids new deviations.

### Q2. How convergence is judged
- **A. Keep gating on the order from |e| against the exact circle.**
  Rejected: it mixes the polygon error with the discretisation error.
- **B. Gate on signed errors against a reference for the meshed
  geometry, plus Richardson extrapolation**, following the standard
  procedure [`celik_and_ghia_etal_2008`].
- **C. Revisit the O-H corner topology now** (inner-square size or
  bulged sides).  Deferred: not supported by the evidence (see Q2's
  context).  Max non-orthogonality (23° → 33° → 38°) is expected to
  level off near the 135° corner kink's limit; task 0020 measures one
  more level to check.

### Q3. Global refinement
- **A. None**: scripts scale parameters themselves.
- **B. `Assembly.refined(k)`**, integer k, built from the saved
  description (decision 0001's Intent layer).

## Decision

- **Q1: A.**  Straight slabs use ruled side surfaces.  The conformance
  kit gains a wall-exactness check for every sweep.  DESIGN §6 is
  amended (below).
- **Q2: B.**  Verification cases report signed errors and gate on
  Richardson-extrapolated values.  For a circular pipe the reference uses
  the cross-section actually meshed.  An observed order is reported, and
  gated only where no geometric error competes with it (u_max here).
  The O-H topology is not revisited now.
- **Q3: B.**  `Assembly.refined(k)` for integer k ≥ 1.

**Amendment (2026-10-27, accepted by the user; task 0033).**  On O-H
sections the observed order is **reported, not gated**, for every
quantity: the heated rod (pure diffusion, no competing geometric error)
converges at L2 order 1.3–1.8, falling with refinement, slowest in the
core square.  Gates are the extrapolated value against the exact one
and the fine-level error, with GCI reported.  Use the observed order in
GCI (not an assumed 2).  Cause and remedies: decision 0022 (proposed).

### DESIGN §6 amendment (applied 2026-10-26)

Appended to "Exactness lives in curves and nodes":

> A filled surface may carry interior mesh nodes only where it is the
> exact surface.  A slab with several axial layers therefore needs exact
> side surfaces: straight slabs use ruled surfaces (a ruled surface
> between two identical parallel arcs is the cylinder).  Where no exact
> surface is available, use one axial layer per slab.  The conformance
> kit checks every wall and interface node against its analytic surface.

## Consequences

- **Task 0025:** ruled straight slabs and the wall-exactness check.
  Every mesh with a multi-layer `Straight` changes slightly (node
  positions only; topology and cell counts are unchanged).
- **Task 0026:** `Assembly.refined(k)`.
- **Task 0020** (revised acceptance, depends on 0025): re-run with exact
  walls and judge by the new rules.
- The tee's run slabs (deviations table) also have plate sides with
  several layers.  Ruled sides may fix them too; a follow-up once 0025
  shows the method.
- RESEARCH §7.4 records the measurements.

## Verified vs. assumed

- **Verified:**
  - the sag, by the agent (single layer) and the design session (two
    layers, both surfaces, `nang` 6 and 24);
  - the polygon area deficit equals the measured inlet-flow deficit at
    all three levels;
  - the Richardson numbers above, computed from `RESULTS.md`.
- **Assumed:**
  - ruled surfaces are exact for every straight slab, including the
    material interfaces.  The agent measured the outer wall; task 0025
    checks all;
  - max non-orthogonality levels off near the corner limit.  Task 0020
    measures it.
