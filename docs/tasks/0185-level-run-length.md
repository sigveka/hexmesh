# 0185 — Every level in `results.json` records how long its run took

- **Status:** ready
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

## Questions for design

## Outcome
