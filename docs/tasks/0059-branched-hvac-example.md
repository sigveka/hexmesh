# 0059 — Example: a branched HVAC supply

- **Status:** ready (after 0057, 0058)
- **Decision:** [0027 — Tees in rectangular ducts](../decisions/0027-duct-tees.md)
- **Depends on:** 0057, 0058.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `hvac_supply` is a single run.  A branched supply shows duct
tees in the setting they are for.

**Where.**  `hexmesh/examples/applications/` (new `hvac_branched.py`,
or extend `hvac_supply` if it reads better), `hexmesh/examples/__init__.py`
(`CATEGORIES`), the README examples table, gallery
(`python3 docs/gallery/build.py --only hvac_branched`).

**Do.**
- A rectangular supply main from a fan transition, with two
  rectangular taps (one wide-face, one narrow-face) and one round tap
  to a round branch duct; a duct bend; named outlets.
- Use `axial_cell` and `toward=` where they make the script shorter.
- Docstring in the style of the other examples: what it shows, then the
  limits in one line.

**Accept.**
- Meshes all-hex, meshed = predicted, quality ok, no warnings; gallery
  entry generated; example test passes.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
