# 0190 — The bend's level 3 as a volunteer card; does `ddtCorr` cause the algorithm spread?

- **Status:** ready
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

## Questions for design

## Outcome
