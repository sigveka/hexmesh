# 0090 — Parallel OpenFOAM runs in the shared helpers, used by every driver

- **Status:** done
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md) (toolchain), [0025 — study runner](../decisions/0025-study-runner.md) (shared OpenFOAM stages); DESIGN §3.1 ("one description per concept")
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).  This task
works in `hexmesh/study/openfoam.py`, `validation/*/run.py` and `tests/`.
Follow CLAUDE.md "Both sessions, shared machine": this machine has **4
physical cores** (8 threads), shared by two sessions.

**Why.**
- **Cost.**  Task 0071's finest levels (415 k cells) took 28 min (O-H)
  and 18 min (control) serial.  Tasks 0084 (the H series) and 0072
  (square bend) will run levels like these.
- **Duplication.**  Parallel runs exist already, three times over:
  `validation/womersley/run.py:423–427`, `validation/stenosis/run.py:228,
  491–499` and `validation/heated_pipe/run.py:270`.  Each writes its own
  `decomposeParDict` and calls `decomposePar` / `mpirun`.

**Where.**  `hexmesh/study/openfoam.py` (new helper); the three drivers
above, `validation/rect_duct/run.py`; `tests/test_openfoam_runner.py`;
`docs/integrations/openfoam.md`.

**Do.**
1. **One helper** in `hexmesh.study.openfoam`, e.g.
   `run_solver(case, solver, *, n_proc=1, method="simple", axis=…)`:
   - `n_proc = 1` runs serially, exactly as `foam()` does today;
   - `n_proc > 1` writes `decomposeParDict`, runs `decomposePar -force`,
     `mpirun -np N <solver> -parallel` and `reconstructPar`;
   - it returns the log, like `foam()`.
   - Use `method simple` along the case's long axis.  Scotch is missing
     in v1912 (`docs/integrations/openfoam.md`); check v2406's image and
     record the result.
   - Reject `n_proc` above the physical core count with a clear error.
     Open MPI counts cores, not threads (integration note, 2026-10-30).
   - Clean up processor directories after reconstructing (unless asked
     to keep them).
2. **Use it in the three drivers.**  Their results must be unchanged:
   rerun one level of each, serial and parallel, and compare the
   reported quantities.  Decomposition changes round-off and iteration
   counts, so expect agreement to the solver tolerance, not bit-identity.
   Record the tolerance seen.
3. **`--np N` on `validation/rect_duct/run.py`**, default 1.  Same
   option name in every driver.
4. **Shared machine:** the helper doesn't check for other sessions'
   runs.  That stays the caller's duty (CLAUDE.md).  Drivers default to
   serial.  `tests` always run serially.
