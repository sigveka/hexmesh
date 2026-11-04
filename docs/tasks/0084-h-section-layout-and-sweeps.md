# 0084 — The H section: the layout, `layout=` on the spec, and every sweep

- **Status:** done
- **Decision:** [0036 — Cartesian (H) rectangular section](../decisions/0036-cartesian-rectangular-section.md) (items 2–4, rollout step 1); [0037](../decisions/0037-capability-boundaries.md) (the shared section interface); DESIGN A4, §6.1 "Sections"
- **Depends on:** 0082 (the O-H layout in `sections`), 0083 (the shape
  protocol); 0089 (Richardson) before step 8; 0090 (parallel runs)
  helps step 8.

Ground rules for all tasks: [README](README.md#ground-rules).  This task
works in `sections/`, `core/` and `assembly/`, and in
`validation/rect_duct/`.

**Why.**  On a rectangle the O-H face converges at order 0.3–0.9, while
a Cartesian grid converges at order 2 with 16× fewer cells per section
(RESEARCH §7.11).  The user accepted the H face as the default duct
face.  This task builds the layout and every sweep on it.  The default
stays `"oh"` until task 0087.

**Where.**
- New `hexmesh/sections/h.py`.
- `sections/` (the shared interface).
- `core/spec.py` (`layout=`, validation, serialisation).
- `assembly/signature.py`, `assembly/interface.py` (`port_type`),
  `assembly/sweep.py`.
- `tests/test_fitting_conformance.py` and the other tests listed below.
- `validation/rect_duct/`.

**Do.**
1. **The H layout** (`sections/h.py`): one transfinite patch with
   `nang_w` × `nang_h` cells, and corners NE, NW, SW, SE as in DESIGN
   §6.1's corner table (P = π, or π/2 for a square with equal counts).
   - The pure declaration (corners, edges with counts and grading, one
     patch) and the GMSH face both come from it (DESIGN §3.1, "one
     description per concept").
   - **Wall grading:** a two-sided progression on each side, from
     `first_cell=` (via `core/grading.py`) or an explicit ratio.  Check
     how gmsh's transfinite `Bump` and `Progression` behave for
     two-sided grading in the installed version.  Record that in
     `docs/integrations/gmsh.md` with version, evidence and date.
2. **The shared section interface.**  With `oh` and `h` both in
   `sections`, write down what fittings, the assembler and block
   layouts actually ask of a layout.  Make that the interface, as a
   `typing.Protocol`, implemented by both.
   - Make `CrossSection` generic.  The O-H anatomy (inner points,
     radials) moves into the O-H layout's own data.
   - Record the interface and why each member exists in *Agent notes*.
     It's what decision 0035's multi-core sections will implement.
3. **`PipeSpec.core(name, shape, ..., layout=)`.**
   - Values `"oh"` and `"h"`; the default stays `"oh"` in this task.
   - `"h"` is valid only with a `RectShape` core and no shells.  Shells
     come in 0086; until then, reject with a structured error that
     names the layout and the task.
   - `nrad` with `"h"` is an error naming both fixes (decision 0036
     item 4).  `first_cell=` / `mprg` apply to the wall grading.
   - The layout is part of `port_type` (A4) and of the signature (kind
     `h_core`).  Signatures that differ in layout classify as class 1
     when the counts match.
   - `to_dict()` writes `layout`.  `from_dict()` of a description
     without it gives `"oh"`, so old saved files are unchanged.
4. **Sweeps on H:** `Straight`, `Bend`, `Elbow`, `MiterBend`,
   `SplinePipe`, `Closure`, `Reducer` (H ↔ H, profiled included).  The
   sweep builder should need nothing beyond the section interface;
   record any H-specific code it needed.
   - The wall-exactness check (decision 0015): planar duct walls, and
     the bend's cylindrical side walls.
5. **Everything else rejects H ports before GMSH**: `Tee` / duct taps,
   `Wye`, `Transition`, equipment.  Structured errors name the fitting,
   the layout, and the task that adds support (0085 / 0086).
6. **Cell count and predicted quality** for H, exact before GMSH, as
   for O-H (`Assembly.cell_count()`, `section_quality.py`).
7. **Conformance kit:** add H duct specs (a/b 1, 2, 4; graded and
   uniform) to the sweep cases in `tests/test_fitting_conformance.py`.
8. **Task 0071's case on H** (`validation/rect_duct/`):
   - add an H series at k = 1, 2, 4, with about the same cells per
     section as the control;
   - gate it like the control (decision 0015 amendment 2): extrapolated
     value within 0.1 %, finest level below 1 %, order reported;
   - RESULTS.md: control, H and O-H side by side;
   - `case.json`: the H series becomes the accepted hexmesh result.

   - Task 0071 is done: extend its driver, which already has the
     control at these levels, and reuse the control results.
   - Convergence: don't gate on `residualControl` for `U`.  Its
     transverse components never settle when they are exactly zero
     (`docs/integrations/openfoam.md`, 2026-11-02).  Use `p` and the
     axial component, or the measured quantities.
   - Richardson through task 0089's shared function (do 0089 first).
   - The u_c gate is net of the centre fit's bias: decision 0015
     amendment 3.  Compare F(u_h) against F(u_exact) at the same faces.
     The driver already computes F(u_exact) (`u_c_sampling_err`).

**Accept.**
- The kit passes for every sweep on H; the agreement test from 0082
  covers `h`.
- `layout="h"` combinations not yet supported fail before GMSH with the
  named error; `nrad` with `"h"` gives the two-fix error.
- A description saved before this task (a fixture written from today's
  code) loads as `"oh"` and gives an identical mesh.
- **Every existing example and test mesh is unchanged** (the default is
  still `"oh"`): task 0065's before/after method.
- The H series of the rect duct passes the V1 gates for a/b = 1, 2, 4,
  with an observed order near 2 (OpenFOAM v2406).
- `tests/test_architecture.py` passes, with no new shape-type switches
  outside `core.shape` and `sections`.
- Full suite: no new failures; `-m openfoam` for the rect duct.

**Out of scope.**  The switch (0085), junctions and shells on H (0086),
the default flip (0087).

## Agent notes

- **Design refinement to step 3 (design session, 2026-11-03, the user
  agreed; answers to 0083's Questions):**
  1. **The wall span for `first_cell`.**
     - `core` keeps one table keyed by layout name.  Each row holds the
       scalar(s) a layout needs for the core's wall span: `OH_RATIO`
       for `"oh"`, and whatever `"h"` needs.
     - The table replaces `OH_RATIO` / `oh_core_wall_span` in
       `core/shape.py`.  The geometry stays in `sections`, and a
       `sections` test checks each layout's geometry against its row.
     - No registration hook and no global state; `core` doesn't import
       `sections`.  A few numbers per layout are spec data, not layout
       geometry, so DESIGN §3.1 holds.
     - Any other layout-dependent read left in `core` goes under
       *Questions for design*.
  2. **`shape.corner(k)` is shape geometry.**  The structural corners
     follow from `n_outer` and `rot`, and every layout must land on
     them (DESIGN §7).  So `corner(k)`, `spec.corners()` and
     `shell()`'s ring-thickness check stay in `core`.

- **Coding session, 2026-11-03: how the refinement landed.**
  - **The table.**  `core.shape.LAYOUTS = {"oh": {"ratio": 0.6}, "h": {}}`
    and `core_wall_span(radius, layout="oh")`.  `sections.oh.OH_RATIO`
    reads its row.  An H core needs no row: its wall span is the side
    itself, so `first_cell` goes straight to the side's `Bump`.
    `core_wall_span` keeps the old formula, `R − (hypot(ρ + ρ/√2, ρ/√2)
    − ρ)` with ρ = 0.6 R.  It's bit-identical to `oh_core_wall_span`
    over 10 000 radii.  Storing the span as one fraction of R would have
    changed the last bit for 86 % of radii, and so meshes.
    `test_sections.py::test_every_layout_row_has_its_geometry` ties each
    row to its layout; `test_first_cell` checks the O-H span on the
    built face.
  - **Errors.** `core.spec.LayoutNotSupported(ValueError)`, with
    attributes `where`, `layout` and `task`.  It is raised by
    `PipeSpec.shell` on H (0086), `Tee` and duct taps (0086, from
    `resolve`, before the duct tap's own checks), `Wye` (0086),
    `Transition` (0085), and `check_port_pairs` for an O-H ↔ H pair
    (0085).  Equipment needs no check: drum nozzles must be round, and
    an H core is a rectangle.
  - **Signature.**  O-H ↔ H on one rectangle with equal counts and
    `mbmp` is class 1 with `ends="pillow"`.  Termination is
    `ends="wall"`.  `Straight` and `Bend` declare class 1 for
    termination, so `check_port_pairs` refuses a pillow unless the
    fitting has `pillows = True`: the switch, task 0085.  The H core's
    `LayerSig.mprg` slot carries `PipeSpec.wall_grading`.
  - **Wall grading.**  `mprg` on an H core is the wall growth ratio
    (second cell over first); `first_cell` is the end cell at all four
    walls; both resolve to one `Bump` coefficient per side, `wall_bump`
    (`core.grading.bump_for_first_cell` / `bump_for_ratio`; Question 1's
    answer and its correction).
    `Progression` and `Beta` are one-sided in gmsh 4.12.1
    (`docs/integrations/gmsh.md`).
  - **H-specific code the sweep needed** (step 4):
    `corners.connect_patch` (one hex block per slab: four corner lines,
    four side faces, the two patches) behind a `layout` branch in
    `connect_layer`; `face_grading` and `section_cells` delegate to
    `sections.h`.  `blocks.face_vertices`, `face_patches` and
    `corner_shift` now ask `sections.layout_of(spec)`.  `Reducer`
    stations keep the layout and interpolate the wall coefficients
    geometrically, as `mprg`.  Its ends must both have `wall_bump`
    (from `first_cell=`) or neither.
  - **Elbow** stays round-only: its ASME schedules are for round
    pipe, so the kit has no H elbow case.
  - **`refine_spec_dict`** keeps `wall_bump`, so a series nests
    (Question 1).
- **Coding session, 2026-11-03: the section interface (step 2).**
  - **`sections.SectionLayout`**, a `runtime_checkable` `Protocol`.
    The layout modules `sections.oh` and `sections.h` implement it;
    `sections.LAYOUT_MODULES` maps a name to its module, and
    `layout_of(spec)` looks it up.  Its members, and who asks for
    them:

    | member | asked by |
    |--------|----------|
    | `NAME` | `PipeSpec.core(layout=)`, the table |
    | `CORE_KIND` | `assembly.signature`: kinds that differ never share nodes |
    | `levels(spec)` | `blocks.face_vertices`; `test_sections` checks the GMSH face against it |
    | `patches(spec)` | `blocks.face_patches`: port faces, cell zones |
    | `corner0_angle(spec)` | `blocks.corner_shift`: corner matching between frames |
    | `side_counts(shape, n_outer)` | sweep connections, face grading |
    | `section_cells(spec)` | `Assembly.cell_count` (via `sweep.section_cells`) |
    | `node_grids(spec)` | `section_quality`: predicted quality before GMSH |

    The O-H node grids (`_ring`, `_coons`, the patch assembly) moved
    from `section_quality` into `sections.oh.node_grids`, and the O-H
    cell formula into `sections.oh.section_cells`, with the code
    unchanged.  `progression` moved to `core.grading`, next to `bump`;
    `section_quality` re-exports both.
  - **Generic `CrossSection`** (`core.cross_section`).  It keeps what
    every layout has: the patches, the outer corners and sides, the
    shape, the plane, `lc` and `layout`.  The O-H anatomy (`center`,
    `inner_points`, `inner_curves`, `radial_curves`, `nrad`,
    `corner_angles`) moved to `sections.oh_gmsh.OHCrossSection`.
    The assembly reads a face only through two methods, which the
    subclass extends: `corner_entities()` (roles `op`, `oc`; plus
    `ip`, `ic`, `rc` on O-H) and `point_tags()`.  The H face is the
    base class as it is.
  - **Not in the interface, and why.**  Two pieces in `assembly`
    still branch on the layout:
    - the slab connection (`corners.connect_patch` vs
      `connect_aligned`);
    - the face grading (`sweep.face_grading`).

    Both build or tag GMSH entities from a built face, through
    `assembly.corners.canonical_geom`.  `sections` can't import
    `assembly`, so moving them there would mean moving the corner
    orientation helpers down a layer as well.  A third layout would
    add a third branch to each: a candidate for decision 0035's
    multi-core work, not this task.
  - **Step 8: a uniform H series, the control's counts** (coding
    session, 2026-11-03).  "About the same cells per section as the
    control" with no wall grading makes the H patch the control's own
    grid, so the gates test the hexmesh route (gmsh, `gmshToFoam`,
    boundary roles), not the graded H core.  A graded series needs a
    first cell chosen: Question 2.  The driver gains `--meshes h`
    (cases `h_ar<r>_k<k>`); `recheck` gates `h` like the control
    (`_gates`, shared); `versus_control` covers H and O-H, its rows
    gain `mesh` and `cells_<mesh>`.
  - **Step 9: a graded H series (Question 2's answer, 2026-11-04).**
    - a/b = 2 only, rect_duct's setup on v2406, `run_solver`'s n_proc.
    - Graded H core: `first_cell` at k = 1 about 0.3–0.5 of the uniform
      wall cell, chosen and stated.  **Chosen: D_h/30 = 6.67e-4 m, 0.40
      of the uniform D_h/12 on both sides** (`HG_FIRST_CELL`).  Stored
      `wall_bump` (0.2223, 0.1751); nested wall cells 0.37 / 0.36
      (wide) and 0.34 / 0.32 (narrow) of the uniform cell at k = 2 / 4.
    - Levels k = 1, 2, 4 by `Assembly.refined(k)` (k = 8 would be 1.7M
      cells), so the stored `wall_bump` nests.
    - Reported, not gated: RESULTS.md rows beside the uniform H series
      (f·Re and u_c per level, Richardson status, order, extrapolated
      against exact).  Rows in results.json; `recheck` reports them.
    - Expected: converging, order near 2, extrapolated f·Re about as
      close as the uniform series.  If not, numbers go under Questions
      before going further.
    - Driver: mesh `hg` (cases `hg_ar2_k<k>`), `HG_RATIOS = (2,)`.

## Questions for design

1. **Refinement series on a graded H core (needed by step 8).**  A
   `Bump` with the same coefficient and k× the cells nests exactly:
   every k-th node is a coarse node.  One `first_cell` gives each side
   its own coefficient.  At k× it can't keep both: for a 0.4 × 0.1 duct,
   16 × 4 cells, first cell 0.004, the nested first cells at k = 2 are
   0.00175 on the wide side and 0.00071 on the narrow one.  `first_cell
   / k` moves nodes by up to 2 % (k = 2) and 2.9 % (k = 4) of the side
   from the nested ones.  A ratio doesn't nest either: 1.3 at n = 8
   nests to 1.159, against 1.3^½ = 1.140.  `refine_spec_dict` raises
   for now.  Options: (a) store the per-side coefficients in the spec's
   description (`wall_bump: (c_w, c_h)`), and `first_cell=` only
   resolves them at `core()` time, as O-H's `first_cell` resolves to
   `mprg`; (b) refine by `first_cell / k` and accept non-nested grids;
   (c) per-side `first_cell`.  (a) mirrors O-H and keeps the series
   nested.  Not blocking steps 1–7.

   **Answer (design session, 2026-11-03; the user agreed): (a).**  No
   new decision; this sits inside 0001 and 0015.
   - Store the per-side coefficients in the description, `wall_bump:
     (c_w, c_h)`.  `first_cell=` only resolves them at `core()` time, as
     O-H's `first_cell` resolves to `mprg`.  `to_dict` writes them;
     `from_dict` and `refine_spec_dict` use them as stored.
   - Refine with the same coefficients and k× the cells, so the series
     nests exactly.  Lift `refine_spec_dict`'s raise.
   - Why: decision 0015 needs geometrically similar levels for a clean
     Richardson order (with (b), each level's grading change mixes into
     the error, step 8 included); it is the same as O-H; the
     description holds the grading actually used (decision 0001).
   - API.md, next to `first_cell`: exact at the level where it is
     given; refined levels get the nested first cell, not `first_cell
     / k`.  Said once for O-H and H.
   - Tests: a refined series nests (every k-th fine node is a coarse
     node, to 1e-12, k = 2 and 4, both sides); `wall_bump` round-trips;
     an explicit ratio still refines as today.

   **Done (coding session, 2026-11-03).**  `PipeSpec.core(wall_bump=)`,
   for H only.  `first_cell=` resolves to it from each side's length
   (between `shape.corner(k)` and `corner(k + 1)`) and count;
   `wall_grading` is `("bump", (c_w, c_h))`.  `Reducer` stations
   interpolate the coefficients geometrically, side by side.  Tests in
   `test_h_layout.py`.

   **Correction (design session, 2026-11-03; the user agreed):** an H
   core's explicit `mprg` also resolves to `wall_bump` at `core()` time,
   so its series nests too ("as today" withdrawn for H).  O-H is
   unaffected: the design session measured one-sided `mprg ** (1/k)`
   nesting at gmsh's ~1e-9 node floor (gmsh 4.12.1; Progression 1.3 and
   0.85, k = 2 and 4: 2.6e-9 and 1.5e-9; Bump 0.2: 3–4.5e-9), so only
   H's two-sided ratio didn't nest.  **Done:** `wall_grading` is now
   `("bump", (c_w, c_h))` or `None`; `to_dict` stores `wall_bump` only.
   A description from e0e88dc that saved an H ratio as `mprg` still
   loads, resolving it the same way.  The nesting test covers
   `first_cell` and `mprg` (k = 2, 4, both sides, analytic nodes, 1e-12).

2. **A wall-graded H series in the rect duct (not blocking).**  Step 8
   ran H uniform, which is the control's grid (Agent notes).  A graded
   series (`first_cell=` at k = 1, nested Bump at k = 2, 4) would test
   `wall_bump` in OpenFOAM too, but would be gated against what?  The
   exact solution needs no clustering at Re 100, so grading moves cells
   away from the centre and the error may rise.  Options: (a) a
   reported (not gated) H-graded series next to the uniform one, first
   cell e.g. D_h/100; (b) leave it to a case that needs a wall layer
   (heated or turbulent ducts); (c) nothing.  I'd take (b).

   **Answer (design session, 2026-11-04; the user: "Let us do a"):
   (a).**  No planned case is a graded duct (0049 is a pipe; 0072 can
   run uniform), so (b) could leave `wall_bump` untested in a solver
   for a long time.  Storing per-side coefficients was for nested series
   and Richardson, and this checks it directly.  Scope: step 9 (Agent
   notes).

## Outcome

**Steps 1–7 (coding session, 2026-11-03).**  Step 8 (the rect duct H
series on OpenFOAM) is not started: it waits for task 0090, as the index
orders.  Commits 244a55b (steps 1, 3–7), 1668408 (step 2), e0e88dc
(Question 1's answer), 912fe1c (the heated-rod import).

- **Files.**
  - New: `hexmesh/sections/h.py`, `tests/test_h_layout.py` (35 tests),
    `tests/data/saved_before_0084.json`.
  - Changed: `core/{spec,shape,grading,cross_section}.py`;
    `sections/{__init__,oh,oh_gmsh,_gmsh_helpers}.py`;
    `assembly/{blocks,corners,sweep,signature,interface,fittings,tee,
    wye,duct_tap,section_quality,intent}.py`;
    `validation/heated_rod/run.py`; `tests/test_sections.py`
    (+5 H specs, +3 tests), `tests/test_fitting_conformance.py`
    (+16 H cases), `tests/test_first_cell.py`; `API.md`;
    `docs/integrations/gmsh.md`.
- **Every existing mesh unchanged** (task 0065's method): full-suite
  recordings at c92cbd6 and e0e88dc, compared with the new `"layout":
  "oh"` key dropped from `to_dict`.  All 439 distinct meshes before
  are in the after run, identical node for node.  The 50 new ones all
  come from H cases (the kit, `test_build_sync`, `test_intent`,
  `test_refined`, `test_h_layout`).  Messages: 634 before, all in the
  after run, apart from one `SystemExit` of a test the import below
  broke; 12 new, the H tests' expected raises.
- **Tests.**  Full suite at e0e88dc: 2597 passed, 15 skipped, 2 failed.
  The 2 (`test_validation_meta` recheck, heated_rod) were a real break:
  `validation/heated_rod/run.py` imported `OH_RATIO` from `core.shape`.
  Fixed in 912fe1c, and `test_validation_meta` passes (28).  Before:
  2327 passed, 15 skipped; so +272 tests, mostly the kit's H cases ×
  its 6 checks and the parametrised suites that iterate the kit.
- **Measurements.**  The meshed H wall cell is the requested one to
  2.5e-8 relative.  `core.grading.bump` matches gmsh's `Bump` to 1.3e-8
  for coef 0.05–0.9, and to 3.3e-7 above 1 (gmsh.md).  A graded H
  series nests to 1e-12 (k = 2, 4).  Cell counts are exact before GMSH
  (`nang_w · nang_h` per section).  The predicted quality of a graded
  H face is scaled Jacobian 1, non-orthogonality 0.
- **Surprises.**
  - Storing the O-H wall span as a fraction of R would have changed
    the last bit of `first_cell`'s `mprg` for 86 % of radii, so the
    table stores the ratio and `core_wall_span` keeps the formula.
  - One `first_cell` can't give a nested refinement series (Question 1,
    answered (a)).
  - `Tee.resolve` runs at `add()`, before `check`, so the layout
    rejection is in both.
  - Renaming a `core` name breaks `validation/` drivers, which no
    import-graph test covers.  Only the meta test caught it.
- **Disk.**  Two recordings (152 MB, 158 MB) and a worktree, all in
  the scratchpad; deleted.  Nothing kept outside the repo.
- **Proposed follow-ups.**
  - The slab connection and face grading still branch on the layout in
    `assembly` (Agent notes, step 2).  Move them behind the interface
    when a third layout or decision 0035's multi-core work needs it.
  - An architecture check that `validation/*/run.py` imports only
    names that exist (or run each driver's `--help` in CI).
  - API.md's rectangular-duct section still says `Tee` rejects ducts,
    which has been stale since the duct taps (task 0057).

**Step 8 (coding session, 2026-11-03).**  The rect duct's H series on
OpenFOAM v2406, 2 processes (task 0090).

- **Files.**  `validation/rect_duct/{run.py, case.json, RESULTS.md,
  README.md, results.json}`; `tests/test_validation.py`
  (`test_rect_duct_h_coarse`).
- **Result.**  H uniform with the control's counts is the control's
  grid, cell for cell (2000 … 414 720; 0° non-orthogonality, min SJ
  1.000).  f·Re agrees with the control's to 1.1e-9 relative over the
  nine levels, u_c to 8e-11.  **The V1 gates pass at a/b = 1, 2, 4:**
  extrapolated f·Re +0.011 / +0.008 / +0.006 %, u_c net of the fit
  +0.012 / +0.005 / +0.003 %; finest |error| ≤ 0.26 %; observed order
  1.93–1.95 (f·Re), 1.90–1.91 (u_c).  All nine levels converged.
- **Tests.**  `-m openfoam -k rect_duct`: 3 passed (O-H, control, H).
  `test_validation_meta`, the driver-import test and
  `tests/test_validation.py`'s default set: 41 passed.  `recheck`:
  every gate passes, 36 (18 control, 18 H), O-H 9 reported.
- **Cost.**  ~20 min on 2 processes for the nine levels; solver time at
  k = 4: 69 / 226 / 609 s against the control's 115 / 362 / 1099 s
  serial.
- **Surprise.**  None in the numbers.  As found: step 8's wording makes
  the H series identical to the control, so it says nothing about the
  graded H core (Question 2).
- **Disk.**  The work directory (`/tmp/hexmesh-0084-h-*`) deleted;
  results.json grew to 34 kB.
- **Proposed follow-ups.**  Question 2.  The other two follow-ups above
  were done in task 0090 (the driver-import test, the API.md line).

**Step 9 (coding session, 2026-11-04).**  The graded H series at
a/b = 2 (Question 2's answer), v2406, 2 processes.

- **Files.**  `validation/rect_duct/{run.py, RESULTS.md, README.md,
  results.json}`: mesh `hg`, `HG_RATIOS`, `HG_FIRST_CELL`; `recheck`
  reports the graded rows, not gated.
- **Grading.**  `first_cell` D_h/30 = 6.67e-4 m at k = 1, 0.40 of the
  uniform wall cell; `wall_bump` (0.2223, 0.1751).  Nested wall cells
  0.37 / 0.36 (wide), 0.34 / 0.32 (narrow) of the uniform level's at
  k = 2 / 4.  k = 1, 2, 4 (3240 / 25 920 / 207 360 cells).
- **Result: as expected.**  All converging: f·Re order 1.93,
  extrapolated +0.014 % (uniform H: 1.94, +0.008 %); u_c order 2.03;
  u_c net of the fit's bias order 1.97, extrapolated −0.0002 %.
  f·Re's error is about 8 % larger than uniform at each level (the
  centre cells are wider); the field's max error is half the uniform
  one's (0.062 against 0.124 % at k = 4).
- **Tests.**  `test_validation_meta`, the driver-import test and
  `tests/test_validation.py`'s default set: 41 passed.  `recheck`
  reports the three graded rows; the gates are unchanged (36 pass).
- **Surprise.**  The centre fit sees fewer faces on the graded grid
  (12 / 40 / 200 against 24 / 112 / 392: the window is fixed, the centre
  cells larger), so its bias is larger (+0.12 % at k = 4).  The net u_c
  takes it out.
- **Cost and disk.**  About 5 min on 2 processes (solver 0 / 7 / 228 s).
  Work directory (`/tmp/hexmesh-0084-hg-*`) deleted; results.json
  +3 levels.

