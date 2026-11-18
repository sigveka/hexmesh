# 0173 — A volunteer run on Windows: gmsh clobbers `PATH`, `mpirun` as root, processor symlinks, and a stopped Docker reported as "no OpenFOAM"

- **Status:** done (2026-11-18)
- **Decision:** [0039 — Platform support](../decisions/0039-platform-support.md)
  (OpenFOAM through Docker from Windows; task 0092)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  On Windows,
`python -m validation.volunteer prepare helical_pipe re3000_n24 --dir run/`
fails in two ways (found 2026-11-18, Windows 11, Python 3.14.7,
gmsh 4.15.2 pip wheel, Rancher Desktop 29.9.3-rd with moby):

1. **Every OpenFOAM command after meshing fails** with
   `FileNotFoundError: [WinError 2] The system cannot find the file
   specified`, raised from `subprocess.Popen` in `foam()`
   (`hexmesh/study/openfoam.py:230`, called by `convert`).  Cause:
   `gmsh.initialize()` overwrites the process's native Win32 `PATH`.
   It went from 1656 to 323 characters; Rancher Desktop's `docker.exe`
   directory, Git and PowerShell were removed, and `C:\` was added.  It
   stays that way after `gmsh.finalize()`.  `os.environ["PATH"]` is not
   updated, so Python still shows the full value and `shutil.which`
   still finds `docker`.  But `CreateProcess` (`Popen` with
   `env=None`) looks programs up on the native `PATH`.  The
   `docker`-based version check passes before meshing and the
   conversion fails after it.  The empty `log.gmshToFoam` from a
   2026-11-17 attempt is the same failure.  Evidence and a probe:
   `docs/integrations/gmsh.md`, "`gmsh.initialize()` on Windows replaces
   the process's native `PATH`".  Linux is unaffected.
2. **A stopped Docker engine is reported as "no OpenFOAM".**
   `openfoam_version()` (`openfoam.py:256`) keeps only stdout and
   ignores the return code and stderr.  With Rancher Desktop not
   running, `require_version` raised
   `runner 'docker:opencfd/openfoam-default:2406' has no OpenFOAM`.
   Docker's own message (`failed to connect to the docker API at
   npipe:////./pipe/docker_engine …`) was thrown away, so the user
   went looking for a missing image.

**Where.**  `hexmesh/_gmsh.py` (`initialize`, used by `start`) and
`hexmesh/session.py` (`Session.__enter__`);
`hexmesh/study/openfoam.py` (`_argv` callers: `have_openfoam`, `foam`,
the `docker stop` in `foam`, `openfoam_version`, `require_version`);
`tests/test_session.py` (new), `tests/test_openfoam_runner.py`;
`CHANGELOG.md`.

**Do.**
1. One helper, `_gmsh.initialize()`, used by every hexmesh start of
   gmsh (`Session.__enter__`, and `_gmsh.start` for `to_mesh`, task
   0167).  It saves `os.environ["PATH"]` before `gmsh.initialize()`
   and assigns it back afterwards.  On Windows,
   assigning `os.environ` calls `putenv`, which resets the native
   variable (checked: 323 → 1656 characters, then `docker` starts).
   A second `initialize()` in the same process doesn't change `PATH`
   again.  This covers every later program start in the process: the
   OpenFOAM helpers, `validation/fenicsx_second_order/run.py`'s
   `docker run`, `volunteer.py`'s `docker stats`, and `git`.
2. `openfoam.py`: one helper that turns an argv into one `Popen` can
   start.  It replaces `argv[0]` with `shutil.which(argv[0])` when that
   finds it, so the lookup uses `os.environ`'s `PATH`.  Use it at every
   program start in the module.  This covers users who call
   `gmsh.initialize()` themselves rather than through `Session`.
3. `openfoam_version()` keeps returning `""` when the runner has no
   OpenFOAM.  When the runner command itself fails (non-zero exit, or
   the program is missing), keep the reason.  `require_version` then
   puts the runner's last stderr line in its message, e.g.
   `runner 'docker:…' could not run (failed to connect to the docker
   API …)`, with a hint to start Docker Desktop / Rancher Desktop.
   Keep the error code `openfoam_version_mismatch`.
