# 0041 — Per-side counts on rectangles next to circles and shells

- **Status:** accepted (2026-11-06, the user: "follow your recommendation")
- **Date:** 2026-11-05
- **Tasks:** 0100 (step 1: trace the ties; done), 0101 (B: shells
  around rectangles).  C is held (see "After task 0100").

## Context

Task 0098's advisor found that some rectangular sections can't take
different counts on their two sides.  Its Agent notes: `nang = nang_w =
nang_h` wherever

- a `Transition` joins a circle to a rectangle, or
- a layer stack has a rectangular core and shells.

The rectangle's short side is then as fine as its long side.  Density
is also shared by every section in an assembly (CLAUDE.md, "Parameter
separation"; a `Reducer` changes radii only).  So one such fitting sets
the counts for the whole network.  With water at 2 mm/s, "medium"
(task 0098, *Outcome*):

| Example | Cells |
|---|---|
| circle networks | 22k–117k |
| `rect_duct` (H, untied) | 270k |
| `lagged_duct` | 0.9M |
| `duct_transition` | 2.6M |
| `hvac_supply` | 2.7M |
| `hvac_branched` | 10M |
| `cooling_channels` | 20M |

The axial counts make it worse: the straight-run aspect limit (6,
task 0098 Q7) is measured against the smallest cross-section cell, so
long runs follow the tied short side.

HVAC ducts are mostly rectangles with insulation, and many have a
round connection.  This is the main use case for rectangles, so the
cost matters for users, not only for the examples.

## Options

### A. Keep the tie; document it

The advisor already reports it, and the budget lowers the counts.
- For: no change.
- Against: at a fixed budget, ducts get coarser cells than circles.
  The H duct already converges more slowly per cell (3–4 % f·Re error
  at k = 1, against 0.9 % for Poiseuille).

### B. Shells around a rectangle carry per-side counts

A shell outline around a `RectShape` core keeps `nang_w` and `nang_h`
side by side (`RectShape.side_count(k)` already returns per-side counts,
`core/shape.py:323`).
- For: a shell is a ring of 4 side patches, so each side's count only
  has to match the core side it sits on.
- Against: a rounded or circular shell around a rectangle would need B
  and C both.

### C. A circle meeting a rectangle takes unequal arc counts

A circle's four quarter-arcs take `(nang_w, nang_h, nang_w, nang_h)`
instead of `nang` each.  Its O-H centre patch becomes `nang_w × nang_h`:
still 4 corners, still transfinite (DESIGN §9).
- For: the transition then joins a rectangle with any side counts.
- Against: the circle's cells are uneven around it.  The circle's
  calibration (`poiseuille`) is uniform, so the advisor would mark it
  `"validated": false` above some ratio.  "`nang`: divisions per 90°
  arc, shared by every layer" changes for circles in CLAUDE.md and
  DESIGN.

### D. Density per section group

Let density vary between sections separated by a fitting that can
change it (a counts-changing `Transition` or `Reducer`).
- For: the most general.
- Against: it breaks the topology/density split that `Reducer` rests
  on, and a fitting that changes counts in a structured mesh needs a
  non-conformal or hanging-node face.  That's against DESIGN's
  "conformal by construction".  Listed for completeness; not
  recommended.

## Decision

**Recommendation:** first verify where the tie comes from (a small
coding task: name the check or code that ties the counts in each case).
Then:
- **B** if the shell tie is only a spec rule or an advisor choice, not
  a geometric need;
- **C** for transitions, with a limit on the ratio `nang_w / nang_h` (an
  `info` limit, calibrated later);
- **A** for everything else, with the report naming which fitting ties
  the counts and its cost.

**Accepted** 2026-11-06 by the user, as recommended:
1. Task 0100 traces each tie first.
2. Then B for shells and C for transitions, where 0100 shows the tie
   isn't a geometric need.  C's uneven circle is accepted in principle,
   with a ratio limit.
3. A for the rest.

The design session writes the B and C tasks from 0100's outcome.  If
0100 shows a tie is geometric, that case falls back to A, and this
record gets a note.

## Consequences

- B: no DESIGN change if it holds.  The shell code and the advisor
  lose the tie for rectangles.
- C: CLAUDE.md's `nang` definition and DESIGN §9 gain the unequal-arc
  circle.  The section signature (task 0082) compares per-arc counts.
  The O-H ↔ H switch (decision 0036) must accept it.
- The advisor (0098) re-measures the five tied examples.
- **Future expansions:**
  - vascular networks (0018): circles only, so not affected;
  - the agent SDK (0019, 0040): lower budgets for HVAC networks;
  - flow restrictions (0021): not affected;
  - the simulation suite (0030): not affected;
  - pipe-in-pipe and multi-core (0035): B and C carry over to an
    annular or rectangular carrier.

## Verified vs. assumed

- **Measured** (task 0098): the cell counts in the table.
- **Traced** (task 0100): the cause of each tie, below.  *Correction:*
  the design session's quick look missed the shell check; it is
  `PipeSpec._check_counts` (`core/spec.py:571`), decision 0026 item 3.
- **Reasoning:** that an O-H patch with `nang_w ≠ nang_h` is valid for
  a circle (a 4-cornered transfinite patch; not built or measured).

## After task 0100 (2026-11-06, design session; the user: "yes")

**What 0100 found** (its *Outcome* has the table, with file and line):
- **Shells around a rectangle:** only a spec rule,
  `rect_stack_counts_unequal` (decision 0026 item 3, which left unequal
  counts as "a later class-2 question").  With it bypassed, untied
  stacks build, validate and mesh conformally: H and O-H, one and two
  shells, a rectangular outer, a straight and a 90° bend.  **B holds.**
- **A circle beside a rectangle** (a circle → rectangle `Transition`, a
  circular shell round a rectangle, a round duct tap, a non-square
  `BundleSpec` tile): geometric, because `CircleShape` carries one
  count.  Only C lifts these.
- **Rectangle → rectangle `Transition`:** already untied.

**The gains.**  B alone takes `lagged_duct` from 936k to 527k cells
(−44 %).  The other four (`duct_transition`, `hvac_supply`,
`hvac_branched`, `cooling_channels`) are tied by transitions.

**C's gain, estimated** (design session; arithmetic, not built).  Under
C a circle's quarter-arcs take the rectangle's counts (a, b, a, b)
instead of a each, with a the long side's count and b = a / (a/b) the
short side's.  Per O-H or H section with a core of a × b and n rings
of `nrad` cells:

  cells(C) / cells(tied) = (a·b + 2(a + b)·n_r) / (a² + 4a·n_r)

where n_r is the total ring count.  That lies between b/a (no rings)
and (a + b)/(2a) (rings dominate).  At a count ratio a/b = 2
(`lagged_duct`'s 60 × 30; the other four examples' ratios aren't
checked): **0.50 to 0.75**, so C would cut them by 25–50 %
(`cooling_channels` 20M → about 10–15M), if the axial counts don't
change.  A flatter duct gains more: at a/b = 4, 0.25 to 0.63.  The
axial counts follow the smallest cross-section cell, which C doesn't
change when the cells are square.  The ratio applies to every section,
circles included, so it bounds the whole assembly.

**So C is held.**
- Its cost is high: `nang`'s definition in CLAUDE.md and DESIGN, the
  section signature's period (task 0082), `Transition`, the round duct
  tap and the switch.
- Its gain is at most 2×, while the four examples are 4–30× over a
  circle network of the same reach.
- The cause is that one density runs through a whole network: one
  rectangle's long side sets every circle's count.  The question that
  matters is whether the count can change conformally at a fitting
  (refinement templates in a transition, for example).  That's a new
  design question.  Today's answer stays option D: not conformal, so
  not done.  It isn't opened yet.
- C stays the next step if a user needs a circle beside an unequal
  rectangle for its own sake (a non-square bundle tile, say), not for
  cost.

**Amends** decision 0026 item 3 (task 0101): a stack of rectangular
outlines may have `nang_w ≠ nang_h`, each outline taking the core's
counts.  A circular outline in a stack with a rectangle keeps equal
counts.

## C's form, if it is done (2026-11-06, design session)

**The user agreed** to the count per arc (2026-11-06), and **C stays on
hold**: no task.  These points fix its form, so that a later task
doesn't build a narrower version:

1. **General per-arc counts, not two alternating counts.**  Each of a
   circle's arcs carries its own count.  The main user is decision
   0035 stage B: cell-decomposed multi-core sections (umbilicals)
   have irregular Voronoi cells, whose sides each need their own count.
   A round duct tap on a rectangle, a circle → rectangle `Transition`
   and a non-square `BundleSpec` tile are special cases.  Hexagonal
   rod-bundle cells also need `n_outer = 6`, which is a separate change.
2. **In the generic `CircleShape`, not a special circle type.**
   - The precedent: `RectShape` holds `nang_w` and `nang_h`, and a
     square is the case where they are equal (`core/shape.py:26`).
   - A second circle type would break "one description per concept"
     (DESIGN §3.1) and raise the shape-specific-site cap, which only
     goes down.
   - `CircleShape(radius, nang=…)` keeps its meaning: one count on every
     arc.  Per-arc counts are an optional field.
3. **Fittings opt in.**  A fitting that doesn't handle unequal arcs
   rejects them with a coded error, as `check_supported` rejects
   `n_outer = 8` today.  Support arrives fitting by fitting.
4. **Topology and density.**  A circle's count *pattern* (which arcs
   are equal, and their ratios) is **topology**: it sets the section's
   symmetry and signature class.  A uniform multiplier on all arcs is
   **density**.  So `Reducer`'s "same topology and density" still holds,
   and `refined(k)` still nests.  CLAUDE.md's parameter list and DESIGN
   gain this sentence when C is tasked.
