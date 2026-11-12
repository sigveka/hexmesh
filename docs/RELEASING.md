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
4.12.1, the reference version.

```sh
gh run list --branch main --limit 3
gh run view <run id>
```

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

After the release commit is pushed and CI is green on it.  **The user
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
