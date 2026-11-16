# 0168 — A volunteer card for the junction-flow benchmark

- **Status:** ready (after 0162's level-3 point; see *Do* 1)
- **Decision:** [0044](../decisions/0044-volunteer-runs.md) (volunteer
  runs: one tool, a card per case, a mechanical check)
- **Case:** `validation/junction_loss/` (task 0162)
- **Depends on:** 0162 (the driver, the gates, the level-3 point and
  the "close" criterion); 0119 and 0160 (the tool).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  0162's 20-point set at level 2 takes about 60 h on this
machine (about 3 h a point at 3 processes), and the k–ε comparison and
the Re check add more.  The points are independent, so they split
naturally into volunteer levels.  The user asked for a card for each
validation case (2026-11-16).

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
