# 0157 — Platform rules as architecture tests; a `posix_only` marker

- **Status:** done
- **Decision:** [0052](../decisions/0052-ci-gates-main.md) (measure 1).
- **Depends on:** none.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The cross-system failures follow patterns a test can find
without that system: `docs/integrations/platforms.md`'s quirks.  The
encoding rule (`ENCODING_TREES` in `tests/test_architecture.py`) already
works this way.

**Do.**
1. **A `posix_only` marker**, registered in `pyproject.toml`;
   `tests/conftest.py` skips it on `sys.platform == "win32"`, with the
   reason "needs a POSIX shell (platforms.md: WSL's bash)".
2. **Rule: a test that runs a POSIX tool carries it.**  In
   `tests/test_architecture.py`: any `subprocess.run`/`Popen`/`call`/
   `check_output` in `tests/` whose argv literal starts with `bash`,
   `sh` or a known OpenFOAM tool, in a test without `posix_only` (on the
   function or the module's `pytestmark`) and outside the `openfoam`
   marker, is a violation.  Report file:line.
3. **Rule: no path inside compared text.**  An `assert` in `tests/`
   comparing text (`==`, `in`, `startswith`, `endswith`) with an
   f-string that interpolates `tmp_path` or a `Path`-named variable
   bare (no `.as_posix()`, `.name`, `shlex.quote(...)`) is a violation.
   Keep it narrow: false positives cost more than a missed case.  Report
   what it finds today and fix or exempt each (an exemption names its
   reason).
4. **Apply the marker** to `tests/test_volunteer.py`'s `bash -n` check
   (replacing c7a64b9's inline `sys.platform` skip) and to anything step
   2 finds.
5. **Check the WSL cause** that `platforms.md` only infers: a CI step
   on Windows printing `where bash` and `bash --version`, or the test
   capturing `bash -n`'s stderr.  Update the entry's heading to
   *verified* or correct it.
6. **`platforms.md`:** each rule cites the entry it comes from, and each
   entry names its rule.

**Accept.**
- Both rules pass on the tree, and each fails on a deliberate example
  (a small fixture string, as the encoding rule's tests do).
- The Windows CI jobs pass (a run ID under *Outcome*).

**Out of scope.**  Rules on `hexmesh/` code beyond the existing
encoding rule (propose any under *Questions for design*).

## Agent notes

- **Rule 2's tools:** `bash`, `sh`, `timeout` (Windows has a
  `timeout.exe` that waits for a key: the same trap as `bash`), and ten
  OpenFOAM utilities (`OPENFOAM_TOOLS`).  `docker` is left out: it runs
  on Windows.  Only literal argv lists count; `sys.executable` and
  computed argv don't.
- **Helpers count too**, so `run_foam` (`test_openfoam_output.py`, a
  `bash -c` helper) is caught.  It is called only from openfoam-marked
  tests, through `_types` in `test_openfoam_boundary.py`, so it is
  exempt by name in `POSIX_ALLOWED`, with that reason.  Like
  `BARE_ALLOWED`, a test fails when an exemption is no longer needed.
- **What rule 2 found today:** `test_volunteer`'s `bash -n` (c7a64b9's
  inline skip, now the marker); `test_study.py`'s
  `test_other_runs_sees_a_detached_process`, which ran `bash -c … &`
  behind `skipif(os.name == "nt" or …)`: now `posix_only`, the `no
  bash` skip kept; and `run_foam`, exempt.
- **Rule 3 finds nothing today:** the one case, the volunteer test, was
  fixed in 4473cb1 with `shlex.quote`.  Its old form is a planted
  example.  Names: `tmp_path` and `*path`/`*dir`, bare or in `str(…)`;
  `.name`, `.as_posix()`, `shlex.quote(…)` are safe.  `PATH_TEXT_ALLOWED`
  exists, empty.
- **The marker's skip is unit-tested** on fake items with
  `sys.platform` patched: setting it before pytest imports breaks pytest
  (`_winapi`).
- **Step 5:** a Windows-only CI step, `continue-on-error`, prints
  `where.exe bash`, `shutil.which("bash")` and what
  `subprocess.run(["bash", "--version"])` returns, stderr included.  The
  last is what the tests meet: Windows' process search looks in System32
  before PATH, so it may differ from `where`.

## Questions for design

## Outcome

Done 2026-11-13.

- **Files:** `pyproject.toml` (the `posix_only` marker); `tests/conftest.py`
  (skips it on win32); `tests/test_architecture.py` (`RULE_POSIX`,
  `posix_tool_violations`, `POSIX_ALLOWED`; `RULE_PATH_TEXT`,
  `path_text_violations`, `PATH_TEXT_ALLOWED`; 6 tests, 25 planted
  cases); `tests/test_volunteer.py` and `tests/test_study.py` (the
  marker); `docs/integrations/platforms.md`.
- **Found on the tree:** rule 2, three (two marked, `run_foam` exempt
  by name); rule 3, none.
- **CI:** d26b83d on `next`, run 43428690797: all 8 jobs green; both
  Windows jobs 4523 passed, 19 skipped (the `posix_only` tests among the
  skips).  Promoted: `main` is d26b83d.
- **Step 5, the WSL cause, verified** by a temporary CI step (removed
  after): Git's bash is first on the PATH (`where.exe`,
  `shutil.which`), but `subprocess.run(["bash", …])` starts System32's
  WSL launcher (Windows searches System32 first), which exits 1 with "no
  installed distributions" on stdout, in UTF-16.  `platforms.md`'s entry
  corrected: the launcher was right, the reason (PATH order) wasn't.
- **Tests here:** architecture, volunteer, study, README, promote and
  OpenFOAM-output tests: 236 passed.

