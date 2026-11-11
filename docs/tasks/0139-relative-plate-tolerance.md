# 0139 — Interior plates' tolerance relative to the face

- **Status:** done
- **Decision:** task 0128's design answer (2026-11-11, Q1: "yes"); [0018](../decisions/0018-future-vascular-networks.md) (constraint 8); [0046](../decisions/0046-gmsh-meshes-hexmesh-corrects.md)
- **Depends on:** none.  Not alongside task 0088 if it touches
  `blocks.py` or `corners.py`: coordinate in the shared tree.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0128 found hexmesh isn't scale-free.  The junction's
interior plates (`blocks.py` `addSurfaceFilling(loop)`, ~line 578, and
`corners.py`'s default `side_surface`) take gmsh's default
`tol3d = 1e-4`, an absolute length (0.1 mm).  The wall plates already
pass `_WALL_TOL × scale`.  Measured on the README tee (`docs/integrations/gmsh.md`,
2026-11-11): with the default, a network scaled by s moves interior
nodes by 7e-5 of the size at s = 0.5 and 2.5e-4 at 0.05, and fails
below about 1:33; with `tol3d` scaled, it is exact (1e-15) at half size
and builds at 1:33.  The user: make it relative.

**Where.**  `hexmesh/assembly/blocks.py`, `hexmesh/assembly/corners.py`,
the gallery (`docs/gallery/build.py` output, `metrics.json`,
`GALLERY.md`, README metrics), pinned test values, `tests/test_units.py`,
`docs/GUIDE.md` (*Current limitations*), API.md (`hexmesh.units`),
`docs/integrations/gmsh.md`, `CHANGELOG.md`.

**Do.**
1. **The tolerance:** every `addSurfaceFilling` hexmesh calls passes
   `tol3d` relative to the face's extent (the largest side of its
   loop's bounding box, as the wall plates' `scale`).  Choose the factor
   by measurement: the candidates are 1e-3 (0.1 mm on a 0.1 m face,
   today's value at that size) and `_WALL_TOL` (1e-6, the wall plates').
   Pick the one that keeps quality and build time, and say why under
   *Agent notes*, with the numbers (min SJ, build time of the junction
   examples, failures if any).  One named constant, beside `_WALL_TOL`.
2. **Scale test:** extend `tests/test_units.py`: the README tee at
   s = 0.5 and 0.05 gives the same nodes as full size × s to 1e-9 of
   the size (it drifted 7e-5 and 2.5e-4).  Re-measure where it now
   fails (bisect s), and move the strict `xfail` to the first scale that
   still fails (the B-spline fill, OCC's fixed tolerance, out of scope);
   if the 1:50 case now builds, it becomes a passing test.
3. **Meshes change, deliberately:** regenerate the gallery (images,
   `metrics.json`, `GALLERY.md`, README metrics) and update pinned
   numbers in tests, each with the old and new value under *Agent
   notes*.  Expected: interior nodes of junctions move by up to ~1e-4 of
   the size; quality figures change little.  A change larger than that
   is a finding.
4. **Docs:** GUIDE *Current limitations* and API.md's "Length units"
   paragraph with the new scale limit; `gmsh.md`'s entry (the fix and
   its numbers); a CHANGELOG line saying junction meshes move slightly
   (by how much).

**Accept.**
- No hexmesh `addSurfaceFilling` call uses gmsh's default `tol3d`.
- The scaled README tee matches full size to 1e-9 down to the
  re-measured limit; the docs state that limit.
- Gallery regenerated; full suite: no new failures.

