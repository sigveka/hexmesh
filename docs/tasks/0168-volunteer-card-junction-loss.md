# 0168 — A volunteer card for the junction-flow benchmark

- **Status:** ready (after 0186; retargeted 2026-11-23 by the user to 0186's
  fixed-wall family: its level 3 and the 20-point sweep)
- **Decision:** [0044](../decisions/0044-volunteer-runs.md) (volunteer
  runs: one tool, a card per case, a mechanical check)
- **Case:** `validation/junction_loss/` (task 0162)
- **Depends on:** 0186 (the fixed-wall family, its method, and levels 1–2
  stored); 0190 (the resumable transient and `mapFields` start); 0119
  and 0160 (the tool).
- **Blocks:** none.  Not a 1.0 criterion: the tee is reported with 0186's
  two levels, as the bend was.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  0162's 20-point set at level 2 takes about 60 h on this
machine (about 3 h a point at 3 processes), and the k–ε comparison and
the Re check add more.  The points are independent, so they split
naturally into volunteer levels.  The user asked for a card for each
validation case (2026-11-16).

**Retargeted (the design session, 2026-11-23; the user: "yes").**
Steps 1 and 3 below were written for 0162's `refined(k)` levels, which
change the wall model with refinement (RESEARCH §7.2's correction).
They now read:
- **Levels offered:**
  - `fixed_k3` for 0162's main point (Div a, q 0.6), the tee's grid
    study's finest level;
  - then the 20-point sweep at the fixed-wall level 2: the four
    configurations × five q, with the k–ε point and the two Re-check
    points on the same family.
  - The `refined(k)` levels are **not** offered.
- **Method:** whichever 0186 settled on (steady, or time-accurate with
  0050's convergence stop), resumable, with level 3 started from level 2
  by `mapFields`, as 0190 built for the bend.
- **Step 1's gate** becomes: offered once 0186 has stored levels 1 and 2.
- **Requirements:** measured here at level 3 for a few chunks, as 0190
  did (s per step at a stated core count, peak memory, peak disk), and
  stated as a range.  The sweep's levels are measured from 0186's
  level 2.
- **The tag** (step 5) is `volunteer-junction-1`, on a `main` commit
  carrying the card, with the user's OK.
- **The dry run** (step 6) is on level 1 of the fixed-wall family.

**Do.**
1. **Gate on 0162:** the card's 20-point levels are offered only once
   0162's level-3 point is "close" (the user's budget rule, in 0162's
   notes).  Until then the card offers only the level-3 convergence
   point, if 0162 hasn't run it yet.  If 0162 stops on a design
   question, so does this card.
2. **Hooks:** give `validation/junction_loss/run.py` the `prepare`,
   `run` and `collect` hooks the tool calls, reusing `run_point` (as
   the helical driver does).
3. **Levels**, one per point: `<config>_q<q>_k<k>` (e.g.
   `diva_q06_k2`), for the four configurations × five q at k = 2, the
   convergence point at k = 3, the k–ε point and the two Re-check
   points.  `list` groups them so a volunteer can pick a batch.
4. **The card** (`volunteer.json`) as the helical one: plain-words
   summary; OpenFOAM v2406; the hexmesh tag; requirements per level
   labelled *measured* (k = 1 and 2 from 0162's runs: wall time,
   Docker peak memory 148 MiB at k = 1 and 761 MiB at k = 2, disk) or
   *estimated* (k = 3 scaled by cells); `reproduce` on ξ_PG and ξ_MGb
   with the tolerance the window averaging allows (state it); returns.
5. **The tag:** a `volunteer-junction-1` tag on a commit `main` carries,
   after 0166's renames have landed (the drivers change with them);
   the user's OK, as for the helical tags.
6. **Dry run here** at k = 1 on one point: `prepare` → `bash job.sh` →
   `collect` → `check --merge` into a scratch copy of `results.json`,
   reproducing the stored k = 1 point within `reproduce`'s tolerance.
   Delete the run after.
7. `VOLUNTEERS.md` regenerated; its stale-file test passes.

**Accept.**  The dry run passes `check`; tampered contributions are
rejected (the existing tests cover the tool; add one for this card's
levels); `list` shows every level with labelled requirements; full
suite green.

**Out of scope.**  The 45° points (no equal laterals); running the
levels here beyond the dry run; opening GitHub issues for volunteers
(the user's).

## Agent notes

## Questions for design

## Outcome
