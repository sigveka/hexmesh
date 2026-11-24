# 0194 — Python 3.12 is the oldest supported

- **Status:** ready
- **Decision:** [0039](../decisions/0039-platform-support.md), amendment 2
  (2026-11-24)
- **Depends on:** none.  Do it after 8bf69d7 (the f-string fix) is on
  `main`.
- **Blocks:** none; before 1.0.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user (2026-11-24): "Remove 3.11".  CI on ce6de5f failed
on 3.11 for 3.12-only syntax, which local tests on 3.12 didn't catch.
Task 0113 did the same for 3.10.  Follow its steps.

**Do.**
1. **The floor:** `pyproject.toml` gets `requires-python = ">=3.12"`.
   `.github/workflows/tests.yml` gets the matrix `["3.12", "3.x"]`, with
   the comment updated.  The `3.12, gmsh 4.12.1` include stays.  Say
   whether it now duplicates `ubuntu-latest, Python 3.12`, and keep both
   unless design says otherwise.
2. **Code:** remove workarounds kept only for 3.11, if any, and list
   them.  `git grep` for `sys.version_info` and `3, 11`.
3. **Docs** saying 3.11 become 3.12:
   - README's badge and its *Requirements*;
   - GUIDE *Installation*;
   - `validation/README.md`;
   - `validation/volunteer.py`'s generated text, then regenerate
     `validation/VOLUNTEERS.md`;
   - `docs/integrations/platforms.md`;
   - RELEASING's required-checks list and its `gh api` block.
   Leave task and decision history, CHANGELOG entries of past releases,
   and numbers that merely contain "3.11", as they are.
4. **A syntax guard for the floor:** a check that every Python file in
   the repository parses as 3.12, run in the suite or the local check,
   so syntax newer than the floor fails before a push.
   - The simplest that works without a second interpreter:
     `ruff check --target-version py312 --select` on the syntax rules,
     if ruff is in `dev`; or another tool you can justify.
   - Show it fails on a planted 3.13-only construct.
5. **CHANGELOG** *Unreleased*: "**Breaking:** Python 3.12 is the oldest
   supported (3.11 users: hexmesh 0.8.x)".
6. **Tell the user** before the push that changes the CI matrix: if
   `main`'s protection lists the 3.11 checks, they must update it (decision
   0039 amendment 2, rule 6), or promotion waits.

**Accept.**
- CI green on the new matrix (7 jobs).
- No doc on `main` says 3.11 is supported.
- The guard catches a planted construct.
- The full suite passes.

**Out of scope.**  Changing existing volunteer tags.

## Agent notes

## Questions for design

## Outcome