4. CHANGELOG under *Unreleased*: both fixes, for Windows users.

**Accept.**
- New tests, platform-independent:
  - a fake `gmsh.initialize` that changes the native `PATH` with
    `os.putenv` only.  Inside `Session`, a child Python (absolute
    `sys.executable`) sees `os.environ["PATH"]`;
  - the helper resolves a bare name via `shutil.which` and leaves an
    unresolvable one unchanged;
  - `require_version` with a runner whose command exits 1 with
    "failed to connect to the docker API" names that reason, not "no
    OpenFOAM".  With exit 0 and empty output it still says "no
    OpenFOAM".
- A Windows-only test with the real gmsh: inside `Session`, the native
  `PATH` (`GetEnvironmentVariableW`) equals `os.environ["PATH"]`.
- The full suite: no new failures.
- On Windows, `python -m validation.volunteer prepare helical_pipe
  re3000_n24 --dir <dir>` gets past `gmshToFoam` and `checkMesh`.

**Out of scope.**  The OneDrive delete failure seen in the same session.
`shutil.rmtree(run/case)` in `helical_pipe/run.py:setup_level` gets
`[WinError 5] Access is denied` on an emptied directory that OneDrive had
synced (cloud reparse tag `0x9000e01a`).  A new folder deletes normally,
and the same `rmdir` from WSL succeeds.  It needs its own task, if any:
a retry, or a docs note to run outside OneDrive.

## Agent notes

- **Written on a v0.6.0 checkout, then moved to `next`** (2026-11-18).
  The session started on a detached `v0.6.0`, where the next free task
  number was 0156.  On `origin/next`, 0156 to 0172 were taken, so this
  is 0173.  Upstream had added a second start of gmsh, `_gmsh.start()`
  for `Assembly.to_mesh()` (task 0167).  Fixing only `Session` would
  have missed it, so the `PATH` restore is `_gmsh.initialize()`, used
  by both, and a test checks that both call it.  `run.py`'s conflict
  took upstream's `n_arc` (task 0166).  The runs and measurements below
  were made on the v0.6.0 checkout plus these changes.

- The task was written and fixed in the same session that found the bug
  (2026-11-18), at the user's request: "write the task …, then implement
  the fix and report the result".
- The fixed `PATH` in `Session` was checked first: after
  `gmsh.initialize()` the native `PATH` was 323 characters; after
  `os.environ["PATH"] = saved` it was 1656 and `docker` started.  A
  second `initialize()` in the same process doesn't change it again.
- **Do 3** became one helper, `_probe_version() -> (version, reason)`.
  `openfoam_version()` keeps its signature and returns its first item.
  `tests/test_volunteer.py::test_require_version` now mocks
  `_probe_version`, not `openfoam_version`.
- `hexmesh/session.py` had no logo header; it has one now (ground rule:
  files edited).
- **Scope added (2026-11-18), a third Windows bug found by running the
  case** (the user: "It would be nice to try").  The first `volunteer
  run` stopped at `mpirun -np 16 simpleFoam -parallel`: "mpirun has
  detected an attempt to run as root".  A Windows host passes no
  `--user`, so the container is root, and Open MPI refuses root.
  `docker_argv` now adds `-e OMPI_ALLOW_RUN_AS_ROOT=1 -e
  OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1` when it passes no `--user`.  It
  belongs here because it is the same path (the Docker runner from
  Windows, decision 0039) and blocked the same acceptance run.  Recorded
  in `docs/integrations/openfoam.md`.
