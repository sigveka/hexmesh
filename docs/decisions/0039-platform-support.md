# 0039 — Platform support: meshing everywhere, OpenFOAM through Linux or Docker

- **Status:** accepted
- **Date:** 2026-11-02 (accepted 2026-11-02 by the user: "I agree with your recommendations, go ahead")
- **Tasks:** 0092; 0113 (amendment 2026-11-08, the Python floor)

## Context

The user asked whether hexmesh works on Windows ("I think I saw some
hardcoded paths").  No platform is stated anywhere: not in DESIGN.md,
the README or a decision.  Everything has been developed and run on
Linux.

A read of the code (design session, 2026-11-02, hexmesh `4938e32`; not
run on Windows):

- **Meshing is portable.**  `core`, `sections`/`faces`, `assembly`,
  `interchange`, `io.readers` and the `.msh` output make no POSIX
  calls, and gmsh ships Windows and macOS wheels.  `Assembly.save` /
  `load` set UTF-8.  One read without `encoding=`
  (`io/readers/pcf.py:655`).
- **The OpenFOAM and study layers are Linux-only, and some of them crash
  elsewhere:**
  - The Docker runner calls `os.getuid()` / `os.getgid()`, which don't
    exist on Windows (`study/openfoam.py:73`).
  - It mounts host paths at the same path in the container
    (`-v C:\…:C:\…`, `-w C:\…`), which is not a valid Linux path.
  - The native runner and `run_stage` source
    `/usr/share/openfoam/etc/bashrc` through `bash`.  That's expected:
    OpenFOAM's native builds are Linux.
  - `other_runs()` reads `/proc` (`study/stages.py:321–327`), so
    `run_stage` crashes on Windows **and macOS** unless `--force`.
  - `io/writers/openfoam.py` writes text in text mode, so on Windows
    every line ends in CRLF.  `Allrun`'s `#!/bin/sh\r` then fails under
    bash, and `chmod(0o755)` does nothing.
- **Encodings:** about 46 text reads and writes in `hexmesh/` don't pass
  `encoding=`.  Windows Pythons before 3.15 then use the locale code
  page.  Most of these files are ASCII (JSON is written with
  `ensure_ascii`), so this is a latent risk, not a known failure.
- **No CI** runs the suite anywhere, so no platform claim is checked.

## Options

### A. Linux only, stated
Cheapest.  But meshing is already portable, and users who want a mesh
for their own OpenFOAM, Fluent or STAR-CCM+ setup are often on Windows.

### B. Meshing on every platform; OpenFOAM through Linux, WSL or Docker (recommended)
- Meshing: Linux, macOS, Windows.
- Studies and validation: Linux, WSL, or Windows / macOS through the
  Docker runner.
- Native OpenFOAM runner: Linux only.
- Fix the crashes above, and check the claim with CI.

### C. Everything on every platform, natively
OpenFOAM's Windows builds (MSYS2 / blueCFD) are a separate toolchain,
and the project has no way to test them.  Not worth it.

## Decision

**B** (the user, 2026-11-02).

| layer | Linux | macOS | Windows |
|---|---|---|---|
| meshing (`core`, `sections`, `assembly`, `interchange`, `io`) | yes | yes | yes |
| studies and validation, Docker runner | yes | yes | yes (Docker Desktop) |
| studies and validation, native runner | yes | — | WSL only |

Rules that follow:
- **Files OpenFOAM or a shell reads are written with `\n` line endings**
  on every platform (`newline="\n"`).  They are Linux-side files
  whatever the host.
- **Every text read and write in `hexmesh/` names its encoding**
  (UTF-8).  The architecture test enforces it.
- **No POSIX-only call without a fallback** in `hexmesh/`: `os.getuid`,
  `/proc`, `fcntl` and the like are guarded and degrade with a clear
  message, never crash.
- **The Docker runner maps host paths to container paths** (`/work/0`,
  …) and does not assume they are the same.
- **CI proves it:** the suite without OpenFOAM on Linux, macOS and
  Windows.  OpenFOAM tests stay on Linux (and the Docker runner where a
  CI host has Docker).

## Consequences

- **DESIGN.md §1:** a "Platforms" paragraph with the table above.
- **README "Install":** the same, briefly.
- **Task 0092:** the fixes, the encoding rule, CI.
- **Task 0091 (in progress):** its `.msh` post-processing keeps the
  file's own line endings (binary read and write, or `newline=""`), so
  it doesn't turn LF into CRLF on Windows.
- **Harder:** the Docker runner's path mapping means every absolute
  path in a command must be rewritten.  Drivers that pass absolute
  paths in `cmd` need checking.
- **Validation drivers** inherit the runner.  They aren't promised on
  Windows beyond what the runner gives them.

**Future expansions:**
- **0019 (agent SDK):** helps.  Agents and their hosts are often not
  Linux; meshing works there.
- **0030 (simulation suite):** consistent.  Its solver adapters run in
  containers; the path mapping here is what they need.
- **0018, 0021, 0035:** none.

## Verified vs. assumed

- **Verified:** the code sites listed (read, 2026-11-02);
  `os.getuid` is absent from Windows Python (documented: "Availability:
  Unix").
- **Assumed, to be checked by task 0092's CI:**
  - that meshing runs on Windows and macOS (gmsh wheels, OCC);
  - that OpenFOAM reads CRLF dictionaries badly or not at all (moot
    after the `\n` rule);
  - that Docker Desktop accepts `C:\…` host paths in `-v` with the
    container side mapped (`/work/0`).

## Amendment: Python 3.11 is the oldest supported (2026-11-08; the user: "I also want to drop 3.10 python")

**Context.**  Python 3.10 reached its end of life in October 2026.  The
last two CI runs (42466812439, 42468603272) failed on
`windows-latest, Python 3.10` in `actions/setup-python`, before any
test ran; every other job passed.  ~~Assumed: that the runner image no
longer provides 3.10.~~  **Corrected (2026-11-08, task 0113):** the log
shows a 504 from GitHub's download of `python-3.10.11-win32-x64.zip`, a
transient server error; macOS and Linux at 3.10 passed in the same runs.
CI was also red on every job for an unrelated test bug (NumPy 2's
`repr`), fixed in 0113.  The drop stands on end of life alone.

**Decided:**
1. `requires-python = ">=3.11"`.  CI's oldest version is 3.11, beside
   the newest (`3.x`), on all three platforms.
2. Code kept only for 3.10 may go (e.g. the `tomllib` workaround in
   `tests/test_readme.py`).  No other behaviour changes.
3. The docs and badges say 3.11; CHANGELOG states the drop under
   *Unreleased*, as a breaking change for 3.10 users.
4. **The rule for the future:** the oldest supported Python is the
   oldest one still in its upstream support window.  When it reaches end
   of life, it is dropped in the next release, by a task under this
   decision (no new decision needed).
