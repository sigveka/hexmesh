# 0185 — Every level in `results.json` records how long its run took

- **Status:** done (2026-11-20)
- **Decision:** [0044](../decisions/0044-volunteer-runs.md), note of
  2026-11-19
- **Depends on:** 0184 (done: the store already knows when a run starts).
- **Blocks:** none.  Worth landing before 0050's long runs.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0184 could check a level's commit stamp only for levels
that record their length (`helical_pipe` n_arc 24, merged volunteer
levels).  The user (2026-11-19): "add how long the run took to each
level".  It also gives the cards and RESULTS.md measured costs instead
of estimates.

**Do.**
1. **`validation/tools/results.py`:** `Store.put` adds `wall_s` to the
   level: seconds from the level's start to the write.
   - **The level's start:** the later of the store's start (0184) and
     the previous `put` in this process.  Or add `Store.begin(level)`
     for drivers that do other work between levels.  Choose the form
     that needs fewest driver edits, and say which in *Agent notes*.
   - If `values` already has `wall_s` (helical's resumed levels), keep
     it.
   - Use `time.monotonic()`, not the date.
2. **`cores`:** where a driver knows the MPI process count of the solve,
   pass it (a keyword on `put`, or in `values`).  Don't guess it for
   drivers that don't.
3. **`solve_s`, optional:** for OpenFOAM drivers that already read the
   log, sum `ClockTime` the way volunteer `run` does (0044's earlier
   note, rule 3).  Share the helper rather than copy it.  Skip drivers
   where this isn't simple, and list them.
4. **Volunteer merges:** unchanged (they carry `wall_s`, `cores`, peak
   memory already).  Check the field names match the store's, so a
   level reads the same whoever ran it.
5. **Readers:**
   - the summary (`validation.tools.summary`) and the cards (0179, if
     landed) may show `wall_s` where present.  Don't add columns to the
     README table unless they fit; a line in each RESULTS.md is enough.
   - `hexmesh/agent/validation.json`: include it only if the generator
     already carries per-level fields.
6. **Tests** (no OpenFOAM):
   - a fake driver puts two levels with a monkeypatched clock: each gets
     its own `wall_s`;
   - a supplied `wall_s` survives;
   - a level written without the field still loads (version 1).
7. **Records:** no rerun and no guesses.  Where a task's notes give a
   level's run length (0162's nutk run: 3 h 46 min; others you find),
   you may add `wall_s` by hand, with the source in the commit message.
   List what you filled.
8. CHANGELOG *Unreleased*: one line.

**Accept.**
- New levels from every `Store`-based driver carry `wall_s`.
- `cores` and `solve_s` where stated above.
- The tests pass, the format stays version 1, and the full suite passes.

**Out of scope.**  Peak memory for maintainer runs (volunteer `run`
measures it; reusing that here is a follow-up if wanted); timing per
solver chunk.

## Agent notes

- **The start (step 1):** both forms.  The store's construction and
  every `put` begin the next level, and `Store.begin()` restarts the
  clock; `run_level` calls it before running a level, so reused levels
  and work between levels don't count.  No driver on `run_level` needed
  an edit for `wall_s`.  The three drivers that call `put` themselves
  in a loop (SU2, code_saturne; FEniCSx's levels pair two solves per
  mesh and are left on "since the last put") call `begin()`.
- **Only full levels are timed.**  A level filled from RESULTS.md
  (`rounded`) gets no `wall_s`: its run wasn't measured.
- **`cores`:** a `cores=` keyword on `put` and `run_level`; without it,
  the level's own `n_proc` (heated_pipe, stenosis, rect_duct,
  stenosis_pulsatile put one).  Passed from turbulent_pipe, square_bend,
  junction_loss, mms, womersley and turbulent_bend (`--np`), SU2 (its
  OpenMP threads) and code_saturne (1).  Not stated, so absent:
  helical_pipe (its mapped levels run partly from another level's case),
  poiseuille, heated_rod, layered_conduction (serial, but the driver
  doesn't say so), FEniCSx.
- **`solve_s` (step 3):** `results.clock_s(*logs)`, each log's last
  `ClockTime`.  The task's pointer was wrong: volunteer `run` measures
  `wall_s` with `time.monotonic()` and never reads `ClockTime`, so there
  was no helper to share.  Used in turbulent_bend (its precursor and
  bend logs).  **Skipped**, for a follow-up: the other OpenFOAM drivers
  (poiseuille, heated_rod, layered_conduction, heated_pipe, womersley,
  stenosis, stenosis_pulsatile, rect_duct, mms, turbulent_pipe,
  square_bend, helical_pipe, junction_loss): each keeps its logs in a
  different shape (one per phase, per period, per region), so each
  needs its own few lines.
- **Volunteer merges (step 4):** the merge called `put` in the checking
  process, which would have stamped the check's seconds.  It now passes
  the contribution's `run.wall_s` and `run.cores`; the names match the
  store's.
- **Readers (step 5):** nothing changed.  The summary and the agent
  manifest carry no per-level fields, and 0179's cards haven't landed.

## Questions for design

## Outcome

- **Verified in CI:** run 44716344111 at f268501, green on all 8 jobs,
  promoted (the full suite here was stopped for low memory; the first
  push, run 44694117515, failed on a stale agent manifest from tasks
  0050/0181/0183, fixed in f268501).
- **Files:** `validation/tools/results.py` (`Store.begin`, `put`'s
  `wall_s`/`cores`, `run_level(cores=)`, `clock_s`),
  `validation/results.schema.json` (the three fields, optional),
  `validation/volunteer.py` (the merge), `cores=` in six drivers,
  `validation/junction_loss/results.json` (filled by hand, below),
  CHANGELOG.
- **Tests:** four new in `tests/test_validation_meta.py` (two levels
  with a fake clock; a supplied `wall_s` kept and a rounded level
  untimed; a level without the fields still validates and loads;
  `clock_s`).  `test_validation_meta` (the store tests),
  `test_volunteer` and `test_study`: pass (83 in the last two).  The
  full suite: see below.
- **Filled by hand (step 7), from task 0162's notes, all on 3
  processes:** `div_a_q0.6_k2_rke_nutk` 13 560 s ("3 h 46 min", Q4's
  answer), `div_a_q0.6_k1` 1 980 s and `div_a_q0.6_k3` 51 060 s ("Run
  cost: k = 1 33 min, … k = 3 14 h 11 min").  Not filled: 0162's k = 2
  ("about 4 h"), and set totals that name no level (0049 "2 h 50 min",
  0075 "about 2 h 45 min", 0074 "4 h 10 min").
