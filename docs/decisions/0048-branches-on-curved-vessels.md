# 0048 — Branches on curved vessels: placing junctions along a centreline

- **Status:** proposed (recorded at the user's request, 2026-11-10: the
  aorta's lessons; no tasks until accepted)
- **Date:** 2026-11-10
- **Tasks:** none

## Context

Building the idealised aorta (task 0121) from today's fittings showed
three gaps for vascular networks (decision 0018):

1. **A `Tee` needs a straight run** of about two branch diameters (the
   hole plus enough run for its cells).  The aortic arch curves with a
   radius of about 3 aortic radii, and its three branches sit 1.7–3.4 cm
   apart.  To fit straight tees, the arch had to be widened by 20 % and
   two branches moved 1.4–1.7 cm from their cited positions.
2. **A `Tee` leans only downstream** (`angle` in (0, 90]).  Vessels
   branch at their own angles, and on a curving main a branch heading
   "up" leans upstream on one side of the curve.  The aorta's branches
   were made square.
3. **Joining fittings along a curve is left to the user.**  The aorta
   needed its own Hermite connector (sampling the anatomical curve left
   kinks where a tee's straight run leaves it), a lead `Straight` before
   each rolled tee (task 0062's twist), and a trial loop for the arch
   scale.  Decision 0018's input is a centreline with radii, which
   is exactly this placement problem.

## Options

### A. A centreline route builder (no new fitting)
Given a centreline (points or a curve, with radius per point) and the
junctions' positions as arc lengths, hexmesh lays out the route itself:
`SplinePipe` connectors with matched end tangents, a lead `Straight`
where a roll needs one, `Reducer`s where the radius changes, and each
junction on the curve's tangent at its position.  It reports where it
had to move a junction (and by how much) to fit, rather than failing.
Uses only existing fittings; the placement is pure Python before gmsh.

### B. Upstream leans
`Tee(angle=…)` in (0, 180): a branch leaning upstream.  Today's hint
says "the same lateral with the run reversed", which a network with a
flow direction can't do.  Needs the tee layout measured for the
mirrored lean (likely symmetric to today's).

### C. A branch on a curved main
A fitting whose main is a bend (or a spline piece) with a branch off it:
no straight run needed.  The largest change: a new block layout whose
saddle lies on a torus, with its own projection and quality tiers.

## Recommendation (not decided)

**A first, then B; C only if A's measured moves are too large for real
vascular trees.**  A removes most of the aorta's hand work and gives the
numbers (how far junctions move on real centrelines) that decide C.  B
is small if the mirrored lean measures as today's.

## Consequences (if accepted)

- **API:** A is a builder (a function or a method on `Assembly`), an
  addition; B widens one field's range; C is a new fitting.
- **Decision 0018:** A is its "centrelines + radius" input path, before
  a VMTK reader (its prerequisite 6) and a profiled `SplinePipe`
  (prerequisite 3), which A would use when it exists.
- **Future expansions:** 0018 helped (the purpose); 0019/0040 (agents):
  A's input is JSON-friendly (points, radii, positions); 0021, 0030,
  0035: none.

## Verified vs. assumed

- **Verified:** the aorta's adjustments (task 0121's notes): the 1.2
  scale, the moved branches, the connector and lead straights.
- **Assumed:** that A's moves stay small on real trees with gentler
  curvature than the arch; that B's tiers mirror today's.
