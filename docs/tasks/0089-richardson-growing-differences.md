# 0089 — `richardson()`: no order when differences grow

- **Status:** ready
- **Decision:** [0015 — how convergence is judged](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) (Q2: Richardson extrapolation, [`celik_and_ghia_etal_2008`])
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).  This task
works in `validation/` and `tests/`.

**Why.**  `validation/poiseuille/run.py:341` computes the observed order
as `abs(log(abs(e32 / e21))) / log(r)`.  When the differences between
levels grow (|e32| < |e21|), the true order is negative and there is
no asymptotic range.  The `abs()` turns that into a positive order and
an extrapolation in the wrong direction.

Task 0071 met it: the O-H square duct gives "order 0.24" from
differences 0.39 → 0.46.  rect_duct flags it locally
(`differences_grow`), but the shared function is unchanged, and seven
cases import it: poiseuille, heated_rod, heated_pipe,
layered_conduction, stenosis, stenosis_pulsatile, womersley.  Gates
that rely on it could pass on a non-convergent series.

**Where.**  `validation/poiseuille/run.py` (`richardson`).  Better, a
shared module, e.g. `validation/tools/convergence.py`, imported by every
case; rect_duct's `extrapolate()`; `tests/`.

**Do.**
1. **One shared function** with an explicit result:
   - `"converging"`: |e32| > |e21|, same sign.  Report the order
     p = ln(e32/e21)/ln r, the extrapolated value, e_a, e_ext and the
     GCI, as today.
   - `"oscillatory"`: opposite signs.  Report the oscillation and the
     bounds (min/max of the three).  No order, no extrapolation.
     Celik et al. treat it separately.
   - `"diverging"`: same sign, |e32| ≤ |e21|.  No order, no
     extrapolation.
   - A zero difference: say so, without dividing by it.
2. **Move rect_duct's `differences_grow`** onto the shared result.
   Make every case import the shared function, not Poiseuille's.
3. **Gates:** an extrapolated-value gate on a series that isn't
   `"converging"` **fails** with that reason.  It must not pass on a
   number.  Report-only quantities (decision 0015's O-H orders) show the
   status instead of an order.
4. **Point values net of their extraction bias** (decision 0015
   amendment 3).  Where a case gates a fitted or interpolated point
   value, gate F(u_h) − F(u_exact) at the same samples.  Report F's
   bias separately.
   - rect_duct's u_c is the known case.
   - Poiseuille's u_max fit is exact on its parabola, so its bias
     should be zero; confirm it.
   - List any other case that extracts point values this way.
5. **Recheck every accepted case** from its stored results (RESULTS.md
   levels, or the JSON if kept):
   - recompute each Richardson row with the new function;
   - list any row whose status isn't `"converging"`, and any gated value
     that changes.

   Don't rerun OpenFOAM unless a stored level is missing.

**Accept.**
- Unit tests on synthetic series: converging (p = 2 recovered to 1e-12),
  oscillatory, diverging, and a zero difference.  The O-H square's three
  f·Re values give `"diverging"`.
- No case imports `richardson` from `poiseuille/run.py` any more.
- *Outcome*: the recheck table (case, quantity, old order, new status,
  gate before and after, and for point values the extraction bias).
  If any accepted case's gate flips, set this task `blocked` with the table under *Questions for design*; don't
  re-accept or reject cases yourself.
- `python3 -m pytest tests/test_validation_meta.py` and the full suite:
  no new failures.

**Out of scope.**  Changing gates' thresholds; rerunning cases.

## Agent notes

## Questions for design

## Outcome
