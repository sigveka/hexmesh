# 0104 — Junctions predict non-orthogonality in `validate()`

- **Status:** done
- **Decision:** [0031 — General branch junctions](../decisions/0031-general-branch-junctions.md), amendment 2026-11-07, item 5
- **Depends on:** 0060.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0060 measured 75–78° non-orthogonality in small-ratio
tees, 90° included, and nothing reports it before meshing.  `mesh()`
checks meshed non-orthogonality on the tiers `OUTLINE_NONORTH_WARN`
(70°) and `OUTLINE_NONORTH_MAX` (80°), and section outlines predict it
(`assembly/section_quality.py`).  Junctions predict only the scaled
Jacobian.  Task 0074 also met a duct tap the solver couldn't converge on,
at 64°, so the number matters to users before they wait for a mesh.

**Where.**  The junction fittings (`assembly/tee.py`, `duct_tap.py`,
the wye); `assembly/section_quality.py` or wherever the prediction is
shared; tests; `API.md`; `CHANGELOG.md`.

**Do.**
1. **Predict** the worst non-orthogonality of each junction's blocks
   from the same straight-edge block geometry that predicts the scaled
   Jacobian, without GMSH.  Reuse the outline prediction's definition
   (the angle between a face normal and the line joining the cell
   centres either side), so predicted and meshed values compare.
2. **Report** it in `validate()` on the existing tiers: a warning above
   `OUTLINE_NONORTH_WARN`, an error above `OUTLINE_NONORTH_MAX`.  The
   message names the fitting and the block (e.g. "the turn block at the
   acute crotch"), and the hint names what lowers it (a larger r/R, a
   larger angle).
   - If junction blocks need tiers of their own, propose them under
     *Questions for design*.  Don't add them.
3. **Measure the prediction against the mesh** on the conformance kit's
   junctions and on 0060's sweep (angle × r/R): predicted against meshed
   worst non-orthogonality.  Record the error.  If the prediction is
   optimistic anywhere, say where and by how much.
4. **Docs:** API.md and the GUIDE's quality section; CHANGELOG (new
   warnings can appear on existing networks: list which examples warn).
5. **After design's answers (2026-11-09):** `mesh()` checks junctions'
   meshed non-orthogonality on the switches' tiers; the docs state the
   prediction's error; a short look at the 25 mm node difference.

**Accept.**
- The examples: list every one whose `validate()` result changes.  An
  example that newly *errors* is a question for design before merging.
- The prediction against meshed table is in *Outcome*.
- Full suite: no new failures, apart from expected new warnings, listed.

**Out of scope.**  Changing junction layouts to lower the angle; that
follows from the measurements, by decision.

## Agent notes

- **Step 1 refined: curved-edge cells, not straight edges.**  Hexes
  between the straight-edge block corners were 7–12° off the meshed
  value, so `BlockLayout.cells()` builds the cells gmsh's transfinite
  meshing would make.
  - Divisions and grading come from the layout's edge classes.
  - Edge nodes go at graded length fractions along each edge's declared
    curve.  A `Spline` is read through its control polyline, so
    `validate()` stays scipy-free (task 0107).
  - The volume is a Gordon–Hall edge blend.
  - `predicted_nonorth()` takes the worst shared face with
    `quality_hex.shared_face_angles`, the meshed check's definition.
- **Wall projection is not predicted.**  `Assembly.mesh()` moves the
  wall-face nodes onto `walls` afterwards.  Predicting that moved
  lateral-45-0.9 by under 0.1° (its −3.4° stays) and cost more than all
  the rest, so it was dropped.
- **Shared code** lives in `assembly/junction_quality.py`:
  - `nonorth_tiers`;
  - block names by station prefix;
  - a by-value cache, keyed by `_layout_key`, which moved there from
    `wye.py` to avoid a module cycle.
  It costs 35–290 ms per junction the first time and nothing after.
