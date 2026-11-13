# 0161 — CI runs once per commit; the preflight test without a wall-clock limit

- **Status:** in progress (step 1 waits for the user to confirm `main` is protected)
- **Decision:** [0052](../decisions/0052-ci-gates-main.md); the answers
  in task 0156's *Questions for design*.
- **Depends on:** 0156.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**
- Since 0156 every promotion runs the suite twice on the same commit
  (on `next`, then on `main`), about 40 runner-minutes each.
- `tests/test_study.py::TestGrid::test_preflight_is_fast_and_meshes_nothing`
  asserts `seconds < 2.0`.  It took 2.34 s on macOS, Python 3.11 (run
  43416947315, attempt 1), on a commit that changed no study code.  The
  clock was a proxy for "meshes nothing".

**Do.**
1. **After the user confirms branch protection on `main`** (with admins
   included; `docs/RELEASING.md`): `tests.yml` runs on pushes to `next`
   and on pull requests, not on pushes to `main`.  Its header comment
   says why.  Until then, leave the trigger.
2. **The preflight test:** assert directly that preflight meshes
   nothing: for example, that no 3-D mesh generation is called during
   it (a counter on the call, or gmsh's element count staying zero),
   whichever is reliable.  Drop the 2.0 s assertion; if a time bound
   still helps catch a regression, make it generous (10 s) and say why
   in a comment.
3. Search `tests/` for other fixed wall-clock assertions
   (`seconds <`, `elapsed <`, `time.perf_counter`) and list them under
   *Outcome*, with a proposal for each.  Change only the one above.

**Accept.**
- The preflight test fails when preflight is made to mesh (shown once,
  under *Agent notes*), and passes without a time limit below 10 s.
- Step 1 done after the user's confirmation, or left open with the
  status saying so.

## Agent notes

- **Step 2: what "meshes nothing" checks.**  The `grid` fixture wraps
  `run(study, "preflight")` in `pytest.MonkeyPatch.context()`, counting
  calls to `gmsh.initialize` and `gmsh.model.mesh.generate`, then lists
  the `.msh` files under the study's output.  The test (renamed
  `test_preflight_meshes_nothing`) asserts `{"initialize": 0,
  "generate": 0, "msh": []}`.  The file check also covers meshing in a
  worker process, which the counters wouldn't see.  No time limit: a
  slow preflight that meshes nothing isn't what the test is for.
- **Shown failing** (a scratch worktree; `stages.preflight` made to
  write each variant's mesh after `cell_count()`; deleted after):
  `{'initialize': 9} != {'initialize': 0}`, `{'generate': 18} !=
  {'generate': 0}`, and nine `.msh` files listed: `1 failed`.  On the
  real code: `5 passed` (TestGrid).

## Questions for design

## Outcome

Step 2 done 2026-11-13; step 1 waits for the user to confirm `main` is
protected (with admins included).

- **Files:** `tests/test_study.py` (the `grid` fixture records what
  preflight did to gmsh; `test_preflight_meshes_nothing` asserts it).
- **Other wall-clock assertions in `tests/`** (step 3; none changed):
  - `test_agent_manifest.py::test_the_manifest_does_no_expensive_work`,
    `took < 0.2` (4 ms typical, so a 50x margin).  Proposal: assert
    directly that the live probe isn't called (it was replaced in task
    0102), then drop the clock.
  - `test_agent_manifest.py::test_the_cli_emits_it_in_its_envelope_quickly`,
    `took - base < 1.0`: already measured against a baseline (starting
    Python and importing hexmesh).  Proposal: keep.
  - `test_agent_describe.py::test_preview_every_example`, `elapsed <
    2.0` for each of the 30+ examples: the likeliest next flake on a slow
    runner.  It already asserts `not gmsh.isInitialized()`, the direct
    check.  Proposal: drop the limit, or make it 10 s.

