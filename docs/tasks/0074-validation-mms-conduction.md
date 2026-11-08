# 0074 — Verification (V1): manufactured solutions for conduction on every fitting's mesh

- **Status:** done (2026-11-08)
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md) (V1); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) as amended
- **Category:** V1 (exact: manufactured solutions)
- **Features:** `section:circle`, `section:rect`, `layers`, `straight`, `bend`, `miter`, `spline`, `profiled-reducer`, `transition`, `tee`, `duct-tap`, `wye`, `stack-changes`, `projection`
- **Depends on:** the shared OpenFOAM helpers and the Docker runner
  (0043, 0035's Q2 answer).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The coverage matrix (task 0073) has eight features with no
verification.  No physical experiment checks the discretisation on every
junction mesh; manufactured solutions do.  The same evidence (the error
and its observed order) found the O-H order loss in the heated rod (task
0033).  This task builds one harness and runs it on every fitting.

**The method** (RESEARCH §7.9).
- Pick a smooth field T_m(x, y, z) with a few wavelengths across the
  geometry, e.g. a product of sines and cosines scaled to the fitting's
  size (state it).
- Solve steady conduction ∇·(k∇T) + S = 0 with the source
  S = −k∇²T_m (computed analytically) and Dirichlet T = T_m on every
  boundary patch, walls and ends alike.
- The exact solution is T_m.  Measure the L2 and max errors over the
  cells, overall and per region (junction cells vs the run cells); and
  the observed order over `refined(k)`, k = 1, 2, 4.
- **One conductivity in every layer:** the test is of the mesh, not of
  interface physics.  Layers, stack changes and shells are mesh topology
  here.

**Where.**  `validation/mms/` (`run.py`, `README.md`, `RESULTS.md`,
`case.json`, `meshes()`), on `hexmesh.study.openfoam` with the v2406
runner; `docs/integrations/openfoam.md`.

**Do.**
1. **Spatially varying source.**  Find the cheapest way on v2406 and
   record it in `openfoam.md`:
   - a field-based source with no compiling (e.g. `setExprFields` to
     write S, read by a source option), or
   - `codedFvOption` / `scalarCodedSource`, if the container can compile
     (check `wmake`).

   Boundary values are written per face by Python (nonuniform
   `fixedValue`).
2. **Solver:** `laplacianFoam` to steady (or the steady-state ddt
   scheme); tight tolerances; `Gauss linear corrected` (as task 0033).
3. **Cases** (single material; circular unless noted):
   - straight (the baseline);
   - bend;
   - miter (3 cuts);
   - spline (3-D);
   - profiled reducer (cosine);
   - circle→rectangle transition;
   - tee r/R 0.5, with and without two shells;
   - insulation stopping inside a straight (stack change);
   - wye 60° and 90°, with and without a shell (projected walls);
   - duct tap (rectangular and round);
   - a rectangular duct straight.
4. **Report per case:** L2 and max error at each level, the observed
   orders (overall and in the fitting's own cells), and where the max
   error sits.  Flag any fitting whose order is more than 0.3 below the
   straight baseline's.

**Accept.**
- The harness reproduces the heated rod's behaviour on the straight
  (the order and the error location match task 0033's RESULTS).
- Every case's error falls with refinement.  Orders reported, not gated
  (decision 0015 as amended).  Flagged fittings listed under *Questions
  for design* with the evidence.
- `case.json` (V1, the features above); RESULTS.md; *Outcome* table for
  RESEARCH.

**Option (proposed decision 0034, not required).**  If the OpenFOAM
source-term route is costly, or as a second solver once 0034 is
accepted: the same manufactured solutions in **FEniCSx**, reading the
same `.msh`.  There the source is a Python expression.  Don't start
it without design's go-ahead; record the OpenFOAM route's cost under
*Agent notes* so design can weigh it.

**Out of scope.**  Flow MMS (a follow-up if the conduction results are
useful); different conductivities per layer (interface physics: tasks
0034/0035 cover it).

## Agent notes

- **Source route (no compiling), v2406:**
  - The source is a `scalarSemiImplicitSource` with an `exprField`
    explicit source, `pos()`-based.
  - The boundary values are `uniformFixedValue` with an `expression`
    Function1 on a `".*"` patch entry.  This replaces the planned "Python
    writes face values".
  - `exprFixedValue` also works, with the key `valueExpr`, but it is
    deprecated after 2212.
  - Recorded in `docs/integrations/openfoam.md`.
- **The route's cost:**
  - Nothing to compile.
  - The full study, 16 cases × 3 levels on 4 MPI processes, took about
    4 h 10 min.  The k = 4 levels dominate, and the two diverging duct
    taps ran their 200 steps.
  - Steady laminar solves take 2–9 steps of 10 correctors each.
  - The Python post-processing takes seconds per level.
- **Wave numbers:** 1.5 wavelengths along each extent of the k = 1 mesh's
  bounding box, but no wavelength shorter than D.  Every level solves the
  same problem.
- **`gmshToFoam` inverted valid hexes:**
  - The wye90 k = 4 level failed at first: `checkMesh` reported
    2 negative volumes and 16 open cells, and `laplacianFoam` stopped on
    a floating-point exception.
  - Cause: `gmshToFoam`'s `correctOrientation` turns valid, strongly
    warped hexes inside out.  The gmsh mesh was closed and conformal,
    with corner scaled Jacobian ≥ 0.13.
  - Fix: `convert(..., keep_orientation=True)` (opt-in, with a test),
    which this driver uses whenever the worst scaled Jacobian is
    positive.
  - `foam_would_invert` re-implements the test; it agrees exactly
    (6 hexes on wye90 k = 4).  Its count is stored per level.
  - The whole study was rerun with the fix.
- **Duct taps beyond k = 2:** `laplacianFoam`'s deferred non-orthogonal
  correction stops contracting.  Details in RESULTS.md and Q2.  k = 3
  was tried as the third level and diverged too.  So did `limited
  corrected 0.5` (diagnostic `*_lim` levels).  A pseudo-transient
  (Euler, Δt 1e-3) at k = 2 gives the identical solution (L2 equal to
  12 digits) and barely damps the iteration.
- **`refined` and the wye:** `n_split` is 6 at k = 1, 2 and 4: the
  `WYE_N_SPLIT_MAX` cap holds it there.
- **Reducer:** `chord_tol` is relaxed to 0.05.  The exact field is
  defined everywhere, so the chords' distance from the profile doesn't
  enter the error.
- **Tests changed:** `tests/test_validation_meta.py`.
  - The coverage test now builds coverage from the straight-pipe cases,
    since MMS covers the junctions.
  - The planned-task test points at 0050.
  - The all-gates-pass test applies to `accepted` cases, so 0049 and
    0072 can report failing gates.
- **The design answers' checks (2026-11-07/08).**  Numbers and tables
  are in `validation/mms/RESULTS.md`, "The design answers' checks".
  - **Driver:**
    - `LAPLACIAN` became `SCHEME_EDITS`: `fvSchemes` edits per series.
    - New diagnostic series `<flagged>_loc`, `_lsq` and `_skew`, and
      `straight_lsq`.
    - Every level now also stores `max_edge_ratio`, `scheme_edits`, and
      the focus error split by block-interface cells
      (`focus_block_interface`, `focus_block_interior`,
      `max_at_block_interface`).
    - `_errors` returns None for an empty set: the miter's and reducer's
      cells all touch a slab interface, so their first run of the series
      failed at k = 1.
  - `study.openfoam.check_mesh` also returns `max_aspect_ratio`.
  - **Measured outside the driver** (scratch scripts; the numbers are in
    RESULTS.md):
    - the reducer's chord gaps per k;
    - the transition's blend (linear in u, so exact);
    - the wall-face non-orthogonality per k (straight, bend, reducer,
      transition, tee);
    - the duct taps' aspect at k = 1, 2, 3, with `checkMesh`.
  - **A false lead, noted so it isn't repeated:** a fixed-angle radial
    sag of the transition (via `BlendShape.extent`) falls only at first
    order.  That's an artefact: `extent` is a support function and isn't
    linear in u, while the mesh's nodes follow the linear node blend.
  - **Cost:** the 48 diagnostic levels (5 fittings × 3 series × 3
    levels, and `straight_lsq`) took about 56 min on 3 processes,
    beside the 0075 run (log times: 41, 14 and 1 min).
  - **Corrected:** RESULTS.md had "edge ratios of 12–13 throughout" for
    the duct taps.  That is the maximum; the median is 3.

## Questions for design

- **Q1. The flagged fittings** (order more than 0.3 below the straight's
  1.60; evidence in `validation/mms/RESULTS.md`).
  - The tees (L2 order 1.03), the transition (0.97) and the reducer
    (0.95) converge at about first order.
  - So does the miter: 1.84 between k = 1 and 2, then 1.14.
  - Their worst scaled Jacobian doesn't improve with k (tee 0.258,
    transition 0.577).  That is consistent with Gauss-linear gradients
    being first order on skewed faces.
  - Is first order acceptable for these fittings, or should a fitting's
    interior quality improve under `refined(k)`?
- **Q2. Duct taps can't be solved past k = 2 with `laplacianFoam`'s
  explicit non-orthogonal correction.**
  - Per corrector the iteration contracts by 0.92 at k = 2 and grows by
    1.04 at k = 3.
  - The meshes pass `checkMesh`: non-orthogonality 64°, worst scaled
    Jacobian 0.42, max aspect 26 at k = 3.
  - The tap's cells are thin throughout: edge ratio 12–13 at k = 1,
    7552 hexes against 128 in each neighbouring straight.
  - Wyes at 80° but lower aspect converge, so it isn't
    non-orthogonality alone.
  - Is the duct tap's cell aspect a mesh-quality defect to fix in the
    fitting?  Or is it a solver-settings matter for users (a coupled or
    implicit correction, a guideline), recorded for the CFD guidance?
- **Q3. `refined(k)` can't refine a wye's split region** (`n_split`
  capped at 6, task 0056).  So no convergence study of a wye measures
  the scheme there; the max error doesn't fall.  Should `refined` raise
  `n_split` once the folding is solved, or should convergence studies of
  wyes refine `nang` and the axial counts only, and say so?

**Design answers** (2026-11-07; the user: "reply the hexmesh coding agent
with your answers").
- **Q1: neither yet.  First tell geometry error from scheme error.**
  - A constant worst scaled Jacobian under `refined(k)` is expected: a
    refined mapping keeps its cell angles.  It doesn't explain the
    order by itself.
  - The reducer is the warning sign: a cone has the straight's O-H
    topology and a smooth mapping, so it should match the straight's
    1.60.  0.95 points to a geometry error that doesn't shrink, e.g. a
    profile chord tolerance (`chord_tol`) or station interpolation that
    `refined(k)` doesn't tighten.  The transition's blended stations
    may do the same.
  - The tees and the miter more likely show the scheme on kinked grid
    lines across block interfaces: a property of a conformal block
    mesh, not a bug.
  - **The checks** (no gate change):
    1. does `refined(k)` tighten the reducer's and the transition's
       geometric tolerances (chords, stations)?  Measure the wall's
       distance from the exact surface per k;
    2. OpenFOAM's skewness per k for each flagged fitting, and where
       the error sits (block interfaces or not);
    3. the flagged fittings once more with a skew-corrected gradient
       (e.g. `pointCellsLeastSquares`, or corrected interpolation): does
       the order recover?
  - **Then:** a geometry error is a fitting fix (a task from design).
    A scheme-on-kink error is accepted and documented: expect
    first-order local error in that fitting, in the CFD guidance and
    RESEARCH.
- **Q2: treat it as a mesh defect first.**
  - A tap 59× denser than its neighbours (7552 hexes against 128),
    with thin cells throughout, suggests wrong counts or layout in the
    fitting.
  - Measure **one** aspect metric (`checkMesh` aspect and the edge
    ratio, both) at k = 1, 2 and 3.  If it grows with k, it's a fitting
    defect: refinement must not stretch cells.  Also say what sets the
    tap's counts (which spec field or rule).
  - Meanwhile, a solver note for users (more non-orthogonal correctors,
    or an implicit correction) goes in `docs/integrations/openfoam.md`
    as a stopgap, with the numbers.
- **Q3: refine `nang` and the axial counts, and say so.**  A wye study
  doesn't refine the split region (`n_split` capped at 6, task 0056),
  so its error there isn't verified.  The report says that, per case.
  Raising `n_split` in `refined` waits for the folding fix.
- **Acceptance:** accept the case on what is verified (the fittings that
  converge at the straight's order; the wye outside its split region).
  The flagged fittings and the duct tap are reported, pending the checks.

## Outcome

**Done (2026-11-08): the case is accepted on what is verified** (design
answer, "Acceptance").  The straight, bend, spline, stack change and
rectangular duct converge at the straight's order, and the wyes outside
their split region.  The flagged fittings and the duct taps are reported
with the checks.
- **Q1:**
  - **check 1:** no geometry error that refinement leaves.  The reducer's
    chord gap falls at second order (0.028, 0.0075, 0.0019 R), and the
    transition's wall is exact (a ruled node blend);
  - **check 2:** skewness per k is flat (reducer, miter) or rises a
    little (transition, tees).  In the tee the error isn't concentrated
    at block interfaces;
  - **check 3:** least-squares gradients recover the **miter** (1.67
    against `straight_lsq`'s 1.83): the scheme on kinked grid lines, as
    design expected.  They don't recover the reducer (0.97), the
    transition (1.24) or the tees (1.32, 1.49).  `skewCorrected`
    interpolation changes nothing: OpenFOAM doesn't use it there.
  - **What the unrecovered four share:** a wall-face non-orthogonality
    that refinement doesn't shrink.  Medians: reducer 21–24°, transition
    12–14°, tee 9°; straight about 0°, bend 1.3°.  `fixedValue`'s
    boundary snGrad has no correction for it.
- **Q2:** the taps' aspect doesn't grow with k (edge ratio max 13.1 →
  12.3, median 3).  By design's rule, not a refinement defect.  What
  sets the counts is in RESULTS.md.  The stopgap note is in
  `docs/integrations/openfoam.md`.
- **Q3:** said per wye case in RESULTS.md.
- **Proposed follow-up for design:** which kind is the wall
  non-orthogonality?
  - If accepted as a scheme property ("expect first-order local error
    next to sloped walls in OpenFOAM's `fixedValue`"), it goes into the
    CFD guidance and RESEARCH.
  - If treated as a fitting matter, the fix would make the reducer's and
    transition's near-wall grid lines normal to the wall.
  - A measurement that would tell them apart: the reducer at a smaller
    constriction (wall slope), to see whether the order tracks the
    angle.

_The first study's outcome:_

- **Files:**
  - `validation/mms/` (`run.py`, `README.md`, `RESULTS.md`,
    `case.json`, `results.json`);
  - `hexmesh/study/openfoam.py` (`convert(keep_orientation=)`);
  - `tests/test_openfoam_runner.py` (+2);
  - `tests/test_validation_meta.py` (3 tests updated);
  - `validation/tools/recheck.py` (the 3 new cases);
  - `docs/integrations/openfoam.md`, API.md, CHANGELOG.
- **For RESEARCH:**

  | fitting | L2 order in the fitting (k 2→4) | note |
  |---|---|---|
  | straight (O-H) | 1.60 | as the heated rod (1.57) |
  | bend | 1.72 | |
  | spline | 1.90 | |
  | stack change | 1.81 | |
  | rect duct (H) | 1.99 | |
  | miter | 1.14 | flagged |
  | reducer (cosine) | 0.95 | flagged |
  | transition | 0.97 | flagged |
  | tee, with/without shells | 1.03 / 1.04 | flagged |
  | wye 60/90, with/without shell | 0.34–0.51 | flagged; `n_split` not refined (Q3) |
  | duct taps | 0.78 (k 1→2) | flagged; no k ≥ 3 (Q2) |

- **Surprises:** gmshToFoam's orientation test, and the duct taps'
  non-contracting correction.
- **Follow-ups:**
  - Make `keep_orientation` the default in validation drivers that check
    the Jacobian.
  - Re-run the other validation cases' conversions to check for silent
    inversions (`foam_would_invert` can count them from a mesh).
