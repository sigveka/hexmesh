# Releasing hexmesh

The steps of a release, in order.  Written from the 0.5.0 release (task
0115) and the 0.6.0 one (task 0146).  A release is a task: record each
step's result under its *Outcome*.

A tag and a GitHub release are permanent and public.  **The user approves
each one before it runs**, with the exact commands in front of them.  The
same goes for every push.

## 1. CI green on the release commit

Every job of the `tests` workflow passes on the commit to be tagged:
Linux, macOS and Windows on the gmsh `pip` installs, and Linux on gmsh
4.12.1, the reference version.  The commit reaches `main` only that way
(decision 0052): push it to `next`, where CI runs, then promote it.

```sh
git push origin HEAD:next                # CI runs on next
gh run watch                             # pick the run; wait for it
python3 tools/promote.py <sha>           # main moves to <sha>, if green
```

`tools/promote.py` refuses, saying why, unless the newest `tests` run on
the commit is completed with every job green and the commit is a
fast-forward of `origin/main`; `--dry-run` checks only.  Then tag the
promoted commit (step 6).

### Branch protection on `main` (the maintainer; once)

Protection makes the rule GitHub's, not only a habit.  An admin sets it:
Settings → Branches → Add branch ruleset (or classic rule) for `main`:
- **Require status checks to pass**, with these eight checks (the job
  names in `.github/workflows/tests.yml`; source: GitHub Actions):
  `ubuntu-latest, Python 3.11`, `ubuntu-latest, Python 3.x`,
  `macos-latest, Python 3.11`, `macos-latest, Python 3.x`,
  `windows-latest, Python 3.11`, `windows-latest, Python 3.x`,
  `ubuntu-latest, Python 3.12, gmsh 4.12.1`,
  `OpenFOAM v2406 in Docker (Linux)`;
- **Do not allow bypassing the above settings** (include
  administrators): the maintainer and the agents push with admin rights;
- no force pushes, no deletion.

Or, with `gh` as an admin:

```sh
gh api -X PUT repos/sigveka/hexmesh/branches/main/protection --input - <<'JSON'
{"required_status_checks": {"strict": false, "checks": [
   {"context": "ubuntu-latest, Python 3.11", "app_id": 15368},
   {"context": "ubuntu-latest, Python 3.x", "app_id": 15368},
   {"context": "macos-latest, Python 3.11", "app_id": 15368},
   {"context": "macos-latest, Python 3.x", "app_id": 15368},
   {"context": "windows-latest, Python 3.11", "app_id": 15368},
   {"context": "windows-latest, Python 3.x", "app_id": 15368},
   {"context": "ubuntu-latest, Python 3.12, gmsh 4.12.1", "app_id": 15368},
   {"context": "OpenFOAM v2406 in Docker (Linux)", "app_id": 15368}]},
 "enforce_admins": true, "required_pull_request_reviews": null,
 "restrictions": null, "allow_force_pushes": false, "allow_deletions": false}
JSON
```

`app_id` 15368 is GitHub Actions.  A job renamed in `tests.yml` must be
renamed here too, or `main` waits for a check that never comes.  What
GitHub does with a direct push under this rule is recorded in
`docs/integrations/github.md`.

## 2. The version

One version, in five places.  `tests/test_readme.py`
(`test_the_version_agrees_everywhere`) fails until they agree:
- `pyproject.toml`: `version` (`hexmesh.__version__` reads it);
- `CITATION.cff`: `version` and `date-released`;
- `README.md`: the version badge and the install line
  (`pip install "hexmesh @ git+https://github.com/sigveka/hexmesh@vX.Y.Z"`);
- `CHANGELOG.md`: the newest release heading (next step).

## 3. The CHANGELOG

- *Unreleased* becomes `## X.Y.0 (YYYY-MM-DD)`, with a short summary on
  top: what the release is for, in five or six lines, then
  **Breaking:** if anything is.  A new, empty `## Unreleased` goes above
  it.
- **Mark every breaking entry** since the last release with
  **Breaking:**.  To find them, compare with the last tag: retired
  error codes (`hexmesh.errors.CODES`), removed public names (every
  module's `__all__`), parameters that moved or went (not ones added at
  the end with a default), and the saved description's `VERSION`
  (`hexmesh/assembly/intent.py`).  Check out the tag in a worktree
  (`git worktree add <dir> vX.Y.Z`), never with `git stash`.
- Changed meshes aren't breaking, but each entry that moves nodes says by
  how much.

## 4. The quick validation checks

Decision 0050: a release runs the validation, at least the cheap cases.
The cheap cases are those of the quick checks:

```sh
pgrep -af pytest          # another session's run: wait for it
free -h                   # the checks need a few GB
python3 -m pytest -m openfoam tests/test_validation.py
```

They need OpenFOAM: native, or `HEXMESH_OPENFOAM`
(`docs/integrations/openfoam.md`).  Record each check's pass or fail in
the release task.  A check that can't run is reported, not skipped
silently.

## 5. The gallery

If meshes changed since the last time the gallery was built (the
CHANGELOG says), regenerate the changed examples, one at a time so the
timings compare:

```sh
python3 docs/gallery/build.py --only <name> …
```

## 6. The tag and the GitHub release

After the release commit is promoted to `main` (step 1).  **The user
approves both commands first.**

```sh
git tag -a vX.Y.Z -m "hexmesh X.Y.Z" <commit>
git push origin vX.Y.Z
gh release create vX.Y.Z --title "hexmesh X.Y.Z" --notes-file <notes.md> --verify-tag
```

The notes are the CHANGELOG's `X.Y.0` section, with relative links
made absolute at the tag
(`https://github.com/sigveka/hexmesh/blob/vX.Y.Z/API.md`).  Check the
release with `gh release view vX.Y.Z`.

## 7. After the tag: the install line

In a fresh venv with no system packages, outside the checkout:

```sh
python3 -m venv <tmp>/venv
<tmp>/venv/bin/pip install "hexmesh @ git+https://github.com/sigveka/hexmesh@vX.Y.Z"
<tmp>/venv/bin/python -c "import hexmesh; print(hexmesh.__version__, hexmesh.__file__)"
<tmp>/venv/bin/hexmesh estimate <pcf_line.SAMPLE> --spec sizes.json --insulation
```

The version is X.Y.Z, imported from the venv, and the estimate is the
sample's cell count.  Record it, then delete the venv (about 330 MB).

Wheels on the release (task 0149) and PyPI are later steps.
