# 0017 — Y-junction (wye): prototype first, quality limit after measurement

- **Status:** accepted
- **Date:** 2026-10-26 (accepted 2026-10-26 by the user: "I want it, let
  us be practical with the quality limit and see how it goes before
  deciding")
- **Tasks:** 0030

## Context

- There is no wye.  The legacy Y-block (`y_block.py`, `junction.py`)
  glued blocks with `occ.fragment()` and recovered surfaces by bounding
  box, both now forbidden (P2), and left a seam of SICN ≈ 0 cells.  It
  was deleted in task 0017 (decision 0004).  The only junction is the
  perpendicular, centred `Tee` (DESIGN §7.1).
- The tasks README kept Y-junction work out of every task until a design
  decision exists.
- **Research is ready** (RESEARCH §4):
  - topology from Decroocq et al. [`decroocq_and_frindel_etal_2023`]:
    separation half-planes meeting on the line CT₀–X–CT₁; sections
    swept from each end to the planes;
  - geometry from Marcinnó et al. [`marcinno_and_hinz_etal_2025`]:
    closed-form Hermite curves between the branch ends' anchors, and a
    "butterfly" dividing face of six ellipse quadrants.  All of it can be
    validated before GMSH;
  - Marcinnó reaches **min scaled Jacobian 0.488** (mean 0.907) on a
    5-patch O-H section, with no fragment step and no smoothing.  Worst
    cells sit at the extraordinary vertices next to the butterfly.
- **Corners.**  Both constructions need structural corners at
  0°/90°/180°/270° in the branch frame, so the split lands on corners.
  The 4-corner O-H section has them when the bifurcation plane passes
  through two opposite corners (corner k is at π/4 + rot + kπ/2,
  DESIGN §6.1).  `n_outer = 8` (decision 0005) is not needed.
- **Infrastructure exists.**  The tee is a `BlockLayout`
  (`hexmesh/assembly/blocks.py`): blocks share entities by topological
  identity, edges have kinds (`Line`, `ArcAbout`, `Spline`), and
  `validate()` checks face sharing, division classes and corner
  Jacobians in pure numpy.
- **Quality limit is open** (DESIGN §10, "Reject or degrade?").  The best
  published bifurcation (0.488) is below the 0.6 its authors suggest, so
  a hard global limit would reject the best known result.

## Options

### Approach
- **A. Block layout on `BlockLayout`**, topology after Decroocq,
  geometry after Marcinnó, explicit node placement, no smoothing
  (RESEARCH §4.4).
- **B. Sweep-based** (sections swept to the separation planes,
  Decroocq's own volume method).  Rejected: it relies on Laplacian
  relaxation that moves interface nodes (contradicts P3 and §6).
- **C. Wait for `n_outer = 8`.**  Rejected: not required (above), and
  decision 0005 is still proposed.

### Quality limit
- **A. Decide now** (a global hard limit, or a per-fitting one).
- **B. Measure first.**  The prototype reports quality per fitting
  without rejecting; the limit is decided from the numbers.

## Decision

- **Approach A.**  A `Wye` fitting built as a block layout.
- **First scope**, as the tee started: symmetric wye, both daughters
  with the inlet's radius, coplanar, single-layer spec, `rot = 0`.  The
  bifurcation plane passes through two opposite structural corners of
  the inlet section.
- **Quality: B, measure first.**  The wye's quality is reported (min
  scaled Jacobian, min SICN, NES, and where the worst cells are) and
  compared with Marcinnó's 0.488.  Nothing is rejected on quality in the
  prototype beyond what the conformance kit already requires (valid,
  positive-Jacobian hexes).  DESIGN §10 "Reject or degrade?" is decided
  afterwards, from task 0030's numbers.
- DESIGN §7 gets a "7.2 Wye" section after the prototype, from what it
  shows; not before.

## Consequences

- **Task 0030:** the wye prototype and its measurements.
- The tasks README's "not part of any task" note drops the wye.
- Later, once tee and wye both work, and only then (DESIGN §6.1, "not
  built on speculation"): unequal radii and angles, laterals, multi-layer
  wyes, and any generic N-port topology.
- The quality decision follows the measurements, as its own decision or
  an amendment to this one.

## Verified vs. assumed

- **Verified:** the legacy wye's deletion and failure mode; the
  published figures (RESEARCH §4.2); the `BlockLayout` capabilities
  listed above; corner positions on the 4-corner section.
- **Assumed:**
  - hexmesh can reach quality comparable to Marcinnó's without
    smoothing, given the same explicit construction;
  - the butterfly's curved petals can be realised as block faces whose
    interior nodes are acceptable.  DESIGN §6 (decision 0015) only allows
    interior nodes on exact surfaces; the petals have no "true" surface,
    so they are internal faces defined by their own construction, not
    walls.  The **outer wall** of the junction is the question: task 0030
    measures how far its nodes are from the construction's intended
    surface, as the tee's deviation was measured.
