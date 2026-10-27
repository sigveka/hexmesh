# 0024 — Parallel test suite (pytest-xdist) and registered markers

- **Status:** done
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

- **Configuration** was already in place when this was picked up again
  (2026-10-27; it landed with commit faddea0): `pytest-xdist>=3` in the
  `dev` extras; `addopts = "-n auto -m 'not openfoam'"`; the `openfoam`
  marker registered.  `-n auto` gives 8 workers on this 8-core machine
  and does not oversubscribe, so it was kept.  No `slow` marker.
- **OpenFOAM gating:** every OpenFOAM-dependent test carries both
  `@pytest.mark.openfoam` and a `skipif` on a missing installation
  (`OPENFOAM_RC` / `gmshToFoam`).  The marker keeps them out of the
  default run; the `skipif` keeps `-m openfoam` clean on machines
  without OpenFOAM.  `-m openfoam` selects 19 tests (in
  `test_openfoam_output.py`, `test_openfoam_boundary.py`, `test_wye.py`,
  `test_validation.py`).
- **Parallel safety:** no test needed fixing.  `gmsh_session`
  (`tests/conftest.py`) gives each test its own gmsh session, and tests
  write to `tmp_path`.

## Questions for design

_None._

## Outcome

- **Done** 2026-10-27, on commit aa07a67 (8 cores, no other session's
  run active; checked with `pgrep -af pytest`).
- **Files:** `pyproject.toml` (`dev` extras, `[tool.pytest.ini_options]`),
  `docs/tasks/README.md` (ground rules), and the `openfoam` marks on the
  four OpenFOAM test modules.  These landed earlier; this session adds
  the measurements and this record.
- **Three parallel runs** (`python3 -m pytest`): identical results, each
  1255 passed, 5 skipped, 19 deselected, 0 failed.  Wall times 223 s,
  270 s, 267 s.
- **Serial** (`-n 0`), same commit: same counts, wall 741 s (12 min 18 s).
  Parallel is about 2.8–3.3× faster on 8 workers; the long tail of
  10 s tests limits it.
- **`-m openfoam`:** selects 19 tests (1260 deselected).
- **10 slowest tests (serial, `--durations=10`):**

  | s | test |
  |---|---|
  | 11.5 | `test_assembly.py::TestLoopClosure::test_ring_closed_by_closure` |
  | 11.4 | `test_assembly.py::TestLoopClosure::test_twisted_closure` |
  | 10.9 | `test_assembly.py::TestLoopClosure::test_ring_closed_by_exact_bend` |
  | 9.6 | `test_examples.py::test_example[fittings.loop]` |
  | 8.4 | `test_build_sync.py::test_records_match_model[spline-3d-2layer]` |
  | 7.6 | `test_fitting_conformance.py::TestConformance::test_order_independence[profile-cosine]` |
  | 7.2 | `test_examples.py::test_example[fittings.spline_pipe]` |
  | 6.9 | `test_examples.py::test_example[fittings.reducer_network]` |
  | 6.9 | `test_assembly.py::TestQuality::test_two_layer` |
  | 6.2 | `test_examples.py::test_example[sections.insulated_route]` |

- **Surprises:** none.  No parallel-only failures or flakes.
- **Follow-ups (proposed):** the three `TestLoopClosure` tests (~11 s
  each) and the loop example are the slowest; check whether they can
  share a built model or use lower density.
