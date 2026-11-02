# 0080 — Installable package: extras, version, console command, install smoke test

- **Status:** done (2026-11-02)
- **Decision:** none (packaging).  Agreed with the user on 2026-11-01.
- **Depends on:** none.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `pip install .` must give a working hexmesh in an empty
environment.  The design session's test (2026-11-01, a clean venv)
found three faults, two now fixed:
- **fixed:** the build backend `setuptools.backends.legacy:build` did
  not exist, so every install failed.  It is now
  `setuptools.build_meta`;
- **fixed:** `import hexmesh` failed after install.  gmsh and scipy
  (imported at module level by `assembly/blocks.py`) weren't declared.
  Both are now core dependencies.  A system gmsh (apt `4.12.1.dev1`) is
  accepted by pip, so nothing is installed twice; that was tested;
- **open:** this task.

After the fix, a clean venv installs gmsh 4.15.2, numpy and scipy, and
the tee and wye examples mesh as predicted.  The name `hexmesh` is free
on PyPI (HTTP 404, 2026-11-01).

**Where.**  `pyproject.toml`, `hexmesh/__init__.py`,
`hexmesh/study/__main__.py`, `README.md` and `docs/GUIDE.md` (install
sections), `tests/`.

**Do.**
1. **Extras.**
   - `[bathymetry]`: rasterio, xarray, fiona, shapely (imported lazily
     in `io/readers/bathymetry.py`).  State minimum versions you can
     test.
   - `[gallery]`: vtk, Pillow, jsonschema (`docs/gallery/build.py` and
     `tests/test_validation_meta.py`).
   - `[dev]` as now, plus anything the suite needs that isn't in core.
   - **Remove `[io]`**: scipy is core now, so it's redundant.  Grep the
     docs for `[io]` and update them.
2. **`hexmesh.__version__`** from `importlib.metadata.version("hexmesh")`,
   falling back for a source checkout that isn't installed.  A test
   that it equals `pyproject.toml`'s version, and `CITATION.cff`'s
   (task 0078 asks for the same; do it once).
3. **Console command:** `hexmesh-study = "hexmesh.study.__main__:main"`
   (or whatever the module's entry function is; add a `main()` if
   needed).  `python3 -m hexmesh.study` keeps working.
4. **Package contents:**
   - build the sdist and the wheel;
   - check the wheel holds `hexmesh/` and every subpackage, including
     `hexmesh.examples.*`;
   - check the sdist holds `LICENSE`, `README.md` and
     `CITATION.cff`, and not `docs/papers/`, `validation/` work
     directories or `*.msh`.
5. **Install smoke test** (`tests/test_install.py`, marked `slow`, and
   skipped without network or `venv`):
   - build the wheel;
   - install it into a fresh venv in `tmp_path`;
   - run `python -c "import hexmesh; …"`, mesh one small example
     there, and check the cell count.

   This catches the faults above, and any future one like them.
6. **README / GUIDE install sections:** `pip install hexmesh` once
   published, with the checkout form beside it.  Keep the note that a
   system gmsh is used as is.

**Accept.**
- A clean venv: `pip install <wheel>` and the smoke test pass; extras
  install where their wheels exist.
- `hexmesh.__version__` and `hexmesh-study --help` work after install.
- Full suite passes.

**Out of scope.**  Publishing to PyPI or TestPyPI.  That's the user's
decision (account, permanence); propose the steps in *Outcome*.

## Agent notes

- **Extras' minimum versions** are the conservative floors I'd expect to
  work (rasterio 1.3, xarray 2023.1, fiona 1.9, shapely 2.0; vtk 9.2,
  Pillow 10, jsonschema 4.10 are the versions on this machine).  Tested:
  a clean venv installs `[bathymetry,gallery,dev]` from PyPI and imports
  every one (rasterio 1.5.2, xarray 2026.9.0, fiona 1.10.1, shapely 2.2.0,
  vtk 9.7.1, Pillow 13.0.0, jsonschema 4.26.0).  The floors themselves
  weren't installed.  The bathymetry reader's GeoTIFF / NetCDF paths have
  no test in the suite.
- **`__version__`** reads `pyproject.toml` when the package sits in a
  checkout (by the file next to it, named `hexmesh`), else the installed
  metadata.  Metadata first would be stale in an editable install after
  a version bump, and this checkout isn't installed at all.
- **`slow` marker**, excluded by default next to `openfoam`
  (`addopts`).  No other test was slow-marked, so the default run is
  unchanged.
- **The install test needs no network.**  It builds the sdist and the
  wheel with the installed setuptools (`build_meta`, from a copy of the
  tracked and untracked-not-ignored files, so the tree stays clean), in
  two processes: building both in one lost the wheel (setuptools 84).
  The venv uses `--system-site-packages` for gmsh, numpy and scipy and
  installs only the wheel (`--no-index --no-deps`), then `pip check`.
  The network case was run by hand (Outcome).
- **`CITATION.cff`** wasn't in the sdist: `MANIFEST.in` includes it.
- **`hexmesh-study --help`** names itself; `python3 -m hexmesh.study`
  keeps its old name.

## Questions for design

_None._

## Outcome

Done 2026-11-02.

- **Files:** `pyproject.toml` (extras `bathymetry`, `gallery`, `dev`
  plus jsonschema; `[io]` removed; `[project.scripts]`; the `slow`
  marker); `MANIFEST.in` (new); `hexmesh/__init__.py` (`__version__`);
  `hexmesh/study/__main__.py` (prog name); `tests/test_install.py` (new,
  `-m slow`: versions agree, wheel and sdist contents, venv install,
  example meshed, console command; 5 tests, 19 s); `README.md`,
  `docs/GUIDE.md` (install sections), `API.md` (`[io]` →
  `[bathymetry]`).
- **Clean venv from PyPI, by hand** (no system packages): the wheel
  pulls gmsh 4.15.2, numpy 2.5.4, scipy 1.18.1; the tee and wye examples
  mesh as predicted (7 464 and 5 724 cells); `hexmesh-study --help`
  works; the three extras install and import.
- **Wheel:** `hexmesh/` and every subpackage, `hexmesh.examples.*`
  included; entry point `hexmesh-study`.  **sdist:** `LICENSE`,
  `README.md`, `CITATION.cff`, `pyproject.toml`; no `docs/papers/`,
  `validation/`, `*.msh` or `*.pdf`.
- **Full suite:** 2156 passed, 15 skipped (unchanged: the slow tests are
  opt-in); `-m slow` 5 passed.
- **Proposed follow-ups:**
  - run the full suite once against gmsh 4.15 / numpy 2.x (a clean
    install gets those; development is on gmsh 4.12, numpy 1.26);
  - **publishing (the user's decision):** register `hexmesh` on PyPI
    (free on 2026-11-01), try TestPyPI first (`python3 -m build`;
    `twine upload -r testpypi dist/*`; install from it in a clean venv),
    then PyPI with a trusted-publisher GitHub workflow on tags, so no
    token sits on a machine.  A release is permanent: a version number
    can't be reused.
