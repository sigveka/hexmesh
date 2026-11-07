# 0066 — Network interchange, stage 1b: select, cut, join, merge, and the public API

- **Status:** done
- **Decision:** [0032 — Network interchange](../decisions/0032-network-interchange.md) (items 3 and 6)
- **Depends on:** 0065.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user wants networks that "one can break and reconstruct
as needed": cut a plant model at a valve, split a duct system per
floor, join two isometrics at their shared end, all without
re-importing.

**Where.**  `hexmesh/interchange/model.py` (operations), `build.py`
(selections), tests, `API.md`, `README.md` ("Reading plant data").

**Do.**
1. **select:** `model.select(parts=…, network=…, from_port=…,
   up_to=…)` → a selection (the parts reachable from a port, stopping at
   given ports or parts; a named network; an explicit set).  `build`
   takes it.  Open ports at the selection's boundary become open ends,
   named from the port (its tag, or a stable generated name).
2. **cut:** `model.cut(connection)` or `model.cut_at(port)`: remove a
   connection, or split a port into two, so both sides become open ends.
   Names follow the same rule; the cut is recorded (so a document shows
   it, stage 2).
3. **join:** `model.join(port_a, port_b, *, tol)`: connect two open
   ports.  Check position, direction (opposed) and section; reject with
   the numbers otherwise.  Origin "declared" (by the user).
4. **merge:** `NetworkModel.merge(a, b)`: union of two models; ids kept,
   clashes reported (or prefixed on request).  Connections between them
   are added with `join`, or inferred on request with the tolerance rule.
5. **Operation log** (decision 0032, settled 2026-10-29):
   - `cut`, `join` and `merge` change the model in place and append an
     entry to `model.log`: operation, arguments by id, time, hexmesh
     version.  The importer writes the first entry (importer, source,
     options).
   - `model.replay(source_model)` re-applies a log; `model.undo()`
     replays all but the last entry.
   - Selections aren't logged; `build` records the selection in the
     assembly's provenance.
6. **Public API quality:** docstrings with examples, `API.md` section,
   stable names (decision 0019, constraint 4), structured errors naming
   ports and parts by id and provenance.

**Accept.**
- A PCF fixture with a valve: cut at the valve → two selections → two
  assemblies that mesh; joining them back reproduces the original
  build (`to_dict()` identical).
- Two PCF files of one line, read separately, merged and joined at their
  shared end, build the same assembly as reading both together.
- A selection from a port with `up_to` builds only the expected parts.
- `join` rejects a direction or section mismatch with the numbers.
- **The `hexmesh` CLI reads PCF** (task 0098, Q5): once the readers are
  in `interchange.importers`, `hexmesh validate | estimate | describe |
  preview | advise | build` accept a `.pcf` file with `--spec`.  The
  `cli_input_unreadable` error for PCF goes.  No new architecture edge.
- **Log:** after cut + join, the log has three entries (import, cut,
  join); replaying it on a fresh import gives an identical model;
  `undo()` after the join restores the cut state.
- Full suite: no new failures.

**Out of scope.**  The JSON-LD document (stage 2: cut and join are
recorded in the model now, serialised later); cross-document
references.

**Design note (2026-11-02, decision 0037 items 4–5; DESIGN §3.1).**  Two
additions while you're in the interchange:
1. **Readers move to `hexmesh.interchange.importers`** (decision 0032
   §8).  Today `io.readers` imports `interchange.build`, which puts
   `io` on both sides of the assembly.
   - Keep `hexmesh.io.readers` as a re-export, since it's public in
     API.md ("Readers"): plain re-export, no warning yet.
   - Update API.md's heading to name the new home.
   - Remove the `io.readers` → `interchange` entry from
     `tests/test_architecture.py`'s allowlist (task 0081, if done).
2. **Split `interchange/build.py` along its concerns** as you add the
   selections: parts-graph analysis (pieces, tree checks, roots, ends),
   insulation planning, and the mapping to fittings.  No behaviour
   change in the split itself; keep it a separate commit from the
   operations.

Both are covered by the existing "no behaviour change" method (task
0065).  If they make this task too large, do them as a separate task
right after it and say so in *Outcome*.

## Agent notes

- **The builder connects ports by position.**  `Connection`s were
  recorded but never read.  So a cut must reach the builder's graph:
  - `graph._graph` and `graph._pieces` skip a pair of points that a
    `model.cuts` entry separates.  They key on the two parts and the cut
    ports' positions, which also covers a host straight split around a
    tap.
  - If the other points there still join the two sides, `_graph` raises
    `model_cut_bypassed`.  That happens at a zero-length weld, where
    three ports meet; `cut_at` cuts every pair.
- **`join` requires the builder's tolerance.**  It accepts a wider
  `tol=`, but the builder joins only within its own tolerance, so a
  wider join needs `build(..., tol=...)` too.  This is documented.  The
  builder doesn't join declared connections beyond its tolerance, since
  placement would reject the gap anyway.
