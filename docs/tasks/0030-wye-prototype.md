# 0030 — Wye prototype: symmetric Y-junction as a block layout

- **Status:** done
- **Decision:** [0017 — Y-junction (wye): prototype first, quality limit after measurement](../decisions/0017-wye-junction-prototype.md)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  hexmesh has no Y-junction; the legacy one was deleted for
using `occ.fragment()` and gave SICN ≈ 0 seams.  Published constructions
reach min scaled Jacobian 0.488 on a 5-patch O-H section without
smoothing (RESEARCH §4.2).  This task builds a first, symmetric wye and
**measures** it, so the quality limit can be decided from numbers
(decision 0017).

**Where.**
- New `hexmesh/assembly/wye.py`, on `hexmesh/assembly/blocks.py`
  (`BlockLayout`, `face_vertices`, `bind_face`, edge kinds).  Model it on
  `hexmesh/assembly/tee.py`.
- `hexmesh/assembly/__init__.py`, `hexmesh/__init__.py`,
  `hexmesh/assembly/intent.py` (fitting registry).
- `tests/test_fitting_conformance.py` (kit cases), a new `tests/test_wye.py`.
- Reading: RESEARCH §4.1, §4.2 and §4.4; the papers
  `docs/papers/decroocq_and_frindel_etal_2023.pdf` and
  `docs/papers/marcinno_and_hinz_etal_2025.pdf`.

**Do.**
1. **API** (propose the exact signature under *Agent notes*; this is a
   suggestion):
   `Wye(angle, run_length, branch_length, n_run=…, n_branch=…, n_split=…)`.
   - `angle`: the full angle between the two daughters, split equally
     about the inlet direction.
   - Ports: `[left, right]` outlets with the inlet's spec.
   - The bifurcation plane passes through two opposite structural
     corners of the inlet section (corner k at π/4 + kπ/2 from
     `frame.right` with `rot = 0`).  So the plane's orientation follows
     the inlet frame; to turn it, roll upstream (Assembly `up`, a `Bend`
     roll).  If you find a cleaner convention (e.g. a `roll` limited to
     multiples of 90°), propose it.
   - Outlet frames: chosen so each daughter's corners also lie in and
     perpendicular to the bifurcation plane, matching the construction.
   - Limits, rejected in `validate()` with messages: single-layer spec,
     `rot = 0`, `n_outer = 4`, angle range (propose one from what
     meshes, e.g. 30°–120°).
2. **Topology** after Decroocq (RESEARCH §4.1): one inlet and two outlet
   regions meeting at an internal dividing face (the butterfly).  Only
   the three branch ends are interfaces; the dividing face and every
   other block face are internal to the layout (DESIGN §7).  Draw the
   block layout (blocks, shared faces, division classes) under *Agent
   notes* before coding it.
3. **Geometry** after Marcinnó (RESEARCH §4.2): anchors on each end
   section, Hermite curves between matching anchors, the six ellipse
   quadrants of the butterfly.  All closed form, so `ports`, `validate`
   and `cell_count` run without GMSH (P3, P4), and `BlockLayout.validate`
   checks corner Jacobians before GMSH.
   - **No smoothing** and no node moves after meshing.
   - Edges: use the existing kinds (`Line`, `ArcAbout`, `Spline`); add an
     edge kind only if needed, and record it.
4. **Quality report, no rejection on quality.**  The wye must pass the
   conformance kit (positive Jacobians, conformity, fill order, groups).
   Beyond that, don't reject on quality.  If the default quality
   threshold makes `check_quality().ok` false for the wye, record it and
   don't tune; the example test may assert the kit criteria and the
   cell count only.  Decision 0017 decides the limit from your numbers.
5. **Measure** (record all under *Outcome*):
   - for `angle` 30°, 60°, 90° and 120°, at `nang` 6 and 12:
     min scaled Jacobian, mean, min SICN, max NES (RESEARCH §4.2 for the
     definition), cell count, and mesh time;
   - **where the worst cells are** (which blocks, near which vertices);
     compare with Marcinnó's report (extraordinary vertices next to the
     butterfly);
   - wall deviation: how far junction wall nodes lie from the surface
     the construction intends (the swept circles of each branch, blended
     by the Hermite map), as DESIGN's deviations table records 2–5 % of
     R for the tee.  Report it; it does not block;
   - one OpenFOAM check (opt-in, `-m openfoam`): `gmshToFoam` +
     `checkMesh` on the 60° wye: "Mesh OK", max non-orthogonality and
     skewness.
