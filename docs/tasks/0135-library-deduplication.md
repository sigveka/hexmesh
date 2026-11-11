# 0135 — De-duplicate four repeated blocks in the library

- **Status:** done
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

- **Item 1:** `interface.check_port_frames(fitting, expected, given,
  scale)`, beside the other port and frame helpers; Tee, Wye and Switch
  call it.  The message takes the class name from `type(fitting)`, as
  the three hard-coded names did (none of the three has a subclass).
  Left alone: `Transition`'s check (an "outlet interface" message, no
  `up` test) and `Sweep.validate`'s (roll modulo the section's period):
  they test different things.
- **Item 2:** a private base `fittings._AxialOutlet(Sweep)` holds
  `ports()` and the positive-length check; `Reducer` and `Transition`
  derive from it, and their `check()` keeps its own checks after
  `super().check(spec)`.  The positive-length check is
  `fittings._check_length(fitting)`, which `Straight.check` calls too
  (the scan's remaining Straight/base run).
- **Item 3:** `duct_tap._stations(lay, spec, maps, n_y, n_z, n_x, n_run,
  place)`; each layout passes its corner placement as `place(sx, sy,
  sz)`.  Vertices and edges are added in the original order (station
  Sa's corners and edges, then Sd's), so the block layout is unchanged.
- **Item 4: left as is.**  The sites don't share one form, so a
  metadata-driven check can't keep every payload identical:
  - error classes: `SpecError` (`core/shape.py` radius, half_w,
    half_h; `core/spec.py` LayerSpec.dR; `core/grading.py` thickness;
    `sections/oh_gmsh.py` dR), `AssemblyError` (fittings, switch,
    assembler), `EquipmentError` (`equipment.py`, two sites);
  - messages: `{v!r}` (most) vs `{v}` (`shape.py`); prefixed
    (`LayerSpec.dR`, `drum {name}: …`, `Tee: mprg`); one message for two
    fields (the drum's diameter and length);
  - `where`: `{field}` vs `{label, field}` (LayerSpec) vs `{part,
    field}` and `{part, nozzle, field}` (equipment);
  - NaN: `x <= 0` lets NaN through, `not x > 0` (`axial_cell`) catches
    it; a generated check would pick one;
  - three sites check function arguments, not dataclass fields
    (`oh_gmsh.build_annulus` dR, `grading` thickness,
    `Assembly(axial_cell=)`);
  - order: each check sits among others (e.g. radius before nang in
    `CircleShape`), and a generated pass would move it.
  Only `Straight.length`, the `_AxialOutlet` length and `Switch.length`
  match exactly; the first two now share `_check_length` (item 2), and
  `switch.py` doesn't import `fittings`, so `Switch` keeps its own.  `test_schema_ranges_are_enforced` already keeps the
  metadata and the checks consistent.

## Questions for design

## Outcome

**Done 2026-11-11.**  Items 1–3 done; item 4 evaluated and left (*Agent
notes*).

- **Duplicate scan** (the review's scanner, from design; runs of ≥ 6
  normalised statement lines): before (HEAD 7473759) 19 runs, 234 lines;
  after 15 runs, 194 lines.  Gone: the port-frame check, the Reducer /
  Transition `ports()` and `check()` start, the duct-tap stations, and
  Straight's length check.  The scanner merges runs between the first
  two locations of a window, so a block with three copies counts once.
  Left: the two probes against `cube.py` and `wye.py` (6 + 3 runs,
  until 0124 settles), `oh_gmsh.py` (4 runs; `build_oh_circle8`, task
  0088), and two in `fittings.py`: field declarations (`length`,
  `n_layers`, `axial_grading` in Straight, Reducer and Transition; the
  same plus `roll` in Bend and Elbow).  They are data, one per class.
- **Files:** `hexmesh/assembly/{interface,tee,wye,switch,fittings,duct_tap}.py`.
  No test changed: every message, code, `where`, `value` and `limit` is
  as before.
- **Meshes byte-identical:** all 31 examples, written with HEAD's code
  (worktree) and with this change, compared without the `$Comments`
  block.
- **Tests:** full suite 4079 passed, 15 skipped, 1 xfailed (as at
  7473759).
- **Follow-ups:** none proposed.
