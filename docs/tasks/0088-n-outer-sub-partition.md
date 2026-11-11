# 0088 — `n_outer = 8` as a sub-partition of the O-H face

- **Status:** done
- **Decision:** [0005 — `n_outer = 8` as a sub-partition](../decisions/0005-n-outer-as-sub-partition.md) (accepted 2026-11-02, with its condition on exact core cuts); [0010](../decisions/0010-section-symmetry-period.md) as amended; DESIGN §6.1, §7, §9
- **Depends on:** 0082 (the O-H layout in `sections`).

Ground rules for all tasks: [README](README.md#ground-rules).  This task
works in `sections/`, `assembly/` (`corners.py`, `interface.py`,
`sweep.py`) and `core/spec.py`.

**Why.**  `n_outer = 8` builds a different face today (one 8-sided
centre patch, `build_oh_circle8`), which can't bound a hex block, so
validation rejects it (DESIGN §9).  Decision 0005 defines `n_outer = 4m`
as the 4-corner face cut along existing grid lines.  The design session
measured it (RESEARCH §9.2):
- connectivity is identical;
- ring cuts are exact;
- straight, uniformly meshed core cuts miss the full patch's nodes by
  up to 0.0043 R.

With the core cut-line nodes on the full patch's TFI isoline, the
partitioned face reproduces the 4-corner mesh (Coons restriction).

**Where.**  `sections/oh.py` (the partition in the pure declaration and
the GMSH face); `faces`' successor modules from 0082
(`build_oh_circle8` goes); `assembly/corners.py` (`frame_offset`,
`corner0_angle`, P); `assembly/interface.py` (`check_supported`);
`core/spec.py`; tests.

**Do.**
1. **Partition in the O-H layout.**
   - `n_outer = 4m` (m ≥ 1, `nang % m == 0`, already enforced in
     `PipeSpec`): each ring patch is cut into m and the core into
     m × m, along the grid lines at the patch fractions j/m.
   - Corner and patch numbering follow DESIGN §6.1 (corner k at
     `π/4 + rot + k·2π/n_outer`).
   - The pure declaration (corners, edges, patches) and the GMSH face
     both come from the layout (DESIGN §3.1).
2. **Exact cut lines.**
   - **Ring cuts:** straight lines meshed like the radials (same count
     and progression).  The design session measured these exact.
   - **Core cuts:** compute the full core patch's discrete TFI isoline
     from its boundary nodes, before GMSH (pure numpy).  Then make
     gmsh's nodes on the cut lines sit there.
     - First candidate: mesh dimension 1, move the cut-line nodes with
       `gmsh.model.mesh.setNode` (coordinates and parametric
       coordinate), then mesh 2-D / 3-D.  Decision 0029's wall
       projection already relocates nodes between stages.
     - If gmsh's transfinite fill doesn't take relocated 1-D nodes,
       record that in `docs/integrations/gmsh.md` (version, evidence,
       date).  Then try the next mechanism; if none works, stop and
       write *Questions for design*.
   - This must hold for circle, rectangle and blend O-H cores, and in
     3-D slabs (the cut surfaces' interior nodes).
3. **Replace `build_oh_circle8`** with the partitioned face.  Allow
   `n_outer = 8` in `check_supported` for sweeps (`Straight`, `Bend`,
   `Elbow`, `MiterBend`, `SplinePipe`, `Closure`, `Reducer`,
   `Transition` between O-H ends).
   - Junctions (`Tee`, duct taps, `Wye`) and equipment keep rejecting
     `n_outer ≠ 4`, with a structured error.  Their templates don't need
     it, and accepting finer port partitions is deferred (decision
     0005, "Deferred").
   - `n_outer ≠ 4` with `layout="h"` (if 0084 is done) is an error.
4. **Symmetry period:** circular O-H P = π/2 for every `n_outer`
   (decision 0010 as amended).  `frame_offset` and roll absorption use
   it, and twist never exceeds π/4.
5. **Equality test** (the point of the task): for `n_outer` 4 and 8
   (and 12 with `nang % 3 == 0`), on a circle, a 2:1 rectangle and a
   transition blend, at `nang` 8 and 24, graded and uniform, and one
   bent sweep, check:
   - identical node count and element count;
   - element→node connectivity identical after matching nodes by
     position;
   - **max node displacement below 1e-10 R**, in 2-D faces and in 3-D
     sweeps.

   Report the measured maximum.

**Accept.**
- The equality test passes for every case in step 5.
- The conformance kit passes with `n_outer = 8` on every sweep.
- `build_oh_circle8` is gone, and nothing references it.
- DESIGN §9's `n_outer` row can be removed: propose it in *Outcome*,
  and the design session removes it.  CLAUDE.md's `n_outer` table row
  ("rejected") is updated by the design session too.
- Every existing `n_outer = 4` mesh unchanged (task 0065's method).
- Full suite: no new failures.

**Out of scope.**  Fittings accepting a finer port partition than their
template, and per-interface partition resolution (decision 0005,
"Deferred"); junction templates that use `n_outer = 8`; the H layout's
partitions.

## Agent notes

- **Step 2, first candidate: fails as stated; the next mechanism works**
  (2026-11-11; scratch script, circle face, `nang` 4/8/24, `mprg`
  1/1.2/1.05; recorded in `docs/integrations/gmsh.md`, "Transfinite
  surfaces: parameters from averaged opposite sides").
  - Moving the core cut lines' 1-D nodes onto the full patch's TFI
    isoline after `generate(1)` works: they stick through `generate(2)`.
  - But the sub-patch interiors still miss by 1.3e-4 R: gmsh 4.12.1
    parametrises a transfinite patch by the *averaged* segment lengths of
    opposite sides, so a sub-patch averages a half inner arc with a cut
    line spaced differently.  The decision's "a Coons patch restricted
    to a sub-rectangle is the Coons patch of that sub-rectangle" holds
    for a Coons patch, not for gmsh's fill.
  - Next mechanism, the one decision 0029 uses: also set each
    sub-patch's interior nodes to the full patch's grid after
    `generate(2)`.  Result: identical counts and connectivity, max shift
    2.7e-15 R.
- **Exact 1-D nodes on the pieces need more than symmetry.**  A half
  arc's nodes equal the full arc's only where gmsh's placement is
  symmetric about the split.  A miter station's stretched (elliptic)
  arcs aren't; gmsh's own placement on the full curve isn't reproducible
  in numpy.  So each partitioned face also builds the 4-corner side
  curves (sharing the corner points), as construction curves meshed
  exactly as the 4-corner builder meshes them.  After `generate(1)` their
  nodes are copied onto the halves and the split vertex.  This also
  gives `mbmp` ≠ 1 for free: the full curve carries the bump.  They are
  in no surface, so in no physical group, so not written.
- **Plan of the placement** (per partitioned face, every layer):
  - after `generate(1)`: halves and split points from the full curves;
    ring cuts `(1 − f)·inner_split + f·outer_split` with f the corner
    radial's node fractions (the ring's isoline is that line); core
    cuts and the centre from the full core's Coons grid (gmsh's
    averaged-length convention, `sections.oh`);
  - after `generate(2)`: core and ring sub-patch interiors from the full
    patches' Coons grids.
  - 3-D: only `Straight` slabs have several layers, and their faces are
    unstretched; there the cut surfaces and side surfaces are
    translations, so gmsh's fill is exact (to verify).  All other sweeps
    are one layer per slab: no interior nodes.
- **Scope: m = 2 (`n_outer` 8) only.**  At m = 3 the core's isolines at
  1/3 and 2/3 are curved, not straight (only the middle isoline is, by
  symmetry), so straight core cuts can't hold their nodes; ring cuts
  would be fine.  `n_outer` 12 stays rejected with a structured error;
  see *Questions for design*.
- **Wider than the task's "Where"**: `CircleShape.period` is
  2π/`n_outer` (decision 0010 as amended: π/2); `signature` uses
  360°/`n_outer`; `PipeSpec` rejects a rectangle with `n_outer` ≠ 4
  (`rect_stack_needs_n_outer_4`); `section_quality` and `first_cell`
  reject `n_outer` ≠ 4 (they can use the 4-corner spec: same mesh).

- **The partition records itself** (design's condition, decision 0046
  rule 5): `Assembly.corrections[...]["sub_partition"]`, for every
  fitting with a partitioned port or station; `test_corrections`
  covers an `n_outer = 8` assembly at orders 1 and 2.
- **Second order:** `setOrder(2)` puts a curve's mid-edge node at its
  parameter midpoint, and a half B-spline isn't parametrised as the
  whole; the full sides are meshed too, so the halves' mid-edge nodes
  are copied from them (`place_partition_nodes` stage 3, before a
  bend's revolve).

## Questions for design

1. **`n_outer = 12` and up.**  Rejected (`section_not_supported`, "n_outer
   must be 4 or 8").  With m = 3 the core's grid lines at 1/3 and 2/3
   are curved (only the middle one is straight, by symmetry), so a
   straight core cut can't carry them.  Curved cuts (a spline through
   the TFI isoline) would work in principle, but gmsh places a curve's
   nodes by its own parametrisation, and they would have to be moved like
   the halves'.  Keep rejecting, or a task for curved cuts?
2. **Step 5's 1e-10 R in multi-layer slabs.**  A `Straight` with several
   layers per slab and curved sides (a circle) agrees to 1.4e-7 R, not
   1e-10 R.  The 4-corner mesh is itself 1.3e-7 R off the exact
   extrusion there: gmsh fills a curved side face's interior in the
   face's parameter space, and a half face is parametrised differently.
   The cut mesh is closer to the exact extrusion (2.7e-9 R).  Matching
   the 4-corner mesh to 1e-10 R would mean reproducing gmsh's own error
   (building the full side faces as construction surfaces too).  The
   test bounds the two meshes by 1e-6 R and each by its distance from
   the exact extrusion.  Accept that, or ask for the exact extrusion
   (which would change the `n_outer = 4` meshes)?
3. **Second order on a `Transition`.**  Its side faces are B-spline
   fillings; their mid-face nodes are placed in each face's parameter
   space, so the cut mesh's differ from the 4-corner mesh's by up to
   4e-4 R (circular arcs: 3e-13 R).  Both are nodes on an OCC filling
   of the same boundary, neither on an exact surface.  Accept and
   document, or reject `order=2` for `n_outer = 8` transitions?

## Design answer (2026-11-11, the user, choosing the recommended options)
1. **n_outer 12 and up: keep rejecting.** No use case: junctions need corners at 0/90/180/270° only (DESIGN §7), and curved cuts would mean more nodes corrected after meshing, for nothing. The structured error stays. The supported values are 4 and 8 (the error's text already says so).
2. **Multi-layer slabs: accept the 1e-6 R bound** between the two meshes, plus each mesh's distance from the exact extrusion. The n_outer 4 meshes stay as they are. The 8-corner mesh is closer to exact (2.7e-9 R against 1.3e-7 R); say so in the Outcome. It's gmsh filling a curved face in that face's own parameter space (record it in gmsh.md if it isn't there already).
3. **Second order on an n_outer 8 Transition: accept and document.** Both meshes' mid-face nodes lie on an approximate OCC filling, and second order on Transitions isn't verified (task 0077 covered straights, bends and tees). API.md, at mesh(order=2) or n_outer, gets one line: on an n_outer 8 Transition, the mid-face nodes differ from the 4-corner mesh's by up to 4e-4 R.

## Outcome

Done 2026-11-11.

**What changed.**
- `sections/oh.py`: the partition in the pure layout (`partition`,
  `split_corners`, `CENTRE`; the cut corners, core cuts and four core
  patches in `levels`/`patches`; `section_cells`), and `coons`, gmsh's
  averaged-length fill.
- `sections/oh_gmsh.py`: `build_oh_split` replaces `build_oh_circle8`
  (circle, rectangle, blend; the 4-corner sides as construction curves);
  `build_ring`'s 8-corner branch; `place_partition_nodes` (stage 1
  after `generate(1)`, stage 2 after `generate(2)`, stage 3 after
  `setOrder(2)`).
- `assembly/corners.py`: four core blocks around a centre axial line,
  cut surfaces at the odd corners; the core patches turn with the
  corners (offset / 2).  `_realise.mesh()` places the nodes (only when
  a partitioned face exists: the 4-corner path is unchanged) and records
  them as `corrections[...]["sub_partition"]`.
- `check_supported` takes 4 and 8; 12 and up: `section_not_supported`
  (design answer 1).  Junctions keep `junction_needs_rot_0_n_outer_4`;
  `Tee.resolve` now checks it before it measures the template (it raised
  a bare `KeyError`).  `PipeSpec`: the period is π/2 for a circle at
  every `n_outer`; `side_counts`, `corners()` (always the 4 structural
  corners), `first_cell` and rectangle stacks take 8; the signature's
  period and counts are the 4-corner face's.  `section_quality` computes
  on the 4-corner spec.  `Transition.station` keeps `n_outer` (it built
  4-corner stations).
- Docs: API (`n_outer`, `first_cell`, rectangle stacks, `sub_partition`,
  the order-2 `Transition` line), GUIDE (the cut face), CHANGELOG,
  `docs/integrations/gmsh.md` (the fill convention, curved faces in their
  own parameter space, `setOrder(2)` midpoints); `support.json`
  regenerated (only the `circle_n_outer_8` entries changed; the probe's
  `Transition` outlet is an 8-corner O-H rectangle).

**Measurements** (`tests/test_n_outer_partition.py`, 22 tests; counts,
connectivity after matching by position, largest node distance):
- 2-D faces, circle and 2:1 rectangle, `nang` 8 and 24, graded, bumped,
  stretched (a miter station), one cell per half, a blend station:
  identical, ≤ 2.7e-15 R.
- 3-D, one layer per slab (bend, miter, rectangle bend, reducer,
  transition, spline): identical, ≤ 4e-15 R.
- 3-D, multi-layer `Straight` of a circle: identical connectivity, 1.4e-7
  R apart.  The 4-corner mesh is 1.3e-7 R off the exact extrusion, the
  cut one 2.7e-9 R: **the 8-corner mesh is the closer to exact.**  gmsh
  fills a curved face's interior in that face's parameter space.
  Bounded at 1e-6 R plus each mesh's distance from the extrusion (design
  answer 2).
- Order 2: arcs identical to 3.7e-13 R (miter, bend); an `n_outer = 8`
  `Transition`'s mid-face nodes differ by up to 4e-4 R (design answer 3,
  documented in API.md).
