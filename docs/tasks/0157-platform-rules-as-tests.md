# 0157 — Platform rules as architecture tests; a `posix_only` marker

- **Status:** ready
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
