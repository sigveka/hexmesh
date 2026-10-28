# 0048 — Examples for layer outlines and multi-layer transitions

- **Status:** ready
- **Decision:** [0026 — Layer outlines: shells of any shape](../decisions/0026-layer-outlines.md)
- **Depends on:** 0045, 0046 (both done).  Independent of 0047.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Tasks 0045 and 0046 added shells with any outline
(`.shell(name, outer=CircleShape | RectShape)`, and `dR` around a
rectangle) and `Transition` across whole layer stacks.  No example uses
either.  Only the conformance kit and the `API.md` snippets show them.
Some example docstrings also still state the old limits:
- `hexmesh/examples/sections/duct_transition.py:11`, "single-layer
  specs";
- `hexmesh/examples/sections/rect_duct.py:12`, "single-layer ducts; no
  reducer … for ducts yet".

**Where.**  `hexmesh/examples/sections/`, `hexmesh/examples/__init__.py`
(`ALL`), `tests/test_examples.py` (runs every listed example), and the
`README.md` examples table (the `sections` row).

**Do.**
1. **`sections/layer_outlines.py`.**  Three stacks, each through a
   straight and a bend, laid out side by side in one assembly or as
   three runs:
   - a conductor in a square filler in a round sheath (circle → square →
     circle, `outer=`);
   - a rectangular duct with a wall and lagging (`dR` around a
     rectangle);
   - a round pipe set in a rectangular block (circle in a rectangle).
     Keep the block's w/h within task 0047's measured range: w/h ≤ 2,
     gap ratio ≥ 0.3.
   The docstring states the rules: one count per side through a stack
   with a rectangle; each outline inside the next.
2. **`sections/insulated_transition.py`.**  An insulated round pipe that
   a `Transition` turns into an insulated rectangular duct, a duct bend,
   then a `stack_changes` where the insulation stops.  The docstring
   states that `Reducer` changes sizes and `Transition` changes shapes.
3. Each `main()` writes `<name>.msh`, like the other examples; list both
   in `ALL`.
4. Update the stale limit lines in `duct_transition.py` and
   `rect_duct.py`.  Add the new examples to the README `sections` row.

**Accept.**
- `tests/test_examples.py` runs both: they mesh, meshed = predicted, and
  `quality.ok`.  `test_every_example_is_listed` passes.
- Each example runs on its own as
  `python3 -m hexmesh.examples.sections.<name>`.
- No example docstring states a limit that tasks 0045 and 0046 removed.
- Full suite: no new failures.

**Out of scope.**  New capability; the 0047 quality limit itself.

## Agent notes

## Questions for design

## Outcome
