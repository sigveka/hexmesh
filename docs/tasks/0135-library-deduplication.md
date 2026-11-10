# 0135 — De-duplicate four repeated blocks in the library

- **Status:** ready
- **Decision:** DESIGN §3.1 ("one description per concept"); [0042](../decisions/0042-road-to-1-0.md) (before the 0.8 API review)
- **Depends on:** none.  Don't run alongside a task editing the same
  files (`tee.py`, `wye.py`, `switch.py`, `fittings.py`, `duct_tap.py`):
  coordinate in the shared tree.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The architecture review (2026-11-10) scanned the library for
repeated runs of six or more statements: 19 runs, 234 lines (0.9 %),
about 140 of them the two probes (task 0134 removes one).  Four repeats
are real code that would drift if one copy is fixed:

1. **Port-frame matching:** `Tee.validate`, `Wye.validate` and `Switch`
   repeat "the expected port frames equal the given ones, to 1e-9"
   (`tee.py` ~778, `wye.py` ~586, `switch.py`).
2. **`Reducer` and `Transition`:** identical `ports()` and the start of
   `check()` (`fittings.py` ~731 and ~884): the outlet frame one length
   along the axis, and the positive-length check.
3. **`duct_tap.py` ~242 and ~439:** the same 16 lines building the ring
   edges and port slabs in two tap layouts.
4. **Positive-size checks:** "must be positive, got …" with
   `size_not_positive` is hand-written at 17 sites in 9 modules, while the
   same bound is declared in the field's metadata (`core.params.param`,
   `exclusiveMinimum=0`).  `test_schema_ranges_are_enforced` keeps them
   consistent.

**Where.**  `hexmesh/assembly/{tee,wye,switch,fittings,duct_tap}.py`,
`hexmesh/core/params.py` (item 4 only), `tests/`.

**Do.**
1. Items 1–3: one helper or shared base each, in the module that owns the
   concept (a junction port-frame check beside the junction contract; a
   shared base for the two-port straight-axis fittings in `fittings.py`;
   a layout helper in `duct_tap.py`).  Every error's message, code,
   `where`, `value` and `limit` unchanged.
2. Item 4: evaluate generating the positive-size check from the field
   metadata (one function that checks a dataclass's `exclusiveMinimum` /
   `minimum` fields and raises the existing coded error).  Do it only if
   every message, code and `where` stays identical (tests that match
   messages pass untouched).  Otherwise list the sites that differ under
   *Agent notes* and leave them.
3. **Check:** the duplicate scan again (runs of ≥ 6 normalised
   statements, comments and docstrings ignored): report before/after in
   *Outcome*.

**Accept.**
- Meshes byte-identical for every example; error payloads unchanged;
  full suite: no new failures.

**Out of scope.**  `build_oh_circle8` (task 0088 replaces it); splitting
`Assembly` (task 0136); behaviour changes.

## Agent notes

## Questions for design

## Outcome
