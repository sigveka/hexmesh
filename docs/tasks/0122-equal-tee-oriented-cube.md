# 0122 — Equal tees and equal laterals: the oriented junction cube behind `Tee`

- **Status:** done
- **Decision:** [0043 — The wye-layout redesign](../decisions/0043-wye-layout-redesign.md), amendment 2026-11-10; [0031](../decisions/0031-general-branch-junctions.md) (one public `Tee`; amendment 2026-11-10); [0046](../decisions/0046-gmsh-meshes-hexmesh-corrects.md) (gmsh meshes)
- **Depends on:** 0118 (done): `hexmesh/assembly/_cube_probe.py`, the
  orientation search and the harness.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Equal tees are a 1.0 criterion (decision 0042), and today
`Tee(branch_radius = R)` raises `equal_tee_unsupported`.  Task 0118
measured the oriented cube (Bošnjak et al. 2024) on gmsh's transfinite
path: the equal tee builds with min SJ 0.577 and no warning, the equal
lateral at 45° builds with a warning (0.134).  The crease chord misses
0043's 1 % R gate (3.7 % at `nang` 8); that miss is accepted and stated,
not hidden.

**Where.**  A layout module beside `tee.py` and `wye.py` (e.g.
`hexmesh/assembly/cube.py`, private names), `tee.py` (the routing),
`limits.py`, `junction_quality.py` (its tiers), `errors.py` (codes),
`docs/GUIDE.md`, `API.md`, the gallery, `tests/`.  `_cube_probe.py`
is folded in and removed; `_wye_probe.py` stays.