6. **Example** `wye`: inlet straight, a 60° wye, a straight on each
   daughter (named outlets).  Register it in `tests/test_examples.py`.
7. **Docs.**  `API.md` (`Wye`, its limits), the README table and
   limitations ("No Y-junction yet" goes).

**Accept.**
- Conformance-kit cases: wye at 60° and 90°, and one off-axis inlet
  direction (like the tee's oblique case).  All-hex, meshed = predicted,
  conformal, every fill order, every kit check passing.
- The measurement table from step 5, with worst-cell locations and the
  comparison with 0.488.
- Save/load round-trip.
- Full suite: no new failures.

**Out of scope.**  Unequal radii or angles, laterals, multi-layer wyes,
n-furcations, a generic N-port builder (DESIGN §6.1: derived from tee
and wye later), and any quality limit (decision 0017 follows your
numbers).  Keep in mind that asymmetric, non-planar wyes with unequal
radii are a planned expansion ([decision 0018](../decisions/0018-future-vascular-networks.md), constraint 3): restrict
the prototype in `validate()`, not in its data model.  If quality is far below 0.488, report the numbers and your
diagnosis under *Questions for design* instead of adding smoothing.

## Agent notes

- 2026-10-27.  Marcinnó's anchors are arc midpoints, not corners (paper
  Fig. 3: the square's corners are on the diagonals; Fig. 7: petals are
  ellipse quadrants cut along the axes).  See Q1.
- 2026-10-27.  Reproducer for Q2: a `geo` unit cube whose top face is two
  plane surfaces split at x = ½.  The two 5-curve side faces are made
  transfinite with `cornerTags`, and so is the volume (8 corners).
  `generate(3)` fails with "Transfinite algorithm only available for
  volumes bounded by 5 or 6 surfaces".
- **API** (2026-10-27):
  `Wye(angle, run_length, branch_length, n_run=3, n_branch=3, n_split=3)`.
  - `angle` is in degrees, between the daughters.
  - `run_length`: inlet port → bifurcation point O on the inlet axis.
  - `branch_length`: O → each outlet port, along the daughter axes
    d = cos(angle/2)·n ∓ sin(angle/2)·right.
  - Ports `[left, right]`, each with the inlet's spec.  Outlet frame:
    normal d, up = inlet up (perpendicular to the plane, so no twist).
  - `n_run`, `n_branch`: layers of the straight runs.  `n_split`: layers
    of each daughter's turning block, from the hub to its station.
  - The plane is the inlet's (normal, right) plane.  It contains two arc
    midpoints (Q1).  To turn it, roll upstream.
- **Intended wall** (used to place wall vertices and to measure
  deviation): the canal surface of radius R about the skeleton.  The
  skeleton is the inlet axis up to O plus the two daughter rays from O,
  so the surface is {p : dist(p, skeleton) = R}.  It is exact on all
  three cylinders, has a sphere about O at the outer knees, and a crease
  (the half-ellipse X_top → AP → X_bottom in the mirror plane) at the
  crotch.  Wall curves are base curves pushed onto it along rays from
  the nearest skeleton point.
