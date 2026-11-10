# 0127 — The equal tee at fine `nang`: a measured tier in `validate()`, before gmsh

- **Status:** ready
- **Decision:** [0043](../decisions/0043-wye-layout-redesign.md) (note on tasks 0122 and 0126); DESIGN §2 principle 4 (fail before meshing)
- **Depends on:** 0122, 0126 (done).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The equal tee's meshed min SJ falls with refinement (0.511,
0.399, 0.353, 0.330, 0.305 at `nang` 8, 16, 24, 32, 48), and task 0126
found no explanation and no floor.  The predicted SJ doesn't see it.  So
a user at `nang` 64 or finer may get a warning, or `mesh()`'s
`meshed_sj_below_minimum`, only after gmsh has meshed.  The user
(2026-11-10): measure it and check it in `validate()`.

**Where.**  `hexmesh/assembly/limits.py`, the equal tee's checks in
`tee.py`/`cube.py`, `errors.py` if a code is added,
`validation/tools/equal_tee.json`, GUIDE's equal-tee table, DESIGN §7.2's
numbers (proposed under *Questions for design*), `tests/`.

**Do.**
1. **Measure** the equal tee at 90°, `nang` 64 and 96, single layer, and
   with one shell at 64: meshed min SJ, inverted cells, peak memory, wall
   time.  Check `df -h .` and free memory first; if `nang` 96 doesn't fit
   this machine, say so and stop at 64.
2. **The rule, fixed now:**
   - `EQUAL_TEE_NANG_CLEAN`: the largest measured `nang` (8, 16, 24, 32,
     48, 64, 96) with meshed min SJ ≥ 0.3, single and shelled.  Above it,
     `validate()` warns, coded, naming the measured SJ at the next
     measured `nang` and the hint "nang ≤ N builds without a warning".
   - `EQUAL_TEE_NANG_MAX`: if some measured `nang` gives < 0.1, the
     largest one at or above 0.1; above it, `validate()` rejects, coded.
     If none falls below 0.1, no maximum: say so.
   - Beyond the last measured `nang`, the warning says the quality there
     is unmeasured.
   - Measured values only: no extrapolation and no fitted model.
3. **Docs:** GUIDE's table gains the new rows; propose DESIGN §7.2's
   updated numbers under *Questions for design*.

**Accept.**
- The two limits in `limits.py` with their source (this task, the JSON
  rows).
- Tests: an equal tee above the clean `nang` warns in `validate()`
  before gmsh; above the maximum (if any) it is rejected before gmsh.
- Full suite: no new failures; gallery byte-identical.
- Meshes deleted; numbers in the JSON.

**Out of scope.**  Explaining or fixing the slide (task 0126 closed;
the projected grid's obliquity stays a follow-up); laterals.

## Agent notes

## Questions for design

## Outcome