5. **Measure** the speed-up on rect_duct's ar1 k = 4 level at
   `n_proc` 1, 2, 4, and only while no other session's run is active
   (`pgrep -af "simpleFoam|pimpleFoam|pytest"`; don't time otherwise).
   Record it in `docs/integrations/openfoam.md` with version, evidence
   and date.

**Accept.**
- `decomposeParDict` and `mpirun` appear only in
  `hexmesh/study/openfoam.py` (grep).
- One level of womersley, stenosis and heated_pipe gives the same
  reported quantities serial and parallel, within the recorded
  tolerance.
- `tests/test_openfoam_runner.py` covers `n_proc` 1 and 2 (Docker
  v2406; skipped without the image), and the too-many-processes error.
- The speed-up table is in the integration notes.
- Full suite and `-m openfoam` for the touched cases: no new failures.

**Out of scope.**  Running several cases at once (job-level parallelism,
decision 0020/0025); cluster submission.

## Agent notes

- **Coding session, 2026-11-03: refinements to the steps.**
  - **Four drivers, not three.** `validation/stenosis_pulsatile/run.py`
    also had its own `decomposeParDict` and `mpirun`; it uses the
    helper too.
  - **One call per chunk.**  Every driver marches in chunks (periods,
    end times).  Some decomposed once and kept `processor*` between
    chunks.  `run_solver` leaves the case serial again: decompose the
    start time, run, `reconstructPar -newTimes`, remove `processor*`.
    So each driver calls it per chunk, as womersley already did.
    Decomposing and reconstructing map fields exactly, so the restart
    is the same.  The pulsatile driver's `current_time` and `prune` no
    longer look in `processor0`.
  - **The helper:** `run_solver(case, solver, *, n_proc=1, log=None,
    regions=(), axis=None, keep=False)`, plus `physical_cores`
    (psutil when installed, else `/proc/cpuinfo`, else
    `os.cpu_count()`), `long_axis` (the mesh's longest extent),
    `decompose_dict` and `start_time_option`.  `regions` adds
    `-allRegions` and writes the dictionary into each
    `system/<region>/` (heated_pipe).
  - **The start time.** `decomposePar -latestTime` alone breaks a case
    with `startFrom startTime` (the test found it: the solver wanted
    `processor0/0`).  `start_time_option` reads `controlDict` and
    decomposes the time the solver starts from
    (`docs/integrations/openfoam.md`).
  - **Womersley used `method scotch`**, which works in v2406.  It now
    uses `simple` like the rest; its results agree within 3e-5.
  - **Grep acceptance.**  `decomposeParDict` and `mpirun` occur only in
    `hexmesh/study/openfoam.py`.  `hexmesh/study/stages.py` names
    `mpirun` only to detect other sessions' processes, not to run one.
  - **Drivers' unused `n_proc` parameters removed** from
    `write_case` / `write_dicts` (stenosis, heated_pipe,
    stenosis_pulsatile).
  - **rect_duct rows gain `n_proc`.**  Older rows in its results.json
    don't have it, and the stored-levels reuse doesn't need it.
- **Added at the design session's request (2026-11-03, the user agreed;
  0084's follow-ups 2 and 3).**
  - `tests/test_validation_drivers_import.py` imports every
    `validation/*/run.py` and `validation/tools/*.py` as a module,
    without running it.  So a renamed or moved hexmesh name (as in
    0084's `OH_RATIO` break) fails the ordinary suite, on every CI
    system.  It also checks that every case with a `case.json` has a
    driver.  It caught the 0084 break when tried on a copy with the old
    import.
  - API.md's rectangular-duct section: `Tee` duct taps are listed, no
    longer "rejected".
- **The results.json cap is 20 MB, not 1 MB** (the user, 2026-11-03:
  "do not be extremely literal about the result size limit.  Let us keep
  it below 20MB").  `test_pulsatile_stenosis_one_period` writes 4.5 MB
  and failed at task 0093's 1 MB cap.  It failed the same way on the
  pushed 52ffc40, so not because of this task.
  `validation/tools/results.py` `MAX_BYTES = 20_000_000`.  The design
  session has been told; task 0093's text is unchanged.

## Questions for design

## Outcome

**Coding session, 2026-11-03.**

- **Files.**
  - `hexmesh/study/openfoam.py`: `run_solver`, `physical_cores`,
    `cpuinfo_cores`, `long_axis`, `decompose_dict`,
    `start_time_option`.
  - `validation/{womersley,stenosis,stenosis_pulsatile,heated_pipe}/run.py`
    use it; `validation/rect_duct/run.py` gains `--np` (default 1).
  - `validation/tools/results.py` (the 20 MB cap).
  - Tests: `tests/test_openfoam_runner.py` (+11: cores, dictionary,
    start time, the process-count errors, serial vs 2 processes in
    Docker), `tests/test_validation_drivers_import.py` (new, 13).
  - Docs: `docs/integrations/openfoam.md`, API.md.
- **Grep:** `decomposeParDict` and `mpirun` occur only in
  `hexmesh/study/openfoam.py`.  `study/stages.py` names `mpirun` only to
  detect other sessions' processes.
- **Serial against 2 processes, one level each** (each driver's own
  `run_level`, coarsest level, its usual runner):

  | driver (level) | worst reported quantity | serial → 2 processes |
  |---|---|---|
  | womersley (k1, v2406) | dpdx phase 2.3e-5, dpdx_mean_err 2.9e-5 relative | 106 → 82 s |
  | stenosis (coarse, native v1912) | x_reattachment 2.9e-5 relative (2e-4 absolute) | 72 → 59 s |
  | heated_pipe (k1, v2406) | dtb_dx_err 2.6e-5; Nu, temperature rises ≤ 3e-7 relative | 775 → 636 s |
  | stenosis_pulsatile (coarse, v2406) | periodic_change 1.6e-5; same period count | 945 → 661 s |

  Error measures that are zero to round-off move at their own scale:
  mass errors ~1e-8, the energy balance ~1e-7, the interface mismatch
  ~1e-11.  **Tolerance seen: 3e-5 relative on every reported
  quantity.**  The pulsatile comparison covered scalar outputs only (not
  the per-phase profiles); its one-period validation test passes.
- **Speed-up** (rect_duct ar1 k = 4, 138 240 cells, nothing else
  running): solver time 184 / 107 / 64 s on 1 / 2 / 4 processes, i.e.
  1.73× and 2.90× (2.03× and 2.79× per iteration: the iteration count
  varies with round-off).  f·Re is the same to 4e-9.  Table in
  `docs/integrations/openfoam.md`.
- **Tests.**  Full suite 2614 passed, 15 skipped (before the import
  test was added; it passes alone, 13).  `-m openfoam`:
  `test_openfoam_runner.py` and the stenosis, womersley, pulsatile and
  two rect_duct validation tests pass.  The pulsatile one passes only
  with the 20 MB cap.  heated_pipe has no OpenFOAM test; the comparison
  above covers it.  The full `-m openfoam` run of every case takes over
  50 min here, and I didn't run it; untouched cases (poiseuille,
  heated_rod, layered_conduction) weren't rerun.
- **Surprises.**
  - `decomposePar -latestTime` alone breaks a case that starts from
    `startTime`: the solver wants a time that wasn't decomposed.  The
    new Docker test found it.
  - v2406's Scotch works; only the native v1912's is a stub.
  - A hand-written `docker run` of the image fails to write to its
    mount without `--entrypoint bash` (the image's entrypoint changes
    the user).  `foam()` already passes it.
  - Scratchpad paths can't be mounted into containers here, so the
    Docker work went to unique `mktemp -d /tmp/hexmesh-0090-*`
    directories, deleted after each run.
- **Disk.**  All cases and work directories deleted: the driver
  comparison (`/tmp/hexmesh-0090-*`), the speed-up runs, the worktree.
  The numbers are here and in the integration notes.  The scratchpad
  keeps the comparison script and its JSON (≪ 1 MB).
- **Proposed follow-ups.**
  - A `heated_pipe` validation test under `-m openfoam` (the only
    parallel driver without one).
  - Task 0084 step 8 can now run the rect duct's H series with
    `--np`.

