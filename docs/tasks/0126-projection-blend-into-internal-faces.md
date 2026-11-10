# 0126 — Carry the wall projection's move into the internal faces: stop the equal tee's slide with refinement, and re-measure equal laterals and second order

- **Status:** ready
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

## Questions for design

## Outcome
