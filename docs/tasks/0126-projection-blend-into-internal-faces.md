# 0126 — Carry the wall projection's move into the internal faces: stop the equal tee's slide with refinement, and re-measure equal laterals and second order

- **Status:** done
- **Decision:** [0046](../decisions/0046-gmsh-meshes-hexmesh-corrects.md) (hexmesh may correct node positions; recorded); [0029](../decisions/0029-wall-exactness-by-node-projection.md) (projection); [0043](../decisions/0043-wye-layout-redesign.md) (its gates, unchanged)
- **Depends on:** 0122 (done).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user asked for this (2026-11-10, through the coding session),
from design's candidate in task 0122.  The equal tee's meshed quality
falls with refinement (min SJ 0.511 at `nang` 8, 0.305 at 48), equal
laterals degrade faster and fail `checkMesh` from 60° down, and Hex27
inverts near the projected wall.

**Design's reading of the cause** (to be confirmed in step 1).
`_project_walls` runs between `generate(2)` and `generate(3)`.  It moves
the nodes of the projected wall surfaces, their curves and points (up to
0.18 R on the cube's flat wall sides).  gmsh's transfinite volume then
interpolates the block interiors from the face nodes, so the interiors
follow the wall.  But the **internal faces** that meet the wall along a
moved curve (the faces between blocks) were meshed before the move, and
nothing moves their nodes.  Their first row of cells next to the wall
takes the whole move, which is fixed by the geometry.  As `nang` rises,
that row gets thinner and the move crushes it.

**The correction.**  After projection and before `generate(3)`, for each
internal face touching a moved curve, move its interior nodes by the
transfinite interpolation (TFI) of its boundary nodes' moves: the
moves on its four boundary curves blended across the face along its
grid lines.  This is closed form, with no iteration and no smoothing,
and deterministic.  It is a node-position correction (decision 0046,
rule 2), recorded with the projection.

**Where.**  `hexmesh/assembly/assembler.py` (after `_project_walls`),
the fittings' projection setup (which faces are internal), `limits.py`
if a switch is needed, `junction_quality.py`; the harness
`validation/tools/` and a JSON of the runs; `tests/`.

**Do.**
1. **Confirm the cause** on the equal tee at `nang` 8 and 24: where the
   worst cell is (which block and face, how far from the wall), and how
   thick it is before and after projection.  If the cause is elsewhere,
   stop and report under *Questions for design*.
2. **The correction**, for every projected fitting (reduced tee, wye,
   equal tee, and duct taps if they project):
   - only the interior nodes of internal faces whose boundary has a moved
     node;
   - never port faces or their curves (ports stay class-0 with the
     straights);
   - never wall faces (already on the wall);
   - nodes are moved in place (`setNode`), and no node or element is
     added.  Record per fitting: faces corrected, nodes moved, the
     largest move.
3. **Measure**, before and after, at `nang` 8, 16, 24, 32 and 48 (single,
   and with one shell at 8 and 16):
   - the equal tee at 90°;
   - equal laterals at 75°, 60°, 45° and 40°;
   - a reduced tee (r/R 0.5 and 0.9), and the 60° wye;
   - `mesh(order=2)` for the equal tee and the wye at `nang` 8 and 16:
     inverted Hex27 count.
   Report min meshed SJ, inverted cells, non-orthogonality and checkMesh
   v2406 (at `nang` 8 and 16) per case.

**Gates, fixed now:**
- **Ship the correction for a fitting** if no case of that fitting gets
  a lower min meshed SJ at any measured `nang`, single or shelled, and
  none gets an inverted cell.  Otherwise it stays off for that fitting,
  and the numbers are reported.  The gallery's meshes for the fittings it
  doesn't touch stay byte-identical; the others change, and are listed.
- **Equal tee:** report whether the slide stops (min SJ at `nang` 48
  within 0.05 of `nang` 8's).
- **Equal laterals come back** at an angle θ only if, at θ and every
  measured angle above it: min meshed SJ ≥ 0.1 at `nang` 8–32 (≥ 0.3 at
  every `nang` for no warning, otherwise the usual warning), no inverted
  cells, and checkMesh v2406 passes at `nang` 8 and 16.  Then
  `EQUAL_LATERAL_ANGLE_MIN` moves to the smallest such θ, and the
  lateral is back in the gallery.  Otherwise it stays at 90.
- **Second order comes back** for a fitting only if its Hex27 has no
  inverted cell at `nang` 8 and 16, single and shelled.  Otherwise the
  `second_order_unsupported` rejection stays.

**Accept.**
- Every gate answered with numbers; the JSON committed; reruns
  byte-identical.
- The correction recorded in `projection_report` (and in task 0123's
  report if it has landed).
- DESIGN §7.2's "Range" and quality sentences: proposed new wording under
  *Questions for design* if any gate changes them.
- Full suite: no new failures.  Meshes and cases deleted afterwards.

**Out of scope.**  Smoothing of any kind (iterative, optimisation);
moving wall or port nodes; a predicted-quality model that includes the
correction (propose it as a follow-up if the numbers show the prediction
is now far off).

## Agent notes

- **Step 1: the cause is elsewhere** (2026-11-10; equal tee, 90°, R 0.1,
  nrad max(3, nang/2 − 1), single layer).  The projection's moves,
  taken inside `_project_walls` (before and after; gmsh renumbers
  nodes after `generate(3)`, so a census after `mesh()` misreads them):

  | max move / R | nang 8 | nang 24 |
  |---|---|---|
  | wall faces' interior nodes (27 surfaces) | 0.167 | 0.184 |
  | wall curves; wall points | 0; 0 | 0.0001; 0 |
  | internal faces' interiors; internal curves | 0; 0 | 0; 0 |
  | largest boundary move of any internal face | 0 | 0.0001 |

  The cube's edges are splines through points on the wall
  (`cube._layout`'s `on_wall`), so they are on it before projection;
  only the wall faces' interiors move, the flat (Stretch) fills bulging
  out onto the cylinder by up to 0.18 R.  No internal face has a moved
  boundary, so the TFI of boundary moves across internal faces would
  move nothing.
- **The worst cell** (meshed twice, with projection and with it
  replaced by a no-op; transfinite element order is the same):

  | | nang 8 | nang 24 |
  |---|---|---|
  | its SJ projected / unprojected | 0.511 / 0.781 | 0.353 / 0.784 |
  | where | at a wall face's edge, against an internal face | the same |
  | its nodes | a wall point, two wall-curve nodes, a wall-face node, internal-face and internal-curve nodes, a volume node | the same |
  | moves (× R) | wall-face node 0.124, volume node 0.083, the rest 0 | 0.055 and 0.050, the rest 0 |
  | shortest edge (× R) before / after | 0.162 / 0.163 | 0.0445 / 0.0445 |

  It isn't crushed (its edges keep their length); it is **sheared**: its
  wall-face node and the volume node behind it move outward with the
  wall face's bulge, while its nodes on the internal face and the
  wall curve stay.  The shear, the move over the cell's edge, grows
  with refinement: 0.77 at nang 8, 1.24 at 24, because the first row of
  the bulge moves by more than the shrinking cell edge.  The 20 worst
  cells are all of this kind (2–6 of 8 nodes moved).

## Questions for design

1. **The correction needs a different source.**  The internal faces'
   boundaries don't move; the move field lives inside the wall faces.
   Options, all node-position corrections (decision 0046) unless noted:
   - **(a) Carry the wall face's interior moves into the internal faces
     beside it** (recommended to measure first): for an internal face
     meeting a wall face along a cube edge, give each of its interior
     nodes the move of the wall face's node in the same grid row
     (the wall face's first row off that edge), blended to zero across
     the internal face toward the cube.  The volume's TFI then follows
     both, so the cell beside the edge moves as a whole instead of
     shearing.  Unlike the task's TFI it needs the two faces' grids
     matched row by row (they are: both transfinite, sharing the edge's
     nodes).
   - **(b) Shape the wall faces before meshing**, so they need little
     projection: replace the Stretch fill of the cube's wall sides with
     a surface through on-wall points (as the edges already are), e.g.
     a B-spline surface fitted to the cylinder.  Not a correction: it
     changes the geometry the transfinite mesh is built on.  The move
     would shrink to the fit's error.
   - **(c) Project along grid lines**, not to the nearest point: move
     each wall-face node along its own block line through the volume
     (toward the centre hex), and move that whole line with it, blended.
     A larger change to `_project_walls`, for every projected fitting.
2. Should step 2's "for every projected fitting" still hold?  The census
   above is for the equal tee; the reduced tee and the wye project their
   saddle and crotch walls.  **Measured** (same census, nang 8, single):

   | fitting | wall faces' interiors | wall curves | internal faces' largest boundary move |
   |---|---|---|---|
   | reduced tee r/R 0.5 | 0.0002 R | 0 | 0 |
   | reduced tee r/R 0.9 | 0.0001 R | 0 | 0 |
   | wye 60° | 0.180 R | 0.014 R | 0.014 R |
   | equal tee 90° | 0.167 R | 0 | 0 |

   Reduced tees hardly project: nothing to correct.  The wye follows
   the equal tee's pattern: its move is in the wall faces' interiors,
   13 times its curves' largest; the task's TFI would act on it, but on
   0.014 R of the 0.18.  So whichever option you choose, it is for the
   equal tee and the wye (duct taps not yet measured).

## Design answers (2026-11-10, the user: "yes")

- Design's reading of the cause was wrong; step 1 caught it: the cells
  are sheared, not crushed.
1. **Q1: measure (a) first.**  Carry each wall face's interior moves
   into the adjacent internal faces, row by row, blended to zero toward
   the cube; between generate(2) and generate(3), keyed on tags read
   there (`Mesh.Renumber`).  A node-position correction (decision 0046
   rule 2), recorded with the projection; never wall or port nodes; no
   node or element added.  The gates hold unchanged.  **(b) is the
   fallback, for the cube only,** if (a) misses the equal tee's gates:
   then report and stop here; don't build (b) (decision 0029 found
   fitted wall surfaces erratic on the wye, and the wall sides beside
   the branch span the crease).  **(c): no.**
2. **Q2: the equal tee and the 60° wye only** (step 2's "every
   projected fitting" replaced, per the census above).  Reduced tees
   untouched: their gallery meshes stay byte-identical.  Duct taps: the
   same census; include them only if they show the pattern, else report
   the numbers.
- The gmsh.md note on `Mesh.Renumber` is committed with this task.

## Agent notes, after design's answers

- **Duct taps** (census as above, nang 8, a 0.2 × 0.1 m duct, wide-face
  tap, branch 0.03 m round or square): every move is 0 (wall faces,
  curves, internal faces).  They don't project anything measurable, so
  they stay out of scope.
- **Option (a), prototyped and measured** (in a spy on
  `_project_walls`, after the projection, before `generate(3)`; nothing
  in the library changed).  For each wall face W, each of its curves C,
  and each internal face F beside C (never a wall or port face): F's
  interior node in row j off C (row 0 = C, row J its far edge, toward
  the cube) moves by the displacement of W's first-row node in its
  column, times a weight w(j).  An internal face between two blocks
  takes the mean of its two wall faces' carries (adding them folded
  cells).  Equal tee, 90°, single layer, meshed min SJ (no inverted
  cells unless noted; non-orth. in brackets):

  | w(j) | nang 8 | nang 24 |
  |---|---|---|
  | none (today) | **0.511** (46°) | **0.353** (50°) |
  | 0.25 (1 − j/J) | 0.486 (46°) | 0.284 (52°) |
  | 0.5 (1 − j/J) | 0.416 (48°) | 0.205 (53°) |
  | (1 − j/J), mean | 0.271 (54°) | 0.071 (66°) |
  | (1 − j/J)², mean | 0.335 (49°) | 0.053 (61°) |
  | (1 − j/J), summed | −0.040, 4 inverted | −0.431, 20 inverted |
  | −0.25 (1 − j/J) | 0.476 (46°) | 0.244 (52°) |

  The SJ is highest with no carry and falls either way, more steeply at
  nang 24; the worst cell stays in a wall side's block.  So (a) misses
  the equal tee's ship gate (no case may get a lower min SJ), and per
  design's answer I stopped here: (b) not built, the wye not measured.

## Questions for design (after (a))

3. **(a) fails; is (b) next?**  Moving the internal faces doesn't relieve
   the shear: it moves the cell next to the wall curve as a whole, but
   the wall curve's nodes are fixed, so the shear reappears between the
   curve and the face's first row (the summed variant inverts exactly
   there).  The move field is a property of the wall face's own grid:
   its first row lands 0.055 R off a 0.0445 R cell at nang 24, so only
   a wall face that needs less projection (b), or a wall face whose
   first rows are graded toward its edges so they move less, can help.
   Your answer said (b) needs its own look (decision 0029's erratic
   fitted surfaces on the wye; the crease).  Options:
   - **(b) as you described**, for the cube only: a task of its own.
   - **(b′) grade the wall sides' faces toward their edges** (a `Bump`
     or progression on the wall-side blocks' lines across the face), so
     the projected first row stays inside its cell: still transfinite,
     gmsh meshes it, no correction; cheaper to measure than (b).  It
     changes the equal tee's mesh (counts unchanged), so its gallery
     mesh would change.
   - **Stop here**: the equal tee as shipped (0.305 at nang 48, clean),
     laterals and second order stay off, 0126 closes with these numbers.

## Design answer (2026-11-10, the user: "yes")

Q3: close 0126 with its numbers, no library change.  Design's
hypothesis: with refinement the cell at a wall face's edge converges to
the geometric corner angle between the internal face and the wall's
tangent plane along that cube edge, which the flat pre-projection face
hides on coarse meshes; that would explain the levelling off and why no
carry helps, and means neither (b) nor (b′) would help (not pursued).
One check before closing: compute that angle from the layout and compare
the corner SJ it implies with the meshed trend.  Equal laterals and
second order stay deferred (the fix would be a layout change, not a
correction).  The `Mesh.Renumber` note is committed with this task.

## Outcome

**Status:** closed by design's answer, no library change.

**The check of design's hypothesis: not confirmed.**  From the layout
(nang 8, single layer, `corner.py`-style computation in the session's
scratchpad), the limit of a cell's scaled Jacobian as its size goes to
zero:
- at every block corner on the wall: the |det| of the unit tangents of
  its three block edges (wall-curve tangents from a parabola through the
  corner and the spline's first two points): **min 0.665** (the eight
  cube corners, on the port columns' blocks);
- along every wall edge, |det[t, n × t, d]| (t the edge's tangent, n
  the wall's normal, d the internal face's line to the matching point
  of its opposite edge): **min 0.707** (mid-edge, on the wall sides).

The meshed min SJ is 0.511, 0.399, 0.353, 0.330 and 0.305 at nang 8, 16,
24, 32 and 48, below both and still falling, so the block faces meet the
wall far more squarely than the meshed cells do: the geometric angle
doesn't explain the slide, which stays unexplained.  One assumption
limits this: the along-edge value takes the wall face's own grid lines
to cross the edge at right angles; if the projected grid is oblique
there, the floor is lower.  That obliquity wasn't measured.

**Findings, all in `validation/tools/projection_blend.json`:**
- The move census (Agent notes): only the wall faces' interiors move
  (equal tee 0.167–0.184 R; wye 0.18 R); reduced tees and duct taps
  project nothing measurable.
- The worst cell is sheared, not crushed (its edges keep their length).
- Option (a), every variant, lowers the min SJ (the table above): no
  carry is the optimum.
- `Mesh.Renumber`: recorded in `docs/integrations/gmsh.md`.

**Files.**  `docs/integrations/gmsh.md` (the `Mesh.Renumber` quirk),
`validation/tools/projection_blend.json`, this task.  No library or
test change, so the suite wasn't rerun; the gallery is untouched.

**Proposed follow-ups.**
- Measure the projected wall face's grid-line angle at its edges (the
  one assumption above) if the slide matters again.
- A redesign of the cube's layout would be the route to equal laterals
  and second order; the slide's cause is unknown (the grid's obliquity
  is the open lead); not planned (the user's simplicity priority).
