# 0010 — Corner identity by index and the section symmetry period P

- **Status:** accepted
- **Date:** 2026-10-25
- **Tasks:** none now (see Consequences)

## Context

DESIGN §6.1 defined corner *k* by angle (`π/4 + rot + k·2π/n_outer`) and
matched faces modulo `2π/n_outer`.  §8 absorbed loop twist modulo the same
period.  Both assume corners equally spaced by angle and a section that
repeats every `2π/n_outer`.  That holds for circular O-H sections, but not
for:
- **rectangles** (decision 0009, proposed).  Corners are at
  ±atan(h/w), and a w ≠ h rectangle repeats only every 180°.  A 90°
  offset would wrongly match a w×h face to an h×w face;
- **`n_outer = 8` as a sub-partition** (decision 0005, proposed).  The
  mesh still repeats only every 90°, not 45°.

## Options

### A. Keep angle-based corners and `2π/n_outer`
Fails for both cases above.

### B. Corners by index; each section shape declares its symmetry period P
P is the smallest roll that maps the section's **mesh** onto itself (not
its block partition).  Correspondence is the roll between frames rounded
to a multiple of P.  For circular sections this gives the same results as
today.

## Decision

**B**, accepted 2026-10-25 by the user ("add this into the design").
DESIGN §6.1 (corner identity) and §8 (roll) were updated the same day
with the wording from the design discussion.

## Consequences

- DESIGN §6.1 has a table of corner definitions and P per section shape
  (circular O-H: `2π/n_outer`; square: π/2; rectangle: π).  DESIGN §8
  absorbs twist modulo P, never more than P/2.
- **Code:** no change needed now.  The assembly supports only circular
  `n_outer = 4` sections, where P = π/2 = `2π/n_outer`, so
  `corners.frame_offset` and `interface.roll_mismatch` already match.
  When rectangular sections land (decision 0009), both must take P from
  the spec instead of `2π/n_outer`, and `frame_offset` must use the roll
  between frames rather than corner 0's angle.  That goes in 0009's first
  task.
- **Decision 0009:** to-settle items 1 (corner identity by index) and 2
  (roll symmetry per section shape) are settled by this decision.
- **Decision 0005:** if accepted, the circular row's P becomes π/2 for
  every `n_outer`.  DESIGN §6.1 already notes this.

## Verified vs. assumed

- Verified in code: `frame_offset` rounds to `2π/n_outer` from corner 0's
  angle; `roll_mismatch` wraps into `(−π/n_outer, π/n_outer]`; the
  assembly accepts only `n_outer = 4` circular cores (`check_supported`).
  So current behaviour is unchanged.
- Assumed: rectangle corner order NE, NW, SW, SE matches `build_oh_rect`
  (its docstring says so; not checked against geometry).
