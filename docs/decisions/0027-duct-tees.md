# 0027 — Tees in rectangular ducts

- **Status:** proposed (recorded 2026-10-28 at the user's request: "This
  sounds like a good idea"; accept to get tasks)
- **Date:** 2026-10-28
- **Tasks:** none until accepted.

## Context

Ducts (decision 0009, tasks 0028/0029) have straights, bends, miters,
splines, closures and transitions.  They cannot branch: `Tee` rejects
rectangular specs ("Tee supports circular pipes only; no rectangular
tees yet (decision 0009)", `tee.py`), and so does `Wye`.  Task 0028 put
rectangular tees out of scope.  Branching is the main gap for the HVAC
use case (`hvac_supply` is a single run) and for cooling-channel
manifolds.

**The duct case is geometrically easier than the pipe tee.**  A pipe
branch meets the main pipe along a saddle curve (RESEARCH §3).  A duct
branch meets a **flat** wall, so the joint is a plane outline:
- a rectangular branch → a rectangle in the wall's plane;
- a round branch (the common HVAC round tap / spin-in) → a circle in the
  wall's plane.

Both are exact by construction (DESIGN §6) with no intersection maths.

The pipe tee's block layout (`tee.py`, DESIGN §7.1) carries over: the
O-grid ring layer turns continuously from the main into the branch, the
turn faces bisect the re-entrant corner, and all three ports keep the
standard 5-patch O-H face.  A duct's O-H face has the same 5-patch
layout (decision 0009), so the layout should port with straight edges
where the pipe tee has arcs.  Not yet prototyped.

## Options

### A. Which branches
1. **Rectangular branch on a rectangular main** (straight tap).
2. **Round branch on a rectangular main.**  The branch core is
   circular; the hole on the flat wall is a circle.  It is an outline
   change inside the junction (decision 0026), with equal counts per
   side.
3. Rectangular branch on a round main (rare in practice).

### B. Which face
A flat duct branches off its **wide** or its **narrow** face.  `roll`
(task 0040) cannot select that: a non-square rectangle's symmetry period
is 180°, so a 90° roll is rejected.  Needs an explicit field, e.g.
`face="wide" | "narrow"` (combined with `roll` 0 / 180 for the side).

### C. API
- **One `Tee` with a `branch=` shape** (`CircleShape` or `RectShape`;
  `branch_radius=` kept as shorthand for a circle).  The template is
  chosen from the main and branch shapes; one fitting for agents and
  users (decision 0019, constraint 4).
- **A separate `DuctTee`.**  Clearer limits per class, but two fittings
  to learn for one concept.

### D. Limits
- The branch must fit inside the face it leaves from, with a margin
  (the turn blocks need room): branch extent < face extent − margin, in
  both directions.  Full-width ("bullhead") branches are out.
- Counts: the branch shares the main's counts per side (as the pipe
  tee's branch shares `nang`).
- Single-layer first; insulated duct tees need junction layers (open for
  pipe tees too).

### E. HVAC fitting shapes
Real duct tees are often "shoe" (45° entry) taps or have splitter vanes.
A shoe is an angled branch: it belongs with laterals (the general-branch
decision, not yet recorded).  Vanes are internals (decision 0021, stage
4 territory).

## Recommendation

- **A1 then A2**: rectangular straight tap first (closest to the pipe
  tee's layout), then the round tap.  A3 not planned.
- **B**: `face="wide" | "narrow"`, default `"wide"`; `roll` 0 / 180
  picks the side.
- **C**: one `Tee` with `branch=`.
- **D**: as above; the margin and any quality limit measured in the
  prototype (decision 0017's approach: prototype, measure, then limit).
- Perpendicular, centred, single-layer.  Shoe taps go to the
  general-branch decision.

Tasks once accepted:
1. Rectangular straight tap: block layout, `face=`, limits, kit cases
   (wide and narrow face, square and 2:1 ducts, branch sizes near the
   limit), quality table.
2. Round tap on a rectangular main.
3. An `hvac_supply`-style branched example (a supply main with two taps)
   and its gallery entry.

## Consequences

- `Tee` gains `branch=` and `face=`; its docstring and `API.md` list
  which main/branch shape pairs are supported.
- **Effect on future expansions:**
  - 0019 (agent SDK): one `Tee` with typed shape fields; the size margin
    in `limits.py` (constraint 6); errors name the face and the limit.
  - 0026 (layer outlines): the round tap is an outline change inside a
    junction, using the same outline protocol; insulated duct tees would
    combine 0026 with junction layers later.
  - 0018 (vascular), 0021 (flow restrictions): none.
  - The general-branch decision (laterals, offset taps, arbitrary roll;
    discussed 2026-10-28, not yet recorded) should cover ducts as well
    as pipes, so shoe taps don't need a separate design.

## Verified vs. assumed

- **Verified (code, 2026-10-28):** `Tee` and `Wye` reject rectangular
  specs; the tee's block layout and its port faces (`tee.py`); a
  rectangle's symmetry period is 180° (decision 0010; `roll` multiples,
  task 0040).
- **Assumed:** that the pipe tee's layout ports to ducts with straight
  edges, and that the round tap needs no new switch class (equal counts,
  "shape is geometry").  The first task's prototype checks both.
