# 0014 — Test infrastructure: parallel runs and shared-machine rules

- **Status:** accepted
- **Date:** 2026-10-25 (accepted 2026-10-25 by the user)
- **Tasks:** 0024

## Context

- The suite has no pytest configuration (no `pytest.ini`, no
  `[tool.pytest]` in `pyproject.toml`) and runs serially.  A full run
  took over 10 minutes, measured while another run competed for CPU, so
  the figure is an overestimate.
- `pytest-xdist` 3.8.0 is installed locally but not used, and not in the
  `dev` extras.  The machine has 8 cores.
- A static check suggests the suite is parallel-safe:
  - `conftest.gmsh_session` gives each test its own gmsh session, and
    xdist workers are separate processes;
  - tests write through `tmp_path`, and no fixed output paths were
    found;
  - `test_examples.py` changes into a temporary directory.
- Markers are unregistered.  Task 0020 needs `openfoam`, excluded by
  default.
- On 2026-10-25 the design session killed the coding session's test run
  with a name-pattern `pkill`.  The two sessions share this machine.

## Options

- **A. Stay serial.**  Simple, but slow for every task gate and for the
  coding agent's loop.
- **B. pytest-xdist, configured in `pyproject.toml`**, with registered
  markers and documented rules for sharing the machine.

## Decision

**B**, accepted 2026-10-25.

- `pytest-xdist` in the `dev` extras.  `[tool.pytest.ini_options]` with
  `addopts` running in parallel by default and excluding `openfoam`.
  Registered markers: `openfoam`, and `slow` if useful.
- A serial run stays possible (`-n 0`) for debugging.
- Shared-machine rules for both sessions, in `CLAUDE.md` (applied
  2026-10-25): stop only your own processes by ID; check for another
  session's run before heavy runs or timing; scratch output never goes
  to shared fixed paths.

## Consequences

- **Task 0024:** configuration, markers, measured serial vs. parallel
  times, and fixes for any test that fails only in parallel.
- Task gates ("no new failures") run in parallel by default.
- OpenFOAM tests stay opt-in (`-m openfoam`), and may need serial
  execution or one case directory per worker.

## Verified vs. assumed

- Verified: no pytest config; xdist installed; 8 cores; `tmp_path`
  used throughout; the pkill incident.
- Assumed: the suite is parallel-safe.  Task 0024 checks it by running
  it.