- **A fourth, found the same way.**  The run then reached step 100 and
  crashed in `run_solver`'s `shutil.rmtree(processorN)`: `[WinError
  1920]` on `processor0/50/uniform`.  That is a Linux symlink written by
  the container, which Windows sees as a WSL reparse point
  (`0xa000001d`) it can't open.  `run_solver` now removes `processor*`
  with `rm -rf` inside the runner.  On native and `path` runners that is
  the same deletion as before.  Recorded in
  `docs/integrations/openfoam.md`.
- **And the OneDrive delete, once.**  After the coarse level
  converged and was mapped, `run()`'s `shutil.rmtree(d / "source")`
  failed with `[WinError 5]` on the emptied `constant/polyMesh/sets`
  (the out-of-scope OneDrive behaviour).  `setup.json` was already
  written, so resuming skips to the fine solve.  The delete is only
  cleanup, and `main()` already calls it with `ignore_errors=True`, so
  `run()` now does too.  The general fix (`setup_level`'s
  `rmtree(case)`) stays follow-up 1.

## Questions for design

None.

## Outcome

**Files.**
- `hexmesh/_gmsh.py`: `initialize()` keeps `PATH`; `start()` uses it.
  `hexmesh/session.py`: `Session.__enter__` uses it.
- `hexmesh/study/openfoam.py`: `_spawnable(argv)` (program looked up
  with `shutil.which`, i.e. on `os.environ`'s `PATH`), used at all four
  program starts (`have_openfoam`, `foam`'s `Popen` and its
  `docker stop`, the version probe).  `_probe_version()` returns the
  runner's failure reason: the last stderr line, or "docker not found".
  `require_version` says `runner '…' could not run (<reason>)`, with a
  hint to start the Docker engine for `docker:` runners.  Code still
  `openfoam_version_mismatch`.
- `tests/test_session.py` (new, 4 tests): a stand-in gmsh that changes
  only the native `PATH` (`os.putenv`), and a child process after
  `_gmsh.initialize()` sees `os.environ`'s `PATH`; `Session` and
  `start` both call the helper.  Windows only, with the real gmsh, in a
  `Session` and in `to_mesh`: `GetEnvironmentVariableW("PATH") ==
  os.environ["PATH"]`.
- `tests/test_openfoam_runner.py` (+4 tests): `_spawnable`; a runner
  failing with "failed to connect to the docker API" is named, not "no
  OpenFOAM"; a missing runner program; exit 0 with no version still
  says "no OpenFOAM".
- `tests/test_volunteer.py`: `test_require_version` mocks
  `_probe_version`.
- `hexmesh/study/openfoam.py` `docker_argv`: Open MPI's run-as-root
  opt-in (`_MPI_AS_ROOT`) when there is no `--user`;
  `tests/test_openfoam_runner.py::test_docker_as_root_lets_mpirun_run`.
- `hexmesh/study/openfoam.py` `run_solver`: `processor*` removed by
  the runner (`foam("rm -rf processor*", …)`), not `shutil.rmtree`;
  `tests/test_openfoam_runner.py::test_run_solver_removes_processor_dirs_in_the_runner`.
- `docs/integrations/openfoam.md`: the `mpirun`-as-root behaviour, and
  the processor symlinks.
- `validation/helical_pipe/run.py` `run()`: the source's removal after
  mapping is `ignore_errors=True`, as in `main()`.
- `CHANGELOG.md` (*Unreleased*): both fixes.
- `docs/integrations/gmsh.md`: the gmsh behaviour, with version and
  evidence (written when found, before this task).

**Tests.**  Windows 11, Python 3.14.7, gmsh 4.15.2, the project venv:
- touched files (`test_session`, `test_openfoam_runner`,
  `test_volunteer`): 58 passed, 1 failed, 3 deselected;
- full suite (`-n auto`): **4476 passed, 18 skipped, 1 failed**
  (14 min 21 s).
- The one failure, `test_volunteer.py::test_only_docker_names_containers`,
  is **not new**: it fails the same way with the change stashed.  It
  runs the POSIX program `true` through `foam`, and there is no `true`
  on Windows (`FileNotFoundError`).
- After the `mpirun` fix: `test_openfoam_runner.py` + `test_session.py`
  34 passed; `-m openfoam tests/test_openfoam_runner.py` (real Docker,
  including `mpirun -np 2`) **3 passed** on Windows.
- After the symlink fix: `test_openfoam_runner.py` + `test_session.py`,
  OpenFOAM tests included, **38 passed** on Windows.  The full suite was
  not re-run after the last two fixes; both are confined to
  `docker_argv` and `run_solver`.
- **On `next` (aa04883) with every change here, Windows, full suite
  `-n auto`: 4694 passed, 20 skipped, 0 failed** (14 min 28 s).
- The Linux suite was **not run**: WSL here has no Python with pytest
  (the only venv is the Windows one).  The new tests are written to
  pass on both: the stand-in test uses `os.putenv` and an absolute
  `sys.executable`, and on POSIX `Popen` with `env=None` inherits the
  native environment too.  CI's Linux and macOS jobs will confirm.

**End to end** (Windows, Rancher Desktop 29.9.3-rd with moby,
`docker:opencfd/openfoam-default:2406`):
`python -m validation.volunteer prepare helical_pipe re3000_n24 --dir run/`
exits 0.  `OpenFOAM v2406`; meshes nang 24 (2 711 232 cells, predicted =
`checkMesh`, all hexahedra) and nang 16 (803 328);
`gmshToFoam` and `checkMesh` run in Docker: **Mesh OK**, non-orthogonality
max 38.87° (mean 7.13°), max skewness 0.515.  Mesh sha256
`09deb19d…3b3352`.  Output 697 MB in `run/` (kept: the disk-space rule
doesn't apply on this machine, per the user 2026-11-18).

**The validation run, end to end on Windows** (the user asked to try
it, 2026-11-18).  `python -m validation.volunteer run run --np 16`, then
`collect` and `check` (no `--merge`):
- **Coarse source (nang 16, 803 328 cells):** converged in 812 steps,
  34 min at 16 processes.  f = 0.0491771385, which is the stored
  `re3000_n16` value to **1.0e-9** (`f_vs_stored`).  The Windows/Docker
  toolchain reproduces the Linux runs.
- **Fine level (nang 24, 2 711 232 cells),** started from the mapped
  coarse result: converged in **440 steps** (the card estimated about
  560).  About 12 s per step at 16 processes; the card had 51–70 s at
  4.  **f = 0.048558**, `f_ito` 0.048304, so **+0.53 %**.
  `turn_agreement` 1.1e-6; min scaled Jacobian 0.730.
- **Re 3000 series** (f, vs Ito): nang 8 0.050507 (+5.3 %, not
  converged); 12 0.049998 (+3.8 %); 16 0.049177 (+1.9 %); 24 0.048558
  (+0.53 %).
- **`check`: accepted.**  The mesh hash matches (`09deb19d…`).  Gates:
  Re 3000 GCI (nang 12, 16, 24) **1.44 %**, f at nang 24 **+0.53 %**;
  Re 1800 GCI 0.55 %, −0.27 %; Re 2400 GCI 0.95 %, +0.26 %; spline vs
  helix 3.41e-4 d.  All pass.
- **Contribution file:** `run/helical_pipe-re3000_n24.contrib.json`
  (19 kB).  Re-collected with `--machine "HP ZBook Fury G1i laptop:
  Intel Core Ultra 7 265HX (20 cores), 64 GB; Windows 11, OpenFOAM in
  Docker (Rancher Desktop, WSL2: 20 CPUs, 31 GB); 16 MPI processes"`.
  No name: the repository owner ran it.
