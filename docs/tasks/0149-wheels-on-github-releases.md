# 0149 — A wheel and an sdist on every GitHub release

- **Status:** in progress
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

- **2026-11-15, the steps refined.**
  - **Trigger:** the release's publication (`release: published`, which
    includes pre-releases), not the tag's push.  `docs/RELEASING.md`
    step 6 pushes the tag and only then creates the release, so at the
    push there is no release to attach to.  A `workflow_dispatch` with
    a tag adds the files to an existing release, at that tag's commit.
  - **Steps 1 and 4 are one check,** `tools/check_dist.py`:
    - the tag's version, in the wheel's file name, its METADATA, and
      the sdist's name and top directory;
    - nothing in the wheel but `hexmesh/` and its `.dist-info`;
    - every non-Python file git tracks under `hexmesh/` is present (four
      today, `support.json` among them);
    - both commands (`hexmesh`, `hexmesh-study`) in the entry points.

    `tests/test_check_dist.py` runs it on hand-made archives (6 tests,
    no build).
  - **`hexmesh --version` didn't exist,** so I added it
    (`hexmesh/agent/cli.py`, `--version` prints `hexmesh X.Y.Z`), with a
    test in `tests/test_agent_manifest.py`.  The JSON envelope already
    had the version; this is a plain line for people and the job.
  - **Permissions:** `contents: write` only, at the workflow level.
  - **The README's example** in the install job is the README's own
    "Ten lines" block, extracted from the README at the tag (a sparse
    checkout of `README.md` only).  hexmesh comes from the wheel; the
    job asserts that `hexmesh.__file__` is under `site-packages`.
- **2026-11-15, checked locally** (Linux, Python 3.12, the wheel built
  at db9ff14 plus these changes):
  - `twine check --strict`: PASSED for both files.
  - `check_dist`: ready for v0.6.0; for a v0.7.0 tag it refuses, naming
    the version in four places.
  - The wheel has 135 files: `hexmesh/` and its `.dist-info` only, with
    the four data files.
  - In a clean venv the wheel (by path, not URL) prints `hexmesh 0.6.0`
    and runs the README example: 13 164 cells, as the README says, and a
    1.6 MB `.msh`.
  - `actionlint` 1.7.12 is clean on the workflow.
- **The README's URL line** is generic (`vX.Y.Z`, "releases after
  0.6.0"), since 0.6.0 has no files and can't get them: its tag lacks
  the workflow and the check.  `docs/RELEASING.md` step 2 now makes the
  next release name it.
- **Not yet done, for the accept criteria:** the live run (a test tag on
  a fork, or a pre-release here; the user chooses), and so the check on
  three platforms and decision 0042's assumption.

## Questions for design

## Outcome
