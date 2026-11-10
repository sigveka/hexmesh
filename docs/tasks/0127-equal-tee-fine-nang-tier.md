# 0127 — The equal tee at fine `nang`: a measured tier in `validate()`, before gmsh

- **Status:** done
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

- **Resources.**  `df -h .`: 31 GB free.  Memory: 15 GB total, about 6 GB
  available beside the Re 3000 run (task 0119).  `nang` 64 peaked at
  4.7 GB (single) and 4.9 GB (shelled); `nang` 96 has (96/64)³ ≈ 3.4×
  the cells, so about 16 GB: **it doesn't fit this machine, so the
  measurement stops at 64.**
- **Shelled rows were missing above `nang` 16**, and step 2's rule needs
  single and shelled, so they were measured too (one steel shell 0.1 R,
  `nrad` 2): shelled equals single to 1e-13 at every `nang`.
- **The warning's code.**  A fitting's `validate()` messages already go
  out as `HexmeshWarning` coded `fitting_quality_warning`; the new tier
  uses that path, so no code was added to `errors.py`.

## Questions for design

1. **DESIGN §7.2's numbers (proposed wording, not a blocker).**  Line
   507 reads "…so the meshed quality falls with refinement (min scaled
   Jacobian 0.511 at `nang` 8, 0.305 at 48)."  Proposed: "…falls with
   refinement (min scaled Jacobian 0.511 at `nang` 8, 0.305 at 48, 0.293
   at 64; above `EQUAL_TEE_NANG_CLEAN` = 48 `validate()` warns before
   meshing, and nothing finer than 64 is measured)."

## Design answer (2026-11-10, the user: "yes"): applied in 95bfe59

Q1: DESIGN §7.2 carries the proposed wording, verbatim, plus "task 0127".

## Outcome

**Status:** done.

**Measured** (90°, R 0.1 m; `validation/tools/equal_tee.json`, key
`fine_nang`), meshed min SJ, single = shelled at every `nang`:

| `nang` | min SJ | inverted | max non-orth. | crease miss | peak memory |
|---|---|---|---|---|---|
| 48 | 0.305 | 0 | 58° | 0.7 % R | 2.2 GB |
| 64 | 0.293 | 0 | 66° | 0.5 % R | 4.95 GB |
| 96 | not measured: about 16 GB, more than this machine's 15 GB | | | | |

At `nang` 64 the predicted non-orthogonality is 75.6° (the branch run),
above `OUTLINE_NONORTH_WARN` 70°, so `validate()` already warned there
on that count as well.

**The rule.**  `EQUAL_TEE_NANG_CLEAN = 48` (the largest measured `nang`
with SJ ≥ 0.3, single and shelled).  No `EQUAL_TEE_NANG_MAX`: nothing
measured falls below 0.1 (lowest 0.293).  Above 48, `CubeTee.validate`
warns (`fitting_quality_warning`) with the measured SJ at the next
measured `nang` (0.293 at 64), or, above 64, that the quality is
unmeasured; the hint is "nang <= EQUAL_TEE_NANG_CLEAN (48) builds without
a warning".  The measured values live in `cube._MEASURED_SJ`, with their
source.

**Files.**  `hexmesh/assembly/limits.py` (`EQUAL_TEE_NANG_CLEAN`),
`hexmesh/assembly/cube.py` (`_MEASURED_SJ`, `_nang_tier`),
`tests/test_equal_tee.py` (+4: warns at 56, 64 and 96 before gmsh;
silent at 48 shelled), `API.md` (the bullet and the limits row),
`docs/GUIDE.md` (the 64 row and the tier), `CHANGELOG.md`,
`validation/tools/equal_tee.json`.

**Checks.**  Full suite: 4048 passed, 15 skipped, 0 failed (19 min 46 s).
All 30 examples' meshes are byte-identical to HEAD's (sha256 of each
`.msh`, built from a HEAD worktree and from this tree).  Meshes deleted.

**Surprises.**  The first attempt at the full `nang` 64 row was stopped
by Claude Code's memory guard while the Re 3000 run (task 0119) was also
running; it was rerun alone after the user removed an old project's
containers.

**Proposed follow-ups.**  Measure `nang` 96 on a machine with more than
16 GB if a user needs it; the warning names it as unmeasured until then.
