# 0005 — `n_outer = 8` as a sub-partition of the 4-corner grid

- **Status:** accepted (2026-11-02 by the user: "accept 0005")
- **Date:** 2026-10-24 (accepted 2026-11-02, after the two experiments
  below were run in the design session)
- **Tasks:** 0088

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

**Accepted 2026-11-02: B.**  `n_outer = 4m` is the 4-corner O-H face
cut along existing grid lines: each ring patch into m, the core into
m × m.  It is a block partition, not a different mesh.

**The two experiments** (RESEARCH §9.2, measured 2026-11-02):
1. **Connectivity: identical** at `nang` 4 to 24, with and without
   radial grading.  Same node and element counts; element→node sets
   equal after matching nodes by position.
2. **Node positions:**
   - **ring cuts: exact** (2e-15 R);
   - **core cuts: not with straight, uniformly meshed cut lines.**  The
     core's middle isoline is straight, but its nodes are not uniform
     (the inner sides are bulged arcs).  The miss is up to 0.0043 R,
     a fixed absolute offset, so 2 % of the local spacing at `nang` 4
     and 10 % at `nang` 24.

**Condition from experiment 2 (part of this decision):** the core
cut-line nodes are placed on the full core patch's discrete TFI
isoline.
- That isoline is computable before GMSH from the boundary nodes, for
  any O-H shape (circle, rectangle, blend).  For the circle it has a
  closed form (RESEARCH §9.2).
- A Coons patch restricted to a sub-rectangle is the Coons patch of
  that sub-rectangle, so exact cut-line nodes give exact interior nodes.
- With that, an `n_outer = 8` face reproduces the `n_outer = 4` mesh to
  round-off, and B's "no mesh change" holds.

**Rules:**
- An interface carries the **finest partition any fitting on it
  needs**.  This answers DESIGN §10's "`n_outer` per network or per
  interface?": per interface, resolved like density.
- The symmetry period P of a circular O-H section is **π/2 for every
  `n_outer`**.
- `n_outer` is an O-H layout parameter.  The H layout (decision 0036)
  has 4 corners and no partition; `n_outer ≠ 4` with `layout="h"` is an
  error.

**Scope now (DESIGN §6.1, "not built on speculation"):** no fitting
needs `n_outer = 8` today.  The tee works with 4 (§7.1), and decision
0017 found the wye doesn't need 8.  So task 0088:
- builds the sub-partition in the O-H layout;
- replaces `build_oh_circle8`;
- lets sweeps carry `n_outer = 8`;
- proves mesh equality with `n_outer = 4`.

**Deferred** until the first junction template that needs a finer
partition: fittings accepting a port partition finer than their own
template, and the assembler resolving the partition per interface.
Until then, both sides of an interface have the same `n_outer`, as
today.

## Consequences

- **DESIGN.md (applied 2026-11-02):**
  - §6.1 corner table: circular P = π/2 for every `n_outer`;
  - §7: `n_outer` described as a partition at no mesh cost, with the
    interface rule;
  - §9: the `n_outer = 8` row now names the sub-partition as the target
    and task 0088;
  - §10: "`n_outer` per network or per interface?" removed (answered).
- **CLAUDE.md:** the open question becomes the decision; the table row
  ("rejected") changes when task 0088 lands.
- **Decision 0010:** P for circular O-H sections changes from 2π/`n_outer`
  to π/2.  Roll handling is otherwise unchanged; twist never exceeds
  π/4.
- **Harder:** the core cut lines need exact node placement, a
  pre-computed distribution that gmsh's transfinite laws (Progression,
  Bump) can't express.  Task 0088 finds the mechanism; relocation
  between 1-D and 2-D meshing (as decision 0029 relocates wall nodes) is
  the first candidate.
- **Effect on future expansions:**
  - 0018 (vascular): bifurcation split planes can land on block corners
    without a π/4 roll, at no mesh cost, once a template asks for it.
  - 0019 (agent SDK): none (`n_outer` stays a spec field).
  - 0021 (flow restrictions): none.
  - 0030 (simulation suite): none.
  - 0035 (multi-core): "a partition along existing grid lines" is a
    general section-layout operation; the shared section interface (task
    0084) should allow a layout to offer partitions.

## Verified vs. assumed

- **Note (2026-11-11, task 0088 done).**  Built and measured
  (`tests/test_n_outer_partition.py`; RESEARCH §9.2):
  - **The Coons argument below doesn't hold for gmsh.**  gmsh's
    transfinite fill parametrises a patch by the averaged segment
    lengths of its opposite sides, not as a Coons patch, so a
    sub-rectangle's fill isn't the restriction of the full patch's:
    with exact cut lines alone, the sub-patch interiors are 1.3e-4 R
    off.  So the partition's nodes are set after `generate(2)`
    (decision 0029's mechanism) and recorded in `asm.corrections` as
    `sub_partition` (decision 0046's amendment).  Largest move 4e-3 R
    (0.026 R with `mbmp` 1.3).
  - **Connectivity identical**, 2-D and 3-D, for every fitting the task
    covered; node positions within 4e-15 R in 2-D faces and one-layer
    slabs.  In a multi-layer `Straight` the two meshes are 1.4e-7 R
    apart, and the 8-corner one is the closer to the exact extrusion
    (2.7e-9 R against 1.3e-7 R): gmsh fills a curved face in its own
    parameter space.  Bound 1e-6 R plus each mesh's distance from the
    extrusion (the user's answer).
  - **Second order:** arcs identical; an `n_outer = 8` `Transition`'s
    mid-face nodes differ by up to 4e-4 R (accepted, documented in
    API.md: the user's answer).
  - `n_outer` 12 and up stay rejected (`section_not_supported`; the
    user's answer).  Junctions still take `n_outer = 4` only
    (*Deferred* above).
  - DESIGN §9's `n_outer` deviation row is removed, and §6's two
    "if decision 0005 makes…" phrasings now state P = π/2 for a circle
    at every `n_outer`.

- **Verified (2026-11-02):**
  - connectivity identity;
  - ring-cut exactness;
  - the core-cut offset and where it peaks (scripts in the design
    session's scratchpad; method and table in RESEARCH §9.2);
  - the closed form of the circle's core isoline, which matches the
    measured peak;
  - `build_oh_circle8`'s 8-sided centre patch (`oh_circle.py:34–36`).
- **Assumed:**
  - that relocating cut-line nodes before 2-D/3-D meshing makes gmsh's
    transfinite fill reproduce the full-patch nodes in 3-D slabs, as the
    Coons argument says;
  - that rectangle and blend O-H cores behave like the circle (their
    ring isolines are straight and linear, so likely; task 0088
    measures them).
