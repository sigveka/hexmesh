# 0158 — An opt-in pre-commit hook: the architecture tests

- **Status:** blocked (the hook's time: *Questions for design*)
- **Decision:** [0052](../decisions/0052-ci-gates-main.md) (measure 2).
- **Depends on:** 0157 (its rules are what the hook runs).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The architecture tests take seconds and catch the platform
patterns (0157) before a commit, rather than after a CI run.

**Do.**
1. **`tools/hooks/pre-commit`**: runs
   `python3 -m pytest -q -n 0 -p no:cacheprovider tests/test_architecture.py`
   and blocks the commit on a failure.  Nothing else: no meshing, no
   suite.  Measure its time on this machine and record it.
2. **Opt-in per clone:** `git config core.hooksPath tools/hooks`,
   documented in CONTRIBUTING.  No `pre-commit` framework dependency
   unless it is simpler (your call, recorded).
3. **Both sessions share this tree:** a hook set here applies to both.
   Set it only after the user's OK (ask under *Outcome*), and say there
   that it does.

**Accept.**
- The hook blocks a commit that breaks an architecture rule, and lets
  others through.
- Its time on this machine is under *Outcome*, and is a few seconds.

**Out of scope.**  Formatters and linters (none is used today).

## Agent notes

- **A plain `sh` script,** `tools/hooks/pre-commit`, mode 100755 in git:
  no `pre-commit` framework (a dependency for one command).  Git for
  Windows runs hooks in its own bash, so it works there too.  `PYTHON=`
  picks another interpreter; it `cd`s to the top level first.
- **It tests the working tree, not the index:** said in the script and
  in CONTRIBUTING.  Testing only the staged files would need a
  checkout of the index (slower, and the rules read whole trees).
- **The first measurement was 27 s** (three runs: 27.5–28.2 s).  Two
  changes to `tests/test_architecture.py`, results unchanged (100
  passed):
  - `shape_sites` and `encoding_violations` computed the file's relative
    path for every AST node (175 000 `relative_to` calls; 9.4 s for
    `test_shape_sites_cap` alone): now once per file;
  - a parse cache, `_parse(path)`, keyed on path, mtime and size, so
    the rules share each file's AST (the planted trees still parse
    fresh).
- **Now about 16 s** (15.6–17.6 s, three runs each, before and after
  the demo): 12.5 s in pytest, the rest startup (`conftest.py` imports
  gmsh).  5.7 s of the 12.5 are three tests that start a fresh Python to
  check what importing hexmesh loads
  (`test_planted_top_level_gmsh_import`,
  `test_without_gmsh_only_build_fails_and_the_manifest_says_so`,
  `test_the_light_commands_load_neither_gmsh_nor_scipy`).  `-n 4`
  gives 10.3 s, against the task's `-n 0` and the other session's CPU.

## Questions for design

- **The hook takes about 16 s, not "a few seconds".**  Options:
  (a) accept 16 s (CONTRIBUTING says "about 15 s");
  (b) leave the three subprocess tests out of the hook (a marker, e.g.
  `-m "not subprocess"`), about 10 s, CI still runs them;
  (c) `-n 4`, about 10 s, but a commit then takes four cores from the
  other session.
  The hook is written for (a); nothing else waits on the answer.

## Outcome

Code done 2026-11-13 (4109048); blocked on the time question.

- **Files:** `tools/hooks/pre-commit` (new, executable);
  `CONTRIBUTING.md` (opt in, skip, opt out); `tests/test_architecture.py`
  (the two speedups).
- **It blocks, and lets through** (a scratch worktree at 4109048, the
  hook enabled with `git -c core.hooksPath=tools/hooks` for those
  commands only; the worktree deleted):
  - a planted `tests/test_planted_hook.py` running `bash` unmarked:
    `FAILED tests/test_architecture.py::test_posix_tools_are_marked`,
    `pre-commit: tests/test_architecture.py failed; fix it, or commit
    with --no-verify`; no commit made (16.5 s);
  - a one-line docs change: `100 passed`, committed (16.2 s).
- **Time on this machine:** about 16 s (above).
- **For the user (step 3): enable it in this shared tree?**
  `git config core.hooksPath tools/hooks` here applies to both sessions'
  commits, adding about 16 s to each.  Not set.

