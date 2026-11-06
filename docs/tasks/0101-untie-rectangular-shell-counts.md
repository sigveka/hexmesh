# 0101 — Unequal side counts through a stack of rectangular outlines

- **Status:** ready
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
