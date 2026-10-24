# 0006 — Save and load the network description (Intent layer)

- **Status:** ready
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

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
