# 0156 — CI on a `next` branch; `main` moves only to a green commit

- **Status:** ready
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
