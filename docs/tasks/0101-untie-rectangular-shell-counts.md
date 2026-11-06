# 0101 — Unequal side counts through a stack of rectangular outlines

- **Status:** done
- **Decision:** [0041 — Per-side counts on rectangles](../decisions/0041-per-side-counts-on-rectangles.md) (option B); amends [0026](../decisions/0026-layer-outlines.md) item 3
- **Depends on:** 0100 (done).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `PipeSpec._check_counts` (`core/spec.py:571`) requires
`nang_w = nang_h` through any stack with a rectangle
(`rect_stack_counts_unequal`).  Task 0100 bypassed it and found that
untied stacks of rectangular outlines build, validate and mesh
conformally (H and O-H; one or two `dR` shells; a rectangular `outer`;
a straight and a 90° bend; worst SJ 0.63–0.71).  The rule only costs
cells: `lagged_duct` is 936k at "medium", against 527k untied.

**Where.**  `hexmesh/core/spec.py` (`_check_counts`);
`hexmesh/agent/advise.py` (`_tied`, `_density`); `hexmesh/errors.py`
(the code's text); tests; `API.md`; `CHANGELOG.md`.

**Do.**
1. **The spec rule.**  In a stack whose outlines are all rectangles,
   every outline takes the core's `(nang_w, nang_h)`.  Unequal
   counts are allowed.
   - A shell's outline with counts different from the core's is still
     rejected, with the same code, saying "the core's counts", not
     "equal counts".
   - A stack with a rectangle **and** a circle keeps today's rule
     (`nang_w = nang_h = nang`): the circle carries one count (0100,
     tie #2).  The error names decision 0041 and says why.
   - `BundleSpec` (`core/spec.py:819`) keeps its rule: its tile has a
     circular core (0100, tie #7).
   - `rect_stack_needs_n_outer_4` is unchanged.
2. **The advisor.**  `_tied` no longer ties a stack of rectangles.  It
   still ties a circle → rectangle `Transition`, a circle in a stack
   with a rectangle, and a round duct tap.  The report's reason names
   the fitting or layer that ties the counts.
3. **Tests:**
   - 0100's untied cases, as tests: an 8 × 4 core with one `dR` shell
     (H and O-H), two shells, a rectangular `outer`, a straight and a
     90° bend.  Each builds, validates and meshes with hexes = predicted
     and no open or coincident faces.
   - The rejections: a shell with counts other than the core's; a
     circle in a stack with an untied rectangle.
   - Messages and codes: existing messages unchanged except the one
     rewritten in step 1.
4. **Re-measure:** run `advise` on the 28 examples (water at 2 mm/s,
   "medium") and record the cell counts that change.  `lagged_duct`
   should go to about 527k.
5. **Docs:** `API.md` (`PipeSpec` with shells on a rectangle),
   `CHANGELOG.md` (an added capability, not breaking).

**Accept.**
- Untied rectangular stacks build and mesh conformally, in the cases
  listed.
- Circle-and-rectangle stacks and `BundleSpec` are rejected as before,
  with a message naming decision 0041.
- The 28 example meshes are unchanged: the examples don't use untied
  counts, so this only adds a capability.
- The re-measured counts are in *Outcome*.
- Full suite: no new failures.

**Out of scope.**  Option C (unequal arc counts on a circle).  It is
held in decision 0041.

## Agent notes

- **Step 1:** `_check_counts` (`core/spec.py`) splits on whether any
  outline is a circle.
  - **All rectangles:** every outline must equal the core's
    `(nang_w, nang_h)`.  The message says "takes the core's counts", and
    `limit` is the core's counts.
  - **Circle and rectangle:** today's rule.  The message adds "since a
    circle carries one count (decision 0041)".
  - The code `rect_stack_counts_unequal` is kept for both.  Its text is
    in `errors.py` and API.md.
- **BundleSpec** needed no change.  Its tile is a circle in a
  rectangle, so the mixed-stack rule applies at `.shell()`, with the
  0041 message.  Tested in `test_shapes.py`.
- **Step 2:** `_tied` now takes the `Assembly`, not the description,
  because each edge's ports carry their specs' outlines.  It ties on:
  - a `Transition` whose ports mix circles and rectangles;
  - a `Tee` with a round branch on a rectangular main;
  - an interface whose stack mixes circles and rectangles.

  The reason names the fitting (`Transition1 (a Transition) joins a
  circle to a rectangle`) or the layer.  `_specs`, now unused, was
  removed.
- **Step 3:** 0100's untied cases joined the conformance kit (DESIGN
  §6.1), not a separate test file, so they get its full set of checks:
  ports untouched, no duplicates or coincident nodes, the predicted
  count, groups, every fill order, and wall exactness.
  - The cases are an 8 × 4 duct with one `dR` shell (H, O-H), two
    shells, a rectangular `outer`, a bend and two-shell bend.
  - I also added a miter bend, a `Reducer`, a rectangle → rectangle
    `Transition` and an O-H → H `Switch` on an untied stack.
  - That makes 10 cases × 6 checks = 60 tests, all passing.
- **Old tests:** two tests asserted the old rejection of a rectangular
  shell with unequal counts.  They now assert that it builds, and that
  counts other than the core's are rejected.
- **Docs:** the rule text in `lagged_duct` and `layer_outlines`
  (docstrings, and their GALLERY copies) and in GUIDE.md now says
  which stacks tie.  The example meshes are unchanged.

## Outcome

**Done.**

**Files changed:**
- `hexmesh/core/spec.py`, `hexmesh/agent/advise.py`, `hexmesh/errors.py`;
- `tests/test_fitting_conformance.py` (+60), `test_shapes.py` (+2,
  one rewritten), `test_rect_duct.py` (one rewritten),
  `test_agent_advise.py` (+2);
- `API.md`, `CHANGELOG.md`, `docs/GUIDE.md`, `docs/GALLERY.md`, and two
  example docstrings.

**Re-measure** (`advise`, water at 2 mm/s, "medium", all 28 examples,
HEAD against this change):

| example | before | after |
|---|---|---|
| `sections.lagged_duct` | 936 000 | **526 500** (−44 %) |

- The other 27 are unchanged.  Four of them (`duct_transition`,
  `hvac_supply`, `hvac_branched`, `cooling_channels`) are still tied,
  each by a circle → rectangle `Transition`.
- None errors.

**Suite:** 3550 passed, 15 skipped, 2 failed (45 min), with the 0075
OpenFOAM run sharing the CPU.  The two failures are the `< 2.0 s` timing
assert in `test_preview_every_example` (`insulated_network` 2.26 s,
`pipe_rack` 2.23 s), and they pass when rerun alone.  The BundleSpec
tile test was added after the run started; it passes alone.

**Surprises:** none.  The kit's extra fittings (miter, reducer,
rectangle → rectangle transition, switch) needed no change for unequal
counts through shells.

**Follow-ups:** none proposed.  C stays held, per decision 0041.
