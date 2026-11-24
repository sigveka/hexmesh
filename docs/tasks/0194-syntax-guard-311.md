# 0194 — A syntax guard at the Python floor (3.11), run before a push

- **Status:** ready
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

## Questions for design

## Outcome
