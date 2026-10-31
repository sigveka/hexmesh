# 0074 — Verification (V1): manufactured solutions for conduction on every fitting's mesh

- **Status:** ready (on the v2406 runner, after 0035's Docker option exists)
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

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
