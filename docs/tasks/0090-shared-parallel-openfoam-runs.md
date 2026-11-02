# 0090 — Parallel OpenFOAM runs in the shared helpers, used by every driver

- **Status:** ready
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

## Questions for design

## Outcome
