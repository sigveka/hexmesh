# 0029 — Wall exactness by node projection where no exact OCC surface fits

- **Status:** accepted
- **Date:** 2026-10-29 (accepted by the user, on task 0051's Q1)
- **Tasks:** 0051 (steps 5–8: projection, tee and wye, crotch
  measurement; done), 0056 (follow-up: wye axial counts); 0053 builds its shells on it.  A conditional follow-up
  for the wye layout (below).

## Context

DESIGN §6 (as amended by decision 0015): "A filled surface may carry
interior mesh nodes only where it is the exact surface."  Task 0051
measured the junctions (2026-10-29):

- **Tee:** walls 2.2–3.2 % of R off before.  Plate fillings pinned to a
  7 × 7 grid of projected points bring them to ≤ 3.0e-4 R.  Cost: about
  +0.35 s per tee, plus 588 construction points per tee.  Those points
  cost about 2.3 s per tee to remove in a 2000-volume model, the
  remaining super-linear term of task 0036.
- **Wye:** walls 11–16 % of R off, and **no OCC surface fixes it.**
  - Unpinned fillings know only the boundary.
  - Pinned plates are erratic (1–46 %).
  - Trimmed exact surfaces get new boundary curves from OCC, so they
    are not conformal.
  - Each wye face spans several smooth pieces of the canal surface
    (inlet cylinder, knee sphere, daughter cylinders), and the crotch
    face contains the **crease** where the daughters' walls meet.
- **Node projection** (prototype): after `generate(2)`, every node on
  the junction's wall curves and faces is moved onto the analytic wall
  (`setNode`); then `generate(3)` interpolates the volumes.
  - Wye 90°: exact to 1e-15 R, quality unchanged.
  - Tee: 7e-7 R.
  - Wye 60°: folded cells (min SICN −0.8).  The fault is
    `Skeleton.to_wall`, not the method: a node just inside the crotch is
    equidistant from both daughters, and the projection ray crosses the
    other daughter, landing the node on the far wall.

## Options

### A. Topology change first: a wye whose faces each lie on one smooth piece
Split faces at the crease and at the cylinder/sphere seams, so pinned
plates or trimmed primitives can work.  It is the published way
(RESEARCH §4.4: separation half-planes as internal block faces), but it
redesigns the wye's layout (decision 0017's prototype), and every
measurement starts over.

### B. Node projection as the general mechanism
Exactness lives in the nodes, as DESIGN §6's first line already says
("exactness lives in curves and nodes").  The OCC surfaces only need to
be valid; the mesh is put on the analytic wall.

### C. Accept the wye's walls as they are
A deviation row, with the flow seeing a wall 11–16 % of R off.  No.

## Decision

**B, with three conditions; A only if the crotch measurement asks for
it.**

1. **Mechanism.**  A fitting whose wall faces can't be exact OCC
   surfaces provides an analytic **wall projector** (pure Python,
   per surface: wall, and later each shell boundary at its offset).
   `Assembly.mesh()` applies it between `generate(2)` and `generate(3)`
   to every node of that fitting's wall curves and faces.  It is the only
   place it happens.  Moving shared nodes is not merging (P2): each node
   is one entity, seen by both neighbours.
2. **Conditions.**
   - **Correct projection:** the nearest point on the analytic surface.
     Where the surface has a crease (the wye's crotch; a union of
     cylinders), it is handled as its own case: the projection may never
     cross into another branch.  The 60° wye is the test.
   - **Safety bound:** a move larger than a set fraction of the local
     cell height (in `limits.py`) is an error naming the fitting and the
     move.  Quality is re-checked after projection, so a bad projection
     fails loudly instead of folding cells.
   - **Checked on the final mesh:** the kit's wall-exactness check
     measures mesh nodes, not OCC surfaces.
3. **Scope.**  The wye and the tee (exact to about 1e-6 R; the tee then
   needs only valid, cheap surfaces, so its pinned plates and their
   construction points may go: measure, then decide in the task).  Swept
   fittings keep their exact OCC surfaces (ruled and swept); no change
   there.
4. **What stays approximate:** the OCC surfaces.  CAD export (`.brep`,
   `.step`) and `gmsh.model` geometry queries see the old wall, and
   projected nodes lose their parametric coordinates.  Both are
   documented (`API.md`, `docs/integrations/gmsh.md`); hexmesh's output
   is the mesh.
