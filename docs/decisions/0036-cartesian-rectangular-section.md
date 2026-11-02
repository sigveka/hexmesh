# 0036 — A Cartesian (H) rectangular section, and the O-H ↔ H switch

- **Status:** proposed (2026-11-02; no tasks until the questions below
  are settled)
- **Date:** 2026-11-02
- **Tasks:** none.  Related: task 0071 (the finding), decision 0015
  amendment 2 (how rectangular sections are gated meanwhile), decision
  0037 (where a new section type lives in the code).

## Context

Rectangular ducts use the 5-patch O-H face (decision 0009, option A), so
that circle ↔ rectangle is a class-0 sweep.  Decision 0009 dropped the
single-patch rectangle (option D) because nothing in the assembly used
it.

Task 0071 measured what the O-H face costs on a rectangle (RESEARCH
§7.11):
- **OpenFOAM, square duct:** f·Re error +2.65 / +1.97 / +1.16 % at
  k = 1, 2, 4.  The differences between levels grow, so there's no
  Richardson estimate, and the fine-level gate (< 1 %) fails.  a/b = 2
  is non-monotone; a/b = 4 changes sign.
- **2-D controlled comparison**, same scheme and cell count: O-H order
  0.3 → 0.9; Cartesian order 2.00 at every aspect ratio.  The Cartesian
  grid at ~1 750 cells beats the O-H face at ~27 600.
- **Cause:** 8 irregular vertices that a rectangle doesn't need, and
  faces along the corner diagonals that stay ~45° non-orthogonal at
  every level.  The inner-square size (`OH_RATIO`) doesn't change it.

Also from RESEARCH §7.11: the O-H face **is** a pillowed H face (one
ring of cells inside the boundary, a diagonal at each corner).  So
H ↔ O-H is class 1 in decision 0011's table: pillow / unpillow.  Task
0069 has prototyped a pillowed construction (the duct tap's dome,
decision 0033 B).

## Options

### A. O-H only (today), gated on a Cartesian control
Decision 0015 amendment 2 already does this for verification.
- **For:** no new code; every duct fitting keeps working.
- **Against:** every straight and bent duct carries the corner cells
  along its whole length.  Accuracy per cell is poor (16× the section
  cells for the same f·Re error on a square), and convergence is
  non-monotone, so users can't run convergence studies on ducts.  For
  HVAC loss studies a 1–2 % f·Re bias may be acceptable; for
  verification and for a product that sells exactness, it isn't.

### B. An H section for rectangular ducts, with a class-1 switch
- **H face:** one transfinite patch, `nang_w` × `nang_h`, wall grading
  instead of a ring for near-wall resolution.  Signature kind `h_core`.
- **Sweeps** (`Straight`, `Bend`, `Elbow`, `MiterBend`, `SplinePipe`,
  `Closure`, `Reducer` between H faces) need only the face: a sweep
  fills slabs between any two faces with matching patches.  (Assumed;
  `sweep.py` has one O-H-specific reference.)
- **Switch fitting** (O-H rect ↔ H rect, equal `nang_w`, `nang_h`):
  removes the `nrad` ring sheets.  Two constructions to prototype:
  1. **turned out:** each ring sheet flares and ends on the wall along
     a loop.  That is decision 0033 B's dome, so task 0069's
     construction carries over;
  2. **capped:** each ring sheet closes with a cup across the duct,
     open toward the O-H side (one core, four side, one cap and four
     corner-wedge blocks).
  Either could also be built into `Transition` (circle O-H → rect H in
  one fitting).
- **Counts:** the H face has `nang_w` × `nang_h` cells, 2 · `nrad`
  fewer across than the O-H face.  The 2-D results say that's still
  more accurate.
- **Multi-layer ducts** (lagged ducts, decision 0026): a shell around an
  H core is a ring layer, which *is* the pillow.  So an H fluid core
  inside rectangular shells puts the 45° diagonals in the solid (pure
  conduction) and keeps the fluid Cartesian.  Needs `build_ring` to
  take the H core's corners as its inner corners.
