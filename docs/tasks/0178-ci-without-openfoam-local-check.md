# 0178 — CI without OpenFOAM; a local check that runs it

- **Status:** done (2026-11-23)
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

- **Export checks to include (from 0183, 2026-11-20):** the SU2 check's
  k = 1 (`validation/exports/su2/run.py --levels 1`, a few minutes at most, needs
  the `hexmesh-su2:8.6.0` image built from its `Dockerfile`); code_saturne's
  k = 1 likewise once 0181 is done.

- **From task 0182** (2026-11-19, step 4 left here): the local check
  should also run every export check's coarsest level,
  `validation/exports/<consumer>/`.  Today that is FEniCSx:
  `python3 validation/exports/fenicsx/run.py --levels 1 --json
  <scratch>/results.json` (Docker, `dolfinx/dolfinx:v0.11.0` pinned by
  digest; about 4 min for the three cases), then `recheck` on that file's
  levels.  `validation/tools/cases.py` lists the checks
  (`names("export")`) and where each lives (`path(name)`).

**The coding session, 2026-11-23.**
- **Step 1:** the `openfoam-docker` job is gone from
  `.github/workflows/tests.yml`, and its header says where OpenFOAM runs.
  CI now has 7 jobs.  Text that said 8, or named the job:
  `docs/RELEASING.md`'s branch-protection list (now seven checks; `main`
  has no protection or ruleset today, checked with `gh api`, so nothing
  waits for the removed check).  CLAUDE.md says "every job" without a
  count: nothing to change.  Task files that record "all 8 jobs" are
  history and stay.
