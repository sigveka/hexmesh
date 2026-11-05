# 0036 — A Cartesian (H) rectangular section, and the O-H ↔ H switch

- **Status:** accepted (2026-11-02 by the user: "accept 0036 with H as
  the default duct face")
- **Date:** 2026-11-02
- **Tasks:** 0084, 0085, 0086, 0087; 0072 now runs on the H section.
  Related: task 0071 (the finding), decision 0015 amendment 2 (how
  rectangular sections are gated meanwhile), decision 0037 (where a new
  section type lives in the code; task 0082 comes first).

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

## Decision

**Accepted 2026-11-02: B, with the H face as the default for rectangular
cores.**  The O-H face stays available on request.  The work starts
after task 0082 (decision 0037), which puts the O-H layout in
`sections`.  The H face is the second layout there, and the interface
the two share is derived from both.

**Settled at acceptance:**
1. **Default: H.**  Runs, bends, reducers and closures of rectangular
   ducts use the H face unless asked otherwise.  Switches sit where a
   duct meets something that needs the O-H face.
2. **Where the setting lives: the core, not the shape.**  The layout is
   a topology parameter of the section, next to `n_outer`, `rot` and
   the layer stack.  So it goes on the spec,
   `PipeSpec.core(name, shape, layout="h" | "oh")`, not on `RectShape`.
   - The proposal sketched `RectShape(..., layout=...)`.  But
     `RectShape` is also a shell outline and a tee branch, and DESIGN
     §3.1 keeps shapes as geometry; layouts belong to `sections`.
   - Circular cores have the O-H layout only; `layout="h"` on a circle
     is an error.
   - The layout is part of the port type (A4) and the signature (kind
     `h_core`).
3. **Old saved files keep their meshes.**  A saved assembly or study
   with no layout field loads as `"oh"`.  The new default applies only
   to specs built in code.
4. **`nrad` on an H core is an error.**  An H core has no ring; its
   near-wall resolution comes from wall grading (`first_cell=` or a
   two-sided progression).  The message names both fixes: drop `nrad`
   and grade the wall, or pass `layout="oh"`.
   - This makes the default flip (task 0087) a **breaking change** for
     scripts that pass `nrad` on a rectangular core.  Bump the version
     (0.3.0 → 0.4.0) and say so in the release notes.
5. **Junctions keep O-H blocks inside and accept H ports.**  Duct
   tees and taps (decisions 0027, 0033) embed the switch in their duct
   legs, declared as a class-1 strategy (decision 0011, item 3).
   `Transition` does the same at its rectangular end.  Users don't
   place switches by hand around junctions.  A standalone `Switch`
   fitting exists too, for O-H ducts placed on purpose.
   - Junction layouts native to the H face (taps on grid lines, which
     may simplify decision 0033's sizing rule) are a later decision,
     taken only if the embedded switch measures badly.
6. **The switch construction** (turned out to the wall, as decision
   0033 B's dome, or capped) is chosen by measurement in task 0085: min
   SJ and max non-orthogonality at a/b 1 / 2 / 4 and `nrad` 1 / 3 / 6.
   If neither meets the quality limits, the task stops for design.

**Amendment (2026-11-04, accepted by the user: "yes, send (a) and
write the amendment"; task 0085).**  Item 6 is settled without
measurement: **the switch is capped.  A turned-out switch can't be
built on a straight duct.**
- **Why** (task 0085's question, checked by the design session;
  RESEARCH §7.11).
  - Take a flat wall where every wall edge has two hexes (the regular
    case).  Two neighbouring hexes there share a face standing up from
    the wall, and that face's wall-normal edges belong to both hexes.
  - So every hex on that wall is in the same wall-normal sheet, from
    one end of the switch to the other.
  - On the O-H side that sheet is the outer ring.  So the outer ring
    stays the wall layer for the whole length of the switch.  It can't
    end on the wall, and it can't leave the wall to cap in the core.
  - The only escapes are irregular wall edges on the flat wall: three
    hexes at one edge (60° wedges against the wall) or one hex with a
    180° angle.  Either breaks the near-wall layer, where the grading
    matters.
  - Decision 0033 B's dome doesn't carry over.  Its sheets end on the
    edge of the hole in the wall, a real wall feature that supplies the
    irregular edges.  A straight duct has none.
- **The construction:** capped.
  - The outer ring stays the wall layer up to the H port.  Its sheet
    closes as a cup through the end block, a frustum whose downstream
    face is the H port.  The side blocks run from the O-H port to the
    H port's wall edges.
  - Quality depends on the slope of the slanted faces only, not on
    the switch length.  Task 0085 measured it at a/b 2, `nrad` 3:
    min SJ is 0.577 at 45° (cap depth d equal to the ring thickness t),
    and falls on either side.  So the cap is d = t, and the switch
    length is L ≥ 1.25 t (`limits.SWITCH_MIN_LENGTH`).  It meets
    `limits.py` across a/b 1 / 2 / 4 and `nrad` 1 / 3 / 6, so the
    hybrid isn't needed.
  - **Correction (2026-11-05, the user agreed; task 0086's Question
    2):** 1.25 t holds only for a uniform H face.
    - On a graded H face, the side blocks' wall nodes move from the O-H
      spacing to the graded H spacing over L.  The cells shear by about
      Δ/L, where Δ is the largest wall-node shift.
    - At L = 1.25 t, min SJ fell to 0.12 (a/b 2, n 8, first cell
      0.002).
    - The rule is now L ≥ max(1.25 t, Δ_max / `SWITCH_MAX_SHEAR`, t +
      Δ_max / `SWITCH_MAX_CORE_SHEAR`), with the constants 0.4 and 1.0.
      Over 450 meshed switches (a/b 1–4, n 8–24, first cell to h/200),
      that gives min SJ ≥ 0.50.  The core term covers short switches,
      whose 0.25 t core carries the same change of grading.
    - `mesh()` checks the meshed min SJ and non-orthogonality on task
      0047's tiers.  Non-orthogonality reaches 70–80° at steep gradings
      and rises with length and `nrad`, so the fix past 80° is a gentler
      grading or a smaller `nrad`, not a longer switch.
    - The switch adds no loss of its own.  Its measured K = −0.073 is the
      change between the two meshes' developed profiles: the
      kinetic-energy balance explains 91 % of it.
    - The capped choice stands.
- **Fallback, only if capped misses `limits.py` or needs an
  impractical length at `nrad` = 6:** the hybrid.  For `nrad` ≥ 2, the
  inner ring sheets cross the outer one and end crosswise on the wall,
  and the outer one is capped.  It is valid, because the wall layer
  doesn't change.
- **Task 0085 step 2** now asks only whether capped meets `limits.py`.
  The tie-break toward turned out goes.  If capped fails, the hybrid is
  prototyped before the task stops for design.
- **Junctions (item 5, task 0086)** embed the capped switch the same
  way.

**Rollout.**  The default flips last, once every rectangular fitting
accepts H ports:
- **0084:** the H layout in `sections`, the shared section interface,
  `layout=` on the spec (default still `"oh"`), every sweep on H, and
  task 0071's case on hexmesh's H face (gated like the control).
- **0085:** the switch (prototype both constructions, choose, build
  `Switch`), and `Transition` with an H rectangular end.
- **0086:** duct junctions accept H ports (embedded switch legs); shells
  around an H core (lagged ducts, decision 0026).
- **0087:** flip the default; version 0.4.0; examples, docs and gallery.
- **0072** (laminar square bend, V3) runs on the H section, after
  0084.

## Consequences

- **DESIGN.md (applied 2026-11-02):**
  - A4: the section layout is part of the port type; O-H ↔ H on a
    rectangle is class 1;
  - §6.1 "Sections": two layouts, H the default for rectangular cores;
  - §7.1: duct junctions keep O-H blocks inside and accept H ports
    through embedded switches;
  - §9: a deviation row (rectangular cores have only the O-H layout),
    removed by tasks 0084–0087.
- **CLAUDE.md:** `layout` added to the topology parameters.
- **Decision 0009:** option D (single patch) revived as the default
  rectangular core; superseded in part.
- **Decision 0011:** first use of class 1 between core layouts, and the
  first fittings (`Switch`, duct junctions, `Transition`) to declare a
  class-1 strategy.
- **Harder:**
  - every rectangular fitting needs H ports, or a switch inside it;
  - the conformance kit and examples gain H cases;
  - scripts passing `nrad` on rectangular cores break at 0.4.0 (clear
    error, two named fixes).
- **Effect on future expansions:**
  - 0018 (vascular): none (circular sections).
  - 0019 (agent SDK): `layout` is a data field in the spec and the
    network JSON; unsupported combinations give structured errors that
    name the layout and the fix.
  - 0021 (flow restrictions): none directly; rectangular orifices are
    rare.  Constraint 4 (one section-geometry abstraction) is met
    through decision 0037.
  - 0030 (simulation suite): V1 duct cases become gateable on hexmesh
    meshes.
  - 0035 (multi-core): the H face is the first section kind that isn't
    O-H.  Task 0084 derives the shared section interface from two real
    layouts, which multi-core sections then implement.

## Verified vs. assumed

- **Verified:** the OpenFOAM levels (task 0071 driver, v2406); the 2-D
  comparison (O-H vs Cartesian, three aspect ratios, five levels; the
  `OH_RATIO` sweep); that the 2-D O-H meshes match checkMesh's
  non-orthogonality; that pillowing a Cartesian face gives the 5-patch
  O-H face (combinatorial argument, RESEARCH §7.11).
  The 3-D Cartesian control converges at order 1.93–1.95 in OpenFOAM
  (task 0071, 2026-11-02).
- **Assumed:**
  - sweeps need no O-H knowledge beyond the face (one reference in
    `sweep.py`);
  - the switch's pillow cells reach acceptable quality (task 0069's
    numbers suggest so, not measured for this layout);
  - H ducts make narrow taps easier.