- **Solver time, for speed comparisons** (the file's `wall_s` isn't
  fit for that; see below).  From the logs:
  - coarse: 2052 s for 812 steps (2.5 s/step);
  - fine: 6173 s of `ClockTime` over 9 chunks, less the 1979 s asleep,
    so about **4190 s for 440 steps (9.5 s/step)**;
  - about **1.75 h** of solving at 16 processes.
- **Merged** (the user: "include the results"), on `next`'s code:
  `python -m validation.volunteer check <file> --merge` re-meshed the
  level.  The hash matched, `accepted`, and all seven gates passed.
  Re 3000's convergence order over n_arc 12, 16, 24 is **1.84**
  (Re 1800 1.93, Re 2400 1.90).  Then `validation.tools.plots
  helical_pipe` (figure.png), `docs/gallery/build.py --markdown-only`
  (the "last run" lines), and RESULTS.md's status section by hand (the
  n_arc 24 table gains Re 3000).
- **Contributions from the volunteer tags carry the old names.**
  `volunteer-helical-1` and `-2` predate task 0166, so a contribution
  says `nang`/`nrad`/`nang_w`/`nang_h`.  `next`'s `check` had no
  translation: `recompute` reads `values["n_arc"]` (`KeyError`), and a
  merge would have stored the old keys.  `validation/volunteer.py` now
  renames them on reading (`OLD_NAMES`, keys and strings such as
  `init_from`), and the report says so.  Test:
  `test_a_contribution_with_the_old_names_is_merged_with_the_new`.
