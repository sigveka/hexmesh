# 0052 — CI gates `main`; platform rules as tests

- **Status:** accepted (2026-11-13, by the user: "yes I agree")
- **Date:** 2026-11-13
- **Tasks:** 0156, 0157, 0158, 0159

## Context

In one week, four red CI runs on `main` came from systems that this
machine isn't:
- gmsh 4.15.2 (what `pip` installs) meshed tees differently from 4.12.1
  (task 0145; CI red from about 3bdc2d0 until 73a2f07);
- Windows quoted a path with `shlex.quote`, so a test's `endswith`
  failed (61894b1);
- Windows' first `bash` is WSL's launcher, which can't open `C:\` paths
  (c1c7c9f; `docs/integrations/platforms.md`);
- the earlier ones in `platforms.md`: cp1252, `\` in paths, CRLF,
  NumPy 2.

Each passed here and was pushed to `main`, so CI found it after the
fact, and a release tag (task 0146) had to wait for a fix and a second
run.  Two sessions push to `main` from a shared tree, with the user's OK
each time.

The user asked whether pre-commit hooks would harden this.  **A hook
runs on this machine**, so it can't see what only another system does.
It can catch the *patterns* that fail there, and CI must test a commit
before `main` or a tag carries it.

## Options

### A. A `next` branch; `main` moves only to a green commit
- Sessions push to `origin/next` (`git push origin HEAD:next`), not to
  `main`.  CI runs on `next`.  When the run is green on every job,
  `main` fast-forwards to that commit (`git push origin <sha>:main`).
- The local tree stays on `main`: nobody switches branches in the shared
  tree.
- **Enforced** by GitHub branch protection on `main`, requiring the test
  jobs to pass: GitHub then refuses a push of a commit without green
  checks.  Free on a public repository; the user sets it (admin).
- Cost: one CI cycle (about 15 minutes) before `main` moves.
- **Approval:** the user's OK to push covers the push to `next` and,
  once its run is green, the promotion of that same commit to `main`.
  A commit that needed fixing is a new push, and needs a new OK.

### B. Pull requests with required checks
- Same gate, with a PR per change.  More ceremony for two sessions that
  commit many small changes; reviews would be by the same sessions that
  wrote the code.

### C. Hooks only
- Catches what can be caught locally; leaves the cross-system cases to
  CI after the fact, as now.

## Decision

**A**, with three supporting measures:
1. **Platform rules as tests** in `tests/test_architecture.py` (which
   already enforces `encoding=`): a test that runs a POSIX tool carries a
   `posix_only` marker, skipped on Windows by `conftest.py`; a test
   doesn't compare a path embedded in text.  Each rule cites the
   `platforms.md` entry it comes from.
2. **A light pre-commit hook**, opt-in per clone: the architecture tests
   only (seconds).  Not the suite: two sessions share this tree, and a
   slow hook stalls both.  CI runs the same tests, so a skipped hook
   loses nothing.
3. **A local check against both gmsh versions** (`nox`) for changes to
   junction or plate code, before pushing.

`docs/integrations/platforms.md` keeps the findings, as CLAUDE.md asks.

## Consequences

- **Workflow** (CLAUDE.md and `docs/tasks/README.md`'s ground rules, by
  the design session once 0156 lands): push to `next`; promote green
  commits to `main`; tag only a commit `main` carries.
  `docs/RELEASING.md`'s "CI green" step gains the commands.
- **The user:** sets branch protection on `main` (the steps in task
  0156).  Until then the rule is followed, not enforced.
- **Tasks:**
  - 0156: CI on `next`, the promote commands, RELEASING.md;
  - 0157: the platform rules and the `posix_only` marker;
  - 0158: the pre-commit hook;
  - 0159: `nox` sessions for gmsh 4.12.1 and the latest.
- **DESIGN.md:** no change; this is process, not design.
- **Future expansions:** none affected.  The simulation suite (0030) and
  the agent SDK (0019) gain from a `main` that is always green.

## Verified vs. assumed

- **Checked (2026-11-12):** the four failures and their commits (CI runs
  as reported by the coding session, and 43185960002); the repository is
  public (`gh api`); `tests.yml` runs on pushes to `main` and on pull
  requests only; no pre-commit config exists; the encoding rule exists.
- **Assumed:** that GitHub's required status checks refuse a direct push
  of a commit without green checks, and accept one with them.  Task 0156
  checks this before the workflow depends on it.  The 15-minute CI
  cycle is an estimate.
