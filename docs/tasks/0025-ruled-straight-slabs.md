# 0025 — Ruled side surfaces for straight slabs, and a wall-exactness check

- **Status:** done
- **Decision:** [0015 — Exact walls in straight slabs, and how convergence is judged](../decisions/0015-exact-straight-slabs-and-convergence-studies.md)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  A `Straight` with several axial layers has OCC plate side
surfaces, and gmsh puts the interior nodes on them, off the cylinder
(RESEARCH §7.4, `docs/integrations/gmsh.md`).
- Single-layer pipe: up to 1.08 % of R inside the circle (task 0020).
- Two-layer pipe, 16 layers: −0.15 % to +0.69 % of R, on the outer wall
  and on the fluid/steel interface.  The same at `nang` 6 and 24.
- It biased Poiseuille Δp by +2.6 % at every level (task 0020).
- It affects every `Straight`, including every `extend_open_ends` run,
  and the material-layer thicknesses of CHT meshes.

DESIGN §6 now says: a filled surface may carry interior nodes only where
it is the exact surface, and straight slabs use ruled surfaces.

**Where.**
- `hexmesh/assembly/sweep.py`:
  - `_fill_sweep`, the `side_surface=_ruled if path.prism else None`
    argument (about line 340);
  - `_ruled` and its docstring ("single axial layer leaves no interior
    nodes" is no longer the only use).
- `hexmesh/assembly/corners.py:187–291`: where `side_surface` is applied.
  Check that it covers every cylindrical side face of every layer: outer
  walls **and** material interfaces.
- `tests/test_fitting_conformance.py`: the new check.

**Do.**
1. **Ruled sides for straight slabs.**  Use `_ruled` for the side faces of
   every straight slab (`path.is_straight`), whatever its `n_layers`.
   - A ruled surface is the exact cylinder only between two congruent,
     parallel arcs.  Check that a straight slab's two stations always
     are: zero corner offset, same radii.  If a case exists where they
     are not (for example a non-zero `offsets[k]`, or a straight slab in
     a layer-termination sweep, task 0018), handle it or reject it in
     `validate()`, and record which under *Agent notes*.
   - Planar side faces (the radial cuts between O-H patches, the inner
     square's sides) are exact already.  Leave them unless the change is
     simpler applied uniformly; record the choice.
2. **Wall-exactness check in the conformance kit.**  For every kit case:
   - collect the nodes gmsh classifies on each wall and material-
     interface surface (`getNodes(2, tag, includeBoundary=True)`);
   - check each against its analytic surface, with tolerance 1e-9 · R:
     - `Straight`: distance to the axis = layer radius;
     - `Bend`, `Elbow`: the torus (distance from the bend circle);
     - `Reducer`: the cone (radius linear in axial position);
     - `MiterBend`: the cylinder of the leg the node belongs to;
   - for `SplinePipe` and `Closure`, which have no closed-form surface:
     assert one axial layer per slab, so no surface carries interior
     nodes; the nodes on the station curves are exact by construction.
   - Make the check reusable (a helper) so new fittings must pass it.
   - **The check must fail on the current code**: run it before step 1
     and record the measured maximum deviation per case under *Agent
     notes*.
3. Update `docs/integrations/gmsh.md` (the "Transfinite interior nodes
   land on the filled surface" entry): add the fix and the task number.

**Accept.**
- The new check passes for every kit case.  Before the fix it failed
  for every case with a multi-layer `Straight`.
- Cell counts, physical groups and topology unchanged
  (`test_topology_invariance`, the cell-count tests).
- Min SICN per kit case unchanged or better; record before/after for
  the straight cases.
- Build and mesh time for the kit: record before/after (ruled surfaces
  should cost nothing; report if they do).
- Full suite: no new failures.

**Out of scope.**
- The tee's run slabs (DESIGN deviations table).  If ruled sides look
  like they would fix them, propose it as a follow-up under *Outcome*.
- Re-running the Poiseuille validation (task 0020 does that).

## Agent notes

- **The check.**  `wall_deviations(asm)` in
  `tests/test_fitting_conformance.py` is reusable: it returns, per
  fitting, the largest node distance from the analytic surface, × outer
  R.  `TestConformance.test_walls_exact` asserts ≤ 1e-9 for every case.
  - It reads the surfaces from the fitting's own `Path`:
    - **arc path:** the torus;
    - **straight or prism path:** the axis line of the nearest slab
      segment, with radii linear between stations, so a reducer's cone
      and miter legs are covered.  A node on a miter cut is on both
      legs' cylinders;
    - **otherwise** (SplinePipe, Closure): it asserts one axial layer per
      slab and doesn't measure.
  - Surfaces are the wall and material-interface surfaces bounding the
    fitting's volumes.  The `{layer}_end` annuli (station planes, task
    0018) are excluded.
  - Tee cases skip: their run slabs are a DESIGN deviation.
- **Two helper bugs, found by the first run and fixed before measuring:**
  - miter nodes on a cut plane fell outside both legs' axial ranges, so
    nodes are now assigned to the nearest segment;
  - end annuli were included.
- **Before the fix (measured):** every case failed, because every kit
  case contains a multi-layer `Straight`.  Per fitting, `Straight`s were
  4.0e-3 to 6.9e-3 R off: 6.9e-3 with 2 layers, 4.0–4.1e-3 with 3,
  5.1e-3 graded.  `Bend`, `Elbow`, `Reducer` and `MiterBend` were exact
  (≤ 1.7e-15).
- **The fix:** `sweep_fill` passes `_ruled` for every slab with
  `path.is_straight or path.prism` (it was prism only).  `corners.
  connect_layer` applies `side_surface` to the outer arc sides (walls),
  the inner arc sides of the core, and, through
  `prev_outer_side_surfs`, the material interfaces.  So all cylindrical
  side faces are covered.
- **Congruent stations: nothing to reject.**  A ruled surface between
  coaxial arcs at the same angles, joined by straight lines, is exact for
  a cylinder and also for a cone (a reducer, whose stations differ in
  radius).
  - A non-zero corner offset (`straight-rolled-90`) only relabels arcs
    that are at the same physical angle.
  - Termination stations (task 0018) keep the common layers' radii.
  - All three are kit cases and measure exact.
- **Block layouts too (`blocks.py`).**  The first full-suite run failed
  6 tests (`test_block_straight_reproduces_sweep` ×4,
  `test_block_layout_grades_like_sweep` ×2).  They require
  `BlockStraight` to reproduce the sweep's `Straight` node for node, and
  `BlockLayout._surface` still used plate filling.
  - It now uses `_ruled` for any 4-sided face with arcs on one pair of
    opposite sides and straight lines on the other.  Such a face is a
    cylinder patch whenever its arcs are coaxial and congruent, which
    holds for every such face the layouts build.
  - **Side effect on the tees (scope note).**  The tee's run slabs are
    built this way, so the tee meshes change.  This was out of scope, but
    keeping `BlockStraight` identical to `Straight` requires it.
  - **`tee-0.5`, measured against a snapshot:**
    - 135 of 1579 nodes moved, by at most 0.69 mm (6.9e-3 R);
    - 21 of them are run-wall nodes, now exactly on the run cylinder
      (previously up to 6.9e-3 R off);
    - the other 114 are interior nodes, following their boundary;
    - `tee-0.9-oblique` is the same;
    - min SICN is unchanged: 0.1490 and 0.2627.
  - Faces bounded by intersection curves still use plate filling, so the
    tee stays skipped in `test_walls_exact`.
- **Planar radial cuts left as plane surfaces:** they are exact already,
  and the change is no simpler if applied uniformly.

## Questions for design

_None._

## Outcome

- **Files:**
  - `hexmesh/assembly/sweep.py`: the `side_surface` choice, and the
    `_ruled` docstring;
  - `hexmesh/assembly/blocks.py`: `_ruled` for arc/line/arc/line faces
    (`_ruled_cylinder`);
  - `tests/test_fitting_conformance.py`: `wall_deviations`,
    `_layer_radii`, `test_walls_exact` (+27 tests: 25 pass, 2 tee
    skips);
  - `docs/integrations/gmsh.md` (fix noted; untracked).
- **Measurements per kit case.**  Max deviation is × R over all fittings;
  min SICN for the whole case:

  | Case | max dev before | after | min SICN before | after |
  |---|---|---|---|---|
  | straight | 6.9e-03 | 2.8e-16 | 0.2899 | 0.2899 |
  | straight-2layer | 6.9e-03 | 2.2e-16 | 0.2899 | 0.2899 |
  | bend | 6.9e-03 | 8.3e-16 | 0.2899 | 0.2899 |
  | bend-rolled-2layer | 6.9e-03 | 4.4e-16 | 0.2885 | 0.2885 |
  | closure-planar | 4.1e-03 | 1.8e-15 | 0.1241 | 0.1241 |
  | closure-twisted | 4.1e-03 | 1.9e-15 | 0.1146 | 0.1146 |
  | bend-as-closer | 4.1e-03 | 1.8e-15 | 0.1489 | 0.1490 |
  | straight-rolled-90 | 6.9e-03 | 2.2e-16 | 0.2899 | 0.2899 |
  | bend-rolled-180 | 6.9e-03 | 6.9e-16 | 0.2170 | 0.2170 |
  | tee-0.5 | skip | skip | 0.1490 | 0.1490 |
  | tee-0.9-oblique | skip | skip | 0.2627 | 0.2627 |
  | miter-1cut | 6.9e-03 | 1.4e-15 | 0.1685 | 0.1685 |
  | miter-3cut-2layer | 6.9e-03 | 1.3e-15 | 0.2899 | 0.2899 |
  | miter-rolled | 6.9e-03 | 4.4e-16 | 0.2899 | 0.2899 |
  | elbow-short | 6.9e-03 | 1.6e-15 | 0.2255 | 0.2255 |
  | reducer | 6.9e-03 | 3.5e-16 | 0.1780 | 0.1780 |
  | expander | 6.9e-03 | 2.8e-16 | 0.1780 | 0.1780 |
  | reducer-2layer | 6.9e-03 | 3.3e-16 | 0.2033 | 0.2033 |
  | spline-s-bend | 6.9e-03 | 1.5e-15 | 0.2591 | 0.2591 |
  | spline-3d-2layer | 6.9e-03 | 2.2e-15 | 0.2899 | 0.2899 |
  | straight-graded-2layer | 6.9e-03 | 2.2e-16 | 0.2733 | 0.2733 |
  | bend-graded-2layer | 6.9e-03 | 1.3e-15 | 0.1867 | 0.1867 |
  | reducer-graded | 6.9e-03 | 3.5e-16 | 0.1780 | 0.1780 |
  | closure-graded | 4.1e-03 | 1.8e-15 | 0.1489 | 0.1490 |
  | straight-insulation-gap | 6.9e-03 | 1.8e-16 | 0.2899 | 0.2899 |
  | bend-insulation-ends | 6.9e-03 | 1.3e-15 | 0.2010 | 0.2010 |
  | spline-graded | 6.9e-03 | 1.5e-15 | 0.1866 | 0.1866 |

  - Min SICN is unchanged everywhere, or 1e-4 better (two closure
    cases).
  - Kit build + mesh time: 91.5 s before, 86.6 s after, so ruled
    surfaces cost nothing.
- **Topology:** cell counts, physical groups and topology are unchanged;
  see the suite.
- **Proposed follow-up: the rest of the tee.**
  - The tee's arc/line faces are now ruled (see *Agent notes*), so its
    run-wall nodes are exact.
  - Faces bounded by the intersection curves still use plate filling.
    They need their own look before the tee can join
    `test_walls_exact`: an analytic surface per junction face, or one
    axial layer there.
- **Tests:** 684 passed, 2 skipped (tee exactness); `-m openfoam` conversion tests 5 passed.  The first run failed 6 block-layout tests, fixed in `blocks.py` (Agent notes).