- **Step 2, `tools/local_check.py`:** steps a (the `openfoam` tests),
  b (the try-out through the volunteer tool), c (the 16 MMS `_k1`
  levels, `--order` adds `_k2`, in parallel, `--jobs`), d (every card's
  levels known to its driver; it runs today on the 3 cards there are),
  e (each export check's coarsest level when its Docker image is on the
  machine; `--no-exports`).  Each level runs its driver as a subprocess
  with `--json` into a temporary directory, so nothing reaches the
  cases' `results.json`; the levels are compared with the stored ones
  key by key, floats within 1e-6 relative.  Left out of the comparison:
  what a run records about itself (`environment`, `wall_s`, `solve_s`,
  `cores`, FEniCSx's `seconds` and `peak_rss_gb`) and
  `last_initial_residual` (round-off, 2e-15 to 1e-14, different every
  run).  A key only in the new values is allowed (a driver that records
  more: today's MMS adds `check_max_aspect_ratio`); one only in the
  stored values is a difference.  Programs are resolved on `PATH` first
  (task 0173).
- **Step 3, `tools/hooks/pre-push`:** lists the pushed files per ref
  (`git diff` against the remote's sha, or the commits not on any remote
  for a new branch; `?` when it can't), and the check's `--if-touched`
  runs only when one is under `hexmesh/study/`,
  `hexmesh/assembly/_output.py` or `validation/`.
- **Step 4:** CONTRIBUTING (what CI runs, the local check, when, the
  hook) and README *Develop* (one line).
- **Step 5:** `tests/test_local_check.py`, 16 tests: the runner choice,
  the skip path (Docker faked absent; `--require`), the filter, the
  hook end to end on a scratch repository (POSIX only), the comparison.
  One found a bug: `pick_runner`'s default bound the original
  `docker_answers`, so faking it had no effect.
- **Step 6, run here** (desktop, 8 cores, Docker, 2026-11-23): 201 s in
  all.  a 33 s (5 tests); b 18 s (accepted); c 32 s for the 16 levels,
  8 at a time (each 4-11 s; tee_shells the slowest); d under 1 s; e 119
  s (code_saturne 110, FEniCSx 119, SU2 77, at once).  Without e, about
  85 s.  The Windows run is still to do.
- **What it found:** stored levels the code no longer reproduces (see
  Questions for design).  Passing: a, b, d; the 12 other MMS fittings;
  code_saturne; FEniCSx's straight and bend.

## Questions for design

**Q1 (2026-11-23): stored levels that today's code doesn't reproduce.**
The local check's first run fails on these, and on nothing else:

| stored level | stored | differs | likely cause |
|---|---|---|---|
| MMS `tee_k1`, `tee_shells_k1` | 2026-11-06, 42357ca | L2 +2.4 %, +1.4 %; max non-orthogonality 62.26° vs 62.42° (24 keys) | tasks 0122 and 0145 changed the tee's interior (11-10 to 11-12) |
| MMS `duct_tap_rect_k1`, `duct_tap_round_k1` | 2026-11-06 | L2 -2.3e-6, -7.2e-6 (10 keys) | task 0135, the duct-tap stations de-duplicated (11-11) |
| FEniCSx `tee_k1_Hex8`, `tee_k1_Hex27` | 2026-11-10, f91e22b | L2 up to +1.1 %, H1 up to +0.5 %; same 2 160 cells | as the MMS tee |
| SU2 `k1` | 2026-11-19, 3680ced | `steps` 20 000 vs 2 000; dp agrees to 4e-10 | `ITER = 2000` since task 0183 |

The k = 2 and 4 levels of the same fittings (and the MMS variants
`tee_loc` and so on) were stored with them and are presumably stale too;
the check doesn't run them.  Options:
- **A.** Rerun the stale levels (the MMS tee, tee_shells and duct taps
  at k = 1, 2, 4 with their variants; FEniCSx's tee at k = 1, 2, 4;
  SU2's three levels), update the numbers quoted from them (RESEARCH,
  the cases' RESULTS), then rerun the check.  My estimate: under an
  hour of machine time; the text is the larger part.
- **B.** As A, but MMS and FEniCSx only; SU2's `steps` is a run setting,
  and the check could leave `steps` out for SU2.
- **C.** Keep the stored levels and let the check tolerate them (a list
  of known differences).  Not recommended: the check then can't tell
  these from a new break.
My recommendation: A, as its own task, after which 0178 is done.  The
check itself needs no change for it.

**The reruns (Q1's option A, 2026-11-23, at 367b7e6).**  Each into a
scratch JSON, compared with the stored level, then merged by name.
- **MMS, 33 levels** (tee and tee_shells with `_loc`, `_lsq`, `_skew`;
  the duct taps with `_lim`): the tee's errors moved 1-14 % (most in the
  boundary cells and the junction block), the cell counts not at all,
  and tee k = 4 takes 14 % fewer steps.  The duct taps at k = 1, 2 moved
  by 1e-5 to 5e-5; k = 3 and 4 still don't converge, as stored.  The
  orders that RESULTS quotes: tee's fitting L2 1.28, 1.03 → 1.31, 1.06;
  tee_shells' 1.29, 1.04 → 1.33, 1.07; under `pointCellsLeastSquares`
  tee 1.32 → 1.30 and tee_shells 1.49 → 1.51.  Time: about 1 h for 31
  levels, 4 at a time, then 3.5 h and 4 h for the duct taps' k = 4 (3
  MPI processes each, barely faster than 1: 200 steps of about 225 CG
  iterations).  My Q1 estimate of under an hour was wrong by that much.
- **FEniCSx tee, k = 1, 2, 4:** errors moved by up to 1.1 % (Hex8) and
  0.3 % (Hex27); the orders are unchanged to two decimals.  29 minutes,
  beside the OpenFOAM runs.
- **SU2, k = 1, 2, 3** at 2000 iterations: every value within 3e-7 of
  the 20 000-iteration levels; orders unchanged.  91 minutes on 2
  threads beside the OpenFOAM runs.
- **Text updated:** `validation/mms/RESULTS.md` (the orders table, the
  first-order range 0.93-1.33, Check 2's skewness and block-interface
  orders, Check 3's table, the tee's wall non-orthogonality),
  `validation/exports/fenicsx/RESULTS.md` (the tee's error table),
  `validation/exports/su2/RESULTS.md` (the runs paragraph); each header
  says what was rerun.  Figures and `hexmesh/agent/validation.json`
  regenerated.  `validation/exports/code_saturne/RESULTS.md`'s column of
  OpenFOAM's orders on the same meshes: tee and tee_shells updated.
  **For the design session:** `docs/RESEARCH.md` quotes the old tee
  orders at two places: the table of fittings below the straight's
  order ("1.03 / 1.04", least squares "1.32 / 1.49"; now 1.06 / 1.07
  and 1.30 / 1.51) and the code_saturne comparison (tee 1.03,
  tee_shells 1.04; now 1.06, 1.07).  No reading changes: the tees are
  still near first order, and least squares still doesn't recover them.

**Answer (the user, 2026-11-23):** "rerun the stale levels first, then
push".  Option A, in this task: the stale levels are rerun before 0178's
commits are pushed.

## Outcome

- **Files:** `.github/workflows/tests.yml` (no OpenFOAM job; 7 jobs),
  `tools/local_check.py`, `tools/hooks/pre-push`,
  `tests/test_local_check.py` (16 tests), CONTRIBUTING, README,
  `docs/RELEASING.md`, CHANGELOG; the rerun levels in
  `validation/mms/results.json`, `validation/exports/fenicsx/results.json`
  and `validation/exports/su2/results.json`, with their RESULTS and
  figures.
- **The local check passes here** after the reruns: 279 s (a 32, b 18,
  c 57, d 0, e 171 s); the first run's 201 s had e at 119 s.  Within
  the 5 minutes, but e is most of it; `--no-exports` gives about 110 s.
- **Tests:** the validation, agent, volunteer and local-check tests,
  402 passed.
- **Not done here:** the Windows run of the check (step 6; the user's
  session has the try-out to run first).
- **Follow-ups:**
  - the gallery pages are behind the cases (`docs/gallery/VALIDATION.md`
    counts 13 cases and 1 export check; there are 14 and 3);
    `docs/gallery/build.py` regenerates them;
  - `docs/gallery/build.py --validation <case>` prints the case's old
    path (`validation/fenicsx_second_order/README.md`) though it writes
    the right file;
  - a stored level can go stale silently whenever a fitting's mesh
    changes; the hook catches it only at push time.  Rerunning the
    affected cases' levels could be part of a mesh-changing task's
    acceptance (for design).
