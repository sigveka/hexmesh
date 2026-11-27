# 0197 — Volunteer cards for the two stenosis cases: the level each study lacks

- **Status:** ready
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
1. **Hooks** for both drivers: `check_level`, `prepare`, `run`,
   `collect`, `recompute`, as in the bend's (`validation/turbulent_bend/run.py`).
   `main()` and the stored levels stay unchanged.
2. **The steady stenosis:**
   - **levels offered:** `k5` (about 1.9 M cells, estimated from k4 by
     (5/4)³) and `k6` (about 3.3 M) if its memory stays under the
     card's stated limit;
   - **start:** from rest, or by `mapFields` from k4's stored state if it
     can be recreated cheaply.  Say which;
   - **the version:** the stored levels are **v1912**.  The card runs
     k5 on v1912 if the image can still be pulled.  Otherwise put the
     choice under *Questions for design*: rerun k3–k4 on v2406 here,
     or accept a mixed series with a stated reason;
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

## Questions for design

## Outcome
