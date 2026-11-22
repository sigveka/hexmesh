# 0190 — The bend's level 3 as a volunteer card; does `ddtCorr` cause the algorithm spread?

- **Status:** done (2026-11-22; step 6 waits for a contribution)
- **Decision:** [0044](../decisions/0044-volunteer-runs.md),
  [0055](../decisions/0055-cards-for-every-case-ci-without-openfoam.md)
  (cards), [0058](../decisions/0058-diagnosis-ladder-and-user-hints.md)
  (the ladder)
- **Depends on:** 0050 (done).  0179 (card form), if it has landed.
- **Blocks:** none.  Not a 1.0 criterion: 0050 is reported with two levels
  (RESEARCH §7.17).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  0050's level 3 (1.49 M cells, time-accurate to steady) would
take 40–150 h on this machine, so it was left for volunteers.  The
algorithm spread at level 1 (K 0.2201–0.2269, `ddtCorr` on) is untested
for its cause.

**Do.**
1. **`ddtCorr` off at level 1** (about 30 min; the user's go-ahead):
   - pimpleFoam time-accurate and SIMPLE, with `ddtCorr off`, on level
     1's mesh and schemes;
   - report K beside the four values with it on.  If the spread shrinks
     below 0.5 %, `ddtCorr` is the cause;
   - record it in `docs/integrations/openfoam.md` with the version, and
     as a lesson for 0188 if it holds.
   This doesn't change the verdict's runs.
2. **A resumable transient:** `--transient` writes its state every 50
   steps (or a set wall-time interval) and restarts from the latest.
   The convergence stop's history must survive a restart.  Test it
   with a forced stop at level 1.
3. **Start from level 2:** `mapFields` from the stored level-2 solution
   onto level 3, then the transient.  Check at level 2 → 2 (identity)
   that the mapped start reaches the same K.
4. **The card** (0179's form, or 0055's if 0179 hasn't landed):
   - **requirements, measured:** s per step at a stated core count,
     early and late; peak memory (under 6 GB expected); disk (about
     2 GB); an estimated total with its range;
   - the convergence stop as in Q5's answer;
   - `collect` returns the level's values, with `wall_s` and `cores`
     (0185) and the machine record (0044).
   Run `prepare` and a short `run` here to check the card.  Don't run
   the level to the end.
5. **A volunteer tag** on a `main` commit carrying the card (CLAUDE.md:
   tags only on `main`; `docs/RELEASING.md`).  It needs the user's OK.
6. **When a contribution arrives** (after this task): it merges with
   `check --merge`; the GCI and the gates at level 3 follow; the status
   is decided then.
7. Docs: the card in `validation/VOLUNTEERS.md`; RESULTS.md says level 3
   is open to volunteers.

**Accept.**
- Step 1 reported.
- A restart test passes.
- The card validates, and a short `run` works.
- The tag pushed, with the user's OK.

**Out of scope.**  Running level 3 to the end here; LES.

## Agent notes

**Step 1, ddtCorr off at level 1 (2026-11-22; `transient_fixed_k1_noddtcorr`,
`lts_fixed_k1_noddtcorr` in `results.json`).**
- In v2406 ddtCorr is a `PIMPLE` switch (`ddtCorr`, default true), read
  in `pimpleControl.C`.  simpleFoam has none (`steadyStateDdtScheme`'s
  correction is zero), so "SIMPLE with ddtCorr off" is SIMPLE as run.
  The two runs off: pimpleFoam time-accurate and pimpleFoam with
  localEuler.  `run.py --transient --no-ddtcorr`.
- Results (both converged by Q5's stop):

  | algorithm | K, ddtCorr on | K, ddtCorr off |
  |---|---|---|
  | pimpleFoam, time-accurate, Co 1 | 0.2201 | 0.2127 |
  | pimpleFoam, localEuler, Co 5 | 0.2257 | 0.2225 |
  | simpleFoam, SIMPLE | 0.2223 | (none to switch) |
  | simpleFoam, SIMPLEC | 0.2269 | (none to switch) |

- **The spread doesn't shrink** (task's test: below 0.5 %): with ddtCorr
  off it is 0.2127-0.2269, 6.7 %, against 3.1 % on.  ddtCorr isn't the
  cause.  ddtCorr alone moves the time-accurate K by 3.4 %, and localEuler
  off lands on SIMPLE (0.2225 against 0.2223).  The reading, not proven:
  at level 1 the face flux's momentum interpolation is a discretisation
  error of several percent in K.  It should shrink with refinement;
  level 2 wasn't checked.
- RMS with ddtCorr off (time-accurate): 0.080, 0.079, 0.059, 0.072,
  0.100, 0.106.  The profiles move less than K.
- Recorded in `docs/integrations/openfoam.md`; RESULTS.md's spread table
  has the off column; 0188's lesson updated (one algorithm and one
  ddtCorr setting per study).
- The verdict's runs are unchanged (ddtCorr on, the default).

**Steps 2 and 3, the resumable transient and the mapped start
(2026-11-22).**
- `transient_run(d, …)` keeps each phase on disk: `setup.json`;
  `start.json` (the steady start, or the mapped one); `zones.json` (the
  pimpleFoam case written); `chunks.json`; the K and probe histories
  under `postProcessing` (as before); `result.json` at the end.  A
  rerun skips what is done and continues from the latest written time.
- Each solver run is one chunk: `stopAt nextWrite`, `writeControl
  timeStep`, `writeInterval` = the chunk (500 steps here, 50 for
  volunteers).  Chunk logs are named by their start time, so a rerun
  doesn't overwrite them.  A function object's later files
  (`<stem>_<time>`, after a restart from a time that already has a
  directory) are read too, oldest first.
- **Two fixes found by the test:**
  - The time names: with adjustable steps and `timePrecision 10`, a
    restart looked for `processor*/1.506584979` where the write was
    `1.5065849792`.  Now 17 digits; recorded in
    `docs/integrations/openfoam.md`.
  - The `.dat` parser split on a space; the columns are tab-separated
    without padding at 17 digits.
- **Restart test, level 1, chunks of 100 steps:**
  - a crash after a chunk's solve, before `chunks.json` was written;
  - then a kill 20 s into a chunk, with the processor directories left.
  Each rerun resumed: the start phase skipped, the run continued from
  the last written time.  It converged at 2.08 flow-throughs, K
  0.220123 against the uninterrupted 0.22013 (−3e-5).  A chunk cut
  short isn't in `chunks.json`, so its steps and wall time are missing
  from the level's own counts.  The volunteer tool's `wall_s` counts
  them.
- **Mapped start (`mapped_start`):** this level's precursor and inlet,
  the bend at rest written, then `mapFields -consistent -sourceTime
  latestTime` from the source case.  The inlet entries of U, k and ω are
  put back to this level's precursor profile (checked: identical).
  - **Identity check at level 1 → 1** (the task's 2 → 2 would need a
    5 h source): K 0.220123031 against the source's 0.220123033, and
    converged at 1.43 flow-throughs instead of 2.08.
  - A 1 → 2 check (a real refinement, against 0.26233) would take
    about 1.5-2.5 h; not run.
- **Volunteer hooks** for `transient_fixed_k<k>`:
  - `prepare` sets up `level/` and, for k > 1, `source/` (level k − 1);
  - `run` solves the source (resumable), maps it, deletes it, and
    solves the level (resumable), in 50-step chunks;
  - `collect` returns the result, with `k_bend` and `rms_<plane>` at the
    top for `check`, and the source's K as `map_sources`;
  - `recompute` rederives `k_bend` from the stored slab pressures and f,
    and the RMS from the stored profiles;
  - the verdict reads merged `transient_fixed_k<k>` levels too;
  - `validation/volunteer.py`'s log tail falls back to the newest
    `level/transient/log.pimpleFoam.*`.
- Tests: validation meta, agent manifest, README and volunteer (199)
  pass.

**Step 4, the card (2026-11-22; the user's go-ahead for the level-3
measurement).**  `validation/turbulent_bend/volunteer.json`, 0055's form
(0179 hasn't landed), one level `transient_fixed_k3`, tag
`volunteer-bend-1` (not yet made).
- **Measured, 4 processes, the desktop:**
  - level 1 from rest to converged: 8.4 min (the source used here, as
    the 2 → 3 source would take 5.3 h);
  - preparing (mesh, convert, check): level 3 5.4 min, level 2 1.6 min;
  - level 3's start: precursor (20 000 steps, residuals flat at
    p 1.4e-4 and U 7e-5 from step 4 000, the pressure gradient
    constant to 10 digits) and mapping, 16 min;
  - three 50-step chunks: 67, 49, 45 s per step (Co 1.003; GAMG about
    95 iterations per pressure solve in the first chunk); K 0.246,
    0.236, 0.232 at t 0.14, 0.28, 0.40 s, falling from the level-1
    start toward level 2's 0.262 or below;
  - peak memory 2.4 GB (the volunteer tool's meter, a chunk); peak disk
    3.5 GB (with the per-process copies), 1.8 GB between chunks.
- **Estimated:** 150 h at 4 cores as the upper bound.  A flow-through is
  about 4 600 steps at level 3 (dt about 0.0028 s); a mapped start took
  1.43 flow-throughs at 1 → 1, so 1.5-2.5.  At 45 s per step that's
  87-144 h, plus 5.6 h for the level-2 source and start; if the steps
  fall to 15 s, as level 2's fell 3.7-fold, about 30-50 h.  Memory 3 GB
  (2.4 measured, the mapping not metered).  The job script asks for
  1.5× both: 225 h and 5 GB.
- **Changes:**
  - `spectrum` returns empty values when the run stops before its
    averaging window starts (a short run crashed on it);
  - the card test calls `check_level` (the driver's public hook) rather
    than `_parse`, which the bend's driver hasn't got.
- **`prepare` and a short `run`:** `prepare turbulent_bend
  transient_fixed_k3 --runner docker:…` wrote `level/`, `source/` and
  `job.sh` (`--time=225:00:00`, `--mem=5G`, 4 tasks).  `bash job.sh`
  solved the level-2 source's start (0.47 h) and two 50-step chunks
  (9.5 and 7.7 min); killed, then run again, it skipped the start and
  continued from t 0.527 s with a third chunk (7.9 min).  Stopped
  there, as the task says.
- **Found, not fixed (a follow-up for the volunteer tool):** `prepare
  --dir a/b` fails with `FileNotFoundError` when `a` doesn't exist: its
  free-disk check reads the parent before making the directory.

**After step 4 (2026-11-22, found in task 0176).**  The contribution
schema requires `steps` and `converged` in a level's values; the
time-accurate record had `transient_steps` and `settled` only, so
`check` would have rejected a level-3 contribution.  `accurate_values`
now adds both.  A test builds a contribution from the stored level-2
run under level 3's name, validates it against the schema and checks
it (accepted; the values take 0.12 MB of the 1 MB limit at level 2).

## Questions for design

## Outcome

- **Step 1:** `ddtCorr` isn't the cause of the algorithm spread: off, the
  spread at level 1 widens to 0.2127-0.2269 (6.7 %).  In RESEARCH §7.17,
  `docs/integrations/openfoam.md`, the GUIDE and 0188's lessons.
- **Steps 2-3:** `transient_run` is resumable (phases on disk, one chunk
  per solver run) and can start from a coarser level by `mapFields`.  A
  restart test at level 1 converges to K 0.220123 (-3e-5 from the
  uninterrupted run); the 1 → 1 mapped start reaches it to 8 digits.
  `timePrecision 17` (a restart missed its own time directory at 10).
- **Step 4:** the card `validation/turbulent_bend/volunteer.json`,
  `transient_fixed_k3`: measured 67, 49, 45 s per step at 4 processes,
  2.4 GB memory, 3.5 GB disk; 150 h stated as the bound (30-150 h).
  `prepare` and a killed-and-resumed `job.sh` checked.  The contribution
  lacked `steps` and `converged`, which the schema requires; fixed in
  task 0176, with a test.
- **Step 5:** tag `volunteer-bend-1` on `main` at abd771b (the user's
  OK, 2026-11-22); it also carries the try-out (task 0176).
- **Step 7:** VOLUNTEERS.md, RESULTS.md and the README say level 3 is
  open to volunteers.
- **Tests:** the full suite at abd771b, 4 780 passed and 18 skipped; CI
  green on 8 jobs.
- **Follow-ups:** step 6 when a contribution arrives; a 1 → 2 mapped
  check (about 2 h), not run; `prepare --dir a/b` fails when `a` is
  missing (the volunteer tool).
