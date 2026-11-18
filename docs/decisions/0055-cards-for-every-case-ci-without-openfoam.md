# 0055 — A card for every validation case, one command to re-run it; CI without OpenFOAM

- **Status:** accepted (2026-11-18, by the user; the solver comparison
  stays proposed, see *Not decided*)
- **Date:** 2026-11-18
- **Tasks:** 0178, 0179

## Context

The user (2026-11-18): "I am wondering if the validations should have
cards similar to the volunteer to make them easy to run", then: "I do
not want the CI to be dependent on OpenFoam, that is a local check, but
a local CI may run the very cheapest case to verify the volunteer and
validation cards work.  I do want a very easy way to re-run validation
cases."

Today (checked 2026-11-18):
- There are 14 validation cases (`validation/*/case.json`).  Each has
  its own `run.py` with its own flags.  Re-running one means reading
  its README.
- Only the helical pipe has a card (`volunteer.json`, decision 0044).
  Tasks 0168, 0169 and 0176 add three more: the tee's points, the bend,
  and the try-out.
- Four cases still record OpenFOAM v1912 (poiseuille, heated_rod,
  layered_conduction, stenosis), and the others v2406.
- CI has one OpenFOAM job, `openfoam-docker` in
  `.github/workflows/tests.yml` (decision 0039, task 0092).  It runs
  `-m openfoam tests/test_openfoam_runner.py tests/test_msh_recipe.py`
  against `opencfd/openfoam-default:2406`, in about a minute.  Today's
  note on decision 0044 also put the try-out card into CI (task 0176
  step 7).
- The suite already keeps OpenFOAM tests out by default (pyproject's
  `addopts`, the `openfoam` marker).  The pre-commit hook
  (`tools/hooks/pre-commit`, task 0158) is the pattern for an opt-in
  local check.

## Options

### Cards
- **A. Keep cards for volunteer levels only.**  Re-running stays per
  case.
- **B. One card per case, every level on it, and one command to re-run
  (chosen).**  The volunteer card becomes the general case card: each
  level is marked as run here or as a volunteer level.  The volunteer
  tool and the re-run command read the same file.
- **C. A Makefile-style list of commands per case.**  It is easy to
  write, but it has no requirements, no reproduce check and no single
  format.

### CI and OpenFOAM
- **D. Keep the `openfoam-docker` job, and add the try-out to it.**
  CI then depends on Docker Hub, the image, and OpenFOAM's behaviour.
- **E. CI without OpenFOAM; a local check that runs it (chosen).**

## Decision

**B and E.**

1. **A case card for every validation case.**
   - The file is the case's `card.json`.  `volunteer.json` is renamed,
     or read as a card, whichever keeps the tags' files working (task
     0179 says which).
   - It lists every stored level, with:
     - its requirements, *measured* where the level was run here;
     - the OpenFOAM version and image the stored result was made with
       (so v1912 for the four older cases, until someone re-runs them);
     - `reproduce` tolerances;
     - whether it is offered to volunteers.
   - The gates stay in `case.json`, and the card quotes them, as now.
2. **One easy command to re-run:**
   - `python3 -m validation run <case>` re-runs the case's cheapest
     level by default; `--level` picks one, `--all` runs every level.
   - It ends with **reproduced** or **not reproduced**, compared with
     the stored values within the card's tolerances.
   - It runs in a temporary directory and never writes `results.json`.
     Storing a re-run stays a deliberate step (`check --merge`, or the
     driver's own flags).
   - It uses the same `prepare` / `run` / `collect` / `check` as the
     volunteer tool, so a re-run and a volunteer run go the same way.
   - `python3 -m validation list` shows every case and level with its
     cost.  The cheapest level of each case comes first.
   - It is repository tooling (decision 0054): it needs a checkout, and
     adds nothing to the `hexmesh` API.
3. **CI doesn't depend on OpenFOAM.**
   - The `openfoam-docker` job leaves `.github/workflows/tests.yml`.
     The runner and recipe tests it ran move to the local check.
   - Tests that need OpenFOAM stay marked `openfoam`, and CI keeps
     excluding them, as now.
   - The fast tests of the card format, the tool's logic (`check`,
     `--merge` refusals, schema) and the re-run command's comparison
     stay in CI, because they need no OpenFOAM.
   - This replaces the CI line in decision 0044's note of 2026-11-18:
     the try-out runs in the local check, not in CI.
