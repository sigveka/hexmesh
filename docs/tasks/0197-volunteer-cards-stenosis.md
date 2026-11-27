# 0197 — Volunteer cards for the two stenosis cases: the level each study lacks

- **Status:** in progress (2026-11-27)
- **Decision:** [0044](../decisions/0044-volunteer-runs.md) (volunteer
  runs); [0055](../decisions/0055-cards-for-every-case-ci-without-openfoam.md)
  (the card format)
- **Case:** `validation/stenosis/` (steady, V2) and
  `validation/stenosis_pulsatile/` (pulsatile, V2)
- **Depends on:** 0190 (the resumable chunks and the `mapFields` start,
  built for the bend); 0196 (`of.num`).
- **Blocks:** none.  Not a 1.0 criterion: both cases are accepted
  already.  The cards would strengthen their convergence claims.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user (2026-11-27): "Write the volunteer cards we need for
validation".  The rule (2026-11-18): every case that can use more
hardware is a volunteer case.  The design session went through the
cases without cards (2026-11-27):
- **The stenosis, steady:** k2–k4 (122 688, 414 072, 981 504 cells) are
  **oscillatory** for u_peak and both reattachment lengths, so there's
  no order and no GCI (`RESULTS.md`).  A k5 level, and k6 if it can be
  run, tests whether the series turns monotone.  k4 took 17 705 s here
  on 4 cores.
- **The stenosis, pulsatile:** k1–k3 give an observed order of 1.05
  against the schemes' 2, and *"the coarse level is outside the
  asymptotic range"* (`RESULTS.md`).  A k4 level gives three levels,
  k2–k4, that may all lie inside it.  k3 took 6.8 h per period on 4
  cores, and 3 periods from rest.
- **No card needed:** the square bend (converged: order 3.8–5.3, GCI
  ≤ 0.08 %); the turbulent pipe, the rectangular duct and the V1 cases
  (cheap, and within their gates).

The other cards are covered elsewhere:
- the tee: 0168, after 0186;
- the bend: done in 0190.  0169 is superseded by it;
- the Taylor bubble (0079), the Vattenfall T-junction (0120) and the KTH
  duct (0180): each task writes its own card.

**Do.**
0. **First, here: the steady stenosis's k2–k4 on v2406** (the user,
   2026-11-27), so the volunteer levels extend a series made on the
   same version.
   - **Cost:** 760 s, 5 647 s and 17 705 s on 4 cores on v1912, about
     6.7 h in all.  Check `pgrep -af pytest` and free memory first, and
     don't time it while another session's heavy run is on.
   - **Stored:** with `wall_s` and `cores` (0185) and the environment
     (0184).  The v1912 levels are replaced, not kept beside them.
     `RESULTS.md` keeps a short table of the v1912 values for comparison.
   - **Report:** each quantity, v1912 against v2406.  Is the series still
     oscillatory?  Do the gates still pass (u_peak, both reattachment
     lengths)?  A gate that changes verdict goes under *Questions for
     design*, and the card waits.
   - **The run directories:** deleted after collecting.
   - **Not in scope:** the other v1912 cases (Poiseuille, heated rod,
     layered conduction).  They are cheap and converged.  Moving them is
     a separate question.
1. **Hooks** for both drivers: `check_level`, `prepare`, `run`,
   `collect`, `recompute`, as in the bend's (`validation/turbulent_bend/run.py`).
   `main()` and the stored levels stay unchanged.
2. **The steady stenosis:**
   - **levels offered:** `k5` (about 1.9 M cells, estimated from k4 by
     (5/4)³) and `k6` (about 3.3 M) if its memory stays under the
     card's stated limit;
   - **start:** from rest, or by `mapFields` from k4's stored state if it
     can be recreated cheaply.  Say which;
   - **the version (the user, 2026-11-27: "We should rerun the lower
     levels locally now"):** the stored levels are **v1912**.  The card
     runs on **v2406**, so step 0 reruns the lower levels here first;
   - **the result:** whether k3–k5 (and k4–k6) are monotone, and if so
     the order, the extrapolation and the GCI, by the same method as
     the stored ones.
3. **The pulsatile stenosis:**
   - **level offered:** `k4` (981 504 cells, the same mesh as the steady
     k4);
   - **resumable** per period, as the bend's transient is per chunk.
     It starts from k3's periodic state by `mapFields`, which saves the
     two warm-up periods if 0190's start carries over, and runs to the
     case's periodic test;
   - **cost:** estimated from k3 (cells × 2.37, steps per period about
     × 1.3): about 20 h a period on 4 cores here.  Measure a fraction of
     a period here, as 0190 did, and state the card's requirements as a
     range;
   - **the result:** the order over k2–k4, against k1–k3's 1.05.
4. **Requirements on both cards:** measured, or estimated with the
   method (decision 0044), plus peak memory and disk.  Delete the run
   directories after measuring (disk is limited).
5. **The docs:** the two cards in `VOLUNTEERS.md` (regenerated), and each
   case's README says which level is offered and why.
6. **Tests** (no OpenFOAM): each card's levels pass `check_level`.
   `prepare` with `mesh_only` writes the expected cell count.  The
   resume tests follow 0196's (a stand-in solver).
7. **Tags:** `volunteer-stenosis-1`, on a `main` commit, with the user's
   OK.  Each card names its tag.

**Accept.**
- Both cards in `VOLUNTEERS.md`, with measured or stated requirements.
- The tests pass.
- The tag pushed with the user's OK.
- The v1912 question answered or asked.

## Agent notes

- **Step 0 done (2026-11-27):** k2-k4 rerun here on v2406
  (`opencfd/openfoam-default:2406`, Docker), 4 processes, from rest,
  hexmesh c5790d9; `--json` to a scratch file, then it replaced
  `validation/stenosis/results.json` (same `extra`; the levels now carry
  `wall_s` 769, 6235 and 17 685 s, `cores` 4, the environment, and no
  `source` caveat: the v1912 values had been reposted from fields).
  Nothing else was running; 6.9 h in all.
- **v1912 against v2406:** k2 and k4 bit-identical in every stored
  quantity; k3 from the 9th-10th significant digit (u_peak
  4.723710492759 → …493112; τ_w reattachment 11.405468790 → …819; the
  probe's 11.019001647 → …702; mass balance 2.0e-11 → 1.3e-11).  Time
  steps and "steady from t" the same; solver time 760/5647/17 705 s →
  684/5924/17 042 s.  Checked that the old levels ran on a native v1912
  and the new on v2406 (their `environment`).
- **The series** converges oscillatorily as before (u_peak 4.7038,
  4.7237, 4.7168; τ_w reattachment 11.123, 11.405, 11.402).  **The
  gates' verdicts are unchanged**: no question for design.
- **Follow-on edits:** `RESULTS.md` (the run note, the Levels table's
  solver times, a "v1912 and v2406" table in place of the k2-only
  cross-check), figure regenerated (`validation.tools.plots`);
  `case.json`'s toolchain v2406/docker and the driver's default runner
  `of.V2406`, like the other v2406 cases; README.  The run directories
  were deleted by the driver as each level was stored.

## Questions for design

## Outcome
