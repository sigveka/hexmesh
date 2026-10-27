# 0005 — `n_outer = 8` as a sub-partition of the 4-corner grid

- **Status:** proposed
- **Date:** 2026-10-24
- **Tasks:** none (proposed decisions get no tasks)

## Context

`n_outer` sets how many structural corners a cross-section has.
Junctions need corners at 0°/90°/180°/270° (DESIGN §7), which is why
`n_outer = 8` is the stated target.  But:

- the current `build_oh_circle8` builds an 8-arc inner boundary and one
  8-sided centre patch (`hexmesh/faces/oh_circle.py:34–36`).  That patch
  can't bound a transfinite hex block, which is the last row of DESIGN §9
  "Current deviations";
- DESIGN §10 leaves open whether `n_outer` is set per network or per
  interface; mixed values would need transition templates;
- CLAUDE.md's table already describes `n_outer = 8` as having 4 centre
  patches (a 2×2 square grid), not an 8-sided one.

RESEARCH §9.1–9.2 (dual view, after `harris_and_benzley_etal_2004`):
adding block boundaries along existing grid lines adds no twist planes,
so the mesh connectivity is unchanged.  With `nang` even, the 4-corner
face already has grid lines through 0°/90°/180°/270°: the middle line of
each ring patch, and the two centre lines of the core.

## Options

### A. Keep `n_outer = 8` as a separate cross-section (octagonal core)
Fix the 8-sided patch by splitting it some other way.  The meshes differ
from `n_outer = 4`, so switching between them needs transition templates,
and the §10 question stays open.

### B. Define `n_outer = 8` as the 4-corner grid plus cut lines
Cut the 4 ring patches at their middle grid lines (8 ring patches) and
the core at its two centre lines (2×2 core).  Same twist planes, same
node connectivity.  Generalizes: `n_outer = 4m` cuts each ring patch into
m and the core into m×m, which needs `nang % m == 0`.  That is the
existing constraint `nang % (n_outer // 4) == 0`.

### C. Drop `n_outer = 8`; use `n_outer = 4` with a π/4 interface roll at junctions
Corners land at 0°/90° by roll alone (RESEARCH §4.4).  No new face
builder.  But a fitting whose template needs corners at *both* the 45°
and the 0° positions can't have them.

## Decision

Not decided.  **Recommendation: B.**  It makes `n_outer` a block-partition
choice instead of a mesh-topology parameter, removes the §9 deviation,
and settles §10.

To settle first:
1. **Connectivity check.**  Mesh one face as the 4-corner face and as its
   8-corner sub-partition (same `nang`, `nrad`, grading).  Compare node
   count, element count and element→node connectivity after canonical
   ordering.  Also report the largest node displacement.
2. **Node positions.**  By symmetry, the cut lines are straight radial
   lines along the axes for uniform or bump angular grading.  Check that
   gmsh's transfinite interpolation on the half-patches puts interior
   nodes where the full patch did, or measure the shift.

Both are experiments, not production code.  They can be run in a design
session, or as a spike task if spike tasks are allowed for proposed
decisions (currently they are not).

## Consequences (if B is accepted)

- **A4 port type** compares the mesh-level type (boundary kind, layer
  stack, `rot`, `nang`, `nrad`).  The partition is chosen per interface,
  as the finest any fitting on it needs.  Every fitting must accept a
  port face with a finer partition than its own template, by splitting
  its blocks along the same grid lines.  Sweeps carry the finer partition
  along their whole length.
- **DESIGN §6.1 corner identity** is unchanged.  Corner k at
  `π/4 + rot + k·2π/n_outer` includes the 4-corner positions as every
  other corner.
- **DESIGN §6.1/§8:** since decision 0010, roll is absorbed modulo the
  section's symmetry period P.  Under B, the circular row's P becomes
  π/2 for every `n_outer` (the mesh repeats every 90°).  Twist never
  exceeds π/4.
- **DESIGN §9:** remove the `n_outer = 8` row once
  `build_oh_circle8` is replaced.
- **DESIGN §10:** remove "`n_outer` per network or per interface?".
- **DESIGN §7:** the reason for `n_outer = 8` becomes "partition the
  junction needs", at no mesh cost.

## Verified vs. assumed

- Verified: `build_oh_circle8`'s 8-sided centre patch
  (`oh_circle.py:34–36`).  The dual-view statement comes from
  `harris_and_benzley_etal_2004` §4.1.
- Assumed, to be checked as above: identical connectivity in gmsh, and
  small or zero node displacement.
