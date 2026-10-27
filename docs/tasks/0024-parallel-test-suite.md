# 0024 — Parallel test suite (pytest-xdist) and registered markers

- **Status:** in progress
- **Decision:** [0014 — Test infrastructure](../decisions/0014-test-infrastructure.md)
- **Depends on:** —  (do it between other tasks; see "Measure" below)

Ground rules for all tasks: [README](README.md#ground-rules).  Also
follow `CLAUDE.md`, "Both sessions, shared machine".

**Why.**  The suite runs serially and took over 10 minutes (measured
while contended).  `pytest-xdist` 3.8.0 is installed but unused, and the
machine has 8 cores.  Task 0020 needs a registered `openfoam` marker,
excluded by default.

**Where.**  `pyproject.toml` (`dev` extras, a new
`[tool.pytest.ini_options]`); `tests/conftest.py`; any test that fails
only in parallel; `docs/tasks/README.md` (ground rules: the test
command).

**Do.**
1. **Configuration.**
   - Add `pytest-xdist` to the `dev` extras.
   - Add `[tool.pytest.ini_options]` with `addopts` running in parallel
     by default (`-n auto`, or a fixed count if `auto` oversubscribes;
     record the choice) and excluding `openfoam` (`-m "not openfoam"`).
   - Register markers: `openfoam`, and `slow` if you mark any.
   - Make sure a serial run still works with `-n 0`.
   - Check how existing OpenFOAM-dependent tests (e.g.
     `test_openfoam_output.py::test_openfoam_cht_split`) are gated.  If
     they skip on a missing `gmshToFoam`, decide whether to also mark
     them `openfoam`; record it under *Agent notes*.
2. **Parallel safety.**  Run the full suite in parallel 3 times.
   - Any test that fails only in parallel, or flakes, is a bug: find the
     shared state (fixed paths, cwd, module-level gmsh state, environment
     variables), and fix the test, not the configuration.
3. **Measure**, following the shared-machine rules: check `pgrep -af
   pytest` first, and only measure when no other session's run is
   active.
   - Wall time serial (`-n 0`) vs. parallel, on the same commit.
   - The 10 slowest tests (`--durations=10`).
   - Record both in *Outcome* and in a short note in
     `docs/tasks/README.md` under "Ground rules" (the test command and
     the expected run time).
4. Update the ground rules' test command in `docs/tasks/README.md` if it
   changes.  Keep "no new failures" as the gate.

**Accept.**
- `python3 -m pytest` runs in parallel by default and excludes
  `openfoam`.  `-n 0` runs serially.  `-m openfoam` selects the
  OpenFOAM tests.
- Three consecutive parallel runs: identical results, no new failures.
- Serial vs. parallel wall times and the slowest tests recorded.

**Out of scope.**  Speeding up individual slow tests (propose them as
follow-ups); CI configuration (no CI yet).

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
