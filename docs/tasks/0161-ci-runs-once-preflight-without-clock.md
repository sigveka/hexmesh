# 0161 — CI runs once per commit; the preflight test without a wall-clock limit

- **Status:** ready (step 1 after the user confirms `main` is protected)
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

## Questions for design

## Outcome
