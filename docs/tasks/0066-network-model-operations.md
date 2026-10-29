# 0066 — Network interchange, stage 1b: select, cut, join, merge, and the public API

- **Status:** ready (after 0065)
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
- **Log:** after cut + join, the log has three entries (import, cut,
  join); replaying it on a fresh import gives an identical model;
  `undo()` after the join restores the cut state.
- Full suite: no new failures.

**Out of scope.**  The JSON-LD document (stage 2: cut and join are
recorded in the model now, serialised later); cross-document
references.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