- **Ports aren't shared between parts** in this model: each part has its
  own, and neighbouring ones coincide.  So "split a port into two" is
  `cut_at(port)`, which cuts the port from every port it meets.
  `Port.tag` was added, so that `names=` can name both new open ends.
- **Names:** an open end at a cut, or where a part outside the selection
  meets the ones built, is named by its `tag`, or `<network>_<port id>`.
  It isn't counted in `<network>_end<k>`.  Builds without cuts or
  selections name exactly as before; the 43 test PCF fixtures are
  unchanged.
- **The selection's provenance:** the `Assembly` has no provenance field
  (`Edge.origin` is diagnostic and never saved).  So `build` records the
  selection in `model.report["selection"]` (parts and how), and the
  acceptance's identical `to_dict()` holds.
- **The log:**
  - `import_entry` writes `{op: "import", args: {importer, source,
    options}}`, with `read_pcf`'s arguments as given.
  - `merge` stores the other model's whole log.  `replay` re-reads it
    through `model.IMPORTERS`, a registry like `FORMATTERS`: PCF
    registers one, bathymetry logs its import but registers none.
  - `undo` keeps the state from before the first logged operation and
    replays all but the last entry onto a copy of it.
- **The merge acceptance needs identified components.**  PCF labels
  without `COMPONENT-IDENTIFIER` count per type within a file
  (`PIPE_1`, …).  Two sheets read separately then label differently from
  one read of both, and labels are in `to_dict()`.  The test's sheets
  carry `COMPONENT-IDENTIFIER`, as real isometric sheets do.  This is
  stated in the GUIDE.
- **`io.readers` → `interchange` stays in `ALLOWED_EDGES`.**  The design
  note asked both to keep `hexmesh.io.readers` as a re-export and to
  remove that edge, and a re-export is that edge.
  - The modules are now `sys.modules` aliases of the importers, so
    `hexmesh.io.readers.pcf is hexmesh.interchange.importers.pcf`.
  - A new test (`test_io_readers_only_re_export`) checks they hold no
    code of their own.
  - The edge's reason says so.  The edge can go when the re-export
    does (a deprecation is design's call).
- **The CLI's `--spec`** is a `PipeSpec` description, or a list of
  `{"nominal", "spec"}` per size.  A size the list lacks is the new code
  `cli_spec_size_missing`.
- **The helical-pipe driver** (task 0075, Q5) was prepared in the same
  session, on the user's request.  Commit 8b863f0, separate from this
  task.

## Questions for design

_None._

## Outcome

**Done.**

**Commits:**
- 9370c9b: readers moved to `interchange.importers`; the CLI reads PCF;
- e9236ca: `build.py` split into `graph.py` (the parts graph, pieces,
  roots, open ends) and `insulation.py` (planning).  No behaviour
  change: all 43 test PCF fixtures, with and without insulation, give
  identical `to_dict()` or errors before and after;
- the operations commit.

**Files:**
- `hexmesh/interchange/` (`operations.py` and `importers/` new; `model.py`,
  `graph.py`, `build.py`, `__init__.py`);
- `hexmesh/io/readers/` (re-exports);
- `hexmesh/agent/cli.py`, `hexmesh/errors.py` (14 codes);
- tests: `test_interchange_operations.py` (new, 9),
  `test_agent_advise.py` (the CLI PCF test replaces the "waits" test),
  `test_architecture.py` (+1), `test_interchange.py`;
- `API.md`, `docs/GUIDE.md`, `CHANGELOG.md`.

**Acceptance:**
- The valve fixture, cut at the valve, gives two selections and two
  assemblies.  Both validate and mesh with hexes = predicted.  Joining
  them back reproduces the original `to_dict()`.
- Two sheets read separately, merged (`prefix=`) and joined, build the
  same assembly as one read of both files.  The same holds with
  `infer=True` instead of the join.
- `select(from_port=…, up_to=[elbow])` builds pipe, valve, pipe and
  elbow only.  A port in `up_to` isn't crossed.
- `join` rejects a gap (0.01 m), a direction (180°) and a section
  (0.1 against 0.05), each with the numbers.
- The CLI reads a `.pcf` with `--spec`, and its validate, estimate and
  describe results equal those of the saved assembly.
- After cut + join, the log has three entries.  Replaying it on a fresh
  import gives an identical model, and `undo()` after the join restores
  the cut state.

**Suite:** 3562 passed, 15 skipped, no failures (19 min).

**Surprises:**
- Connections were never used for connectivity (see the notes).
- The design note's re-export and edge removal conflict.

**Follow-ups (proposed):**
- Stage 2's JSON-LD document should serialise `cuts`, `log` and
  `Port.tag`.  The log is plain data already.
- Whether to deprecate `hexmesh.io.readers`, which would remove the last
  allowed edge.
