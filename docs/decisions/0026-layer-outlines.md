# 0026 — Layer outlines: shells of any shape

- **Status:** accepted
- **Date:** 2026-10-28 (accepted by the user: "rectangular shells around
  circles and circular shell around rectangles is something I want";
  recorded with tasks at their request)
- **Tasks:** 0045 (outlines in the spec, faces and fittings), 0046
  (multi-layer `Transition`), 0047 (quality limit for skewed rectangles)

## Context

A layer stack today is a circular core with circular shells, or a
single-layer rectangle (`check_supported`, `interface.py`).  Wanted:
- a rectangular shell around a circle (a round conductor in a square
  insulation block, a pipe in a square casing);
- a circular shell around a rectangle (a busbar in a round enclosure);
- a rectangle around a rectangle (busbar and hairpin-winding insulation,
  insulated ducts).

The use that prompted it is electrical: busbars, hairpin windings,
hollow and insulated conductors (design discussion, 2026-10-27).  It
also gives insulated rectangular ducts and multi-layer transitions.

Existing pieces:
- `CircleShape`, `RectShape` and `outline(shape, k, s)`
  (`core/shape.py`);
- `build_annulus` (`faces/annulus.py`, circles only);
- the legacy `square_shell` / `SquareShellSpec` / `faces/square_shell.py`
  (a circle in a square; rejected by the assembly);
- `BlendShape` (task 0029) for `Transition` stations.

### Name

"Concentric shape" was suggested.  Rejected: every stack is already
concentric, so it doesn't name what's new, and eccentric cores (decision
0021, stage 3) and contour sections (decision 0018, item 7) need layers
that are not centred.  The code already says **outline**.

## Decision

1. **Every layer has an outline; a shell is the region between the
   previous outline and its own.**
   - `shell(name, dR=…, nrad=…)`: the previous outline grown by `dR`
     (circle: radius + dR; rectangle: half_w + dR, half_h + dR, sharp
     corners).
   - `shell(name, outer=Shape, nrad=…)`: a new outline, `CircleShape`
     or `RectShape`.  Exactly one of `dR` and `outer`.
   - `square_shell` and `SquareShellSpec` are removed (replaced by
     `outer=RectShape(…)`); `faces/square_shell.py` is replaced by the
     general builder.
2. **Combinatorics: still an annulus.**  A ring between any two outlines
   is four blocks, one per side, the same layout as a circular ring.  By
   "shape is geometry" (decision 0009) the port signature is unchanged,
   so a circle-in-square ring and a circle-in-circle ring with equal
   counts are class 0.  This replaces 0009 option C's and 0016's
   reading of the square shell as a class-3 layout change.
3. **Equal counts per side.**  Each block maps one side of the inner
   outline onto one side of the outer, so every outline in a stack has
   `nang_w = nang_h = nang` (as `Transition` requires).  Unequal counts
   are a later class-2 question.
4. **Corner lines.**
   - Circle inside: the corner lines leave the circle at the O-H
     corners (45°) and end at the outer rectangle's corners.  Square
     outer: straight and radial.  Flat rectangle: skewed, so quality
     falls with aspect ratio; limit from task 0047.
   - Rectangle inside: the corner lines leave the rectangle's corners
     along their own diagonals; an outer circle's arcs are then unequal.
5. **Containment** is checked in `validate()`: each outline strictly
   inside the next, with a minimum gap, naming the layer.
6. **Fittings:** `Straight`, `Bend`, `Elbow`, `MiterBend`, `SplinePipe`,
   `Closure`, `Reducer` (radii and outline sizes may change, shapes may
   not) and `Transition` (task 0046: shapes may change).  Bend radius is
   checked against the outermost outline's half-extent in the bend
   plane (as for ducts).  `Tee` and `Wye` stay single-layer.
   `stack_changes` keeps working on whole outer layers.
7. **Grading:** `first_cell` on a shape-changing shell is solved at its
   longest radial, so no wall cell exceeds it (as the O-H core does).
8. **Exactness (DESIGN §6):** flat sides are planes; on straights they
   are ruled, on bends swept arcs.  The wall-exactness check of task 0025
   covers rectangle sides.

## Consequences

- DESIGN.md (applied with this decision, below): A4's layout table gains
  "annulus between any two outlines"; the cross-section scope names
  layer outlines.
- Removed: `square_shell`, `SquareShellSpec`, `faces/square_shell.py`.
  Decision 0009's option C (tube bundles) stays deferred: it is about
  several pipes sharing faces, not about the shell's shape.
- **Effect on future expansions:**
  - **0018 (vascular):** the outline abstraction is where a contour
    section joins (item 7).  Keep outlines behind one protocol
    (`outline(k, s)`, corners, extents), with no `isinstance` chains in
    new code, so a contour shape is one more class.
  - **0019 (agent SDK):** `outer` shapes serialise in the JSON
    (constraint 2); errors name the layer and the limit (constraint 3);
    the aspect-ratio limit lives in `limits.py` (constraint 6).
  - **0021 (flow restrictions):** constraint 4 (one section-geometry
    abstraction) is met.  Don't assume a shared centre in the data
    model: keep "outlines are centred" a `validate()` rule, so an
    eccentric core can be added (as 0021 constraint 1 does for stack
    changes).
  - **Electrical applications** (discussed 2026-10-27, not recorded as
    a decision): busbars and hairpin windings need rectangle-in-rectangle
    stacks through easy- and hard-way bends: covered.

### DESIGN.md amendment

To be applied by the design session when task 0045 is done.  Text:

> A layer stack is a core and shells, each with an outline (a circle or
> a rectangle).  A shell fills the region between the previous outline
> and its own; whatever the two shapes, it is four blocks, one per side,
> so its connectivity is that of a circular annulus with the same counts
> ("shape is geometry", decision 0009).  Every outline in a stack has
> equal counts per side.

## Verified vs. assumed

- **Verified (code, 2026-10-28):** the current shell builder is
  circle-only (`build_annulus`); `check_supported` rejects shells around
  rectangles and `square_shell`; `Transition` is single-layer.
- **Assumed:**
  - that skewed corner lines give acceptable quality up to a useful
    aspect ratio (task 0047 measures);
  - that the signature needs no change (task 0045 checks by
    classifying the new rings against circular ones).
