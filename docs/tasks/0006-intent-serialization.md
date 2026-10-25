# 0006 — Save and load the network description (Intent layer)

- **Status:** done
- **Decision:** [0001 — Complete A5/A7 in the assembly prototype](../decisions/0001-complete-assembly-prototype.md)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  DESIGN §3 defines the Intent layer as a graph, but today it only
exists as a sequence of `Assembly.add()` calls.  A serialized form enables
parametric studies, plant-data readers (DESIGN §10) and reproducible test
cases.

**Where.**  `Assembly.add` (`assembler.py:93`), `Edge`, `Interface`; fitting
dataclasses in `assembly/fittings.py` and `assembly/tee.py`; `PipeSpec` in
`core/spec.py`.

**Do.**
1. Add `Assembly.to_dict()` and `Assembly.from_dict(d)` (plain
   JSON-serializable data):
   - inlet pose and spec
   - an ordered edge list: fitting type name, dataclass fields, source
     interface index, outlet names
   - loop closures (`close()` calls).
2. Use a small explicit registry mapping type names to classes; no
   plugins or entry points (DESIGN §6.1 "not built on speculation").
3. `PipeSpec` needs `to_dict()`/`from_dict()`; include layer names, radii,
   `nrad`, `mprg`, `n_outer`, `rot` and `nang`.
4. Units: document that lengths are in the user's unit and unconverted.

**Accept.**
- Round trip for every conformance-kit case:
  `from_dict(to_dict(a))` produces identical interface frames and an
  identical mesh (node count, element count, physical group names).
- The JSON file is human-readable (indented, sorted keys).

## Agent notes

- **Format** (`hexmesh/assembly/intent.py`, `format: "hexmesh.assembly"`,
  `version: 1`):
  - `inlet`: `position`, `normal`, `up`, `spec`, `name`;
  - `edges` in creation order.  Each holds `fitting` (`type` plus every
    dataclass field) and either `source` (interface index), or `close`
    (`[source, target]`) for a `close()` call;
  - optional `names` (outlet interface names);
  - `tail`, and `lc` if set.
- **Replay, not geometry.**  `from_dict` calls `add` / `close` in order,
  so the interfaces are recreated in the same order and indices are
  stable.  Outlet frames are derived from the fittings, so editing one
  fitting moves everything downstream (tested).
- **Frame overrides.**  The kit case `straight-rolled-90` sets
  `outlet.frame` by hand after `add()`, which `add` does not record.
  `to_dict` compares each outlet frame with the fitting's `ports()`
  result and stores only the ones that differ, under `frames`.
- **Exactness.**  Frames are rebuilt with `Frame(...)` directly, not
  `Frame.from_vectors`, so they are bit-identical after JSON (Python's
  float repr round-trips).  `PipeSpec.to_dict` stores the resolved
  `mprg`, so `first_cell=` specs reload with the same grading.
- **Registry.**  `FITTING_TYPES` is a plain dict of the eight fitting
  classes.  An unknown type or an unknown field raises `ValueError`;
  missing fields take the dataclass defaults.
- **PipeSpec** `to_dict` / `from_dict` cover:
  - `nang`, `nang_w`, `nang_h`, `mbmp`, `rot`, `n_outer`;
  - the core: name, shape (circle or rect), `nrad`, `mprg`;
  - shells: circular, and `square_shell`.
- **Files:** `Assembly.save(path)` / `Assembly.load(path)` write and read
  indented JSON with sorted keys.

## Questions for design

1. **Absolute or relative nodes?**  DESIGN §3 describes the Intent layer
   as a graph whose nodes have absolute positions.  This format stores
   only the inlet pose absolutely; every other interface follows from
   replaying the fittings.  That gives exact round trips and makes edits
   propagate downstream, which suits parametric studies.  A plant-data
   reader, however, produces absolute nodes, and those currently pass
   through `NetworkSpec.to_assembly`.  Should the file also carry each
   interface's absolute frame, as a check on load or as the authority?
   Not blocking.
2. **Hand-set frames.**  Is setting `outlet.frame` after `add()` a
   supported operation?  Only the kit uses it, to test corner rolls.  If
   it is not supported, `frames` overrides could be dropped from the
   format.

## Outcome

- **Files:**
  - new `hexmesh/assembly/intent.py`;
  - `assembly/assembler.py`: `to_dict`, `from_dict`, `save`, `load`;
  - `core/spec.py`: `PipeSpec.to_dict` / `from_dict`;
  - new `tests/test_intent.py` (32 tests);
  - docs: `API.md`, `README.md`.
- **Accept:** all 25 conformance-kit cases round trip through JSON:
  - identical `to_dict`;
  - bit-identical interface frames, with the same names and specs;
  - identical node count, element counts (2-D and 3-D) and physical
    group names after meshing.

  All eight shipped examples round trip, with identical cell counts.
- **Tests:** 434 passed, 0 failed.
