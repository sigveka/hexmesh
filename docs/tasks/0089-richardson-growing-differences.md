# 0089 — `richardson()`: no order when differences grow

- **Status:** done
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
  If any accepted case's gate flips, set this task `blocked` with the
  table under *Questions for design*; don't re-accept or reject cases
  yourself.
- `python3 -m pytest tests/test_validation_meta.py` and the full suite:
  no new failures.

**Out of scope.**  Changing gates' thresholds; rerunning cases.

## Agent notes

- **Three implementations, not one.**
  - Poiseuille's |log| function was used by poiseuille, heated_rod,
    layered_conduction and rect_duct.
  - Stenosis's non-constant-ratio function (|log| too) was used by
    stenosis, heated_pipe and stenosis_pulsatile.
  - Womersley had its own.  It rejected oscillation, but growing
    differences gave a negative order and it still extrapolated.
  - All are replaced by `validation/tools/convergence.py`, which every
    case loads by path (`validation/` is not a package).
- **The shared function:** `richardson(coarse, medium, fine, r21=2,
  r32=None, *, scale=None)`.
  - Every key is present in every result.  `order`, `extrapolated`,
    `e_a`, `e_ext` and `gci_fine` are None unless `status` is
    `"converging"`.
  - `oscillatory` (bool) is kept for existing readers; `bounds` and
    `note` are added.
  - `scale=` gives the absolute GCI that Womersley used for its
    error-against-exact series (exact limit 0).  Its wrapper keeps the
    old |f| ≤ 0.01 rule.
- **Gates:** `gate_extrapolated(rich, exact, limit)` fails with the
  status on any non-converging series.  Poiseuille's openfoam tests use
  it, and its u_max order test requires `"converging"`.
  - The other cases' gates live in RESULTS.md, not in code; their
    drivers now emit statuses.
  - Report-only rows show the status (Poiseuille's table, rect_duct,
    stenosis RESULTS.md).
- **rect_duct:** `differences_grow` is gone.  `extrapolate()` adds
  `u_c_net`: Richardson on (F(u_h) − F(u_exact)) / u_c, absolute GCI,
  with `fit_bias_fine` reported.  RESULTS.md now gates u_c net of the
  bias (amendment 3) and shows statuses.
- **Stenosis's centreline gate** extrapolates per station where the
  series converges.  It was rebuilt read-only from the stored k2–k4
  fields in `validation/stenosis/work/` (no OpenFOAM), with the HEAD
  and new `extrapolate()`:
  - the same 3 of 18 stations;
  - the same max error, 0.929 % at 3 D;
  - "best" values differ by ≤ 1.1e-13.  The old fixed-point loop kept
    the previous iterate when it stopped.
- **Logo headers** (new ground rule) are on every .py file this task
  touched.

## Questions for design

## Outcome

No accepted gate flips.  Done 2026-11-02.

**Files.**
- New:
  - `validation/tools/convergence.py`;
  - `tests/test_convergence.py`, 12 tests: converging (p = 2 to 1e-12,
    and at ratios 4/3, 3/2), oscillatory, diverging, the O-H square
    (diverging), zero difference (3 cases), absolute scale, the gate,
    the status display, and no case importing another case's
    Richardson.
- Changed:
  - the eight drivers, `validation/*/run.py`;
  - `tests/test_validation.py`: Poiseuille's gates through
    `gate_extrapolated`;
  - RESULTS.md of rect_duct and stenosis: statuses, and rect_duct's u_c
    gate net of the fit bias.

**Recheck** of every accepted case from stored results:
- values come from RESULTS.md; rect_duct from the task 0071 JSON;
  stenosis's scalars and centreline from its stored fields;
- "old order" is the HEAD function's;
- only the gated Cartesian rows are listed for rect_duct.  The O-H rows
  are reported: f·Re diverging (a/b 1) / oscillatory (a/b 2) /
  converging (a/b 4, through a sign change), u_c oscillatory.