- **For:** second order where the flow is; fewer cells; a natural fit
  for lagged ducts.  It's also the first section that isn't O-H, the
  smallest test of decision 0035's "fittings sweep any blocked
  section".
- **Against:** a second section family for every rectangular fitting,
  and a switch fitting wherever the two meet.

### C. Keep O-H, smooth or reshape the section (decision 0022 option C)
Elliptic smoothing or bulged inner sides move the interior corners, but
the diagonals still end at the wall corners and split them 45/45.  The
`OH_RATIO` sweep (RESEARCH §7.11) didn't help.  Not measured with
smoothing; not recommended for rectangles.

## Decision (recommended)

**B, prototype first**, after task 0082 (decision 0037, accepted
2026-11-02).  It puts the O-H layout in `sections`, so the H face becomes
the second layout there, and the shared section interface is derived from
the two.  Otherwise the H face would be a tenth place to describe a section
(RESEARCH §12.2, item 1).

To settle before any task:
1. **Default port face of a rectangular duct**, O-H or H.  This sets
   where the switches go:
   - **H by default:** runs, bends and reducers are H; switches sit at
     circle ↔ rectangle transitions and at junctions that need O-H
     ports.  Fewest switches in HVAC-style networks (mostly duct).
   - **O-H by default, H opt-in:** no change for existing users; H only
     where requested (validation, long runs).
   Recommendation: H by default for new rectangular specs, with the
   O-H face selectable (`RectShape(..., layout="oh")`), once the switch
   is measured.
2. **Junctions on H ducts:** duct tees and taps (decisions 0027, 0033)
   are built on O-H ports.  Either they keep O-H ports (a switch on
   each side), or they get H versions.  On an H face the tap's edges
   could fall on any grid line, which may simplify decision 0033's
   sizing rule (unverified).
3. **Switch construction:** turned out vs capped, by measured quality
   (min SJ, max non-orthogonality) at aspect ratios 1 / 2 / 4 and
   `nrad` 1 / 3 / 6.

Prototype scope, when tasked: the H face builder behind the section
abstraction; `Straight` and `Bend` on it; the switch; task 0071's case
rerun on the H section (gated like the control, decision 0015
amendment 2).

## Consequences

- **DESIGN.md:** §5 / §6.1 (section families, not one O-H face), A4
  (port kind `h_core`), §7.1 (which junction ports are O-H).  Wording
  when accepted.
- **Decision 0009:** option D (single patch) revived in a different
  role: superseded in part.
- **Decision 0011:** first use of the class-1 strategy between core
  layouts (not just outer shells).
- **Harder:** every rectangular fitting needs an H version or a switch
  on each side.  Conformance kit and examples gain H cases.
- **Effect on future expansions:**
  - 0018 (vascular): none (circular sections).
  - 0019 (agent SDK): the section layout must be a data field in the
    network JSON and the spec (`layout`), with structured errors when a
    fitting doesn't support it.
  - 0021 (flow restrictions): none directly; rectangular orifices are
    rare.  Constraint 4 (one section-geometry abstraction) is met only
    through decision 0037.
  - 0030 (simulation suite): V1 duct cases become gateable on hexmesh
    meshes.
  - 0035 (multi-core): the H face is the first section kind that isn't
    O-H; its constraint 1 (don't hard-wire the O-H face) is what this
    decision exercises.

## Verified vs. assumed

- **Verified:** the OpenFOAM levels (task 0071 driver, v2406); the 2-D
  comparison (O-H vs Cartesian, three aspect ratios, five levels; the
  `OH_RATIO` sweep); that the 2-D O-H meshes match checkMesh's
  non-orthogonality; that pillowing a Cartesian face gives the 5-patch
  O-H face (combinatorial argument, RESEARCH §7.11).
- **Assumed:**
  - the 3-D Cartesian control converges at order ≈ 2 in OpenFOAM (to be
    measured by task 0071's control);
  - sweeps need no O-H knowledge beyond the face (one reference in
    `sweep.py`);
  - the switch's pillow cells reach acceptable quality (task 0069's
    numbers suggest so, not measured for this layout);
  - H ducts make narrow taps easier.
