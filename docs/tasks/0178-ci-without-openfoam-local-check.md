# 0178 — CI without OpenFOAM; a local check that runs it

- **Status:** ready
- **Decision:** [0055](../decisions/0055-cards-for-every-case-ci-without-openfoam.md)
  rules 3 and 4
- **Depends on:** 0176 for the try-out level.  Until 0176 lands, the
  local check's case step runs Poiseuille's coarse level through its
  driver, and says so.
- **Blocks:** none.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user (2026-11-18): "I do not want the CI to be dependent
on OpenFoam, that is a local check, but a local CI may run the very
cheapest case to verify the volunteer and validation cards work."

**Do.**
1. **CI:** remove the `openfoam-docker` job from
   `.github/workflows/tests.yml`, and update its header comment.
   Decision 0052's "every job green" then counts 7 jobs.  Fix any text
   that says 8 (CLAUDE.md is the design session's; list the places under
   *Agent notes*).
2. **`tools/local_check.py`:**
   - **Runner:** `HEXMESH_OPENFOAM` if set, else
     `docker:opencfd/openfoam-default:2406` when `docker` works.  With no
     runner, each step that needs OpenFOAM prints "skipped: no OpenFOAM
     runner", and the exit status is 0 (pass `--require` to fail
     instead).
   - **Step a:** `pytest -m openfoam tests/test_openfoam_runner.py
     tests/test_msh_recipe.py`, the tests the CI job ran.
   - **Step b:** the cheapest case end to end.  It uses `python3 -m
     validation run poiseuille --level try_np2` once 0179 provides it.
     Until then, the volunteer tool's `prepare` → `run` → `collect` →
     `check` on the try-out level, in a temporary directory.
   - **Step b2, every fitting** (decision 0055's note of 2026-11-18):
     the MMS case's 16 `<fitting>_k1` levels listed there, each compared
     with its stored values.  Run them in parallel as the cores allow.
     `--order` adds the `_k2` levels.  Until 0179 gives MMS its card, call
     the MMS driver for those levels into a temporary directory, without
     touching `results.json`.  Record the time per level and in total
     under *Agent notes*; the budget for the whole check is about
     5 minutes here.
   - **Step c:** every case's card valid and its levels known to its
     driver, with no solving.  This is a no-op until 0179 lands; say so
     in its output.
   - **Output:** a summary line per step (pass, fail or skipped, with
     its time), and the total.  It must run on Linux, macOS and Windows
     (native, Docker Desktop or Rancher Desktop).  Programs are started
     in the `PATH`-safe way (task 0173).
3. **`tools/hooks/pre-push`** (opt-in, as `pre-commit`):
   - runs the local check only when the pushed range touches
     `hexmesh/study/`, `hexmesh/assembly/_output.py` (the OpenFOAM
     writer) or `validation/`;
   - `git push --no-verify` skips it;
   - its header says how to opt in, as `pre-commit`'s does.
4. **Docs:** CONTRIBUTING's testing section (what CI runs, what the
   local check runs and when), and README *Develop* (one line).
5. **Tests (in CI, no OpenFOAM):**
   - the local check's runner choice and its skip path, with `docker`
     faked absent;
   - the hook's path filter on a fake list of changed files.
6. Run the local check here once.  Record each step's time under *Agent
   notes*.  The user's Windows session runs it once natively, or says
   it's still to do.

**Accept.**
- CI has no OpenFOAM job and is green.
- `python3 tools/local_check.py` passes here: the try-out and all 16
  MMS fitting levels reproduce, in about 5 minutes (measured, stated).
  With no runner it reports "skipped".
- The hook runs it only for the listed paths.

**Out of scope.**  Running the validation cases' real levels in the
local check (only the cheapest).  A self-hosted CI runner.

## Agent notes

- **From task 0182** (2026-11-19, step 4 left here): the local check
  should also run every export check's coarsest level,
  `validation/exports/<consumer>/`.  Today that is FEniCSx:
  `python3 validation/exports/fenicsx/run.py --levels 1 --json
  <scratch>/results.json` (Docker, `dolfinx/dolfinx:v0.11.0` pinned by
  digest; about 4 min for the three cases), then `recheck` on that file's
  levels.  `validation/tools/cases.py` lists the checks
  (`names("export")`) and where each lives (`path(name)`).

## Questions for design

## Outcome