- **Block layout** (symmetric hub; corner k of an O-H face at
  45° + k·90° from that face's `right`):

  ```
  top view (bifurcation plane), core level only:

        port L ── S_L ┐            ┌ S_R ── port R
                      D_L   ┌─┐   D_R          D_*: daughter turning cores
                        ╲   │H│   ╱            H: hub (back face = Sa core)
                         ╲  │ │  ╱
                            └┬┘
                         Sa core
                            │  inlet run
                         port A
  ```

  - Stations: Sa on the inlet axis, s_in behind O.  S_L and S_R on the
    daughter axes, s_d ahead of O.  All are internal O-H faces.
  - Runs: port A → Sa (`n_run`), S_L → port L and S_R → port R
    (`n_branch`).  5 blocks each.
  - Hub H: back face = Sa core (Sa0k).  Front face F0..F3 = the
    daughters' inner-square corners on the crotch side at t_W along each
    daughter axis (F0, F3 on d_R; F1, F2 on d_L).
  - D_R: H's +right face (Sa00, Sa03, F3, F0) → S_R core (SR00, SR03,
    SR02, SR01).  D_L mirrored.  `n_split` layers.
  - Ring layer: one ring block over every face of the core region
    (H ∪ D_L ∪ D_R) that is not a station core patch.  H top, bottom and
    front (crotch), plus four per daughter: 11 blocks.  Wall vertices:
    station level-1 corners, and W0..W3 (the wall points of F0..F3, on
    the daughter cylinders).
  - Shared faces: Sa's ring patches are faces of H-top, H-bottom, D_R
    outer and D_L outer.  S_R's ring patches are faces of D_R's four
    rings.
  - Division classes: H has `nang` in all three directions (its length
    is parallel to S_R's core edges through D_R).  D_* have `n_split`;
    all radial edges have `nrad`.
  - Irregular edges: the radial edges at H's back corners (Sa1k) have
    5 blocks around them.  These are the wye's extraordinary
    vertices.
  - Blocks: 5 + 1 + 2 + 3 + 8 + 10 = 29.
  - Cells: (n_run + 2·n_branch)(nang² + 4·nang·nrad) + nang³
    + 3·nang²·nrad + 2·n_split(nang² + 4·nang·nrad).
- **Geometry, as built** (closed form, h = angle/2, R = radius):
  - Sa at R(tan h + 0.1) behind O, so its circle is clear of both
    daughters.  S_L and S_R at R(cot h + 1) along the daughter axes.
    R·cot h is where the crotch generators meet (the apex).
  - Hub front corners F on each daughter's crotch-side core corners at
    0.65·R·cot h.  Wall crotch corners W on the daughter cylinders at
    45° elevation, 0.3 R from the mirror plane.
  - Edges:
    - daughter core outer edges: Hermite curves (tangents n → d,
      Marcinnó);
    - outer-knee wall edges: Hermite curves pushed onto the wall;
    - hub-top wall edges: chords pushed onto the wall;
    - crotch-side edges: on the daughter cylinder, bulging 0.3 R past
      the apex;
    - crotch top and bottom edges: straight in (t, φ) on each cylinder
      to the crease at 45° elevation, meeting there.
  - The placement constants came from a small grid search on block-corner
    Jacobians (pure numpy), and then mesh checks at 30°–120°.
- **Iterations that failed** (2026-10-27):
  - Plate fillings of the wall patches sagged up to 0.66 R: 42 inverted
    cells at 60°.
  - With the wall corners at 0.75·R·cot h, W0 and W1 were 0.07 R apart (a
    sliver patch).
  - A Hermite hub-top edge crossed its mirror image at 120° (a bow-tie
    patch).
  - Plate fillings pinned to wall points were fragile and asymmetric.
  - Settled: `Stretch` B-spline fillings for every curved face.  Valid at
    every angle, mirror-symmetric to 1e-14 R, best cells.  See
    `docs/integrations/gmsh.md`, "Filling choices".
- **Additions outside `wye.py`:**
  - `blocks.Polyline`, a new edge kind: straight segments, C0, for edges
    that cross the crotch crease, where a spline would overshoot.
  - `BlockLayout.filling`: `None` keeps the plate (the tee is unchanged);
    the wye sets `"Stretch"`.
  - `n_split` added to `intent.AXIAL_COUNTS`, so `refined(k)` scales it.

## Questions for design

**Q1. The bifurcation plane must pass through two opposite arc midpoints,
not two opposite corners.**  Decision 0017 (Decision, and Context
"Corners") and step 1 say the plane passes through two opposite
structural corners.  With block faces, that does not work:

- By symmetry, the three regions meet on the separation line
  (X_top–X_center–X_bottom, Decroocq's CT₀–X–CT₁).  It is perpendicular
  to the bifurcation plane.  On each branch's end face it runs through
  the section centre, so it must be a path of mesh edges through the
  centre.
- In the 5-patch O-H face, the only such paths are the core's two
  midlines.  They hit the wall at arc *midpoints* (0°, 90°, 180°, 270°
  from `frame.right` with `rot = 0`), never at corners (45° + k·90°).
- With the plane through corners, the separation line would follow the
  core square's *diagonal*.  The core block's end face would fold along
  its diagonal, and each petal would get a triangle, not a quad.
- **Marcinnó does the same** (paper Figs. 3 and 7).  The 5-patch square
  has its corners on the diagonals, and the anchors are at θ = iπ/2,
  i.e. arc midpoints.  Each butterfly petal is a pair of ellipse
  *quadrants* cut along the axes, through the core's midlines and the
  middle of two ring patches.  RESEARCH §4.4 item 2 ("the split must land
  on corners") reads the anchors as corners; they are not.

**Proposal:**
- Plane: the plane spanned by the inlet's `normal` and `right` (it
  contains two arc midpoints).  The daughters turn toward ±`right`.  With
  `up` = +z on a horizontal pipe, the wye lies horizontal.
- Consequence: **`nang` must be even.**  The fold splits the core and
  the two ring patches it crosses into halves of `nang / 2` divisions.
  `validate()` rejects odd `nang`.  The task's nang 6 and 12 and the
  kit's 4 are all even.
- Each branch is the standard 5-patch O-H sweep.  The blocks crossed by
  the fold (the core, and the two ring patches at the top and bottom
  midpoints) are each split in two at the fold.  No other change to
  decision 0017 (approach A, Marcinnó geometry, measure first).

*Answered by the user, 2026-10-27:* "Proceed with arc midpoints".  Task
unblocked; the decision wording is left for the design session.

**Q2. The butterfly topology cannot be built from transfinite blocks with
5-patch ports.**
- On the butterfly, each branch's end face is two petals.  The fold
  between them runs along the core's midline.  So the core block (and
  the top and bottom ring blocks) would end on two faces, each shared
  with a different neighbour.
- A gmsh transfinite volume must have exactly 5 or 6 faces (verified,
  `docs/integrations/gmsh.md`).  So the split would have to run back to
  the port, where the core is one surface.
- Marcinnó's spline maps carry the fold *inside* a patch, so they never
  meet this.  Decroocq writes nodes directly.
- Therefore the cores need a **hub**, as in the tee: the three cores
  attach to faces of junction core blocks, and a ring layer covers the
  whole core region (an offset of the wall).
- Hermite curves for the walls and the apex (Marcinnó's geometry) still
  apply.

Options:
- **A. Symmetric hub.**  One hub block H continues the inlet core.  The
  daughters' cores leave H's ±`right` faces and turn toward their axes.
  A crotch ring covers H's front face.  Mirror-symmetric; any `nang`.
  Four 5-valent radial edges at H's back corners.  The daughter cores
  turn by 90° − angle/2, so it is worst at small angles.
- **B. Tee topology, deformed.**  Reuses `Tee`'s block structure: one
  daughter "through", one "branch".  Not mirror-symmetric.
- **C. Wait** for a design decision.

*Answered by the user, 2026-10-27:* "Symmetric hub".  A hub needs no
fold, so the even-`nang` limit of Q1 goes; the plane through two arc
midpoints stays (the hub's ±`right` faces).

**Q3. Quality is far below Marcinnó's 0.488; diagnosis and options
(the task asks for this instead of smoothing).**
- **Numbers** (Outcome table):
  - at 60°, nang 12: min scaled Jacobian 0.117 (Marcinnó 0.488), mean
    0.863 (0.907), max NES 0.91 (0.634);
  - 1.9 % of cells below SJ 0.3, 9.2 % below 0.5, 14 % below 0.6;
  - the minimum barely moves with refinement (0.156 → 0.117 at 60°): it
    is block shape, not resolution.
- **Where.**
  - In the daughters' top and bottom ring blocks, at the hub's back
    corners Sa0k / Sa1k: the 5-valent radial edges.  Those blocks have
    11 % of their cells below 0.3.
  - Next worst: the daughter cores (min 0.17) and the crotch ring (0.35).
  - At 30°: the crotch corners (F, W).
  - This matches Marcinnó's report in kind (extraordinary vertices next to
    the junction), not in size.
- **Diagnosis.**
  - The hub's side faces run nearly along the flow, so each daughter's
    core leaves the hub at a grazing angle.  Before GMSH, the block
    corners at Sa0k already have SJ 0.53 (daughter core) and 0.37 (top
    ring).  Curved faces lower it further in the mesh.
  - This comes with the symmetric hub (option A) when the daughter cores
    run straight to their stations.
- **Options:**
  - **(a)** Daughter cores that leave the hub sideways and bend into
    their axes, with a shorter hub.  Untested; it fights the outer ring,
    which runs along the inlet wall.
  - **(b)** A realisation that is not transfinite blocks: direct node
    placement, a decision 0007 backend.  It could carry Marcinnó's fold
    inside a patch (Q2), and with it his quality.
  - **(c)** Exact wall surfaces, e.g. trimmed B-spline surfaces through
    wall point grids, for the deviation below.  Untested.
- **For DESIGN §10 "Reject or degrade?":**
  - with this topology, a global min-SJ limit above about 0.06 rejects
    some wye in 30°–120°;
  - the default `check_quality` (minSICN > 0) passes every case
    measured.

## Outcome

Done 2026-10-27.  Symmetric hub topology (Q2, the user's choice); plane
through arc midpoints (Q1).  Q3 is for the design session.

**Files.**
- New `hexmesh/assembly/wye.py`:
  - `Wye`, plus `Skeleton` (the intended wall and its projection);
  - closed-form `placement`, `check`, `layout`, `validate`,
    `cell_count`, `fill`.
- `hexmesh/assembly/blocks.py`: the `Polyline` edge kind and the
  `BlockLayout.filling` option.
- Exports and registry: `hexmesh/assembly/__init__.py`,
  `hexmesh/__init__.py`, `hexmesh/assembly/intent.py` (`FITTING_TYPES`,
  `AXIAL_COUNTS`).  The `refined` docstring in `assembler.py`.
- `hexmesh/examples/wye.py`, registered in `hexmesh/examples/__init__.py`
  and `tests/test_examples.py`.
- Tests:
  - kit cases `wye-60`, `wye-90` and `wye-60-oblique`; the exactness
    check skips junctions, as it does for the tee;
  - new `tests/test_wye.py` (22 tests: ports, layout without GMSH, the
    closed-form cell count, rejections, crotch corners on the wall,
    all-hex at 30–120°, mirror symmetry to 1e-6 R, a wall-deviation
    guard of 0.25 R, save/load, and an opt-in `checkMesh`);
  - `Wye` added to the registry test.
- Docs: `API.md` (`Wye` section, `refined`, grading note); `README.md`
  (fitting row, example row, accuracy note, limitations; "No Y-junction
  yet" removed).
- `docs/integrations/gmsh.md`: the 5-or-6-face transfinite volume limit,
  and the filling choices.

**Tests.**
- Full suite: 921 passed, 5 skipped (tee and wye wall exactness).  Before
  this task: 863 passed, 2 skipped.
- `-m openfoam tests/test_wye.py`: 1 passed.
- Save/load round trip: the kit cases in `tests/test_intent.py` and
  `test_save_load_round_trip`.
- `refined(k)`: the kit cases in `tests/test_refined.py` (k³ cells; meshes
  as predicted at k = 2).

**Measurements** (step 5).
- Setup:
  - the wye alone, inlet along x, `up` = z, R = 0.1;
  - `run_length` = s_in + 2R and `branch_length` = s_out + 2R;
  - `n_run` = `n_branch` = `n_split` = nang, nrad = nang / 2.
- Metrics:
  - SJ and NES are `hexmesh.quality_hex`: 8-corner scaled Jacobian, and
    NES over the face angles (RESEARCH §4.2);
  - SICN is GMSH minSICN;
  - wall deviation: (distance to the skeleton − R) / R over every node on
    the wye's wall surfaces (the runs are exact);
  - mesh time is `Assembly.mesh()` (fill and generate), with no other
    session running.

| Angle | nang / nrad | Cells | min SJ | mean SJ | min SICN | max NES | Mesh (s) | Wall dev. (× R) | Worst cells |
|---|---|---|---|---|---|---|---|---|---|
| 30° | 6 / 3 | 3780 | 0.065 | 0.769 | 0.091 | 0.946 | 0.9 | −0.198 … +0.185 | daughter top/bottom rings at F (hub front) |
| 60° | 6 / 3 | 3780 | 0.156 | 0.835 | 0.170 | 0.865 | 0.9 | −0.090 … +0.149 | daughter top/bottom rings at Sa0k (hub back) |
| 90° | 6 / 3 | 3780 | 0.164 | 0.860 | 0.195 | 0.865 | 0.9 | −0.124 … +0.126 | daughter top/bottom rings at Sa0k |
| 120° | 6 / 3 | 3780 | 0.117 | 0.852 | 0.157 | 0.905 | 0.9 | −0.134 … +0.090 | daughter top/bottom rings at Sa0k |
| 30° | 12 / 6 | 30240 | 0.062 | 0.799 | 0.085 | 0.946 | 1.0 | −0.198 … +0.185 | daughter top/bottom rings at W (crotch) |
| 60° | 12 / 6 | 30240 | 0.117 | 0.863 | 0.138 | 0.912 | 0.9 | −0.090 … +0.159 | daughter top/bottom rings at Sa0k |
| 90° | 12 / 6 | 30240 | 0.126 | 0.885 | 0.163 | 0.902 | 0.9 | −0.124 … +0.126 | daughter top/bottom rings at Sa1k (wall) |
| 120° | 12 / 6 | 30240 | 0.066 | 0.878 | 0.082 | 0.921 | 0.9 | −0.137 … +0.100 | daughter top/bottom rings at Sa1k (wall) |

- **Predicted vs meshed.** Predicted = meshed in every case.  All four
  symmetric blocks share the worst value.
- **Compared with Marcinnó** (64k nodes): min SJ 0.488, mean 0.907, max
  NES 0.634.
  - Ours is a quarter of his minimum at 60°, with mean SJ close (0.86).
  - The worst cells are at the junction's extraordinary vertices, as he
    reports, but much worse.  See Q3.
- **60°, nang 12, per block** (min / mean SJ):

  | Block | min SJ | mean SJ |
  |---|---|---|
  | daughter top/bottom rings | 0.117 | 0.622 |
  | daughter cores | 0.166 | 0.678 |
  | hub top/bottom rings | 0.266 | 0.795 |
  | crotch ring | 0.346 | 0.590 |
  | daughter crotch rings | 0.351 | 0.710 |
  | outer rings | 0.682 | 0.939 |

  Overall: 0.38 % of cells below 0.2, 1.9 % below 0.3, 9.2 % below 0.5.
- **Wall deviation** (60°, nang 6), per wall patch:

  | Patch | Deviation (× R) |
  |---|---|
  | hub top/bottom (saddle region) | +0.149 outward |
  | crotch (rounded) | −0.090 |
  | daughter tops | −0.078 |
  | outer knees | ±0.03 |
  | daughter crotch sides | 0 (exact) |

  Curve nodes are exact by construction.  Surface nodes lie on `Stretch`
  fillings.  The tee was 2–5 %.  It does not block (decision 0017).
- **OpenFOAM v1912** (60° wye between straights, `gmshToFoam` +
  `checkMesh`):

  | nang | Cells | Mesh OK | Max non-orth. | Avg non-orth. | Max skewness |
  |---|---|---|---|---|---|
  | 6 | 5724 | yes | 76.5° | 18.4° | 2.26 |
  | 12 | 45792 | yes | 81.5° | 18.7° | 2.90 |

  The high maximum non-orthogonality fits the sheared ring cells.

**Surprises.**
- The decision's "plane through corners" cannot be meshed with blocks (Q1).
- The butterfly topology needs 7-face transfinite volumes, which gmsh
  refuses (Q2).
- Plate fillings fail badly on long curved patches (gmsh.md).
- Quality is far below the published 0.488 (Q3).

**Proposed follow-ups.**
- Decision 0017 and RESEARCH §4.4 item 2 need rewording: arc midpoints,
  hub topology.
- The quality options in Q3 (a–c).
- DESIGN §10 limit from these numbers.
- DESIGN §7.2 Wye section.
- Wye wall deviation in the DESIGN deviations table, next to the tee.
