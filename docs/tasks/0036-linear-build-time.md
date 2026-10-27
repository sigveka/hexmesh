# 0036 — Linear build time: fewer `synchronize` calls, and a build benchmark

- **Status:** done
- **Decision:** [0020 — Build time grows linearly with the model; parallelism only across jobs](../decisions/0020-build-time-scaling-and-parallelism.md)
- **Depends on:** 0025 (it changes the same slab code; measure on top
  of it).  Coordinate with 0027 and 0031 if they are in progress.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Building geometry dominates `Assembly.mesh()`; GMSH's meshing
is about 1 %.  `occ.synchronize` takes about 42 % on a small example,
with ~2 calls per volume, and each call costs more as the model grows,
so total time grows roughly quadratically.  `pipe_rack` (576 volumes)
took about 118 s.  Decision 0020 has the profile.

**Where.**
- `hexmesh/assembly/corners.py:225–293`: per-slab synchronizes ("needed
  before addCurveLoop references these lines", "so OCC buffer is
  clean"); `curve_endpoints` (line 29) reads the model back.
- `hexmesh/assembly/sweep.py:331`: per-station synchronize.
- `hexmesh/assembly/blocks.py`, `assembler.py`, `faces/_gmsh_helpers.py`,
  `faces/oh_circle.py`: the remaining calls.
- `docs/integrations/gmsh.md` (what OCC queries work before a
  synchronize, e.g. `occ.getBoundingBox` centre).

**Do.**
1. **Benchmark first.**  A script (e.g. `benchmarks/build_time.py`,
   not part of the test suite) that builds a series of straight + bend
   networks of growing size (e.g. 50 → 1 000 volumes) and records:
   volumes, surfaces, cells, `synchronize` call count, and time per
   phase (faces, fill, physical groups, `generate`).  Run it before any
   change, **on an idle machine** (CLAUDE.md, shared machine), and fit
   the growth exponent.
2. **Remove read-backs.**  hexmesh creates every point and curve it
   uses, so it can record what it later reads back (curve start/end
   points, curve kinds) when it creates them, instead of asking the
   model.  Replace `curve_endpoints`' model queries for curves hexmesh
   created; keep the model query only where an entity came from OCC
   (record which).
3. **Synchronize once per fitting** (or once per assembly, if
   transfinite constraints and physical groups allow; the comment at
   `corners.py:330` says constraints can be reset by a later
   synchronize: investigate and record in `gmsh.md`).
   - Check first what genuinely needs a synchronized model:
     `addCurveLoop` on OCC curves should not (it is an OCC call); record
     the facts with the GMSH version.
4. **Cheaper surfaces where §6 allows.**  On one-layer slabs (bends,
   splines, closures, reducers) side surfaces carry no interior nodes,
   so they only need to be valid.  Measure `addSurfaceFilling` (plate)
   against `addBSplineFilling` ("Stretch", "Coons") for build time and
   for mesh validity; switch if cheaper and valid in every kit case.
   Don't change straight slabs beyond task 0025.
5. Re-run the benchmark; record before/after.

**Accept.**
- The mesh is unchanged: for every conformance-kit case and example,
  the same cell count, the same physical groups, and node coordinates
  equal to 1e-12 (compare before/after files).  If step 4 changes node
  positions on one-layer slab surfaces, there should be none to change:
  confirm.
- Benchmark: growth exponent ≈ 1 after the change (≤ 1.2), and the
  speed-up on the largest network and on `pipe_rack`.  Both runs on an
  idle machine.
- `synchronize` calls per fitting: a small constant, stated in
  *Outcome*.
- Benchmark table in *Outcome*, for RESEARCH.
- Full suite: no new failures; record the suite's wall time before and
  after.

**Out of scope.**  Any parallelism (decision 0020: job level only, in
tooling); changes to GMSH meshing options.

## Agent notes

- **Records instead of read-backs: `hexmesh/_occ.py` (new).**  `line`,
  `circle_arc`, `spline`, `bspline` create a curve and record its start
  and end point tags and its kind; `endpoints`, `kind` answer from the
  records; `coords` reads a point from `occ.getBoundingBox` (exact
  centre, no synchronize).  An unrecorded curve falls back to one lazy
  synchronize and the old model query (`fallbacks` counts them: zero in
  every kit case and the benchmark).  Every curve hexmesh makes goes
  through it: face helpers, `oh_blend` splines, sweep `Arc`, the default
  axial line, `BlockLayout` edges.  Entities that only OCC makes: none
  are queried.
- **Records are trusted only inside a build** (`_occ.building()`: faces,
  every `fill`, and the constraints in `mesh()`), and `build_faces`
  resets them first.  Outside a build the model is always asked.  The
  first version trusted them everywhere and reset only on an empty model;
  `test_corners` then read a stale record left by an earlier model in the
  same xdist worker (same tag, different curve).  Fixed, with a test.
- **Face constraints deferred.**  Face builders set transfinite/recombine
  constraints themselves (4 synchronizes per face, so per bend station).
  `Assembly` already re-applies every one of them in `mesh()`, so inside
  `_occ.building()` the helpers skip theirs.  Standalone face building is unchanged.
- **Synchronizes removed:** 6 per slab (`corners.connect_layer`), 1 per
  sweep with stations, 3 per block layout, 4 per face.  Left: after the
  faces (callers, e.g. the kit, inspect them; the model is small then),
  end of `fill`, after removing construction points, and `mesh()`:
  **4 per assembly, 0 per fitting** (`tests/test_build_sync.py`).
- **Step 3 facts** (gmsh 4.12.1 / OCC 7.6.3, in `docs/integrations/gmsh.md`):
  every OCC construction call works without synchronizing; only
  `gmsh.model` queries and mesh constraints need it; a transfinite
  constraint survives a later synchronize that adds entities (the old
  `corners.py` comment could not be reproduced; comment updated); OCC
  keeps the start point hexmesh gives each curve kind.
- **Step 4:** B-spline "Stretch" filling (`sweep._ruled`) now builds the
  side faces of every sweep slab, not only straight and prism ones:
  1.6 ms against 6.4 ms per plate (`addSurfaceFilling`), and the meshes
  are identical (one-layer slabs carry no surface nodes; 66/66 compared).
  `BlockLayout` faces (tee, wye, drum) are unchanged: they can carry
  interior nodes.
- **Construction points (found on the way).**  With synchronize gone,
  `occ.remove` became the quadratic term: each removed point costs time
  in proportion to the model (3.9 ms per point at 2100 volumes), batched
  or not.  Inside `building()` arc centres are now kept (`_occ.discard`)
  and removed in one call before the final synchronize, and a sweep's
  `Arc` builder shares one centre point per corner height (all slabs of a
  bend), about 6× fewer points.  OCC does not reuse removed tags, so
  every entity tag, node tag and coordinate is unchanged.

**Note from design (2026-10-27):** the examples moved into category
subpackages: `hexmesh.examples.<category>.<name>` (e.g.
`hexmesh.examples.fittings.tee`); `hexmesh.examples.ALL` lists them.
Output file names are unchanged (`<name>.msh`).  For the before/after
comparison, iterate over `ALL`.  `docs/gallery/build.py` records build
time per example and could give the before/after table.

## Questions for design

_None._

## Outcome

**Done.**  Build time is linear over the task's range: growth exponent
**1.03** for 70–1050 volumes (was 1.73), and 17× faster at 1050 volumes.
Meshes unchanged node for node.

Files:
- `hexmesh/_occ.py` (new): creation records, lazy fallback, `building()`,
  `discard`/`remove_discarded`.
- `hexmesh/faces/_gmsh_helpers.py`, `oh_blend.py`, `oh_circle.py`: curves
  through `_occ`; constraint helpers skip inside `building()`.
- `hexmesh/assembly/corners.py`: `curve_endpoints` from records; 6
  synchronizes per slab removed.
- `hexmesh/assembly/sweep.py`: `Arc` from records, shared centres; station
  synchronize removed; Stretch side faces on every slab.
- `hexmesh/assembly/blocks.py`: curves and kinds from records; 3
  synchronizes removed.
- `hexmesh/assembly/assembler.py`: records reset per build; faces, fills
  and mesh constraints inside `building()` (constraints moved to
  `_set_constraints`); one batch removal of construction points.
- `benchmarks/build_time.py` (new, not in the suite).
- `tests/test_build_sync.py` (new, 51 tests): 4 synchronizes for 1 and 4
  bend pairs; for every kit case, the records equal the synchronized
  model's end points and kinds and no fallback happened; fallback, reset,
  and stale records ignored outside a build.

**Mesh unchanged.**  All 46 kit cases and 20 examples dumped before and
after (cell count, physical groups with their entity tags, node tags,
node coordinates, hex connectivity): 66/66 identical, coordinates within
1e-12 (scratch scripts `refdump.py`/`refcmp.py`, run after each step
and after the final fixes).

**Benchmark** (`benchmarks/build_time.py`, serpentine of `Straight` +
`Bend(180)` pairs, nang 4, single layer; idle machine, 2026-10-27):

| volumes | surfaces | cells | syncs before → after | sync s before → after | total s before → after | speed-up |
|---|---|---|---|---|---|---|
| 70 | 243 | 1 280 | 136 → 4 | 1.14 → 0.12 | 3.28 → 1.27 | 2.6× |
| 140 | 481 | 2 560 | 264 → 4 | 4.58 → 0.24 | 8.93 → 2.37 | 3.8× |
| 280 | 957 | 5 120 | 520 → 4 | 20.5 → 0.51 | 29.4 → 4.79 | 6.1× |
| 560 | 1 909 | 10 240 | 1 032 → 4 | 86.3 → 1.01 | 105.2 → 10.3 | 10.2× |
| 1 050 | 3 575 | 19 200 | 1 928 → 4 | 304.2 → 2.15 | 340.0 → 19.8 | 17.2× |
| 2 100 | 7 145 | 38 400 | — → 4 | — → 6.63 | — → 50.0 | — |

Growth exponent of total time vs volumes: before 1.73 (upper half 1.85);
after **1.03** over 70–1050 (upper half 1.07), 1.07 including 2100
(upper half 1.20).  Faces 0.35 s, `generate` 0.49 s at 1050 volumes; the
rest is OCC construction (`addVolume`, `addBSplineFilling`,
`addSurfaceLoop`, about linear).

**`pipe_rack`** (432 volumes, 14 280 cells, current version): 61.7 s →
**6.2 s** (10×), same machine, idle, HEAD `d71d0d8` against this change.

**Suite:** 1255 passed, 5 skipped in **328 s** (before: 1204 passed, 5
skipped in 686.6 s; the suite has grown by 51 tests since, both runs
`-n auto` on an idle machine).

Surprises:
- `occ.remove` costs time in proportion to the model per point removed,
  batched or not (19.7 s for one call removing 2900 points at 2100
  volumes).  It is the remaining super-linear term above ~1000 volumes:
  about 2100 points at 2100 volumes are the face builders' arc centres
  (one per station face), removed after the last synchronize.
- A transfinite constraint is **not** reset by a later synchronize here.

Proposed follow-ups:
- Keep construction points out of the mesh without removing them (e.g.
  hide them and mesh only visible entities, or give each face builder a
  shared centre per sweep), to remove the last quadratic term.  It would
  leave points in the model, so measure the effect on exported files
  first.
- `BlockLayout` plate fillings (tee, wye, drum) could be measured like
  step 4, where their faces carry no interior nodes.

