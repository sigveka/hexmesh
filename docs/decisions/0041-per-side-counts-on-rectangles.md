# 0041 — Per-side counts on rectangles next to circles and shells

- **Status:** accepted (2026-11-06, the user: "follow your recommendation")
- **Date:** 2026-11-05
- **Tasks:** 0100 (step 1: trace the ties).  The B and C tasks follow
  from its outcome.

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
- **Reported, not yet traced** by the design session: the cause of the
  tie in each case.  The coding session's note says the shell case is
  "the spec's own rule".  I found no such check in `core/spec.py` on a
  quick look.
- **Reasoning:** that an O-H patch with `nang_w ≠ nang_h` is valid for
  a circle (a 4-cornered transfinite patch; not built or measured).
