# 0169 — A volunteer card for the turbulent bend

- **Status:** ready (after 0050's driver and its first level)
- **Decision:** [0044](../decisions/0044-volunteer-runs.md)
- **Case:** `validation/turbulent_bend/` (task 0050: the PTB bend,
  Re 50 000)
- **Depends on:** 0050 (the driver, the gates, a measured level);
  0119 and 0160 (the tool).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  0050 is a three-level 3-D RANS study with a 49 D domain; its
finest level is the expensive one, sized to stay under about 6 GB.  A
card lets someone with more cores run the finest level (and, if
memory allows, a full-domain variant the paper also ran).  The user
asked for a card for each validation case (2026-11-16).

**Do.**
1. **Hooks:** when 0050 writes its driver, give it `prepare`, `run`
   and `collect` from the start (coordinate with 0050's agent notes);
   otherwise add them here, reusing the driver's functions.
2. **Levels:** the finest level of the convergence study (the one 0050
   reports with GCI), and optionally a level beyond it that this
   machine can't run (state its cells and estimated memory).  Name them
   as the helical card does (`k3`, `k4`).
3. **The card** (`volunteer.json`): plain-words summary; OpenFOAM
   v2406; the hexmesh tag; requirements labelled *measured* (from
   0050's own runs at the coarser levels) or *estimated* (scaled by
   cells); `reproduce` on the RMS velocity difference per plane, with
   its tolerance; returns.
4. **The tag:** `volunteer-bend-1` on a commit `main` carries, after
   0166's renames; the user's OK.
5. **Dry run here** on the coarsest level: `prepare` → `bash job.sh` →
   `collect` → `check --merge` into a scratch `results.json`,
   reproducing 0050's stored level.  Delete the run after.
6. `VOLUNTEERS.md` regenerated.

**Accept.**  As 0168's.

**Out of scope.**  Hybrid LES/RANS levels (the paper's; not in 0050);
Sudo et al.'s case (no data here).

## Agent notes

## Questions for design

## Outcome
