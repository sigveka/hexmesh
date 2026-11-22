# 0176 — A try-out volunteer card: the whole workflow in a minute or two

- **Status:** done (2026-11-22; the user's native Windows run is under way, its time to be added below)
- **Decision:** [0044](../decisions/0044-volunteer-runs.md), its note of
  2026-11-18 (every heavy case gets a card, and one card to try the
  workflow); [0054](../decisions/0054-validation-needs-a-checkout.md)
  (a checkout)
- **Depends on:** none.  Before 0168's tag, so the first junction
  volunteers can try the workflow first.  If 0175 (the machine record)
  lands first, the try-out shows its record too.
- **Blocks:** the next volunteer tag.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  A volunteer's first contact with the tool should be a run
that takes minutes, not hours, and fails early if their setup is wrong:
Docker stopped, `mpirun` refusing root, a path that can't be deleted.
Task 0173 found three Windows bugs only hours into a real level.  The
user (2026-11-18) asked for a quick "test" people can use to try the
workflow.

**Where.**  `validation/poiseuille/` (the case: V1, accepted, laminar,
its coarse level solves in about 15 s), its `run.py` and a new
`volunteer.json`; `validation/volunteer.py` (`list`, `check`, the
generator of VOLUNTEERS.md); the card format; `tests/test_volunteer.py`;
README *Validate or volunteer*.

**Do.**
1. **The level:** Poiseuille's coarse mesh, solved on **2 MPI
   processes**, so `decomposePar`, `mpirun`, `reconstructPar` and the
   processor clean-up all run.  Name it e.g. `try_np2`.  Measure its
   time here: the goal is under about 2 minutes once the image is
   pulled.  If the coarse mesh is too small to decompose sensibly, say
   what you chose instead.
2. **Driver hooks:** `prepare`, `run`, `collect` in
   `validation/poiseuille/run.py`, as the helical driver has them, with
   `n_proc` passed through to `run_solver`.  The stored levels and
   `main()` are unchanged.
3. **The reference:** solve the level here once and store its values in
   the card's `reproduce` (or as a level in `results.json` marked as a
   try-out, whichever `check` reads more simply; say which).  The
   tolerance must allow for 2 against 1 processes and other platforms:
   measure the difference to the serial coarse level, and set the band
   with margin.  The try-out has no validation gate: `check` compares
   with the reference and runs `recheck`'s mesh hash.
4. **The card** marks the level as a try-out (a field such as
   `"try": true`; extend the card format and its test).
   - `list` shows it first, as "Try the workflow".
   - `check` runs in full: schema, mesh hash, reproduce.  `--merge`
     refuses a try-out with a clear message (nothing is stored, and it
     gives no credit).
   - `collect`'s printout says it's a try-out and that the file needn't
     be sent.
5. **VOLUNTEERS.md** (through its generator): a short first section,
   "Try the workflow first".  It gives the four commands, `prepare` →
   `run` (or `bash job.sh`) → `collect` → `check` on your own file, the
   Windows forms, what "accepted" means here, and what to do if a step
   fails (the error, the runner, and an issue with the log).
6. **README *Validate or volunteer*:** the check command becomes, or is
   followed by, the try-out (one line, linking VOLUNTEERS.md).  Keep
   `test_readme` green.
7. **The local check, not CI** (decision 0055: CI doesn't depend on
   OpenFOAM).  Task 0178's `tools/local_check.py` runs the try-out end
   to end.  Here, make sure it can be scripted: one call per step, in a
   temporary directory, and a non-zero exit on anything but "accepted".
8. **Tests** (fast, no OpenFOAM): the card validates; `list` puts the
   try-out first; `--merge` of a try-out contribution is refused; a
   tampered try-out file is rejected as for a real level.
9. CHANGELOG: one line.

**Accept.**
- The try-out runs end to end here, in about 2 minutes or less
  (measured, stated), and `check` says "accepted".
- `--merge` refuses it; nothing about it reaches `results.json` or
  RESULTS.md.
- The user's Windows session runs it natively once (Docker or Rancher
  Desktop) and records the time under *Agent notes*, or it says that
  run is still to do.
- The full suite passes.

**Out of scope.**  A try-out per runner kind (`apptainer:`, `path`):
the same card serves them all, and the user reports what works.  Timing
or benchmarking the volunteer's machine.

## Agent notes

