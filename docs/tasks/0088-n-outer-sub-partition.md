# 0088 — `n_outer = 8` as a sub-partition of the O-H face

- **Status:** ready (after 0082; don't run alongside 0084, which also
  edits `sections/oh.py`)
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

## Questions for design

## Outcome
