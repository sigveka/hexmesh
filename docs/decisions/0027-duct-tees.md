# 0027 — Tees in rectangular ducts

- **Status:** accepted (2026-10-29, by the user: "accept the duct
  tees"), as recommended below
- **Date:** 2026-10-28
- **Tasks:** 0057 (rectangular straight tap), 0058 (round tap on a
  duct), 0059 (branched HVAC example)

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
  *(Amended 2026-10-30: full width across is allowed, and is the first
  case; see the amendment below.)*
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

## Decision

**The recommendation above, accepted 2026-10-29:**
- **A1 then A2:** rectangular straight tap first, then the round tap.
- **B:** `face="wide" | "narrow"`.
- **C:** one `Tee` with `branch=`.
- **D:** the limits as listed.
- Perpendicular, centred, single-layer.

Added since the proposal:
- **Quality limit:** the predicted corner SJ of the layout, with the two
  tiers of tasks 0047/0052 (reject < 0.1, warn < 0.3, with a hint).
- **Walls:** exact as OCC surfaces where they are planes (every
  rectangular duct wall).  A round tap's branch walls may use decision
  0029's node projection, as the pipe tee does.
- **Shoe taps** go to the general-branch decision (0031).

### Amendment (2026-10-30, after task 0057's Q1): full-width taps first

**Finding (task 0057, checked on paper against `tee.py`):** a duct's O-H
corners are its creases (the edges y = ±a, z = ±b).  With a tap narrower
than its face across (q < a), the pipe tee's layout puts a crease inside
block faces in two places: the station's side edge, and the slab's
corner edge.  So the walls fold and aren't planes.  Making the creases
block edges needs six station vertices where the port has four, which
either changes the port faces (against DESIGN §7.1) or needs new blocks.
With **q = a** the layout ports exactly:
- the station's top corners are the duct's corners;
- the slab corners run along the creases;
- every wall face is a plane;
- the ports are standard.

**Superseded in part (2026-10-30, the user: "aim for B right away"):**
full-width taps are on hold.  The layout of decision 0033 is prototyped
first (task 0069), and full-width taps come back only if it doesn't cover
them.

**Decision (as amended, now on hold):**
- **D changes:** a tap that spans its face **across** (q = a) is
  allowed, with any extent along the duct (p) within the room checks.
  That's common in HVAC: a side branch as tall as a flat main
  (600 × 300 main, 300 × 300 branch off the narrow face).  A narrower
  branch run follows through a `Transition`.
- **Narrower taps (q < a)** and **round taps** (0058) wait for a junction
  layout that keeps the creases on block edges: decision 0033
  (proposed).
- **Rejected:** folding the faces and projecting nodes onto the box
  (decision 0029).  The crease would be cut by a cell width near the
  junction, so the walls wouldn't be exact.

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
  - The general-branch decision (0031, proposed: laterals, offset taps,
    arbitrary roll) covers ducts as well as pipes, so shoe taps need no
    separate design.
  - 0028 (multi-layer junctions) and 0026 (layer outlines): insulated
    duct tees combine them later; single-layer here.
  - 0030 (suite): none.

## Verified vs. assumed

- **Verified (code, 2026-10-28):** `Tee` and `Wye` reject rectangular
  specs; the tee's block layout and its port faces (`tee.py`); a
  rectangle's symmetry period is 180° (decision 0010; `roll` multiples,
  task 0040).
- **Assumed:** that the pipe tee's layout ports to ducts with straight
  edges, and that the round tap needs no new switch class (equal counts,
  "shape is geometry").  The first task's prototype checks both.