**2026-11-22, the coding session.**
- **The level, `try_np2`:** Poiseuille's coarse mesh (5 184 cells), not
  too small to decompose: 2 slabs along the pipe.  `run_level` is split
  into `setup_case` (mesh, case, convert, checkMesh, topoSet) and
  `level_values` (the log's convergence and `results`), so the stored
  levels and `main()` give what they did; the hooks (`check_level`,
  `prepare`, `run`, `collect`, `recompute`) reuse them.  `run` passes
  `n_proc` to `run_solver`; a run cut short starts again from the
  initial fields (seconds).
- **The reference in the card** (the level's own `reproduce`, with
  `value`), not `results.json`: `check` then needs no store and no
  gates for a try-out.  dp 8.036058237403601e-05 on 2 processes; on 1
  process 8.03605823685401e-05, +7e-11 (129 against 125 iterations;
  u_max +8e-11, q +5e-11).  Tolerance 1e-5.
- **Card format:** a level may carry `"try": true` and its own
  `reproduce`.  `list` shows try-outs first under "Try the workflow";
  `info` says there are no pass/fail limits; VOLUNTEERS.md gets "Try the
  workflow first" after "Before you start" (the setup it needs) and
  before the five commands; a card with only try-out levels gets no
  case section.
- **`check`:** a try-out is compared with the card's reference after the
  schema, the mesh hash and `recompute`, and ends "accepted" with "a
  try-out: no pass/fail limits, nothing is stored".  `--merge` is
  refused before anything else.  `collect` says the file needn't be
  sent.
- **`_value`** shows hours under 1 as minutes ("3 min").
- **Found on the way:**
  - The contribution's `log_tail` was checkMesh's log for a case without
    `log.simpleFoam.all`: `_log_tail` took the first `case/log.*`
    alphabetically.  It now prefers `case/log.simpleFoam`.
  - The contribution schema requires `steps` and `converged`.  Poiseuille
    calls the first `iterations`; the bend's time-accurate record had
    neither (`transient_steps`, `settled`), so a level-3 contribution
    would have been rejected by `check` after days of running.  Both
    drivers now add them; a test builds a bend contribution from the
    stored level-2 run and checks it.
- **Measured here** (desktop, OpenFOAM v2406 in Docker, the image
  already pulled), with the tool's own commands: prepare 5.1 s, `bash
  job.sh` 7.9 s (2 processes), collect 2.0 s, check 0.9 s: 15.8 s in
  all.  The card states 3 min as a bound.  Disk 1.7 MB.  Peak memory is
  stated as an estimate (1 GB bound): the tool samples every 2 s, and
  saw 0.03 GB over a 6 s solve.
- **The tag:** the card names `volunteer-bend-1`, the tag still to come
  for the bend's card (task 0190), so one tag carries both.  If the user
  wants the try-out under another tag, only the card's `hexmesh.tag`
  changes.
- **Windows:** the native run in the user's Windows session is still to
  do.
- **For 0178:** the try-out is scriptable as the task asks: `prepare
  poiseuille try_np2 --dir D --runner R`, `run D`, `collect D --out O
  --delete`, `check O/poiseuille-try_np2.contrib.json`; each exits
  non-zero on failure, and `check` exits 0 only on "accepted".

## Questions for design

## Outcome

- **Files:** `validation/poiseuille/run.py` (`setup_case`,
  `level_values`, the hooks), `validation/poiseuille/volunteer.json`
  (new), `validation/volunteer.py` (try-out levels in `check`, `collect`,
  `list`, `info`, VOLUNTEERS.md; `_log_tail`; `_value` in minutes),
  `validation/turbulent_bend/run.py` (`steps`, `converged`),
  `validation/VOLUNTEERS.md` (regenerated), README, CHANGELOG,
  `tests/test_volunteer.py` (+9 tests).
- **Measured:** the try-out end to end in 15.8 s here (prepare 5.1, job
  7.9, collect 2.0, check 0.9); dp on 2 against 1 processes +7e-11.
- **Tests:** the full suite, 4 780 passed and 18 skipped (57 min, 2
  workers).  An earlier run was stopped by the machine's low memory.
- **Surprises:** two bugs any real contribution would have hit (the log
  tail, and the bend's missing `steps`/`converged`); see the notes.
- **Follow-ups:** the Windows run's time here when the user reports it;
  `prepare --dir a/b` with no `a` (task 0190's notes).
