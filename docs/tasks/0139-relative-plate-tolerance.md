# 0139 — Interior plates' tolerance relative to the face

- **Status:** ready
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

## Questions for design

## Outcome