**Do.**
1. **Route** `Tee` with r = R (the existing relative tolerance, or one
   added to `limits.py` and named) to the cube layout.  `offset` must be
   0 at r = R (|h| + r < R can't hold); keep the existing error for it.
   Roll (task 0062) works as for any tee.  Remove
   `equal_tee_unsupported`; the τ < r/R < 1 error's hint keeps "an equal
   tee, or a branch radius ≤ τ·R".
2. **The layout** as 0118 built it: centre hex, a ported side block per
   pipe sweeping to its station, unported sides on the wall; cube
   corners on the wall along the diagonals; shells as offset levels;
   wall projection onto the tube union (decision 0029) with the
   existing `projection_report`; second order as other projected
   junctions.  Orientation by the paper's heuristic; `hub` and `station`
   fixed per angle from 0118's tuning, or tuned before meshing by
   predicted SJ, deterministically (same description, same mesh).
3. **The angle range, measured:** equal laterals at 90°, 75°, 60°, 45°,
   40°, 35°, 30° (`nang` 8, single and shelled).  Set the warn and
   error tiers from the predicted SJ (0.3 warn, 0.1 build: unchanged
   limits) and the folds, and state the smallest angle that builds.  An
   angle that doesn't build is an error before gmsh with a coded hint.
4. **Report per angle,** in the GUIDE and the docstring: min SJ,
   non-orthogonality and the crease chord (% R) at `nang` 8 and 16, so a
   user sees the crease error before meshing.
5. **Gallery:** an equal tee and an equal 45° lateral, with their
   numbers.
6. **Propose DESIGN §7.2 wording** ("Equal tee: the oriented cube")
   under *Questions for design*; design writes it into DESIGN.

**Accept.**
- `Tee(branch_radius = R)` builds at 90° with min SJ ≥ 0.3 and no
  inverted cells, single and shelled; ports class-0; `checkMesh` v2406
  passes on the equal tee (Docker).
- The lateral range and tiers set from step 3's numbers, in
  `limits.py` with their source.
- Every new error and warning coded, with a hint (task 0106's rules).
- No hexmesh-written elements (decision 0046): every element from gmsh.
- Full suite: no new failures; the gallery's other meshes byte-identical.
- Meshes and scratch output deleted; numbers in the task and the JSON.

**Out of scope.**  The crease fix (decision 0045, proposed); wyes
(unchanged); unequal daughters; crosses (noted in 0118: they would fit,
not built); B3 (task 0124).

## Agent notes

- **The implementation.**  `Tee` delegates r = R to
  `hexmesh/assembly/cube.py` (`CubeTee`, private; no cube↔tee import:
  radii come from the spec's outlines).  New limits `EQUAL_TEE_RTOL`
  (info) and `EQUAL_LATERAL_ANGLE_MIN`; new code
  `equal_lateral_angle_below_min`; `equal_tee_unsupported` removed
  (interchange reads equal tees as `Tee`; README's quoted error is now
  the sample's equal tee, `run_length_too_short`).  An equal tee's
  meshed SJ is checked (`meshed_sj_check`), and its hint is the equal
  tee's (`Tee.meshed_sj_hint(spec)`; the assembler calls a callable
  hint with the spec).  An equal tee's ports carry the inlet's spec
  unchanged (rebuilding it drifted a shell's `dR` by 1e-17).
  `tests/test_equal_tee.py` (17), example `fittings.equal_tee`.
- **Second order (step 2).**  The equal tee's second-order hexes invert
  near the projected wall (72 of 4160 in the example at nang 8), so
  `mesh(order=2)` rejects it before meshing, as it does the wye
  (`Tee.second_order_limitation(spec)`; the assembler calls a callable
  limitation with the spec).
- **Shape, step 2.**  `hub` doesn't matter (0.4–0.8: same meshed SJ).
  For laterals the meshed SJ rises with `station` to a plateau (0.5 at
  75°, 2 at 60°, 3 at 45° and 40° were the shortest on it).  At 90° it is
  flat from 0.25 to 4 (design's Q2 below), so `cube.SHAPE` is
  (90°, hub 0.6, station 0.25).
- **Step 3, nang 8** (R 0.1, nrad 3; shelled 0.1 R in brackets where it
  differs).  SJ meshed (predicted); crease chord (mitre) and the rest of
  the wall in % R.

  | angle | min SJ | non-orth. ° | crease % R | rest % R | validate |
  |---|---|---|---|---|---|
  | 90 | 0.511 (0.577) | 46 (47) | 3.7 (4.1) | 0.6 | clean |
  | 82 | 0.418 (0.520) | 49 | 3.8 (4.2) | 0.7 | clean |
  | 75 | 0.363 (0.460) | 53 | 3.8 (4.2) | 0.8 | clean |
  | 70 | 0.333 (0.428) | 56 | 3.8 (4.1) | 0.8 | clean |
  | 60 | 0.304 (0.361) | 61 | 3.6 (3.9) | 1.1 | clean |
  | 50 | 0.227 [0.233] (0.290) | 67 | 3.2 (3.5) | 1.5 | warns |
  | 45 | 0.183 [0.189] (0.253) | 70 | 2.9 (3.2) | 1.8 | warns |
  | 40 | 0.133 [0.135] (0.208) | 72 | 2.6 (2.9) | 2.2 | warns |
  | 35 | 0.028–0.085 at every station | | | | rejected |

  No inverted cells anywhere it builds; ports class-0 everywhere.
  The rows at 90°–70° were measured with stations 1.0–1.33; at 90° and
  75°, station 0.5 measures the same SJ and non-orthogonality within
  1.5° (single and shelled), and 82° and 70° weren't remeasured.  Rows
  as JSON lines in the session's scratchpad, to be committed with the
  task.
- **Refinement lowers the meshed SJ** (single layer; shelled the same
  to 0.003).  The predicted SJ doesn't change; the worst cell is in a
  wall side's block, which the crease crosses: the projection's move is
  set by the geometry (0.10–0.18 R), not by the cell size, so it spans
  more cells as `nang` grows.

  | angle | nang 8 | 16 | 24 | 32 | crease % R at 8 / 16 / 24 / 32 |
  |---|---|---|---|---|---|
  | 90 | 0.511 | 0.399 | 0.353 | 0.330 | 3.7 / 2.0 / 1.4 / 1.1 |
  | 75 | 0.363 | 0.213 | 0.155 | | 3.8 / 2.1 / 1.4 |
  | 60 | 0.304 | 0.108 | rejected (0.031) | | 3.6 / 2.0 |
  | 45 | 0.183 | 0.138 | rejected (0.053) | | 2.9 / 1.8 |
  | 40 | 0.133 | 0.136 | rejected (0.099) | | 2.6 / 1.6 |

  "Rejected" is `mesh()`'s `meshed_sj_below_minimum`, coded, with the
  equal tee's hint: nothing bad is written, but `validate()` passes
  and the error comes only after meshing.  Non-orthogonality at nang 16:
  47° at 90°, 54° at 75°, 63° at 60°, 71° at 45°, 74° at 40°.
- **Run length against real fittings.**  With the 90° station at 0.5,
  a bare square equal tee needs `run_length` > 1.52 R, which a forged one
  gives (ASME B16.9 DN100: C ≈ 1.84 R).  Insulated it needs 1.90 R
  (insulation 0.25 R thick) or 2.27 R (0.5 R), and a lateral far more
  (60°: 3.76 R bare; 45°: 5.45 R).  So bare PCF equal tees build, and
  insulated ones are `run_length_too_short` (the README's example, the
  sample with its insulation).  Shorter stations than 0.5 aren't
  measured.

- **`checkMesh` v2406** (Docker; `-keepOrientation`, every SJ positive).
  The equal tee passes: "Mesh OK" single (non-orth. 46°, skewness 1.8)
  and shelled (fluid and steel regions: 46° / 2.0, 47° / 2.2), and at
  nang 16 (47°, 2.5).  Laterals fail on skewness from 60° down, at
  nang 8 already:

  | angle | nang | SJ | Mesh OK | non-orth. ° | max skewness |
  |---|---|---|---|---|---|
  | 75 | 8 | 0.363 | yes | 53 | 2.6 |
  | 75 | 16 | 0.213 | yes | 56 | 3.5 |
  | 60 | 8 | 0.304 | no | 61 | 4.6 |
  | 60 | 16 | 0.108 | no | 63 | 4.8 |
  | 45 | 8 | 0.183 | no | 70 | 6.2 |

  The gallery example (equal tee, then a 45° lateral) fails the same
  way: 14 faces skewer than 4 (max 6.6).  Without `-keepOrientation`,
  gmshToFoam would turn 16 of the shelled tee's hexes inside out
  (`would_invert`; docs/integrations/openfoam.md, task 0074).

- **Design's Q2 measured (station below 0.5, 90°).**  Stations 0.25,
  0.3, 0.35, 0.4 and 0.45, bare and under insulation 0.25 R and 0.5 R:
  the same meshed SJ at every station (0.511 at nang 8, 0.399 at 16),
  no inverted cells, non-orthogonality 46–48°; crease 3.7 / 4.6 / 5.6 %
  R at nang 8 (bare / 0.25 R / 0.5 R).  `checkMesh` v2406 at station
  0.25, nang 8: Mesh OK bare (skewness 1.3), under 0.25 R (fluid 1.9,
  insulation 0.9) and 0.5 R (2.4, 1.0), and the example (1.8).  So the
  gate passes at 0.25, used always (one station, no fallback).  The run
  needed: 1.27 R bare, 1.58 R under 0.25 R, 1.90 R under 0.5 R, 2.52 R
  under 1.0 R (forged C ≈ 1.84 R): the README sample, insulated 1.0 R,
  needs 0.1315 m and has 0.1.
- **Design's check: nang 48, 90°, single layer.**  Meshed min SJ 0.305
  (no inverted cells; non-orth. 58°; crease 0.7 % R; 4.7 min).  Clean
  (≥ 0.3) at every nang measured, 48 the finest.

## Questions for design

1. **Do equal laterals ship?**  The equal tee (90°) meets the acceptance
   and levels off above 0.3 as `nang` rises (0.33 at 32).  Laterals don't:
   at 60° and below they are rejected after meshing from nang 24 (table
   above), and 75° is at 0.155 by nang 24.  Options:
   `checkMesh` adds to it: from 60° down, laterals fail on skewness at
   nang 8 already.  75° passes at 8 and 16.
   - **(a) Equal tees only for now** (recommended): `EQUAL_LATERAL_ANGLE_MIN`
     at 90 (or a near-square band, e.g. 85°, if you want a tolerance:
     82° is 0.418 at nang 8, not measured finer); equal laterals wait for
     the crease fix (decision 0045), which is what makes them degrade.
     The gallery example drops its 45° lateral.
   - **(b) Ship 40°–90° as measured**, stating per angle the finest
     `nang` that builds, and rely on `mesh()`'s coded rejection above it.
     Users find out after meshing, which is what DESIGN's
     validate-before-gmsh rule is meant to avoid.
   - **(c) A nang-dependent floor** checked in `validate()`, from the
     table above, extended to nang 32 for every angle (about an hour of
     runs).  It needs a model of the decline, which two or three points
     per angle don't give.
2. **Insulated forged equal tees.**  Bare 90° ones build (1.52 R needed,
   1.84 R forged); insulated ones don't (1.90 R at insulation 0.25 R).
   Is a station below 0.5 worth measuring for them, or is
   `run_length_too_short` the right answer until decision 0045?

## Design answers (2026-11-10, the user: "yes")

1. **Q1: option (a), equal tees only.**  `EQUAL_LATERAL_ANGLE_MIN` 90;
   equal laterals rejected in `validate()` (before gmsh), coded, hint:
   equal laterals aren't supported yet; a reduced branch
   (r ≤ `TEE_MAX_RATIO` R) builds at that angle.  The gallery's 45°
   lateral dropped; lateral rows kept here and in the JSON, with the
   checkMesh failures (60° at 4.6, 45° at 6.2, nang 8).  **Cause, as
   design words it:** projection's move is fixed by the geometry
   (0.10–0.18 R), so it crushes more of the thinner cells as nang rises;
   the cause is the gap between the cube's flat wall-side faces and the
   curved wall, not mainly the crease, so decision 0045 alone probably
   wouldn't fix it.
2. **Q2: measure stations below 0.5 for insulated equal tees**, gate:
   the shortest station with meshed SJ ≥ 0.3 at nang 8 and 16, single
   and shelled, no inverted cells, checkMesh v2406 at nang 8; else
   `run_length_too_short` stands with the run needed in its hint.  A
   station used only when the run is short must stay deterministic.
   *Done: 0.25 passes, used always (Agent notes).*
3. **Check nang 48** at 90°, single: *0.305, clean (Agent notes).*
- The Re 3000 measurement (task 0119) may run meanwhile; DESIGN §7.2
  wording proposed for the equal tee only.

## Outcome

**Status:** done.  The equal tee builds through the oriented junction
cube; equal laterals are rejected before gmsh.

**Files.**
- New: `hexmesh/assembly/cube.py` (private: `CubeTee`, `orient`,
  `SHAPE`), `hexmesh/examples/fittings/equal_tee.py`,
  `tests/test_equal_tee.py` (17), `validation/tools/equal_tee.json`
  (every row measured here), `docs/gallery/img/equal_tee*.png`.
- Changed: `tee.py` (delegation, `_is_equal`, `meshed_sj_hint`,
  `second_order_limitation`, ports), `assembler.py` (callable hint and
  limitation), `limits.py` (`EQUAL_TEE_RTOL`, `EQUAL_LATERAL_ANGLE_MIN`),
  `junction_quality.py` (`CUBE_BLOCKS`, `CUBE_HINT`), `errors.py`
  (`equal_lateral_angle_below_min` in, `equal_tee_unsupported` out),
  `interchange/build.py`, `examples/__init__.py`; API.md, GUIDE.md,
  README.md, CHANGELOG.md, GALLERY.md and `metrics.json`; tests
  `test_tee.py`, `test_pcf_robustness.py` (an equal tee read and built),
  `test_pcf_junctions.py`, `test_readme.py`, `test_second_order.py`.

**Acceptance.**
- 90°, nang 8: meshed min SJ 0.511 single and shelled, no inverted
  cells, ports class-0 (and equal to the inlet's spec).  `checkMesh`
  v2406 passes (bare, shelled, insulated 0.25 R and 0.5 R, the example,
  and nang 16).
- Lateral range: square only (design's answer), coded.
- Every new error coded with a hint: `equal_lateral_angle_below_min`;
  the cube's `run_length_too_short`, `branch_length_too_short`,
  `tee_offset_out_of_range`, `predicted_sj_below_minimum`, and
  `mesh()`'s `meshed_sj_below_minimum` and `second_order_unsupported`.
- No hexmesh-written elements: every block is transfinite; nodes moved
  only by the wall projection (`projection_report`).
- Gallery: the 29 other examples' `.msh` byte-identical to HEAD's
  (meshed from a worktree of 39db888 and from the tree, `cmp`).
- Suite: 4043 passed, 15 skipped (33 min), after every change above.  The run
  before the second-order fix had one failure, the example at order 2.

**Step 4, per angle, as shipped** (90° only): see the GUIDE's table:
SJ 0.511 / 0.399 / 0.330 / 0.305, non-orth. 46 / 47 / 52 / 58°, crease
3.7 / 2.0 / 1.1 / 0.7 % R at nang 8 / 16 / 32 / 48.

**Proposed DESIGN §7.2 wording.**

> ### 7.2 Equal tee: the oriented cube
>
> A branch as wide as the main can't keep §7.1's continuous ring: the
> saddle corners would sit on the main's sides, where the ring blocks
> collapse.  The equal tee is built instead around an oriented cube
> (Bošnjak et al. 2024; decision 0043): a centre hex at the T-point; on
> each side of the cube a pipe leaves, a column of five blocks (an O-H
> face) running to that pipe's station; and on each of the other three
> sides one block, whose outer face lies on the wall and is projected
> onto it (decision 0029).  Every block is a transfinite hex; ports keep
> the standard O-H pattern and the inlet's spec.
>
> The crease where branch and main meet lies on cube edges only on the
> main's two sides; beside the branch it crosses the wall sides' faces,
> so its chord error is first order in `nang` (3.7 % R at 8, 1.1 % at
> 32), stated rather than gated (decision 0043).  The wall sides' flat
> faces sit up to 0.18 R inside the curved wall, and projection moves
> their nodes that far at any `nang`, so the meshed quality falls with
> refinement (min scaled Jacobian 0.511 at `nang` 8, 0.305 at 48).
>
> **Range.**  Square and centred only (`EQUAL_LATERAL_ANGLE_MIN` = 90°):
> equal laterals build at `nang` 8 but fold as `nang` rises and fail
> checkMesh's skewness from 60° down.  First order only: second-order
> hexes invert near the projected wall, as the wye's do.

**Surprises.**
- Refinement lowers the cube's meshed quality (above); the prediction
  can't see it, because the projection happens after the layout.
- At 90° the station distance doesn't matter at all from 0.25 to 4,
  which let bare and thinly insulated forged tees fit.
- An equal tee rebuilt its branch spec from cumulative thicknesses, and
  a shell's `dR` drifted by 1e-17; the branch now takes the inlet's spec.

**Proposed follow-ups.**
- (Design's candidate, not a task now.)  Carry each projected wall
  node's move into the block's interior nodes, blended along the
  block's lines toward the cube: a node-position correction, allowed by
  decision 0046, which should stop the crushing as `nang` rises and may
  bring back equal laterals and second order.
- PCF equal tees under thick insulation are `run_length_too_short`; the
  Tee's hint says "run_length=None to resolve it", which a PCF user can't
  do.  The interchange could say "a longer tee (run X) in the file".

**Follow-up done (2026-11-10, the user: "PCF hint now, blend to design").**
The PCF hint: `interchange/build.py` rewrites the hint of a junction's
`run_length_too_short` / `branch_length_too_short` in the file's terms
(what the component measures from its centre, what the junction needs,
"a longer component in the file, or thinner insulation"), from the
error's `value` and `limit`.  Test in `test_pcf_robustness.py`.  The
interior blend went to design for a task.
