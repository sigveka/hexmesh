# 0145 — CI green: three junction tests fail on gmsh 4.15.2 (what pip installs)

- **Status:** ready (first: it blocks the 0.6.0 release, task 0146)
- **Decision:** [0042](../decisions/0042-road-to-1-0.md) (1.0's promises
  rest on CI); the support rule below (design session, 2026-11-11).
- **Depends on:** none.  Coordinate with 0139 (in progress), which edits
  `tests/test_units.py`.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  CI on `main` has been red for over a day (every run since at
least `3bdc2d0`, 2026-11-10).  The last green run is `7b17f3f`.  CI
installs gmsh **4.15.2**, the current wheel `pip install` picks, while
the development machine runs 4.12.1.  Every platform (Linux, macOS,
Windows; Python 3.11 and 3.x) fails the same tests:
- `test_junction_quality.py::TestCells::test_predicted_against_meshed[tee-0.5-0.5]`:
  meshed non-orthogonality 61.42° against the 63.11° expected (± 0.5);
- `test_junction_quality.py::TestMeshed::test_meshed_warns_where_the_prediction_is_optimistic`:
  the warning says 73.4°, the test expects 72.x;
- `test_pcf_junctions.py::test_an_offset_set_on_builds_and_meshes[18-60-45]`:
  min scaled Jacobian 0.0858, below the test's 0.1;
- **since task 0141** (`104fc0c`): `test_units.py::test_small_tee_builds`
  XPASSes, which fails its strict xfail.  0141's plate retry made the
  2 mm tee build.  This is good news, and 0139 may already handle it.

**The support rule** (design session; the user can overrule): hexmesh
supports **both** gmsh 4.12.1 (the reference the gallery and the
validation cases were made with) **and the version `pip install` gives
today**.  A user who follows the README gets 4.15.2, so the junction
quality hexmesh promises must hold there.

**Do.**
1. **Reproduce on 4.15.2:** a scratch venv with `gmsh==4.15.2`.  Run the
   three tests, and say for each why the number moved: gmsh's transfinite
   fill, OCC's plate, or the projection.  Record what you find in
   `docs/integrations/gmsh.md` (version, evidence, date).
2. **Fix at the cause, case by case:**
   - **A prediction tolerance** that 4.12.1 alone met: widen it only if
     4.15.2's value is as correct as 4.12.1's, and say so in the test.
   - **The offset set-on at SJ 0.086:** this is a quality promise.
     Either 4.15.2's mesh is worse and hexmesh must warn or reject (the
     prediction tiers, decision 0031), or the test's floor is wrong for
     this case.  If neither is clear, ask under *Questions for design*.
   - **The XPASS:** if 0139 hasn't, record the new scale limit (task
     0128's measurement) and move the xfail to the next failing scale,
     or drop it.
3. **CI tests both versions:** add a job (Linux, one Python) pinned to
   `gmsh==4.12.1`, beside the default one.  The pinned job keeps the
   byte-identical example meshes meaningful.
4. **README and GUIDE:** the gmsh line names both versions tested.

**Accept.**
- CI green on every job.
- Each of the four tests explained in the task (cause, fix).
- `gmsh.md` updated.

**Out of scope.**  Supporting gmsh versions older than 4.12.

## Agent notes

## Questions for design

## Outcome