- What gmsh alone gets wrong, now recorded per fitting: largest
  `sub_partition` move 2e-4 m on R 0.05 m (4e-3 R, 0.04–0.14 edge
  lengths); with `mbmp` 1.3, 0.026 R (the halves are meshed uniformly,
  then take the full sides' nodes).

**Decision 0005's argument.**  "A Coons patch restricted to a
sub-rectangle is the Coons patch of that sub-rectangle" holds for a Coons
patch but not for gmsh's fill, which parametrises a patch by the averaged
segment lengths of opposite sides; exact cut lines alone leave the
sub-patch interiors 1.3e-4 R off.  The nodes are set after `generate(2)`
instead (decision 0029's mechanism), and recorded.

**Tests.**  Full suite: 4354 passed, 15 skipped, 1 xfailed (3 workers,
40 min; one expected failure in the first run, `test_first_cell`'s "8 is
rejected", updated).  New: `test_n_outer_partition.py` (22), 16
`n_outer = 8` conformance cases (96 tests), an `n_outer = 8` corrections
test (2).  Updated for the new behaviour: `test_faces` (the split face),
`test_sections`, `test_corners`, `test_signature`, `test_layer_outlines`,
`test_agent_manifest`, `test_corrections`, `test_first_cell`.
- Every `n_outer = 4` mesh unchanged: the 31 examples written with HEAD
  and with this tree are byte-identical (`$Comments` aside).

**Proposed for design.**
- DESIGN §9's `n_outer` row can be removed; CLAUDE.md's `n_outer` table
  ("8: no, `check_supported` rejects it") and its "Why `n_outer = 8` is
  rejected" bullets are out of date.
- Decision 0005: the note above (gmsh's fill doesn't restrict like Coons).

**Follow-ups (candidates).**
- A junction taking an `n_outer = 8` port (decision 0005, "Deferred").
- Second order on `Transition`s is unverified at any `n_outer` (task 0077
  covered straights, bends and tees).

