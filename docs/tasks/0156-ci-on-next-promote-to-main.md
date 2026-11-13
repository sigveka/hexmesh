# 0156 — CI on a `next` branch; `main` moves only to a green commit

- **Status:** in progress
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

## Outcome
