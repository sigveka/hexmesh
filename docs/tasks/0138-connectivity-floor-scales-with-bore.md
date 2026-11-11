# 0138 — The connectivity tolerance's floor scales with the bore

- **Status:** ready
- **Decision:** task 0128's design answer (2026-11-11, Q2); [0018](../decisions/0018-future-vascular-networks.md) (constraint 8)
- **Depends on:** none.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `interchange/graph.py` joins component ends closer than
`max(TOL_RELATIVE × model diagonal, TOL_FLOOR)`, with `TOL_FLOOR` =
0.11" (2.8 mm), just above the 1/16" weld gap in plant isometrics
(task 0128's audit).  Right for plant data; for a network of 1 mm
vessels it would join ends 2.8 mm apart.  The user (2026-11-11): the
floor should scale with the bore.

**Where.**  `hexmesh/interchange/graph.py` (`_model_tolerance`),
`operations.py` (its `TOL_FLOOR` fallback), `importers/pcf.py`'s
docstring, API.md (`read_pcf`'s `tolerance`), `tests/`.

**Do.**
1. **The floor:** `min(TOL_FLOOR, TOL_BORE × smallest bore)`, with
   `TOL_BORE = 0.25`, the smallest bore over the model's components
   (`_Comp.bore`, and the branch and end bores where given).  A model
   with no bores keeps `TOL_FLOOR`.  The tolerance stays
   `max(TOL_RELATIVE × diagonal, floor)`.
2. **Unchanged for plant data:** every PCF test file, the shipped
   `pcf_line` example and the PCF gallery entries read to the same
   components and connections (bores of ½" and up keep 0.11").  Say so
   with numbers under *Outcome*.
3. **Tests:** a model of 1 mm bores with ends 1 mm apart is not joined;
   the same model with ends 0.1 mm apart is; a plant model with a ½"
   line keeps 0.11".
4. **Docs:** API.md and `read_pcf`'s docstring state the rule; a
   CHANGELOG line.

**Accept.**
- The floor follows the bore below 0.44" (11.2 mm) and is 0.11"
  otherwise; PCF reads and meshes byte-identical; full suite: no new
  failures.

**Out of scope.**  The geometry kernel's tolerances (task 0128, Q1).

## Agent notes

## Questions for design

## Outcome
