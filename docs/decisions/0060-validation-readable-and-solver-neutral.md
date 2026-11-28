# 0060 — Validation that people can read and other solvers can run: a case sheet, standard plots, a staged pipeline, and bundles

- **Status:** accepted (2026-11-28, the user)
- **Date:** 2026-11-28
- **Tasks:** 0198, 0199, 0200 (before 1.0); 0201 (after 1.0)

## Context

The user (2026-11-28): "I want these validations to be easy to
understand for humans (both the code, setup and results) and to run for
other exporters.  What should be done to achieve this?  Should we for
instance have some additional visualisation of the results?"  Then, on
the design session's four points: "I agree with this, for point four
should it be a multi-stage sequence for instance: mesh, preprocess
(setup case), run case, postprocess, visualize".

**Today** (the design session, 2026-11-28):
- **The code:**
  - each case is one `run.py` of 300–1 450 lines (the tee 1 448, the
    bend 1 373 with 62 functions);
  - each mixes the mesh, the OpenFOAM dictionaries, the reading of
    results and the convergence logic;
  - shared logic is copied, not shared.  The NumPy-2 number bug reached
    8 drivers (task 0196), and the cache that kept a broken controlDict
    was a per-driver `_json` stamp with no inputs in it.
- **The setup** is written as dense table cells in each README.  The
  boundary conditions exist only as OpenFOAM text inside Python, so a
  user of another solver can't reuse them.
- **The results:**
  - one `figure.png` per case, plus tables of GCI, y⁺ and "oscillatory";
  - convergence is a number, not a picture;
  - the tee's cycling (task 0186) was found by reading logs.
- **What exists to build on:** the export checks (decision 0057); the
  cards and hooks (`prepare`, `run`, `collect`; decisions 0044, 0055);
  `results.json` with its schema; the gallery's Validation page; the
  docs site (decision 0049).

## Options

- **A. Docs only:** rewrite the READMEs and add plots, and leave the code.
  This fixes reading, but not running in another solver.
- **B. Docs, plots, and a solver-neutral split (chosen):** a case sheet,
  standard plots, a staged pipeline with files between the stages, and a
  bundle per case for other solvers.
- **C. B, every case converted before 1.0.**  That rewrites all 17
  drivers before 1.0, including the two (bend, tee) with runs in flight.

## Decision

**B.**  Its parts:

1. **A case sheet for each case.**  It's generated, and it replaces the
   README's opening.  Every case has the same layout:
   - the question in one sentence;
   - a dimensioned sketch of the geometry, and the mesh with its named
     boundaries coloured;
   - the boundary conditions in physical words ("inlet: fully developed
     turbulent flow, U_b 0.40 m/s");
   - the reference and the gates;
   - the verdict, then the plots (point 2).
   The details for experts follow below: the method, the numbers, the
   history.
   **A glossary page** explains gates, V1–V4, GCI, observed order,
   y⁺, the time mean and "oscillatory" in plain words, and every sheet
   links to it.
2. **Standard plots**, from `results.json` and the stage outputs, the
   same style in every case:
   - **result against reference,** with the gate band shaded;
   - **convergence:** each gated quantity against cell size, with the
     extrapolated value and its GCI band, and "oscillatory" shown as
     such;
   - **time history** for transient levels, with the averaging window
     and the stop marked;
   - **a flow picture** for the fitting cases (velocity on a mid-plane,
     or the secondary flow at a station).  It's rendered from fields
     written when the level runs, before the run directory is deleted.
     The picture is kept, not the run.  No case reruns only to make one;
   - **a scorecard** on the docs site: every case, its verdict, and its
     margin to each gate.
3. **A staged pipeline.**  Every case runs as six stages, each reading
   the previous stage's files from disk:

   | Stage | Does | Writes | Solver-specific |
   |---|---|---|---|
   | `mesh` | hexmesh only: the assembly, `refined(k)` or the family's rule | the mesh in every checked format; `mesh.json` (cells, groups, quality) | no |
   | `setup` | the solver adapter turns `problem.json` and the mesh into a case | the solver's case directory | yes |
   | `run` | runs it: resumable, chunked, with the stop rule | the solver's raw output | yes |
   | `extract` | raw output into the standard samples; fields for the flow picture | `samples.csv` (the layout `problem.json` names); a slice as VTK | yes |
   | `evaluate` | samples into quantities, convergence and gates | `results.json` (the level) | no |
   | `plot` | figures and the case sheet | PNG/SVG, the sheet | no |

   - **The line that matters is between `extract` and `evaluate`.**
     Everything after it is solver-neutral.  A user of another solver
     supplies `samples.csv` and gets the same verdict.
   - **`problem.json`** is the case's problem in physical terms:
     - fluid and solid properties;
     - the boundary condition per named group;
     - the initial state;
     - steady or transient, and the time-averaging rules;
     - where and what to sample (points, lines, planes, slabs);
     - how each quantity is computed from the samples.
     The gates stay in `case.json`.
   - **Stamps:** each stage's output records the hash of its inputs (the
     previous stage's files, the code version, the arguments).  A stage
     reruns when they change, and is skipped when they don't.  This
     replaces the per-driver caches.
   - **One command:** `python3 -m validation run <case> [--level L]
     [--stage S | --from S --to S]`.  The cards' hooks keep working as
     wrappers: `prepare` is mesh and setup; `run` is run; `collect` is
     extract and evaluate.  The volunteer tags stay valid.
   - **Shared code** in `validation/tools`, not copied: the precursor;
     chunked and resumable runs; history readers; number formatting
     (`of.num`); the convergence and time-mean statistics.
   - **A driver's shape:** `mesh.py` (short enough to read as an example
     of hexmesh), `problem.json`, `openfoam.py` (the adapter's
     case-specific part), `quantities.py`.  Long drivers shrink, because
     the shared parts leave.
