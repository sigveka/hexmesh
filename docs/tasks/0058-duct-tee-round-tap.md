# 0058 — Duct tee: round tap on a rectangular duct

- **Status:** superseded by 0070 (the pillowed tap covers round taps; decision 0033)
- **Decision:** [0027 — Tees in rectangular ducts](../decisions/0027-duct-tees.md) (A2)
- **Depends on:** 0057.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The common HVAC connection: a round branch duct ("spin-in")
on a flat rectangular main.

**Where.**  `hexmesh/assembly/tee.py`, `blocks.py`, `projection.py`
(decision 0029), kit, `API.md`.

**Do.**
1. `Tee(…, branch=CircleShape(radius, nang), face=…)` on a rectangular
   main.  The branch core is circular; the hole on the flat face is a
   circle; its corners sit at the circle's O-H corners (45°).  It is an
   outline change inside the junction (decision 0026's outline
   protocol), with equal counts per side.
2. **Walls:** the main's are planes (exact).  The branch's are a
   cylinder, and the junction faces between the flat face and the
   cylinder are as in the pipe tee.  Use pinned plates or node
   projection (decision 0029) for any face whose exact surface isn't a
   conformal OCC surface.  Every wall node exact on the final mesh.
3. Room checks, quality limit (predicted SJ, two tiers) and
   `run_length=None`, as 0057.
4. **Measure:** quality over branch diameter / face width ∈ {0.3, 0.6,
   0.9} × duct aspect ∈ {1, 2, 3}, `nang` 4 and 8.

**Accept.**
- Kit cases (round tap on a square duct and on a 2:1 duct, wide face):
  all-hex, meshed = predicted, class-0 ports, wall nodes on their
  surfaces, quality ok.
- The quality table; a proposed limit if needed.
- Full suite: no new failures.

**Out of scope.**  Shells; angled taps (decision 0031).

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
