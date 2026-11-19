# 0171 — The bathymetry reader gives the same route on every platform

- **Status:** in progress
- **Decision:** none (a bug fix; DESIGN §3's reproducibility, decision
  0044's mesh fingerprint).
- **Depends on:** none.
- **Blocks:** none.  Before 1.0 is better: it changes one example's
  mesh.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  CI run 44148935916 (2026-11-17): `subsea_pipeline` built on
macOS differs from Linux by up to about 3e-3 in its route points' z,
and about 1e-5 in the inlet normal (task 0166's migration test, the
coding session).  The same script and versions give a different mesh
by platform.  No test covers it.

**Likely cause (the design session, from the code; not verified).**
`_make_interpolator` (`hexmesh/interchange/importers/bathymetry.py`)
uses `LinearNDInterpolator`, which triangulates the points with Qhull's
Delaunay.  Every loader hands it a **regular grid**, flattened: GeoTIFF
and NetCDF always, and the example's XYZ file too.  A grid's cells have
four co-circular corners, so Delaunay may cut each one along either
diagonal.  Which one it picks depends on rounding, so it can differ by
platform and library build.  On a curved surface the two diagonals give
different heights inside the cell, by up to about the curvature times
the cell size squared.

**Do.**
1. **Confirm the cause:** build the example's surface and triangulate
   it.  Count the cells whose diagonal choice is degenerate (four
   co-circular points), and show that flipping their diagonals moves
   the interpolated z by about the observed 3e-3.  If the cause is
   something else, write it under *Questions for design* and stop.
2. **Fix:**
   - when the points form a regular, axis-aligned grid (always for
     GeoTIFF and NetCDF; detected for XYZ), interpolate bilinearly with
     `scipy.interpolate.RegularGridInterpolator`. This is
     deterministic and the usual reading of a DEM;
   - scattered XYZ keeps `LinearNDInterpolator`. Say in its docstring
     and in API.md that a scattered surface's result can depend on the
     platform where points are co-circular.
   - A rotated grid (a GeoTIFF transform with rotation) counts as
     scattered, unless handling it is simple.  Say which.
3. **Behaviour:** routes over gridded surfaces change, by up to about
   the size seen.  CHANGELOG *Behaviour*, with the measured largest
   change on the example.  `subsea_pipeline`'s mesh and its
   `examples_current.json` entry are regenerated, and the gallery image
   if it changes visibly.
4. **A platform test:** a test that builds every example and compares
   its description with `tests/data/examples_current.json` (rel 1e-9,
   abs 1e-15, the helper task 0166 added).  It runs on every CI job, so
   a platform difference in any example fails CI by name.  If it's
   slow, mark it and give CI's time for it.  Before the fix, it should
   fail on macOS for `subsea_pipeline` only; record that run.
5. Record the Qhull behaviour in `docs/integrations/` (a `scipy.md`, or
   `platforms.md`), with the versions and the evidence.

**Accept.**
- Step 1's evidence under *Agent notes*.
- The platform test is green on all 8 CI jobs; the run before the fix
  shows only the expected failure.
- Gridded surfaces interpolate bilinearly; a test with a grid surface
  whose bilinear value is known exactly.
- The other examples are unchanged (byte-identical meshes).

**Out of scope.**  Smoother interpolation (bicubic); making scattered
surfaces platform-independent.

## Agent notes

- **Step 1, the cause confirmed (2026-11-17, scipy 1.11.4, numpy 1.26.4,
  Linux).**  The example's survey is a 161 × 53 grid at 5 m; every one of
  its 8320 cells has four co-circular corners.  Qhull's Delaunay cut
  4149 of them along one diagonal and 4171 along the other: no rule, so
  rounding decides.  At the route's 73 points (after
  `max_segment_length=10`), the two consistent splits differ by up to
  3.7e-3 in z, at 46 points by more than 1e-9; Qhull's own choice is
  3.3e-3 from one and 3.7e-3 from the other.  macOS's differences in CI
  run 44148935916 (z up to about 2.5e-3, values in ninths and
  eighteenths of the file's millimetres, as a linear interpolation of
  3-decimal heights gives) fit.
