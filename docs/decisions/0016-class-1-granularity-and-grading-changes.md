# 0016 — Class-1 granularity, and grading changes across a sweep

- **Status:** accepted
- **Date:** 2026-10-26 (accepted 2026-10-26 by the user: "record as
  decision 0016")
- **Settles:** decision 0011's open questions 2 and 3
- **Tasks:** 0027

## Context

Task 0019 built the port-face signature and the switch classifier
(DESIGN A4) and left two questions (task 0019, *Questions for design*).

1. **Class-1 granularity.**  From signatures alone, "a whole outermost
   layer present on one side only" means the ring's end is exposed, so
   it ends on a wall.  The classifier records that as `ends="wall"`.
   Replacing an outer ring with a layer of another kind (an O-ring
   becoming a square shell, the duct follow-up of decision 0009) changes
   the layer's *kind*, which the classifier puts in class 3.
2. **Grading in the signature.**  Measured with a reducer subclass
   declaring `{0, 2}`, core + shell, `nrad` 6 / 4:

   | `mprg` in → out | Mesh | min SICN |
   |---|---|---|
   | 1.0 → 1.0 | all-hex, predicted count | 0.193 |
   | 1.0 → 1.3 | all-hex, predicted count | 0.094 |
   | 1.3 → 0.77 | all-hex, predicted count | 0.097 |
   | 1.0 → 2.0 | all-hex, predicted count | 0.019 |

   - Joining works mechanically: each station has its own radial
     curves, and axial curves only need matching node counts.
   - The quality cost comes from `Reducer.path`: intermediate stations
     copy the inlet grading (`fittings._with_radii`), so the whole change
     lands in the last slab.
   - **A concrete need exists.**  With an absolute `first_cell` (a fixed
     y⁺ target), the solved `mprg` differs on the two sides of a reducer.
     A wall-resolved mesh through a reducer is rejected today.

## Options

### Q1. A class-1 subclass for "outer ring replaced"?
- **A. No.**  One class 1: outermost layers present on one side only,
  ending on a wall.  A change of layer kind stays class 3.  A fitting
  that bridges one specific class-3 pair (the duct transition) declares
  class 3 and checks the pair itself in `validate()`.
- **B. Split class 1** into 1a (termination on a wall) and 1b (outer ring
  replaced).  Rejected for now: only one fitting would use 1b, and
  DESIGN §6.1 says no infrastructure on speculation.

### Q2. Grading in the signature?
- **A. Keep it, unchanged:** a grading change needs a density switch
  (decision 0003, proposed), so wall-resolved reducers stay impossible.
- **B. Take grading out of the signature.**  Rejected: an interface has
  one node set (P1), so two faces with different grading cannot share
  one.  The signature describes a port face, and grading is part of it.
- **C. Keep it in the signature, and let sweeps bridge a grading-only
  difference** by interpolating grading per station, like radii.

## Decision

- **Q1: A.**  Class 1 stays one class.  Revisit when a second fitting
  needs to tell ring replacement apart from termination; the duct
  transition, when its task is written, declares class 3.
- **Q2: C.**
  - Grading stays in the signature.
  - A class-2 pair whose only differences are radial grading (`mprg`
    per layer, same counts) is **grading-only**.  The classifier marks
    it, as it marks class 1 with `ends="wall"`.
  - A sweep that declares class 2 may bridge grading-only pairs, and
    only those.  Count changes still need a refinement template
    (decision 0003).
  - Grading is interpolated per station, never changed in one slab.
  - `mbmp` (angular) is not included: no use case.

### DESIGN A4 amendment (applied 2026-10-26)

The class-2 row of the table becomes:

> | 2 | counts or grading within the same layout | grading only: a sweep, grading interpolated per station; counts: refinement template (fixed ×2 or ×3) |

## Consequences

- **Task 0027:** grading-only marking in `classify`, per-station grading
  in `Reducer` (and in any other sweep whose ends may differ), and the
  wall-resolved reducer as the acceptance case.
- Decision 0011's questions 2 and 3 point here.
- The duct follow-up of 0009 is class 3, bridged by its own fitting.

## Verified vs. assumed

- **Verified (task 0019):** a grading change in one slab meshes all-hex
  with the predicted count, at a large quality cost (table above).
- **Assumed:** interpolating grading per station recovers most of that
  quality.  Task 0027 measures it.