- **The wye only warns above `OUTLINE_NONORTH_MAX`.**  This is the same
  policy as its SJ tier ("no reject tier until its layout redesign").
  Without it, `fittings.junction_walls` (30° wye, 81.8°) and the narrow
  wye tests would newly error.  See *Questions for design*.

## Questions for design

1. **The wye's reject tier.**  Every wye predicts 72–82° (meshed
   agrees within 1°).  Wyes under about 32° exceed 80°, among them
   `fittings.junction_walls`'s 30° wye at 81.8°.  The prediction applies
   `OUTLINE_NONORTH_MAX` to the wye as a warning only, as its SJ tier
   already does.  Should that stand until decision 0043's redesign, or
   should wyes above 80° be rejected (the example then changes)?
2. **Optimism near the warning tier.**  The prediction is up to 3.4°
   optimistic on r/R 0.9 laterals.  `tee-35-0.9-0sh-nang4` meshes at
   72.8° but is predicted at 69.7°, so it doesn't warn, and `mesh()`
   doesn't check junctions' meshed non-orthogonality (only switches').
   The likely cause is the post-mesh wall projection, though predicting
   it didn't close the gap: the worst block's nodes differ from the mesh
   by up to 25 mm near the branch port, and that is unexplained.  Two
   options:
   - (a) check the meshed value in `mesh()` too, as for switches;
   - (b) a margin on the predicted tier.
   Which, if either?

**Design answers (2026-11-09, the user: "yes"):**
1. **The wye stays warning-only above `OUTLINE_NONORTH_MAX`** until
   decision 0043's redesign.  Rejecting would turn networks that build
   in 0.5.0 into errors (a breaking change), for a layout already
   scheduled to be replaced.  Task 0116 reports each case's worst
   crotch non-orthogonality (predicted and meshed) as a measurement,
   not a gate: the control's result is already known, so it can't
   become a gate now (decision 0043's gates are fixed).
2. **(a): `mesh()` checks junctions' meshed non-orthogonality** on the
   same tiers as switches.  No margin on the prediction: it errs both
   ways (−3.4° to +14.9°), so a margin would guess.  API.md and the
   GUIDE state the prediction's known error (up to 3.4° optimistic at
   r/R ≥ 0.6).  The unexplained 25 mm node difference near the branch
   port gets a short look, recorded in *Outcome*; if it is gmsh
   behaviour, in `docs/integrations/gmsh.md`.

## Outcome

- **Files:**
  - `hexmesh/assembly/blocks.py`: `BlockLayout.cells()`,
    `predicted_nonorth()`, `_edge_starts`, `_fractions` and
    `_edge_nodes`;
  - `hexmesh/assembly/junction_quality.py` (new);
  - `tee.py`, `duct_tap.py` and `wye.py`, each `validate()`;
  - `hexmesh/quality_hex.py` (`shared_face_angles`);
  - `hexmesh/errors.py` (`predicted_nonorth_above_maximum`);
  - `tests/test_junction_quality.py` (11 tests);
  - `benchmarks/junction_nonorth.py` and `.json`;
  - API.md, GUIDE and CHANGELOG.
- **Predicted against meshed** (`benchmarks/junction_nonorth.json`):
  78 cases, which are the kit's junctions plus 0060's sweep (angles 90,
  75, 60, 45, 35; r/R 0.3, 0.6, 0.9; 0 or 2 shells; nang 4 or 8).  The
  Tee rejected another 14 sweep cases.
  - Median |error| 0.5°; 51 cases within 1°, 59 within 2°.
  - Optimistic by more than 1° in 22 cases, at most 3.4°
    (lateral-45-0.9, tee-60-0.9-0sh-nang8), all at r/R 0.6–0.9.
  - Pessimistic by up to 14.9° (90° tees at r/R 0.9 with shells,
    predicted 57°, meshed 42.5°), all well below the warning tier.
  - Duct taps are exact (±0.1°); wyes are within 0.7°.
  - The tiers disagree on 3 cases, all within 0.2–3° of 70°.
  - Cost: 35–180 ms per junction, cached by value after.

  | case | predicted | meshed |
  |---|---|---|
  | tee-0.5 | 61.4 | 61.4 |
  | tee-0.9-oblique | 40.7 | 40.2 |
  | lateral-45-0.9 | 63.2 | 66.6 |
  | lateral-60-0.6 | 64.3 | 64.0 |
  | wye-60 / wye-90 | 74.0 / 72.5 | 74.2 / 73.2 |
  | wye 30° / 45° / 120° | 80.4 / 76.8 / 78.0 | 80.3 / 76.8 / 78.1 |
  | tee-duct-rect-2-narrow | 75.1 | 75.1 |
  | tee r/R 0.3, 60°–90° | 72.5–76.8 | 72.8–77.4 |
- **Examples whose `validate()` changes:** these 5 now warn, and none
  errors.  All the warnings are at wyes:
  - `fittings.wye` (76.1°);
  - `fittings.junction_walls` (30° wye, 81.8°, above MAX, warning only);
  - `sections.insulated_network` (76.3°);
  - `networks.bifurcation_tree` (3 wyes, 72.5–73.1°);
  - `applications.cooling_channels` (73.1°).
- **Full suite:** 3762 passed, 15 skipped and 8 failed, all on the
  expected new wye warning:
  - `test_projection.py::test_wye_projected_without_folds` (7), which
    treats warnings as errors: the new warning is now ignored there, as
    the SJ one already was;
  - `test_readme.py::test_the_primer_s_validations_and_note`: the
    README primer said "no errors, no warnings" for
    `insulated_network`, and now names its one wye warning (76°).
  The 8 pass after the fix, and the 11 new tests pass.
- **Follow-ups:** the two questions above.  The wye's crotch ring
  (72–82° in every wye) is input for task 0116's measurements.

### Step 5 (after design's answers)

- **The meshed check.**  `mesh()` checks every tee, duct tap and wye on
  the outline tiers, as it does switches (`_check_meshed_nonorth`):
  - each junction has `meshed_nonorth_check` set and names its own hint
    (`meshed_nonorth_hint`); the wye has `meshed_nonorth_reject =
    False`, so it warns above 80° too;
  - a junction is measured over its whole fill, including a graded H
    main's switch legs (their SJ check still measures only the legs);
  - **refinement:** no second warning where the prediction already
    warned on that tier, using the cached `predicted_nonorth(frames,
    spec)`.  Errors are always raised.  Without this, every wye would
    warn twice.
  - The switches' meshed message now ends with its hint instead of
    "(a steep wall grading at the switch)".  No test or doc quoted the
    old text.
- **Docs:** API.md, the GUIDE and the CHANGELOG state the known error
  (up to 3.4° optimistic at r/R ≥ 0.6) and the meshed check.  There is
  no margin.
- **Tests:** 4 more in `tests/test_junction_quality.py` (15 in all):
  - the optimistic 35° lateral warns at `mesh()`;
  - one warning per tier;
  - meshed above the maximum raises;
  - the wye only warns.
- **The 25 mm node difference** (lateral-45-0.9, block 6, between the
  departure port B and station Sd) isn't gmsh behaviour.
  - The layout declares that block's outer port-face edge, `("B", 1, 0)`
    → `("B", 1, 1)`, as a `Line`, but the fill meshes the port face from
    the interface's arc.  The meshed top midline in the port plane is at
    z = 0.1 (on the wall); the predicted chord is at 0.071.  The
    prediction follows the layout's declared edges, so it is off in that
    block.
  - It isn't the worst block, so the maximum is unaffected.  The 3.4°
    optimism is in block 15 and stays unexplained.
  - **Proposed follow-up:** declare port-face edges with their
    interface geometry (arcs) in the junction layouts, or read them from
    the port face in `cells()`.  Then re-measure the optimism.
- **Full suite after step 5:** 3774 passed, 15 skipped, no failures.
  Every example's `validate()` result is unchanged from step 4.