5. **The crease.**  With projection every node is on the wall, but
   faces that contain the crease cut across it.  That is a chord error at
   the crotch, first order in the cell size.  Task 0051 measures it (the
   largest distance from the analytic wall at face centres and edge
   midpoints near the crease, against `nang`).  If it is above about
   1 % of R at `nang` 8, design opens a follow-up: a wye layout with the
   crease on block edges (option A).

### DESIGN §6 amendment (applied 2026-10-29)

The decision-0015 paragraph gains:

> Where a face's exact surface can't be built as a conformal OCC
> surface (junctions whose wall crosses several smooth pieces, or a
> crease), the fitting supplies an analytic wall projector instead, and
> `Assembly.mesh()` moves that face's mesh nodes onto the wall between
> surface and volume meshing (decision 0029).  The projection is the
> nearest point on the wall, never crossing into another branch; a move
> beyond the limit in `limits.py` is an error.  The kit checks the final
> mesh nodes.

### Amendment (2026-10-29, after task 0051): projector and move limit

Task 0051 implemented the decision and measured it:
- every tee and wye wall node is within 1e-15 R on the final mesh;
- no folds;
- crotch chord error 0.95 % R (60°) and 0.88 % (90°) at `nang` 8,
  second order in `nang`.

Three points change or settle:
1. **The projector is not nearest-point.**  Nearest-point projection
   folds the crotch: the filled crotch face is a sharper V than the
   wall, so nodes just inside the crease swap order.  `TubeUnion`
   projects along a smoothed normal: the gradient of a soft minimum of
   the tubes' signed distances, landing on the wall point on that line.
   It is the nearest point away from creases, keeps rows of nodes in
   order across one, and never crosses into another branch.  DESIGN
   §6's paragraph is reworded to match.
2. **Inversion is the guard; distance is only a warning.**
   - A limit in cell heights rejects valid fine meshes: a legitimate
     move scales with `nrad` (2.5 cell heights at `nrad` 9, 60° wye).
   - A limit in wall radii rejects valid narrow wyes: measured moves are
     0.77 R at 30°, 0.60 R at 35°, 0.47 R at 40° (`nang` 8), all
     unfolded.  A projector that crosses a branch moves nodes by about
     R, so no distance separates the two cleanly.
   - So `Assembly.mesh()` **rejects inverted cells** (corner SJ ≤ 0) in
     every projected fitting, naming the fitting.  It **warns** when a
     node moves more than **1.0 × its wall's local radius**
     (`WALL_PROJECTION_WARN_MOVE`; above every legitimate move
     measured), and reports the largest move.  Condition 2 ("a bad
     projection fails loudly") is met by the inversion check, without a
     separate `check_quality` call.
3. **The crease measurement is under the 1 % threshold** (item 5), so
   there is no wye layout follow-up.  It's borderline at `nang` 8, and
   3 % at `nang` 4; recorded in RESEARCH.  Revisit if a wye validation
   case shows it.

Also found: the wye's knee (the hub's spherical cap) is resolved by
`n_run` only, so chords there stay at 8–10 % R at any `nang`.  That is
resolution, not exactness: task 0056 derives the wye's default axial
counts from its arcs.  The tee keeps its pinned plates.  Projection
after plain fillings gives the same exactness, but the nodes slide
tangentially (up to 1.3 % R) and the plates cost only about 0.4 s per
tee.

## Consequences

- Task 0051 reopens (steps 5–8) and closes the tee wall row; the wye
  gets a row until the crotch measurement is in.
- 0053 (multi-layer wye) uses the projector at `R + T` for its shells.
- Build cost may fall for the tee (no pinned plates).
- **Effect on future expansions:**
  - **0018 (vascular):** canal surfaces and creases are the vascular
    norm; this is the mechanism that keeps patient-like walls exact.  A
    contour or imported surface needs its own projector.  Keep the
    projector an interface (surface → nearest point), not wye code.
  - **0019 (agent SDK):** a projection error is a structured error (the
    fitting, the largest move, the limit).
  - **0021 (flow restrictions):** none.
  - **0026 (layer outlines) / 0028 (junction shells):** shell boundaries
    project onto their offset surfaces with the same interface.

## Verified vs. assumed

- **Verified (task 0051, 2026-10-29):** the measurements and the
  prototype numbers above, from the task file.
- **Assumed:**
  - that a crease-aware projector fixes the 60° wye;
  - that the crotch chord error is small;
  - that the tee can drop its pinned plates without losing anything.

  Task 0051 measures each.