5. **Acceptance for the C task:** the 28 example meshes byte-identical,
   and every existing port signature unchanged.

**An ellipse: an idea only** (the user, 2026-11-06: "just an idea,
nothing planned").  Making the
circle a special case of an ellipse (a = b) follows the same "one
concept" argument.  It is kept out of C, as a separate question:
- **For:**
  - elliptical sections in vascular networks (decision 0018) and
    ovalised bends;
  - an exact laminar solution (Poiseuille in an ellipse), a V1
    validation case;
  - unequal arcs arise naturally, so it would use C's per-arc counts.
- **Against, and to settle first:**
  - **Shells:** an offset of an ellipse isn't an ellipse.  A wall of
    constant thickness needs a parallel-curve outline (a spline), or
    the wall is taken as a second ellipse with varying thickness.
  - **Every circle site is analytic:** exact wall projection, the
    tee/wye intersection curves (RESEARCH §3, §4), bend-radius checks and
    the advisor's calibration.  Each needs an elliptical form or a
    rejection.
  - **OCC:** the realised curve must stay a `gp_Circ` when a = b, so
    that meshes stay byte-identical.  That is a dispatch, as with
    squares, but it must be checked.
  - **One generalisation at a time:** doing per-arc counts and the
    ellipse in one change would make a failed byte-identical check hard
    to attribute.
- **HVAC note:** HVAC's "flat oval" ducts are stadiums (a rectangle with
  semicircular ends), not ellipses.  If HVAC is the motivation, a
  stadium shape matters more.
- **State:** nothing planned.  Kept here so the points above aren't
  lost.

## Amendment: C is off hold, for 1.0 (2026-11-08; the user: "per-arc count yes", accepted with decision 0042)

Per-arc counts on `CircleShape` are a 1.0 exit criterion (decision
0042, criterion 3, milestone 0.7), in the form fixed above under "C's
form, if it is done": general per-arc counts in the generic
`CircleShape` (an optional field; `nang` keeps its meaning); fittings opt
in, rejecting unequal arcs with a coded error until they support them;
the count pattern is topology, a uniform multiplier density; the 28
example meshes and every port signature unchanged.  They are reviewed
with the rest of the public surface before the 1.0 freeze.  Tasks follow
in milestone order.  The ellipse stays an idea, outside 1.0.
