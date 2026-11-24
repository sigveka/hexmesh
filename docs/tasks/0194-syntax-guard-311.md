# 0194 — A syntax guard at the Python floor (3.11), run before a push

- **Status:** done (2026-11-24)
- **Decision:** [0039](../decisions/0039-platform-support.md) (3.11 is the
  floor; the user kept it, 2026-11-24)
- **Depends on:** none.
- **Blocks:** none.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  CI on ce6de5f failed on all three 3.11 jobs.  The cause was a
nested f-string that reused its quote character (PEP 701, 3.12 only).
The machine here runs 3.12, so local tests passed.  The user considered
dropping 3.11, then kept it ("keeping 3.11 is less work").  A guard
should catch 3.12-only syntax before a push.

**What's known** (the coding session, 2026-11-24):
- `ast.parse(..., feature_version=(3, 11))` rejects newer constructs
  (type-parameter defaults, `except A, B`, t-strings) but **accepts**
  PEP 701 f-strings.  It wouldn't have caught ce6de5f.
- So the guard needs either a tool that knows PEP 701 or a 3.11
  interpreter.

**Do.**
1. **Pick the guard**, in this order of preference, and record the
   choice and its evidence in *Agent notes*:
   - **(a) ruff** with `--target-version py311`, if its version-aware
     syntax errors flag a same-quote nested f-string.  Verify it on a
     planted file; don't assume.  Pin ruff in `dev`.
   - **(b) a 3.11 interpreter** in the local check:
     `python -m compileall -q` over `git ls-files '*.py'` in a pinned
     `python:3.11-slim` image by digest.  Docker is already required for
     OpenFOAM.  Or a local 3.11 if one exists.
   - Don't hand-tokenise f-strings.
2. **Where it runs:**
   - in `tools/local_check.py`, so the opt-in pre-push hook runs it;
   - and in the suite if it's fast and needs no Docker (option a).
   The floor is read from `requires-python`, so a future move needs no
   edit.
3. **Show it works:** it fails on a planted PEP 701 f-string, and on a
   planted 3.13 construct, and passes on today's tree.
4. **Record** the ruff (or ast) behaviour in
   `docs/integrations/platforms.md`, with versions and date.
5. CHANGELOG *Unreleased* (Development): one line.

**Accept.**
- The guard catches the ce6de5f construct before a push.
- It passes on `main`.
- Its result shows in the local check.

**Out of scope.**  Changing the floor; type checking.

## Agent notes

- **The guard: (a), ruff 0.17.6**, verified on planted files
  (2026-11-24): at `--target-version py311` it reports the PEP 701
  f-string ("Cannot reuse outer quote character in f-strings on Python
  3.11"), the `type` alias (3.12), a type-parameter default (3.13) and
  `except A, B` (3.14) as `invalid-syntax`, and passes at `py312` on the
  f-string.  ce6de5f's `docs/gallery/build.py` fails at 870:57; today's
  258 files pass in 0.5 s.  `ast.parse(feature_version=(3, 11))` accepts
  the f-string on 3.12.3 and 3.14.3 (recorded in `platforms.md`).
- **Only syntax:** `--isolated --select E902` (a file it can't read):
  ruff's defaults would add lint findings; `E999` is removed in 0.17 and
  can't be selected.  A test checks an unused import passes.
- **Where:** `tools/local_check.py` step s, first, no OpenFOAM; and in
  the suite (`tests/test_local_check.py`), skipped where ruff isn't
  installed.  CI installs `dev`, so it runs there on every job.
- **The hook:** ce6de5f changed `docs/gallery/build.py`, outside
  `WATCHED`, so the hook would have skipped the check.  A push that
  changes Python files outside `WATCHED` now runs step s alone.
- ruff is found as this Python's module, else on `PATH`.  This machine
  has neither yet (`pip install` here refuses: PEP 668, an
  externally-managed Python); I tested with a binary in my scratchpad on
  `PATH`.

## Questions for design

## Outcome

- **Files:** `tools/local_check.py` (`python_floor`, `ruff_argv`,
  `syntax_errors`, `step_syntax`; step s first; the hook's routing),
  `tools/hooks/pre-push` (comment), `pyproject.toml` (`ruff==0.17.6` in
  `dev`), `tests/test_local_check.py` (7 tests: the floor, four planted
  constructs, lint not checked, the tree passes, a Python-only push runs
  step s only), CONTRIBUTING, `docs/integrations/platforms.md`, CHANGELOG.
- **Tests:** `tests/test_local_check.py`, `test_readme.py`,
  `test_architecture.py`: 143 passed with ruff on `PATH`; without it, 6
  skipped.
- **Follow-up:** `test_no_runner_skips_the_openfoam_steps[True-1]`
  leaves an empty `/tmp/hexmesh-local-check-*` per run (the failed
  check keeps its logs).  Point the check's temporary directory at
  `tmp_path` in the tests.
