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

## Questions for design

## Outcome
