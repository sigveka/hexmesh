# 0176 — A try-out volunteer card: the whole workflow in a minute or two

- **Status:** ready
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
generator of VOLUNTEERS.md); the card format, `.github/workflows/
tests.yml` (the OpenFOAM Docker job); `tests/test_volunteer.py`;
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
7. **CI:** the OpenFOAM Docker job runs the try-out end to end
   (`prepare`, `run`, `collect`, `check`) in a temporary directory, and
   fails on anything but "accepted".  Give its time in the job.
8. **Tests** (fast, no OpenFOAM): the card validates; `list` puts the
   try-out first; `--merge` of a try-out contribution is refused; a
   tampered try-out file is rejected as for a real level.
9. CHANGELOG: one line.

**Accept.**
- The try-out runs end to end here and in CI, in about 2 minutes or
  less (measured, stated), and `check` says "accepted".
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

## Questions for design

## Outcome
