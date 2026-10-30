# 0033 — Junction layout for duct taps narrower than their face (and round taps on ducts)

- **Status:** accepted: **B, the pillowed tap** (2026-10-30, on task
  0069's prototype measurements; prototyping accepted by the user: "aim
  for B right away").
- **Date:** 2026-10-30
- **Tasks:** 0069 (prototype, done); 0070 (merge into `Tee`); 0057
  returns for full-width taps.  Blocks 0058 (round tap) and narrow rectangular
  taps; 0063 (shoe taps) depends on it for anything but full-width taps.

## Context

Task 0057 found that the pipe tee's layout doesn't carry over to a duct
tap narrower than its face (decision 0027's amendment).  The duct's O-H
corners are its creases, and a tap of half-width q < a makes the
creases cross block faces.  Full-width taps (q = a) port exactly and
go first.  This decision is about the rest: rectangular taps with
q < a, and round taps (whose O-H corners sit on the hole circle inside
the face).

Requirements:
- port faces stay the standard 5-patch O-H face (DESIGN §7.1), so the
  tee joins ordinary duct runs;
- the duct's creases and the hole's outline lie on block edges, so every
  wall face is a plane (or the branch's cylinder), exact as an OCC
  surface or by node projection (decision 0029);
- all-hex, conformal, cell count before GMSH, a predicted-quality limit.

## Options

### A. A collar of blocks around the hole (from task 0057)
- **Layout:** on the top wall, the hole's outline is surrounded by a
  ring of blocks with valence-3 vertices.  These take the junction
  station's six-vertex outline (four duct corners, two hole corners)
  back to the port's four.
- **What it needs:** the top ring (and perhaps the core) split through
  the junction section.
- **What it gives:** a direct, explicit block layout in the style of the
  current tee.

### B. Hole on the wall with a pillowed ring
- **Layout:** the hole occupies a patch of the duct's own top-wall cells.
  The branch's O-grid ring layer continues into the main as a
  **pillow** sheet: a dome under the hole patch whose boundary is a loop
  on the top wall around the hole.
- **What's new:** DESIGN §7.1 rejected hole-on-wall layouts because the
  ring sheet had to end at a "cap" block with five faces on one smooth
  surface.  Ending the sheet on the wall along a loop avoids that, as
  pillowing does (RESEARCH §9.5, [`borden_and_benzley_etal_2000`]).
- **What it gives:** the main's blocks are unchanged away from the
  dome, the port faces stay standard, and the same construction serves
  round taps (the hole patch's outline is then circle-like inside the
  face).
- **Risks:**
  - the hole's edges must fall on mesh lines of the main's top face,
    which couples the tap's size to the main's counts (a sizing rule,
    with a hint);
  - pillow-cell quality at the dome's corners.

### C. Reject narrow taps permanently
Full-width taps and transitions only.  Simple, but round taps (the
common HVAC spin-in) would never be possible.

## Recommendation

Prototype **B** first, then **A** if B's quality or sizing rule is
unacceptable.  B reuses one construction for rectangular and round taps,
and keeps the main's layout intact.
- **Measure** for each: predicted and meshed min corner SJ, max
  non-orthogonality, and how the tap size is constrained.  Inputs: tap /
  face ratio 0.3 / 0.6 / 0.9, duct aspect 1 / 2 / 3, wide and narrow
  face.
- **Decide** on the numbers (decision 0017's approach).

**Priority (2026-10-30, the user):** B directly.  Decision 0027's
full-width taps (task 0057) are **on hold**, not the first step:
- **if B also covers full-width taps** (its wall loop needs a margin
  around the hole, so this is open), 0057 is dropped;
- **if not,** 0057 returns as the small complement for q = a.

## Result (2026-10-30, task 0069) and decision

**The prototype** (`hexmesh/assembly/duct_tap.py`, 38 blocks).
- **Main:** the port slabs are standard.  Between the stations, the side
  rings and the bottom ring are unchanged, so every crease is a block
  edge.
- **Top ring:** re-blocked as an O-grid tube around a column under the
  hole.
- **Core:** carries the pillow: a dome sheet continuing the branch's
  ring.
- **Ports:** standard O-H faces, class 0 (the branch has the main's
  counts per side, frame turned to match).
- **Walls:** exact planes or cylinders.

**Measured** (72 meshes: ratio 0.3 / 0.6 / 0.9 × aspect 1 / 2 / 3 × wide
/ narrow × `nang` 4 / 8 × rectangular / round):
- all-hex, meshed = predicted, wall nodes on their surfaces to 3e-16;
- min corner SJ ≥ 0.125 everywhere; wide faces ≥ 0.20, mostly 0.3–0.43;
- narrow faces of a 3:1 duct 0.125–0.164, max non-orthogonality up to
  82°;
- cells 1.6–2.3× a plain main and branch run.
- **No sizing rule:** the tube's O-grid carries the main's across lines
  into the hole, so any tap inside the face fits.
- **Tunables** (station margin, dome depth, sheet thickness) are resolved
  per tap by maximising the predicted SJ (48 pure layouts), worth up to
  2.5×.
- **Full-width taps** (q = a) are not covered: the hole's corners land
  on the creases and blocks degenerate to wedges.

**Decision:**
1. **B is the duct-tap layout** for rectangular and round taps inside
   the face.  The collar (A) is not needed.
2. **One public `Tee`, the layout by ratio** (as for equal tees,
   decision 0031's amendment):
   - pillowed tap for across ratio q/a ≤ ρ_max (set when merging; 0.9
     measures fine);
   - **full-width tap** (task 0057) at q = a;
   - rejected in between, with a hint.
3. **Quality:**
   - the two tiers on predicted SJ (reject < 0.1, warn < 0.3);
   - for **round taps also the meshed SJ**, since the prediction
     overestimates them by up to 0.11;
   - **narrow-face taps on deep ducts** (3:1) are allowed with a warning
     naming the cause and suggesting the wide face; their
     non-orthogonality (≤ 82°) is reported post-mesh, as for tees.

## Consequences

- When chosen: 0058 (round tap) and narrow rectangular taps get tasks;
  0063 (shoe taps) builds on it.  DESIGN §7.1 gains a paragraph (a
  hole-on-wall layout that ends its ring sheet on the wall is allowed,
  if B is chosen).
- **Effect on future expansions:**
  - 0018 (vascular): none directly; a pillowed branch would also be a
    candidate for small side branches on large vessels.
  - 0019 (agent SDK): sizing rules and limits in `limits.py`, errors with
    hints.
  - 0021 (flow restrictions): none.
  - 0028 (multi-layer junctions): shells around a pillowed tap need
    their own construction; single-layer first.
  - 0030, 0032: none.

## Verified vs. assumed

- **Verified:** the crease problem (task 0057's analysis against
  `tee.py`).
- **Assumed:** that B's pillow cells reach acceptable quality, and that
  its sizing rule is acceptable to users.  The prototype measures both.