**Out of scope.**  OCC's B-spline fill tolerance (`Courbes non
jointives` near 1 mm radius), and an output `scale=` (decision 0047's
note): revisit after this task's measurements.

## Agent notes

- **One plate function** (refined step 1): `hexmesh/_occ.py` `plate(loop,
  points=None)` is the only place hexmesh calls `addSurfaceFilling`
  without wall points.  `blocks.BlockLayout._plate` passes points along
  the face's sides (as before for 0141's retry); `corners.py`'s default
  `side_surface` (both slab builders) is `_occ.plate`, whose extent is
  the loop's corner points, read from `_occ`'s records (loops made by
  `_occ.curve_loop`), so no synchronize (`test_build_sync`).  The
  constants sit together in `_occ`: `WALL_TOL` (1e-6; `blocks._WALL_TOL`
  is it), `PLATE_TOL`, `PLATE_RETRY_TOLS` (task 0141's retry, now at the
  other candidate), and `_occ.quiet` (was `blocks._quiet`).
- **The factor (step 1): 1e-3.**  15 junction examples, HEAD against
  each candidate (serial, 2026-11-11): both build every example, min SJ
  identical to HEAD in all 15, build time the same within noise (sum
  100 s HEAD, 103 s at 1e-3, 104 s at 1e-6).  Node drift from today's
  mesh, fraction of the size: 1e-3 ≤ 5.2e-5, 1e-6 ≤ 1.4e-4.  Scaled
  README tee: 1e-3 builds to 1:33, 1e-6 fails at 1:20.  1e-3 is today's
  1e-4 m on a 0.1 m face.  The retry (0141) is at 1e-6.
- **Finding: `tol2d` is a length too.**  With `tol3d` relative, the tee
  still drifted 2.3e-5 at 1:10 and 2.4e-4 at 1:20, and failed at 1:50
  (as task 0128's probe).  Scaling `tol2d` (documented as parametric)
  with s cut 1:10 to 7.6e-7; `Geometry.Tolerance` changed nothing.  So
  every plate (wall plates included) passes `tol2d` = `PLATE_TOL2D`
  (1e-4) × the extent, today's 1e-5 on a 0.1 m face.
- **Step 2, the 1e-9 target holds only at exact scales.**  Drift of the
  README tee against full size × s: 1.0e-15 at 0.5, 1.4e-15 at 0.25,
  7.6e-7 at 0.1, 3.6e-6 at 1/16, 4.5e-6 at 0.05, 6.1e-5 at 1/32,
  3.3e-3 at 0.01, 5.8e-3 from 1/128 to 0.001.  At 0.1 only four
  interior plates move (8 surface nodes, then the volume nodes): inputs
  scaled to the last bit, and the plate is chaotic at rounding level
  (0141).  Below ~1/16 wall plates move too: OCC's fixed tolerance
  (`Precision::Confusion` assumed), out of scope.  Cell count and min
  SJ (0.3156) are the same at every scale down to 0.001, and **it
  builds down to 0.001** (no failing scale found), so there is no strict
  `xfail` to move: `test_small_tee_builds` (1:50) is replaced by a
  1:1000 case of `test_scaled_build_same_cells_and_quality`.  The
  tests: exact (< 1e-9) at 0.5 and 0.25; < 1e-5 at 0.05.
- **Step 3, gallery:** the 11 examples whose meshes change (same list as
  the nonzero drifts; the other 20 byte-identical to HEAD) re-run
  serially.  Min SICN identical in all 11; mean SICN changes in the 4th
  decimal (tee 0.47800 → 0.47775, the largest).  `junction_walls`'
  committed entry was stale before this task (10176 cells; HEAD and
  this task both mesh 16576): updated by the re-run.  The gallery's
  `build_s` are up to 2.6× the committed (2026-11-10) values: machine
  state, not the change.  Interleaved timing of `pcf_line`: HEAD 21.6,
  12.8, 14.2 s; this task 12.1, 11.7, 10.3 s.  No pinned test value
  changed (1633 junction-related tests pass).

## Questions for design

## Outcome

Done 2026-11-11.

- **Code.**  `hexmesh/_occ.py`: `plate(loop, points=None)`,
  `curve_loop`, `quiet`, and the constants `WALL_TOL` (1e-6),
  `PLATE_TOL` (1e-3), `PLATE_RETRY_TOLS` ((1e-6,)), `PLATE_TOL2D`
  (1e-4).  `assembly/blocks.py`: `_plate` → `_occ.plate`; wall plates
  pass relative `tol2d`.  `assembly/corners.py`: the slab builders'
  default side face is `_occ.plate`, their loops `_occ.curve_loop`.  No
  `addSurfaceFilling` call is left at gmsh's defaults.
- **Measurements.**  See *Agent notes*: factor 1e-3 chosen; `tol2d`
  acts as a length; the tee builds down to 1:1000, exact at 1:2 and
  1:4, 4.5e-6 at 1:20, up to 0.6 % below about 1:30 (OCC).
- **Tests.**  `tests/test_units.py`: 1:1000 tee (same cells and min
  SJ), exact nodes at 1:2 and 1:4, drift < 1e-5 at 1:20; the strict
  `xfail` at 1:50 is gone (it builds; this also ends the XPASS on CI
  reported by design).  Full-size meshes cached in the module.  Runs:
  `test_units` 12 passed; junction-related set (19 files) 1633 passed,
  1 skipped.  Full suite not run (shared machine, low memory).
- **Docs.**  GUIDE *Current limitations* and the units paragraph, API.md
  "Length units", `gmsh.md` (the fix, the `tol2d` finding, the numbers;
  0141's entry updated), CHANGELOG.  Gallery: 11 examples re-run,
  pages and README metrics rewritten.
- **Accept.**  The 1e-9 match holds at exact (power-of-two) scales only;
  elsewhere the drift is bounded as measured, and the docs state that
  and the 1:1000 build limit.  A deviation from the task's wording
  (0.05 to 1e-9), for design to judge; the cause is OCC's, out of scope.
- **Follow-ups.**  An output `scale=` (decision 0047's note): building
  at a reference size and scaling the mesh would make small networks
  exact, since 1:2 and 1:4 already are.

## Design review (2026-11-11)

**Accepted, with the deviation.**
- **The 1e-9 match at every scale was the wrong target.**  It asked for
  more than hexmesh controls.  Two things stand in the way, both outside
  hexmesh's plate tolerances:
  - the plate is chaotic at rounding level (0141), and a non-power-of-two
    scale changes the inputs' last bits;
  - OCC keeps a fixed tolerance of its own.

  What 1.0 needs holds at every scale down to 1:1000: the same cells and
  the same minimum quality.  The exact match at 1:2 and 1:4 shows the
  plate tolerances are no longer the cause.
- **The moved nodes are noted in the CHANGELOG,** as the 0.5.0 promise
  requires.
- **The `tol2d` finding** is in `gmsh.md`; good.
- **Output `scale=`:** not a task yet.  Decision 0047 left it as an idea
  until hexmesh was shown scale-free.  0139 shows it is exact only at
  powers of two, so `scale=` would make output exact for a user who
  builds at a reference size.  It is noted on 0047 for the API review
  (task 0150): it adds an argument to every writer.