4. **The local check:** one command, `python3 tools/local_check.py`,
   that:
   - runs the `openfoam`-marked runner and recipe tests;
   - runs the cheapest case end to end through `validation run`.  That
     is the try-out level (task 0176): Poiseuille on 2 processes, about
     2 minutes;
   - checks one card per case without solving: each `card.json` is
     valid, and its levels exist in the driver;
   - prints a pass/fail summary, and says "skipped: no OpenFOAM runner"
     instead of failing when none is configured.
   - **When to run it:** before a push that touches
     `hexmesh/study/`, the OpenFOAM writer or `validation/`.  The sessions
     do this as part of the push steps.  An opt-in `pre-push` hook in
     `tools/hooks/` runs it too, like the pre-commit hook.

## Not decided

**Testing the cases with other solvers** stays *proposed*, with no task.
The options the design session set out on 2026-11-18:
- the cheap exact-answer (V1) cases on the OpenFOAM Foundation build
  (the conversion path its users take);
- one V1 case in SU2 (a second export format end to end);
- the tee (0162) in a second RANS code, to separate the mesh's share of
  its miss from the model's.

The full matrix of every case in every code was not recommended.  Any
of these would be a local check under rule 3, never CI.

## Consequences

- **Task 0178:** the CI job removed, the local check, and its pre-push
  hook.  Task 0176's step 7 (try-out in CI) becomes "in the local check".
- **Task 0179:** the case card, `python3 -m validation run`/`list`, and
  cards for all 14 cases.  The existing card tasks (0168, 0169, 0176)
  use the general card format.
- **CONTRIBUTING.md** and the README's *Validate or volunteer*: the
  re-run command, and the local check.  **CLAUDE.md**'s push steps: run
  the local check when the change touches the paths above (the design
  session updates it when 0178 lands).
- **DESIGN.md:** no change.
- **Harder:** a broken OpenFOAM path is no longer caught by CI on every
  push, only by the local check before a push.  That risk is accepted
  (the user).  The Windows Docker path was never in CI anyway.
- **Future expansions:** 0030 (the simulation suite): the card is
  validation's, and `hexmesh.study` is unaffected.  0018, 0019, 0021,
  0035: not affected.

## Verified vs. assumed

- **Checked (2026-11-18):** the 14 cases and their recorded OpenFOAM
  versions; the CI job and what it runs; the `openfoam` marker excluded
  by default; the pre-commit hook's form; the helical card's fields.
- **Assumed:** that every driver can take the three hooks without being
  restructured.  helical_pipe has them, and Poiseuille gets them in 0176.
  Drivers with other runners (fenicsx_second_order runs FEniCSx in
  Docker, not OpenFOAM) need their runner on the card.  Task 0179 checks
  each one.

## Note (2026-11-18): the local check covers every fitting

The user, the same day: "maybe the cheapest case relevant for each
fitting can be a good idea".  Rule 4's case step widens from one case to
one cheap level per fitting:
- **Flow:** the try-out (Poiseuille on 2 processes, task 0176), as before.
  It covers the parallel path and the volunteer tooling.
- **Every fitting:** the MMS case's coarsest level (`<fitting>_k1`)
  already exists for each fitting, from 576 to 9 472 cells, solved with
  `laplacianFoam` (conduction, decision 0034's MMS).  The check runs the
  16 fitting levels and compares each with its stored values within the
  card's tolerance.  Those levels are: straight, bend, miter, spline,
  reducer, transition, tee, tee_shells, stack_change, wye60, wye90,
  wye60_shell, wye90_shell, duct, duct_tap_rect and duct_tap_round.  The
  scheme and slope variants (`_loc`, `_lsq`, `_skew`, `_s0…`, `_lim`)
  stay out.  They test the solver settings, not the mesh.
- One level per fitting can't show an order of convergence.  It checks
  that the fitting still meshes, converts and solves to the stored
  answer.  `--order` adds the `_k2` levels (up to about 45 000 cells),
  which give an order.
- **Budget:** the whole check should run in about 5 minutes on this
  machine (8 cores, Docker).  Task 0178 measures it.  If the 16 levels
  are well over that, it runs them in parallel, not fewer of them.
- A flow case on a fitting (square_bend for the bend, stenosis for the
  reducer) joins only if its cheapest level runs in under about a
  minute.  Task 0179's table of cheapest levels shows which.

## Note (2026-11-18): other solvers, settled in part by decision 0057

*Not decided* is settled for mesh exports: decision 0057 makes one
consumer per export format an *export check* (FEniCSx, code_saturne,
SU2 before 1.0), run locally under rule 3.  The OpenFOAM Foundation
build and a second RANS code inside a validation case (the tee in
code_saturne) stay proposed, for after 1.0.
