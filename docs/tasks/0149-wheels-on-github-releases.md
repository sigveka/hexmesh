# 0149 — A wheel and an sdist on every GitHub release

- **Status:** done
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
- **The live run (2026-11-15), on a fork** (the user chose it):
  - `Essens-lang/hexmesh`, forked from `sigveka/hexmesh`; tag `v0.6.0`
    at 0912cdd; a published release.
  - **One step needed a person:** a new fork runs no workflows until
    someone clicks "I understand my workflows" on its Actions page.  The
    API reported Actions enabled before the click, but no workflow was
    registered and publishing the release started nothing.  After the
    click, deleting the release and publishing it again started the
    run.
  - **The run, 43764695204: all four jobs green.**
    - Build: `twine check --strict` PASSED for both files;
      `check_dist`: ready for v0.6.0.  Attached to the release:
      `hexmesh-0.6.0-py3-none-any.whl` (484 100 bytes) and
      `hexmesh-0.6.0.tar.gz` (657 095 bytes).
    - Install by URL on `ubuntu-latest`, `macos-latest` and
      `windows-latest`:
      - pip installed hexmesh 0.6.0, with gmsh 4.15.2, numpy 2.5.5 and
        scipy 1.18.1;
      - `hexmesh --version` printed `hexmesh 0.6.0`;
      - hexmesh was imported from the venv's `site-packages`;
      - the README example printed 13164 cells.
    - The setup-python "3.x" was 3.15 on Linux and 3.14 on macOS.
  - The fork's test release and its tag were deleted afterwards; the
    fork itself is left to the user.

## Questions for design

_None._

## Outcome

- **Files:**
  - `.github/workflows/release.yml` (new);
  - `tools/check_dist.py` (new);
  - `tests/test_check_dist.py` (6 tests);
  - `hexmesh/agent/cli.py` (`--version`), with 1 test in
    `tests/test_agent_manifest.py`;
  - `README.md` (the wheel's URL line), `docs/RELEASING.md` (steps 2, 6
    and 7), `CHANGELOG.md`.
- **Accept:**
  - A test tag on a fork produced both files on the release.
  - The install-by-URL job passed on Linux, macOS and Windows.
  - **Decision 0042's assumption is checked: true.**  A wheel attached
    to a GitHub release installs by URL with `pip install <URL>` on all
    three platforms, with no git and no PyPI.  For the design session to
    move into 0042.
- **Surprises:**
  - A new fork's workflows need the click in the UI (above), whatever
    the API says.
  - The workflow runs on the release's publication, not on the tag's
    push (Agent notes).
- **Follow-ups (proposed):**
  - 0.6.0 can't get files: its tag predates the workflow.  The first
    release with them is the next one; `RELEASING.md` step 2 makes it
    name its wheel's URL in the README.
  - The fork `Essens-lang/hexmesh` can be deleted (the user's choice).
