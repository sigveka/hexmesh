# GitHub

**Role:** hosts the repository, runs CI (GitHub Actions,
`.github/workflows/`), and, with branch protection, keeps `main` to
commits CI has passed (decision 0052).

**Versions:** github.com as of 2026-11-13; `gh` CLI on the maintainer's
machine.  The repository is public, on a personal account
(`sigveka/hexmesh`).

**Features used:** Actions workflows on push (`main`, `next`) and pull
requests; required status checks, by classic branch protection or a
ruleset; `gh run list --commit`, `gh run view --json jobs`
(`tools/promote.py`).

## Known quirks

Found by task 0156's live test, 2026-11-13: a throwaway branch
`gate-test`, protected one way at a time, with one required check
(`ubuntu-latest, Python 3.11`, from GitHub Actions, app/integration id
15368), pushed to over SSH by the repository owner (an admin).  The
branch, its protection and the ruleset were deleted afterwards; `main`
was not touched.

| push to the protected branch | protection | result |
|---|---|---|
| a commit with a new tree, no checks run on it (8d666e8) | ruleset, no bypass actors | **refused**, GH013 |
| the same | classic, "include administrators" (`enforce_admins`) | **refused**, GH006 |
| the same | classic, admins not included | **accepted** (admin bypass) |
| a commit green on `main` (07b12bd), a fast-forward | ruleset | **accepted** |
| an empty commit (896edcf) on top of 07b12bd: no checks of its own, the same tree as 07b12bd | ruleset; classic with admins included | **accepted** both |

### A required check refuses a direct push of an untested commit — *verified*
Both mechanisms refuse it, if admins are included.  The ruleset's
message:
`GH013: Repository rule violations found for refs/heads/gate-test.
- Required status check "ubuntu-latest, Python 3.11" is expected.`
Classic protection gives `GH006: Protected branch update failed`, and the
same line.  The ruleset's rule-suite log
(`gh api repos/sigveka/hexmesh/rulesets/rule-suites?ref=…`) records each
push's evaluation, rule by rule.

### A commit green on another branch is accepted — *verified*
07b12bd's checks ran on `main`; pushing it to the protected branch as a
fast-forward was accepted.  Checks belong to the commit, not the branch:
the decision's "push to `next`, then promote" works.

### An admin bypasses classic protection unless admins are included — *verified*
With `enforce_admins` off, the untested push went through (the remote
still printed the "is expected" line).  The maintainer and the agents
push with admin rights, so `main`'s rule needs "Do not allow bypassing
the above settings" (classic) or an empty bypass list (ruleset).  The
docs page *About protected branches* says both that admins can be
included and that admins "are always able to push"; the test settles it.

### A commit with the same tree as a green one passes — *verified; the cause assumed*
896edcf (empty, so 07b12bd's tree) had no check runs
(`commits/896edcf…/check-runs`: 0), yet both mechanisms accepted it;
the ruleset's log says `required_status_checks: pass`.  We infer that
GitHub matches required checks by tree, so a commit that changes no
file inherits its tree's results.  Harmless for the gate (the files are
what was tested), but a test that wants a refusal needs a commit that
changes a file.

### A new rule is in force within 30 s — *verified*
A ruleset refused 30 s after it was created (and after it was
re-enabled), and classic protection 30 s after it was set.  Shorter
waits weren't tested: the first accepted pushes, right after protecting
and 60 s after, were the same-tree commit, so they say nothing about
delay.

## Open questions

- **Rulesets vs classic protection for `main`:** both refuse an untested
  push when admins are included.  Which one the maintainer sets is their
  choice (`docs/RELEASING.md` gives both); task 0156 asks.
- **Tree matching:** the cause of the same-tree pass is assumed, not
  documented; nothing here depends on it.
