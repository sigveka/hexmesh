# 0063 — General branches, stage 4: shoe taps on ducts (`angle` on a rectangular main)

- **Status:** ready (after 0057, 0058, 0060)
- **Decision:** [0031 — General branch junctions](../decisions/0031-general-branch-junctions.md) (stage 4); duct tees from [0027](../decisions/0027-duct-tees.md)
- **Depends on:** 0057 (rectangular tap), 0058 (round tap), 0060
  (`angle`).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  HVAC branch takeoffs are often "shoe" taps: the branch leaves
the main duct at an angle (typically 45°), for lower loss than a
straight tap.

**Where.**  `hexmesh/assembly/tee.py`, kit, `API.md`, the branched HVAC
example (0059) if it reads better with one.

**Do.**
1. `Tee(angle=…)` on a rectangular main, with a rectangular or round
   branch, on either face (0057/0058's `face`).  The hole on the flat
   face is the branch section cut at the angle: a stretched rectangle,
   or an ellipse for a round branch.  The corners stay on the branch's
   O-H corners.
2. Walls: planes are exact OCC surfaces; a round branch's cylinder by
   node projection, as in 0058.
3. Room checks, the predicted-quality tiers, the `run_length` hint.
4. **Measure:** predicted corner SJ over α ∈ {30, 45, 60, 90}° × branch
   ratio ∈ {0.3, 0.6} × rectangular / round branch.

**Accept.**
- `angle=90` matches 0057/0058's meshes (to 1e-12).
- Kit cases (45° rectangular shoe, 45° round shoe on a 2:1 duct):
  all-hex, meshed = predicted, class-0 ports, walls exact, quality ok.
- The quality table.
- Full suite: no new failures.

**Out of scope.**  Offset duct taps; splitter vanes (internals).

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
