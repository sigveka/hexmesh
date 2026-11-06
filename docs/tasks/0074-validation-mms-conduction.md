# 0074 — Verification (V1): manufactured solutions for conduction on every fitting's mesh

- **Status:** blocked (questions Q1–Q3; results complete)
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

## Outcome

_Blocked on Q1–Q3; the harness and the results are complete._

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
