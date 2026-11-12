# 0158 — An opt-in pre-commit hook: the architecture tests

- **Status:** ready (after 0157)
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
