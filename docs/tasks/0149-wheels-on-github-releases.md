# 0149 — A wheel and an sdist on every GitHub release

- **Status:** ready
- **Decision:** [0042](../decisions/0042-road-to-1-0.md) exit criterion 6
  (distribution without PyPI), milestone 0.8.
- **Depends on:** 0146 (the release checklist it extends).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Releases install today only through git (`pip install
"hexmesh @ git+https://…@vX.Y.Z"`), which needs git on the user's
machine.  1.0 promises a built wheel and sdist attached to each GitHub
release, installable by URL, with no PyPI account.  Decision 0042 lists
as *assumed* "that wheels attached to GitHub releases install by URL on
all three platforms (to check in the wheel task)".

**Do.**
1. **A workflow on a pushed tag `v*`:**
   - build the sdist and a pure-Python wheel (`python -m build`);
   - check them (`twine check`, and the wheel's file list: no tests, no
     `docs/`, and `hexmesh/agent/support.json` and the other data files
     present);
   - attach both to the GitHub release.

   Only `contents: write`, nothing else.
2. **Install by URL, checked on Linux, macOS and Windows:** a job after
   the upload, in a clean venv, `pip install <release wheel URL>`, then
   `hexmesh --version`, and a small mesh (the README's example).
3. **The README's Install block and `docs/RELEASING.md`:** the URL line,
   above the git line.
4. **Version check:** the wheel's version is the tag's (fail otherwise).

**Accept.**
- A test tag on a fork, or a pre-release on this repository (the user
  chooses), produces both files on the release.
- The install-by-URL job passes on all three platforms.
- `decision 0042`'s assumption checked: record the result in the task;
  the design session moves it into 0042.

**Out of scope.**  PyPI; conda-forge (0042: a possible later route).

## Agent notes

## Questions for design

## Outcome
