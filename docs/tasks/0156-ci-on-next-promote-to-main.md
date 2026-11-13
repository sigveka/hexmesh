# 0156 — CI on a `next` branch; `main` moves only to a green commit

- **Status:** done
- **Decision:** [0052](../decisions/0052-ci-gates-main.md) (option A).
- **Depends on:** none.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Four red runs on `main` in a week came from systems this
machine isn't (decision 0052's context).  CI should test a commit before
`main` or a tag carries it.

**Do.**
1. **`.github/workflows/tests.yml`:** run on pushes to `next` as well as
   `main` (and pull requests, as now).  The docs workflow is unchanged.
2. **Check GitHub's behaviour before depending on it** (decision 0052's
   assumption), on a throwaway branch pair if needed:
   - a protected branch with required status checks refuses a direct
     push of a commit without green checks;
   - it accepts a fast-forward push of a commit whose checks are green
     on another branch (`next`).
   Record the answer, the evidence and the date in
   `docs/integrations/github.md` (new; the gmsh/OpenFOAM files are the
   model).  If either doesn't hold, stop: *Questions for design*.
3. **`tools/promote.sh <sha>`** (or a Python script, if Windows users
   need it; your call, recorded under *Agent notes*): checks with `gh`
   that every job of the newest `tests` run on `<sha>` passed, that
   `<sha>` is a descendant of `origin/main`, then
   `git push origin <sha>:main`.  It refuses otherwise and says why.
4. **`docs/RELEASING.md`:** "CI green on the release commit" gains the
   commands: push to `next`, `gh run watch`, `tools/promote.sh`, then tag
   the promoted commit.
5. **Branch protection, for the user** (admin; don't do it yourself):
   write the exact steps (Settings → Branches, or the `gh api` call) and
   which checks to require (the job names in `tests.yml`) in
   `docs/RELEASING.md`.  Ask the user under *Outcome*.

**Accept.**
- A push to `next` starts the test workflow (a run ID under *Outcome*).
- `tools/promote.sh` refuses a commit with a failed or missing run, and
  promotes a green one (both shown under *Outcome*).
- `docs/integrations/github.md` records step 2's answer.

**Out of scope.**  CLAUDE.md and the tasks README's ground rules: the
design session updates them when this task is done.  Pull-request
workflows (decision 0052, option B).

## Agent notes

- **Step 3 is `tools/promote.py`, not a shell script:** it runs the same
  on Windows, and its checks are unit-tested with a fake `git` and `gh`
  (`tests/test_promote.py`, 10 tests, no network).  `--dry-run` checks
  without pushing.  It reads the newest `tests` run on the commit (any
  branch: checks belong to the commit), requires every job `success`,
  fetches `origin/main` and requires a fast-forward, then `git push
  origin <sha>:refs/heads/main`.  It never forces.
- **Step 2 needed a live test:** GitHub's page *About protected
  branches* doesn't say what a direct push meets, and says both that
  admins can be included and that they "are always able to push".  With
  the user's OK, a throwaway branch `gate-test`, protected one way at a
  time; all deleted after.  Both assumptions hold, if admins are
  included: an untested commit is refused (ruleset GH013, classic GH006),
  and a commit green on `main` is accepted as a fast-forward.  Without
  "include administrators", the owner's push bypasses classic
  protection.  `docs/integrations/github.md` has the table.
- **A surprise on the way:** the first untested commit, an empty one,
  was accepted by both mechanisms.  It had no check runs, but the same
  tree as a green commit; a commit that changed a file was refused.  The
  rule-suite log (`rulesets/rule-suites`) showed the rule evaluated as
  `pass`, which is how it was caught.  Recorded, cause assumed (tree
  matching).
- **Step 5:** RELEASING.md gives both ways (Settings, or a classic `gh
  api` call with `enforce_admins: true`), the eight job names, and the
  Actions app id 15368 (checked: `api.github.com/apps/github-actions`).

## Questions for design

- **Should `tests.yml` still run on pushes to `main`?**  Every promotion
  now runs the suite twice on the same commit (on `next`, then on
  `main`, about 40 min of runners each).  Dropping `main` from `push:`
  saves that; keeping it shows a green check on `main` itself, and covers
  a direct push while `main` isn't protected.  Not changed here.
- **The flaky timing test** (below): a fixed 2.0 s limit on a shared
  runner.

**Answers (the design session, 2026-11-13):**
1. **Not on `main`, once `main` is protected.**  A promoted commit has
   already passed on `next`, and checks belong to the commit
   (`docs/integrations/github.md`), so a second run tests nothing new.
   Until the user sets protection, a direct push to `main` is still
   possible, so the trigger stays.  Task 0161 removes it after the user
   confirms protection is on.
2. **The test checks "meshes nothing" directly, not by the clock.**  The
   timing was a proxy.  Task 0161.

## Outcome

Done 2026-11-13.

- **Files:** `.github/workflows/tests.yml` (push to `main` and `next`);
  `tools/promote.py` (new); `tests/test_promote.py` (new, 10 tests);
  `docs/RELEASING.md` (step 1: next, watch, promote; branch protection
  for the maintainer); `docs/integrations/github.md` (new) and its row in
  `docs/integrations/README.md`.
- **A push to `next` starts the tests:** 278ff98 pushed to `next`
  (creating it) at the user's OK: run 43416947315.
  - Attempt 1 failed in one job, macOS Python 3.11:
    `test_study.py::TestGrid::test_preflight_is_fast_and_meshes_nothing`,
    `assert 2.3421628339999643 < 2.0`, a wall-clock limit; 278ff98
    changes no study code.  Only that job was rerun.
  - Attempt 2: all 8 jobs green.
- **`tools/promote.py` refuses, and promotes:**
  - refused 278ff98 while its run was in progress (`run 43416947315 on
    278ff98 is in_progress: gh run watch 43416947315, then promote
    again`, exit 1);
  - refused, as dry runs on real history: c1c7c9f (`run 43185960002 …
    isn't green (failure): windows-latest, Python 3.11: failure;
    windows-latest, Python 3.x: failure`), 33fb4c4 (`no tests.yml run on
    33fb4c4: push it to next first`), eca7352 (`doesn't descend from
    origin/main`);
  - promoted 278ff98: `278ff98: run 43416947315 (next, push) green, 8
    jobs` / `origin/main 60767b9 -> 278ff98: a fast-forward` / `pushed:
    main is 278ff98`.
- **Step 2's answer** (`docs/integrations/github.md`): both a ruleset
  and classic protection refuse a direct push of an untested commit, if
  admins are included (GH013, GH006); a commit green on another branch
  is accepted as a fast-forward; without "include administrators" the
  owner's push bypasses classic protection.  An empty commit with a
  green commit's tree passed both (cause assumed: tree matching).
- **For the user (step 5):** protecting `main` is yours: Settings →
  Branches (ruleset or classic rule), the eight checks, **"Do not allow
  bypassing"**, no force pushes; or the `gh api` call in RELEASING.md.
  Until it is set, `main` is gated by habit only.
- **Follow-ups proposed:** the two questions above.

