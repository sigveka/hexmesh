# 0059 — Example: a branched HVAC supply

- **Status:** done (2026-11-02)
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
  rectangular taps (one wide-face, one narrow-face) and one round tap,
  using whatever decision 0033's layout supports; a duct bend; named
  outlets.
- Use `axial_cell` and `toward=` where they make the script shorter.
- Docstring in the style of the other examples: what it shows, then the
  limits in one line.

**Accept.**
- Meshes all-hex, meshed = predicted, quality ok, no warnings; gallery
  entry generated; example test passes.

## Agent notes

- **Where:** a new example, `applications/hvac_branched.py`;
  `hvac_supply` stays the single-run example.
- **The narrow-face tap is full-width.**  A pillowed tap on the narrow
  face of the 2:1 duct (0.5 × 0.25) predicts a corner scaled Jacobian of
  0.19–0.28 at every size tried (half-extents 0.06–0.16 along, 0.04–0.10
  across), so it always warns (0070's table: 2:1 narrow ≤ 0.20 at ratio
  0.9).  The full-width tap (as tall as the duct, task 0057) at 0.1
  along the main doesn't warn; at 0.04 it does (0.21), as 0057's p/t
  rule says.  The wide-face rectangular (0.15 × 0.1) and round (r 0.1)
  pillowed taps don't warn at any size tried.
- **`axial_cell`** (0.08) replaces every `n_layers`.  `toward=` isn't
  used: a duct tap rejects it, and the bend's `roll=-90` is shorter
  than a direction vector here.

## Questions for design

_None._

## Outcome

Done 2026-11-02.

- **Files:** `hexmesh/examples/applications/hvac_branched.py` (new);
  `hexmesh/examples/__init__.py` (`CATEGORIES`); `docs/GUIDE.md`
  (examples table; the README has no examples table any more);
  `docs/GALLERY.md`, `docs/gallery/metrics.json`, two images.
- **The example:** fan Ø 0.3 → `Transition` → 0.5 × 0.25 duct; a
  rectangular tap on the top face, a round tap on the bottom, a
  full-width rectangular tap on the side face; a hard-way bend away from
  the side tap; outlets `supply_up`, `supply_down`, `supply_side`,
  `main_end`.  33 472 cells, meshed = predicted, min SICN 0.166, min SJ
  0.421, 5.5 s; no warnings.
- **Tests:** `test_example[applications.hvac_branched]` passes (with
  `-W error::UserWarning`); full suite 2145 passed, 14 skipped.
- **Follow-up (for design):** pillowed narrow-face taps on a 2:1 duct
  always warn, so an example wanting a small tap on a narrow face has
  only the full-width form.  If that is common in HVAC, a better
  narrow-face layout is worth a look.