- **The same `PATH` bug inside the test suite** (Windows, on `next`).
  The full suite's `test_check_dist::test_package_data_is_what_git_tracks`
  failed with `FileNotFoundError` (no `git`), but passed alone.  Tests
  that call `gmsh.initialize()` directly (conftest's `gmsh_session`,
  test_blocks, test_intent, …) left the native `PATH` without Git for
  the rest of the xdist worker.  `tests/conftest.py` now has an autouse
  fixture, `_keep_path`, that assigns `PATH` back after every test.
- `test_only_docker_names_containers` runs `true`, so it is now
  `posix_only` (task 0157's marker; follow-up 2 done).  Why the
  architecture test `test_posix_tools_are_marked` didn't flag it wasn't
  checked.
- `hexmesh/agent/validation.json` regenerated
  (`python -m validation.tools.summary`): helical levels 11 → 12.
- **Wall time** recorded in the file, 12 730 s (3.5 h), adds up 4
  `run` invocations.
  That includes about 37 min of laptop sleep (Modern Standby
  08:58–09:35, one step with 1979 s wall for 47 s CPU) and the time lost
  to the bugs fixed here.  The solving itself was about 2.3 h.  For the
  rest of the fine solve, a helper held `SetThreadExecutionState`
  (`run/keep_awake.ps1`, ended with the run).
- **Peak memory: not measured** (`peak_memory_how: "not measured"`).
  The meter sums descendants through Linux `/proc` and `docker stats`;
  on Windows it reported nothing.

**Surprises.**
- The gmsh `PATH` change is invisible from Python.  `os.environ` and
  `shutil.which` both still show `docker`, so the version check passes
  and only programs started after meshing fail.  The empty
  `log.gmshToFoam` from the 2026-11-17 attempt was this bug.
- The Windows console prints `°` as `�` in hexmesh warnings (cp1252
  output); cosmetic.

**Proposed follow-ups.**  (Numbers 1–6 from the v0.6.0 checkout; 7–8
from the move to `next`.)
1. **OneDrive deletes** (out of scope here): `setup_level`'s
   `shutil.rmtree(case)` fails with `[WinError 5]` on an emptied
   directory that OneDrive has synced.  The same `rmdir` from WSL works,
   and a new folder deletes normally.  It hits every second `prepare`
   into the same `--dir` under OneDrive.  Options: retry `os.rmdir`
   with a short back-off, or a VOLUNTEERS.md note to use a `--dir`
   outside OneDrive.
2. **`test_only_docker_names_containers` on Windows**: use
   `[sys.executable, "-c", "pass"]` instead of `["true"]` (the same kind
   of fix as `c7a64b9`).
3. **`prepare`'s "next:" line** prints `bash C:\Users\…\OneDrive - <organisation>\…\job.sh`
   (a path with spaces) unquoted and as a Windows path, so it can't be
   pasted into a shell as written.  Quote it, and on Windows say how to
   run the job (WSL or Docker).
4. **Laptop sleep during volunteer runs:** Windows' idle sleep (5 min
   on mains here) freezes Docker and the solver.  `volunteer run` could
   hold `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)` on
   Windows (and `caffeinate` on macOS) for its lifetime, or
   VOLUNTEERS.md could say to disable sleep.
5. **Peak memory on Windows:** `PeakMemory` measured nothing.  Find out
   why (`/proc`-only descendants, or `docker stats` names) and make it
   report there, or record "not measurable on Windows".
6. **Merge the contribution** into `validation/helical_pipe/results.json`
   and update RESULTS.md / task 0075 (Re 3000 nang 24 was the missing
   level).  This is a design-session / user decision.
7. **Finish task 0075's write-up:** RESULTS.md's *Gates* section still
   shows the n_arc 8, 12, 16 analysis.  The stored gates
   (`validation.tools.recheck helical_pipe`) are now all *pass*, with
   n_arc 24 at every Re.  The case status (`case.json`: in progress) and
   the verdict are for the design session.
8. **`validation.tools.plots` on Windows writes RESULTS.md with CRLF**
   (text mode, no `newline="\n"`).  The content was unchanged; it was
   normalised back to LF by hand here.