4. **A bundle for other solvers**, built from the stages:
   - the mesh in each checked format, with the group names;
   - `problem.json`;
   - the reference as CSV;
   - the samples layout with an example `samples.csv`;
   - a short README per solver family (what each boundary condition
     means in common codes, as a table).
   `python3 -m validation compare <case> samples.csv` gives the verdict
   against the same gates.  Downloadable per case from the docs site.

**Before 1.0** (the user's quality aim for 1.0, decision 0042 note when
the open items of 0059 are settled):
- points 1 and 2 for every case, with flow pictures where a level's run
  provides the fields;
- point 3's framework, proved end to end on Poiseuille;
- point 4 for three cases: Poiseuille, the bend and the tee.

**After 1.0:** the other cases converted to stages, and their bundles.

## Consequences

- **Tasks:**
  - **0198:** the stage framework, `problem.json`, `samples.csv` and the
    stamps, proved on Poiseuille.  The command absorbs 0179's `validation
    run`;
  - **0199:** the case sheet, glossary, standard plots and scorecard for
    every case, from stored results;
  - **0200:** bundles and `compare` for Poiseuille, the bend and the tee,
    after 0198, and after 0186/0187 for the tee;
  - **0201** (after 1.0): the remaining drivers converted.
- **Task 0179** narrows: its cards stay, and its `validation run`
  command becomes 0198's.  A note goes on 0179.
- **In-flight runs:** the tee (0186, 0187) and the stenosis cards (0197)
  finish on today's drivers.  Their conversion follows.
- **DESIGN.md:** no change; validation isn't the library.  The public
  API: none.
- **Harder:**
  - two layouts live side by side until 0201;
  - `problem.json` must say enough for a solver that isn't OpenFOAM,
    which the export checks (code_saturne, SU2, FEniCSx) test;
  - VTK slices add a writer per adapter.
- **Future expansions:**
  - **0030** (the study suite): its layers are generators, solver
    adapters, a study engine and datasets.  This decision's stages and
    `problem.json` are its adapter layer at small scale.  Keep the
    formats versioned (`format` fields), as 0030's contracts ask;
  - **0019** (the agent SDK): one command with stages and JSON outputs
    suits tool calls;
  - 0018, 0021, 0035: not affected.

## Verified vs. assumed

- **Verified (2026-11-28):**
  - the driver sizes and the bend's function count;
  - the two copied bugs (0196);
  - the existing hooks and their callers (`validation/volunteer.py`);
  - the gallery's Validation page.
- **Assumed:**
  - that every case's quantities can be computed from a samples file of
    modest size.  K from slab means and the LDA lines can; wall shear
    stress needs wall-face samples, which `problem.json` must be able to
    name.  0198 checks it on Poiseuille, and 0200 on the bend and tee;
  - that a solver-neutral boundary-condition vocabulary covers the
    pilot cases without OpenFOAM terms.  0200 tests it against
    code_saturne's and SU2's setups, which exist.
