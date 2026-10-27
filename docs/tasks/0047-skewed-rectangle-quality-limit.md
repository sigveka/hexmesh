# 0047 — Quality limit for rings with skewed corner lines (aspect-ratio sweep)

- **Status:** ready (after 0045)
- **Decision:** [0026 — Layer outlines: shells of any shape](../decisions/0026-layer-outlines.md) (item 4)
- **Depends on:** 0045.  Can run alongside 0046.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Around a square, a ring's corner lines are radial.  Around a
flat rectangle they are skewed: from the circle's 45° corners to
rectangle corners at atan(h/w), and with equal counts on long and short
sides.  Quality falls with aspect ratio.  Decision 0017's approach:
measure, then set a practical limit.

**Where.**  A measurement script (e.g. `benchmarks/outline_quality.py`,
not in the suite); `hexmesh/assembly/limits.py` for the limit;
validation in the spec or assembly; `RESEARCH.md` table via *Outcome*.

**Do.**
1. **Sweep** for each pairing: circle core in a rectangle shell, and a
   rectangle core in a circle shell; aspect ratio w/h ∈ {1, 1.5, 2, 3,
   4, 6}; gap ratio (thinnest ring thickness / inner size) ∈ {0.1, 0.3,
   1}; `nang` ∈ {4, 8}; `nrad` 4.  Through a straight and an easy-way and
   a hard-way bend.
2. **Record** per case: min SICN, min scaled Jacobian, max
   non-orthogonality (from the hex metric in `quality_hex`, or
   `checkMesh` if simpler and available), and where the worst cell is
   (corner line, long side, short side).
3. **Rectangle in rectangle** (`dR` shells): the same table for aspect
   ratios, to confirm it is unaffected (corner lines on the diagonals).
4. **Propose a limit** under *Questions for design*: the aspect ratio
   (and, if it matters, the gap ratio) beyond which min scaled Jacobian
   falls below a value, with the numbers.  Compare with the tee and wye
   minima (DESIGN deviation rows, decision 0017).  Don't tune the
   builder; if an obvious improvement shows (e.g. a different corner-line
   rule), describe it with one measurement.
5. After design answers: put the limit in `limits.py`, check it in
   `validate()` with a message naming the layer, the ratio and the
   limit.

**Accept.**
- The measurement table, reproducible from the script, in *Outcome*.
- A proposed limit with its basis; after the answer, the check in
  `validate()` with a test on each side of the limit.
- Full suite: no new failures.

**Out of scope.**  Changing the ring builder's rule (unless design asks,
after step 4); unequal counts per side.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
