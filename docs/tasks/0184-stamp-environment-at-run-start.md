# 0184 — `results.json` records the code that ran: the environment taken at the start of a run

- **Status:** ready
- **Decision:** none needed (a fix to the provenance record of decisions
  0012 and 0044; the results format stays version 1)
- **Depends on:** none.
- **Blocks:** none.  Worth doing before 0050's long runs, so their levels
  are stamped right.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0162's k–ε run took 3 h 46 min.  Its level was stamped
with hexmesh ffbf6cd, a design-session commit made while it ran, not
1d5902c, the code that ran.  It had to be set by hand (0162 *Outcome*).

The cause: `Store.put()` calls `validation.tools.results.environment()`
when it writes, at the end of the level.  That calls
`hexmesh.study.manifest.versions()`, which reads `git rev-parse HEAD` and
`git status -- hexmesh` *then*.  The design and coding sessions share one
working tree (CLAUDE.md), so HEAD moves under long runs.  The `+local`
mark has the same problem: it reflects edits at the end, not at the start.

The same pattern is in:
- `validation/volunteer.py` `collect`: `stored.environment()` when
  the contribution is collected, possibly days after `prepare`;
- `validation/fenicsx_second_order/run.py`: its own `_environment()` at
  write time.

**Do.**
1. **Take the environment once, at the start.**
   - In `validation/tools/results.py`, a run's environment is taken
     when the driver starts, before meshing or solving.  Either
     `Store(…)` takes it on construction, or a module-level
     `start_environment()` is called once from each driver's entry.
   - `put()` uses that unless `env=` is given.  Choose the form that
     touches fewest drivers.  `rg "Store\(" validation` lists them; there
     are about 16.
   - The date stays the run's start date.  If an end date or the wall
     time is wanted, add it as a separate field, not by moving `date`.
2. **Volunteer runs:**
   - `prepare` records the environment in the run directory's state;
   - `collect` stamps that one.  Keep `collect`'s own values only for
     what `prepare` can't know, such as the OpenFOAM version the runner
     reports at solve time.  Say which in the code.
   - Older run directories without the stored environment fall back to
     today's behaviour, with a note in the contribution.
3. **FEniCSx:** use the shared helper rather than its own `_environment()`,
   or take it at start the same way.  If 0182 has moved the case, do it
   there.
4. **The study manifest** (`hexmesh/study/manifest.py`, `versions()`
   inside `write_manifest`): check whether `Study.run` stamps at the end
   too.  If it does, take it at the start the same way.  If changing it
   touches the public study output, write it under *Questions for
   design* instead.
5. **Tests** (no OpenFOAM):
   - a fake driver starts, a commit is made in a temporary git repository
     (or `versions()` is monkeypatched to change between calls), then
     `put()` writes;
   - the level carries the start value;
   - the same for `prepare` and `collect`.
6. **Records:** correct no existing `results.json` by script.  0162's
   level is already right by hand.  If other long levels may be
   mis-stamped, list them in the *Outcome* with the evidence (the commit
   date against the level's date), for the design session.  CHANGELOG
   *Unreleased* (Fixed): one line.

**Accept.**
- A level, a volunteer contribution and the FEniCSx results are stamped
  with the commit and `+local` state from the start of their run.
- The tests above pass, and the full suite passes.
- The format stays version 1.

**Out of scope.**  Recording the full diff for `+local` runs; changing
which fields the environment holds (decision 0044's allow-list).

## Agent notes

## Questions for design

## Outcome
