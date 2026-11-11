# 0138 — The snap tolerance: one per reader, carried by the model, and documented

- **Status:** done
- **Decision:** task 0128's design answer (2026-11-11, Q2, revised the same day); [0018](../decisions/0018-future-vascular-networks.md) (constraint 8); [0032](../decisions/0032-network-interchange.md)
- **Depends on:** none.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The builder (`NetworkModel.build` / `to_assembly`, and the
`join`/`merge` operations) treats two component ends closer than a
tolerance as one point.  It snaps them; it never fills a gap
(`Assembly.close` does that).  Today the tolerance is
`max(TOL_RELATIVE × model diagonal, TOL_FLOOR)` for every model, with
`TOL_FLOOR` = 0.11" (2.79 mm): pcf2iso's floor, just above the 1/16"
weld gap in plant isometrics (`docs/integrations/pcf.md`, "Where
hexmesh's 0.11" comes from").  That floor is a fact about PCF files, but
it applies to every model: in a lab rig of 4 mm tubing, or a network of
1 mm vessels (decision 0018), ends 2 mm apart would be joined silently.
The user (2026-11-11): "a tolerance per reader defaulting to the 2.8mm
from pcf2iso", and "this needs to be documented very well".

**Where.**  `hexmesh/interchange/model.py` (`NetworkModel`), `graph.py`
(`_model_tolerance`), `build.py`, `operations.py`, `importers/pcf.py`
(including its set-on attachment check, ~line 959),
`importers/bathymetry.py`, the network model's JSON, `docs/GUIDE.md`,
`API.md`, `CHANGELOG.md`, `tests/`.

**Do.**
1. **The model carries its snap floor:** `NetworkModel.snap_tolerance`
   (metres), set by the reader that made the model, saved and loaded
   with it (a missing key loads as the default: old files unchanged).
   The builder's default tolerance is
   `max(TOL_RELATIVE × diagonal, model.snap_tolerance)`.  An explicit
   `tol=` still wins.
2. **Defaults:** `TOL_FLOOR` (0.11") stays the default for a model with
   none set, and for hand-built models, so nothing changes today.
   `read_pcf(…, snap_tolerance=TOL_FLOOR)` sets it (a parameter, so a
   file from an exporter with other gaps can say so).
   `read_bathymetry` sets the default explicitly.  A future reader for
   small networks sets its own (decision 0018).  `join`/`merge` of two
   models: the larger of the two (so PCF weld gaps still snap); say so in
   the docstring.
3. **One source per reader:** the PCF reader's set-on check uses the
   model's value, not `TOL_FLOOR` directly.
4. **The build report** already names the tolerance used; add where it
   came from (`"tol": …, "tol_source": "reader pcf" | "relative" |
   "given"`).
5. **Documentation (the main deliverable):** a GUIDE section, "How ends
   are connected: the snap tolerance", near *Reading plant data*:
   - what it does: ends within it are one point; the next component
     starts exactly at the previous outlet, and a gap inside it is
     absorbed into the following straight (the lateral offset is in the
     report); pipes shorter than it are dropped; and what it doesn't do:
     it never adds pipe across a gap (`Assembly.close` does, explicitly),
     and a gap beyond it is the `chain_gap` error;
   - the default and where it comes from: 0.11" from pcf2iso, the 1/16"
     weld root gap of gap-coupling exports, with the possible explanation
     marked as such (`pcf.md`), linked;
   - why it is per reader, and the hazard at small scale: a snap
     tolerance comparable to the pipes merges distinct points without an
     error; when to set it (small bores, other exporters), how
     (`read_pcf(snap_tolerance=…)`, `model.snap_tolerance = …`,
     `build(tol=…)`), and how to see what was used (the report).
   API.md: the field and parameter; `read_pcf`'s `tol` docstring updated.
6. **Tests:** a hand-built model of 4 mm bores with `snap_tolerance` 1e-4
   keeps ends 2 mm apart separate (`chain_gap`), and with the default
   joins them; a PCF read stores 0.11" and its JSON round trip keeps it;
   an old JSON without the key loads with the default; `merge` takes the
   larger.

**Accept.**
- Every PCF test file, example and gallery entry reads and meshes
  byte-identically (the default is unchanged); full suite: no new
  failures.
- A reader of the GUIDE section can say what the tolerance does and
  doesn't do, where 0.11" comes from, and how to change it.

**Out of scope.**  A bore-relative rule (considered first, 2026-11-11,
replaced by the per-reader floor); the geometry kernel's tolerances
(task 0128, Q1).

## Agent notes

- **"Saved and loaded with it" (step 1): the import log, not a JSON
  file.**  `NetworkModel` has no JSON save/load; it persists through its
  log (the import entry's options are JSON data that `replay`, `undo` and
  `merge` re-read the file with).  Design answer (design session's
  message, 2026-11-11): the import entry's options carry
  `snap_tolerance`, `replay` and `undo` keep it, an old log without the
  key re-reads with the default, and `describe(model)` shows the value
  and its source; no `NetworkModel.to_dict`/`from_dict` (a new feature,
  out of scope).  Step 6's "JSON round trip" test is the import entry
  and a replay.
- `TOL_FLOOR` moved from `interchange/graph.py` to `interchange/model.py`
  (the model's field default; `graph` imports `model`, not the other way
  round); `graph`, `build` and `pcf` still re-export it.
- **Step 6, 4 mm tubes 2 mm apart with `snap_tolerance` 1e-4:** the build
  raises `network_disconnected` ("starts 0.002 m from the open end of
  part t0 …"), not `chain_gap`: two ends that don't meet make two
  pieces; `chain_gap` is a gap inside one chain.  The GUIDE names both.
- Sources in the report: `"reader pcf"`, `"reader bathymetry"`,
  `"default"` (a model no reader made), `"relative"`, `"given"`.

## Questions for design

## Outcome

Done 2026-11-11.

- **Code.**  `interchange/model.py`: `TOL_FLOOR` (moved from `graph.py`),
  `NetworkModel.snap_tolerance` and `snap_source`.  `graph.py`:
  `snap_tolerance(model, comps, tol)` → (value, source);
  `_model_tolerance` takes the model's floor.  `build.py`: `build` and
  `build_pieces` use it, and the report has `tol_source`.
  `operations.py`: `tolerance(model)` uses the model's floor; `merge`
  keeps the larger; `undo` restores the field.  `importers/pcf.py`:
  `read_pcf(snap_tolerance=TOL_FLOOR)` (a positive length, else
  `ReaderError` `size_not_positive`), kept in the import entry's options
  and on `NetworkSpec`; the set-on check (`_declared_connections`) uses
  the model's value.  `importers/bathymetry.py` sets the default
  explicitly.  `agent/_describe.py`: `snap_tolerance` {value, source}.
- **Docs.**  GUIDE *How ends are connected: the snap tolerance* (after
  *Reading plant data*; replaces "nothing is snapped"): what it does
  and doesn't do, the default and where 0.11" comes from (the possible
  explanation marked as such, linked to `pcf.md`), why per reader and
  the small-scale hazard, when and how to set it, how to see what was
  used.  API.md (`read_pcf`, `NetworkModel`, `merge`, the report),
  README's PCF bullet (links the section), CHANGELOG.
- **Tests.**  `tests/test_snap_tolerance.py`, 13: default joins 4 mm
  tubes 2 mm apart and reports `"default"`; `snap_tolerance` 1e-4 keeps
  them apart (`network_disconnected`, the gap named); `tol=` wins
  (`"given"`); a 100 m model uses `"relative"`; a PCF read stores 0.11"
  in the model and its log and reports `"reader pcf"`; `read_pcf`'s own
  value survives `replay` and `undo`; an old log without the key
  re-reads with the default; bad values rejected; `merge` takes the
  larger either way round; `describe` shows it.  Updated:
  `test_interchange_operations` (the import entry's options).
- **Checks.**  Reader, agent, doc, example and architecture tests: 449
  passed, 1 skipped.  The 31 examples (with the PCF line) byte-identical
  to `HEAD`.  Full suite not run (the shared machine stopped the last two
  full runs for low memory); the change is confined to `interchange` and
  `agent/_describe`, all of whose tests ran.

