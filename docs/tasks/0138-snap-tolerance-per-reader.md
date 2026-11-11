# 0138 — The snap tolerance: one per reader, carried by the model, and documented

- **Status:** ready
- **Decision:** task 0128's design answer (2026-11-11, Q2, revised the same day); [0018](../decisions/0018-future-vascular-networks.md) (constraint 8); [0032](../decisions/0032-network-model.md)
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

## Questions for design

## Outcome