| case | quantity | old order | new status | new order | gate before | gate after | extraction bias |
|---|---|---|---|---|---|---|---|
| poiseuille | dp | 1.252 | converging | 1.252 | pass | pass | — |
| poiseuille | u_max | 1.905 | converging | 1.905 | pass | pass | 0 (parabola fit, ≤ 4.4e-16) |
| heated_rod | ΔT0 (uniform) | 1.286 | converging | 1.286 | pass | pass | 0 (parabola fit, ≤ 2.2e-16) |
| heated_rod | ΔT0 (graded) | 1.371 | converging | 1.371 | pass | pass | 0 (parabola fit, ≤ 2.2e-16) |
| heated_pipe | Nu | 1.741 | converging | 1.741 | pass | pass | — |
| heated_pipe | dT_b/dx | 1.537 | converging | 1.537 | reported | reported | — |
| heated_pipe | ΔT steel | 2.007 | converging | 2.007 | pass | pass | — |
| heated_pipe | ΔT insulation | 1.895 | converging | 1.895 | pass | pass | — |
| layered_conduction | T0 (fixed) | 2.011 | converging | 2.011 | pass | pass | 0 (parabola fit, ≤ 2.2e-16) |
| layered_conduction | T(r1) (fixed) | 2.012 | converging | 2.012 | pass | pass | — |
| layered_conduction | T(r2) (fixed) | 2.012 | converging | 2.012 | pass | pass | — |
| layered_conduction | T0 (convection) | 2.008 | converging | 2.008 | pass | pass | 0 (parabola fit, ≤ 2.2e-16) |
| layered_conduction | T(r1) (convection) | 2.01 | converging | 2.01 | pass | pass | — |
| layered_conduction | T(r2) (convection) | 2.01 | converging | 2.01 | pass | pass | — |
| layered_conduction | T3 (convection) | 1.998 | converging | 1.998 | pass | pass | — |
| womersley | centreline err (u_c) | 1.883 | converging | 1.883 | pass | pass | already net (error against exact at the same faces) |
| womersley | dpdx amplitude | 1.784 | converging | 1.784 | pass | pass | — |
| stenosis_pulsatile | throat peak | 1.081 | converging | 1.081 | reported | reported | n/a (V2: interpolated, no exact field) |
| stenosis | u_peak | 2.837 | oscillatory | — | reported | reported | n/a (V2: interpolated, no exact field) |
| stenosis | x_sep | 4.026 | converging | 4.026 | reported | reported | — |
| stenosis | x_reatt τ_w | 11.274 | oscillatory | — | reported | reported | — |
| stenosis | x_reatt u(0.48D) | 1.172 | oscillatory | — | reported | reported | — |
| rect_duct | fRe (cartesian, a/b 1) | 1.934 | converging | 1.934 | pass | pass | — |
| rect_duct | u_c (cartesian, a/b 1) | 1.914 | converging | 1.914 | pass | pass | fit, raw (see the net row) |
| rect_duct | u_c net of fit (cartesian, a/b 1) | 1.914 | converging | 1.914 | pass | pass | fit, k = 4: +0.0653% |
| rect_duct | fRe (cartesian, a/b 2) | 1.944 | converging | 1.944 | pass | pass | — |
| rect_duct | u_c (cartesian, a/b 2) | 1.904 | converging | 1.904 | pass | pass | fit, raw (see the net row) |
| rect_duct | u_c net of fit (cartesian, a/b 2) | 1.943 | converging | 1.943 | pass | pass | fit, k = 4: +0.0849% |
| rect_duct | fRe (cartesian, a/b 4) | 1.953 | converging | 1.953 | pass | pass | — |
| rect_duct | u_c (cartesian, a/b 4) | 1.909 | converging | 1.909 | pass | pass | fit, raw (see the net row) |
| rect_duct | u_c net of fit (cartesian, a/b 4) | 1.96 | converging | 1.96 | pass | pass | fit, k = 4: +0.0716% |

- **Status changes** affect report-only rows only.
  - Stenosis: u_peak and both reattachment points are oscillatory.  They
    used to show orders 2.84, 10.8 and 1.18.
  - rect_duct O-H: the square's "order 0.24" is now diverging.
- **heated_pipe's dT_b/dx** shows order 1.54 here against RESULTS.md's
  2.03, because the stored % errors (−0.0074, −0.0014) are too rounded.
  It is converging either way, and not gated.

**Point values net of their extraction bias** (amendment 3):
- rect_duct u_c:
  - fit bias at k = 4 is +0.065 / +0.085 / +0.072 % (a/b 1 / 2 / 4);
  - gated net value: +0.012 / +0.006 / +0.003 %, pass.  The raw u_c
    was +0.080 / +0.096 / +0.083 %.
- Poiseuille u_max, heated_rod ΔT₀ and layered_conduction T₀ are all
  c₀ of a c₀ + c₂r² fit, and every exact profile is that parabola.
  - So the bias is zero: measured ≤ 4.4e-16 at random sample points.
- Womersley's centreline (mean of 4 faces) is already gated as the error
  against the exact profile at the same faces.
- Stenosis and stenosis_pulsatile interpolate the centreline to the DNS
  stations.  These are V2 cases with no exact field, so the rule doesn't
  apply.
- heated_pipe's quantities are area averages and integrals, not point
  fits.

**Tests.**
- `tests/test_convergence.py`, `test_validation_meta.py` and
  `test_architecture.py`: 41 passed.
- rect_duct openfoam (coarse, both meshes): 2 passed.
- Poiseuille's three-level openfoam test was not rerun.  It needs more
  than the 30 min I gave it, and the task says not to rerun OpenFOAM.
  Its gate path is covered by the unit tests and the recheck of its
  stored values.
- Full suite: 2201 passed, 15 skipped (after 0081: 2189; +12 new), no failures.

**Proposed follow-ups.**
- Store each case's results JSON next to RESULTS.md, or gzipped.  Then
  rechecks don't depend on rounded tables (the dT_b/dx case above).