- **Step 4's test is written, not committed:** the 35 examples' built
  descriptions compared with `examples_current.json` through
  `_same`, in `test_intent.py`; 35 pass on Linux in 6 s.  Held back so
  the push of the range up to 9de140b stays green while 0167 goes first
  (the design session's order).  It goes in as its own commit, pushed
  alone, for the before-the-fix run.
- **Step 4, committed alone (2026-11-19)** as
  `test_example_builds_the_same_description_on_every_platform`
  (`tests/test_intent.py`): 35 pass on Linux in 6 s, so it isn't marked.
  Pushed before the fix for the run that should fail on macOS for
  `subsea_pipeline` only.
- **Step 4, the run before the fix:** CI run 44478052400 on 3bf6edf
  (2026-11-19).  Both macOS jobs (Python 3.x and 3.11) fail one test,
  `test_example_builds_the_same_description_on_every_platform[applications.subsea_pipeline]`
  (its first difference in `.inlet.normal`); 4734 pass.  The three
  Ubuntu jobs, both Windows jobs and the OpenFOAM job pass.  As
  expected: no other example, and no other platform.
- **Step 2, the fix (2026-11-19).**  `_make_interpolator` checks
  whether the points are every x with every y, once, in any order
  (`_grid`: `np.unique` on each axis, the product equals the count,
  every pair seen).  Then `RegularGridInterpolator` (bilinear, NaN
  outside, as `LinearNDInterpolator` gives); otherwise
  `LinearNDInterpolator` as before.  Spacing may vary along an axis
  (rectilinear).  **A rotated grid counts as scattered:** its x and y
  don't repeat, so detecting it means fitting the transform; out of
  scope.  The docstring and API.md say a scattered surface's heights
  can depend on the platform.
- **Step 3, the change.**  Only `subsea_pipeline` changes among the 35
  examples; the others' descriptions are identical to the stored ones
  (so are their meshes: a mesh is built from its description).  In
  `subsea_pipeline`: points up to 2.04e-3 m, a fitting's roll up to
  2.62e-3°, an angle up to 3.0e-4°, a length up to 2.4e-5 m, the inlet
  normal 1.1e-5.  Gallery: `--only applications.subsea_pipeline`
  rebuilt it (183 744 cells as before; max aspect 985.3 → 982.8, min
  SICN 0.00301 → 0.00302); the images change by a few bytes, not
  visibly.  The `--only` build also rewrites the gallery's header line
  (date, commit, "one core"), as it always does.
- **Refined step 3/4: a fixture of its own.**  `examples_current.json`
  is the version-2 migration test's expected file, and its comment
  keeps it fixed so that test checks the migration only:
  `examples_v2.json`'s `subsea_pipeline` carries the old heights, so
  regenerating that entry would break the migration test.  The
  platform test reads `tests/data/examples_built.json` instead: a copy
  of `examples_current.json` with `subsea_pipeline` rebuilt.  An
  intended change to an example regenerates its entry there.
- **Tests:** `test_a_gridded_surface_interpolates_bilinearly` (a
  rectilinear 3 × 4 grid written shuffled, z = 1 + 0.5x − 0.25y +
  0.75xy, three route points exact to 1e-12; the Delaunay surface,
  planar per triangle, is not exact for the xy term) and
  `test_scattered_points_keep_the_delaunay_surface`
  (`tests/test_io_readers.py`).  `test_intent.py` and
  `test_io_readers.py`: 301 passed; `test_api_inventory.py` and
  `test_architecture.py`: 109 passed.
- **Step 5:** `docs/integrations/platforms.md`, "scipy/Qhull: a grid's
  Delaunay triangulation differs by platform".

## Questions for design

## Outcome
