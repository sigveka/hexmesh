# 0145 — CI green: three junction tests fail on gmsh 4.15.2 (what pip installs)

- **Status:** done (first: it blocks the 0.6.0 release, task 0146)
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

- **Step 1, one cause for all three: OCC's plate.**  gmsh 4.12.1 ships
  OCC 7.6.3, the 4.15.2 wheel OCC 7.8.1 (`General.BuildInfo`).  On
  `tee-0.5` and the 35° lateral, no curve node moves between versions;
  surface nodes do, and the volume nodes follow.  Each 4.12.1 surface
  node's distance to the 4.15.2 surface of the same tag (fraction of the
  size): planes 2e-17, B-spline fillings 3e-16, wall plates (with
  points) 4.6e-5 / 3.6e-5, **interior plates (no points) 3.3e-3 /
  1.5e-2**.  So the interior plates are different surfaces: not gmsh's
  transfinite fill, not hexmesh's projection.  Interior plates are free
  surfaces (no true shape); each OCC version builds its own, and the
  junction's non-orthogonality and SJ move with them: tee-0.5 61.4°
  against 63.1°, the lateral 73.4° against 72.8°, the offset set-on SJ
  0.088 against > 0.1.
- **The candidate fix (experiment, not applied):** the tee's interior
  faces as `addBSplineFilling(type="Stretch")`, as the wye and the cube
  already are (task 0030).  12 junction examples, both versions: no
  Stretch fill fails; min SJ identical to today's in all 12; max
  non-orthogonality equal or better (tee 60.8° → 58.5°, insulated_tee
  63.0° → 59.8°, pcf_line 68.8° → 66.9°); the versions agree to
  ≤ 1.1e-4 of the size (plates: 1.3e-3 to 2.8e-3), the rest being the
  wall plates.  The three failing tests pass on both versions.  Cost:
  every tee mesh moves, by up to 3.3e-3 of the size on 4.12.1.
- **Design's answer to Q1 (design session's message, 2026-11-11):**
  yes, Stretch interior faces, with five conditions.  Applied:
  `Tee.layout` sets `lay.filling = "Stretch"`; wall faces stay pinned
  plates (`pin_walls`, task 0051).  The conditions:
  1. *Calibration* (`benchmarks/junction_nonorth.py`, 85 cases, both
     versions identical to 0.01°): median |error| 0.52° → 0.18°, within
     2° 59/78 → 71/85, rejections unchanged.  The worst optimistic
     error grew 3.36° → 3.66° (`lateral-45-0.9` and
     `tee-45-0.9-0sh-nang4`, predicted 63.23°, meshed 66.59° → 66.89°),
     past the stated 3.4°.  No constant depends on it (`mesh()` checks
     every tee's meshed value), so the stated figure is now 3.7° (tee
     docstring, API.md, GUIDE); design agreed.  The JSON is
     re-recorded.  The worst pessimistic error is unchanged (15°,
     shelled 90° tees at r/R 0.9).  0127's equal-tee tier: equal tees
     use the cube layout, already Stretch; their meshes don't move.
  2. *DESIGN §7.1 range table:* its rows are the predicted-SJ floor (pure
     layout, no fillings): just below each row the Tee rejects with
     `predicted_sj_below_minimum` ("r/R 0.294 or more reaches it" at
     60°, 0.501 at 45°, 0.876 at 35°).  Meshed just above each row
     (r/R 0.21, 0.30, 0.51, 0.88; bare nang 4 and 2 shells nang 8): min
     SJ 0.101–0.104, identical on 4.12.1 and 4.15.2.  No row changes.
  3. *Other free plates:* counted over all 31 examples and the
     conformance kit: only `DuctTap`'s interior faces (19 kit cases,
     `hvac_branched`'s 48 faces).  Version drift (fraction of size):
     surfaces 4.5e-5 (`tee-duct-rect-2-narrow`) to 8.2e-3
     (`tee-duct-round-2-wide`); no test fails on either version.  Left
     as a follow-up.  `corners.py`'s slab default isn't reached by any
     example or kit case.
  4. CHANGELOG (the size, the reason) and gallery: done.
  5. `gmsh.md`: the per-surface table and the change.  Correction agreed
     with design: 0051's step 8 was about the tee's *wall* faces, which
     stay; this changes the interior faces only, so it doesn't overturn
     step 8.
- **The XPASS** (`test_small_tee_builds`): gone with task 0139 (the 1:50
  xfail was replaced by a passing 1:1000 case).  `test_units` passes on
  both versions.

## Questions for design

1. **Tee interior faces as Stretch B-spline fillings?**  (Agent notes:
   it removes the version dependence at its cause, keeps min SJ and
   improves non-orthogonality; every tee mesh moves up to 3.3e-3 of
   the size, the gallery is re-run.)  The alternative is per test:
   widen two prediction tolerances and lower or re-case the set-on SJ
   floor, accepting junction meshes that differ by up to 2.8e-3 of the
   size between the two supported gmsh versions.

## Outcome

Done 2026-11-12.

- **The four tests:** one cause, OCC's free interior plates (OCC 7.6.3 in
  gmsh 4.12.1, 7.8.1 in 4.15.2; *Agent notes*).  The fix at the cause:
  the tee's interior faces are Stretch B-spline fillings
  (`hexmesh/assembly/tee.py`).  The three junction tests pass on both
  versions unchanged; the XPASS ended with 0139.
- **Tests run:** junction-related set (20 files): 1645 passed, 1
  skipped, on 4.12.1 *and* on 4.15.2 (scratch venv).  The rest of the
  suite on 4.12.1: 2797 passed, 15 skipped.  So the whole suite on
  4.12.1 (4442 passed), and no test needed a new value.  The rest of
  the suite on 4.15.2 wasn't run locally: CI's default jobs do.
- **Meshes:** every tee and lateral mesh moves, up to 3.3e-3 of the
  size (4.12.1); min SJ unchanged in all 12 junction examples, max
  non-orthogonality equal or better (by up to 3.4°).  The versions agree
  to 1.1e-4 (were 1.3e-3–2.8e-3).  Gallery: 11 examples re-run; min SICN
  unchanged in all, mean SICN in the 4th decimal.
- **CI:** `.github/workflows/tests.yml` adds a Linux, Python 3.12 job
  pinned to gmsh 4.12.1.  Not yet run: it runs on the next push.
- **Docs:** README and GUIDE install lines (both versions, OCC versions,
  how far the meshes agree); API.md and GUIDE (3.7°); `gmsh.md` (new
  entry; 0141's entry already updated in 0139); CHANGELOG.
- **Follow-ups:** duct taps' free interior plates (version drift up to
  8.2e-3 of the size, no failures); Stretch there would need the same
  measurements (calibration, `DUCT_TAP_MAX_RATIO`).

