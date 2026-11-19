# 0184 — `results.json` records the code that ran: the environment taken at the start of a run

- **Status:** in progress
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

- **Step 1** (2026-11-19): `Store(…)` takes it on construction
  (`self.start = started()`), so no driver changed: every driver makes
  its store in `main`, after `set_runner` and before meshing.
  `started()` is what can move under a run: the hexmesh commit and
  `+local`, gmsh, Python and the date.  `put()` adds the runner's
  OpenFOAM version and name when it writes (`environment(self.start)`):
  they don't move with HEAD, and probing them spawns the runner, which a
  store opened only to read (`volunteer check`, helical's reference)
  shouldn't do.  `environment()` with no argument is today's stamp of
  now, unchanged for the callers that want that.
- **Step 2:** `prepare` already stored `prepared` (versions and date),
  but after meshing; it now takes `started()` before `drv.prepare`.
  `collect` stamps `environment(state["prepared"])`: hexmesh, gmsh,
  Python and the date from `prepare`, the OpenFOAM version and runner
  from `collect` (as the runner reports them then; a comment says so).
  A directory without `prepared` gets today's, a note on stderr, and
  `run.environment_from: "collect"` in the contribution (`"prepare"`
  otherwise).  The field is optional in `contrib.schema.json`, so older
  contributions still pass `check`.
- **Step 3:** FEniCSx's `_environment(store)` is `store.start` with the
  image and `"runner": "docker"`; 0182 hasn't moved the case.
- **Step 4:** `Study.run` stamped at the end (`write_manifest` called
  `versions()`).  `run()` now takes `manifest.versions()` first and
  passes it to `write_manifest(study, rows, started=None)`; called
  without it, `write_manifest` takes them now, as before.  `study.json`
  keeps the same keys, so the public output's format is unchanged; only
  the moment differs.  `hexmesh.study` now has a `manifest` name (the
  submodule, so a test can patch `versions`); not in `__all__`, and
  `test_api_inventory` passes.

## Questions for design

## Outcome

- **Files:** `validation/tools/results.py` (`started()`,
  `environment(start)`, `Store.start`), `validation/volunteer.py`
  (`prepare` before meshing, `collect` from `prepare`),
  `validation/contrib.schema.json` (`run.environment_from`, optional),
  `validation/fenicsx_second_order/run.py`, `hexmesh/study/__init__.py`
  and `manifest.py`, `validation/README.md` (one phrase), CHANGELOG
  *Unreleased* (Fixed).
- **Tests:** 5 new, each moving HEAD during the run (a patched
  `versions()`):
  - a level: `test_validation_meta`;
  - FEniCSx: `test_validation_meta`;
  - `prepare` then `collect`, and an older run directory:
    `test_volunteer`; the contribution is validated against the schema;
  - the study manifest: `test_study`.

  The two existing fakes of `environment` take the new argument.  Run
  locally, `-n 1`: `test_api_inventory`, `test_architecture`,
  `test_errors`, `test_validation_meta`, `test_volunteer` and
  `test_study` give 344 passed, 1 skipped (49 s); `test_readme` gives 13
  passed.  The full suite is left to CI.
- **Format:** `results.json` stays version 1, with the same environment
  fields; contribution version 1, with one optional field.
- **Step 6, levels that may be mis-stamped** (for the design session;
  no record changed).
  - Method: a level's `hexmesh` is HEAD when it was written, so the
    write fell between the stamped commit and the next commit on main,
    on the level's `date`.  A level is mis-stamped only if its run
    started before the stamped commit.  That needs the run's length, and
    only `helical_pipe`'s n_arc 24 levels record one (`wall_s`).
  - **helical_pipe re1800_n24 (4.97 h) and re2400_n24 (5.59 h):**
    stamped `c8c7c76+local`, committed 2026-11-07 21:51.  Both are dated
    2026-11-08, and the next commit came at 09:52, so they may have
    started before c8c7c76.  c8c7c76 changes `hexmesh/` only in
    `__init__.py`'s docstring, and not the helical driver, so the code
    was the same either way.  The `+local` mark (edits under `hexmesh/`
    at the write) can't be checked against the start from the record.
  - re3000_n24 (2.55 h, `c7a64b9+local`, 2026-11-18) was run on another
    machine (task 0173); its tree didn't move with this one.
  - junction_loss: 0162's own notes cover it.  k = 3 and k–ε carry
    972d9cb, checked against a frozen copy; the nutk level was set by
    hand to 1d5902c; k = 1 and 2 record None.
  - Every other level is minutes long (MMS, rect_duct, heated_rod,
    FEniCSx) or older than the shared-tree practice.  Each group's
    stamped commit and the code commits after it that day were listed;
    none implies a wrong stamp without a run length.
- **Surprise:** `prepare` already kept the environment; `collect` didn't
  use it.
- **Follow-ups:** none required.  A level could record its own
  `wall_s`, which would let step 6's check be made for every level.
  That is a new field, so it's for design (decision 0044's allow-list is
  out of scope here).
