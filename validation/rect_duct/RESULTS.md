# Results: laminar flow in rectangular ducts

**Status: accepted** on the Cartesian control (task 0071; gates of
decision 0015 amendment 2).  The hexmesh O-H levels are reported, not
gated: their f·Re error falls at order well below 2, and on the square it
is still +1.16 % at 138k cells.

Run 2026-11-02: OpenFOAM v2406 (Docker `opencfd/openfoam-default:2406`),
gmsh 4.12.1.  O-H levels at hexmesh 1063b15, control at 6309d2c; the two
commits are design documents only (no change under `hexmesh/` or
`validation/poiseuille/`).  Exact values from the series (README):
f·Re 56.908 / 62.192 / 72.931 and u_c/Ū 2.0963 / 1.9918 / 1.7737 for
a/b = 1 / 2 / 4.  Signed errors against them throughout.  The rectangle
is meshed exactly (area − 4ab ≤ 2.4e-16 relative), so the exact solution
is also the meshed geometry's: there's no geometric deficit to separate,
unlike the pipe.

## Gates (Cartesian control)

| Gate | a/b = 1 | a/b = 2 | a/b = 4 | |
|---|---|---|---|---|
| extrapolated f·Re within 0.1 % | +0.011 % | +0.008 % | +0.006 % | **pass** |
| extrapolated u_c within 0.1 % | +0.080 % | +0.096 % | +0.083 % | **pass** (see the centre fit, below) |
| finest f·Re error < 1 % | −0.258 % | −0.202 % | −0.171 % | **pass** |
| finest u_c error < 1 % | −0.110 % | −0.040 % | −0.022 % | **pass** |
| observed order near 2: f·Re | 1.93 | 1.94 | 1.95 | **pass** |
| observed order near 2: u_c | 1.91 | 1.90 | 1.91 | **pass** |

Monotone in every quantity at every ratio, so the setup (exact inlet,
planes, post-processing, Richardson) is sound.

**The centre fit.**  u_c comes from a fit to the plane's face values
(README), and the same fit applied to the exact solution at the same
faces is off by +0.06 to +0.09 % at the fine levels (last column of the
field table).  That bias, not the solver, is almost all of the
extrapolated u_c error.  Subtracting it level by level, the control's
extrapolated u_c is +0.012 / +0.006 / +0.003 % (order 1.91 / 1.94 /
1.96).  The gate passes as measured.  The margin is thin only because
of the fit.

### Errors side by side

| a/b | k | cells O-H / Cartesian | f·Re, O-H | f·Re, Cartesian | O-H ÷ Cartesian | u_c, O-H | u_c, Cartesian | O-H ÷ Cartesian |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 2160 / 2000 | +2.646 % | -3.922 % | 0.67 | +0.088 % | -2.623 % | 0.03 |
| 1 | 2 | 17280 / 16000 | +1.966 % | -1.018 % | 1.93 | +0.431 % | -0.637 % | 0.68 |
| 1 | 4 | 138240 / 128000 | +1.161 % | -0.258 % | 4.50 | +0.344 % | -0.110 % | 3.11 |
| 2 | 1 | 3600 / 3240 | +0.455 % | -3.094 % | 0.15 | +0.173 % | -1.797 % | 0.10 |
| 2 | 2 | 28800 / 25920 | +0.698 % | -0.798 % | 0.87 | +0.402 % | -0.410 % | 0.98 |
| 2 | 4 | 230400 / 207360 | +0.476 % | -0.202 % | 2.36 | +0.321 % | -0.040 % | 8.09 |
| 4 | 1 | 6480 / 6480 | -0.663 % | -2.652 % | 0.25 | -0.002 % | -1.398 % | 0.00 |
| 4 | 2 | 51840 / 51840 | +0.078 % | -0.681 % | 0.11 | +0.234 % | -0.311 % | 0.75 |
| 4 | 4 | 414720 / 414720 | +0.146 % | -0.171 % | 0.85 | +0.190 % | -0.022 % | 8.71 |

### Richardson extrapolation (k = 1, 2, 4; ratio 2)

| a/b | quantity | mesh | observed order | extrapolated − exact | GCI fine | oscillatory | differences grow |
|---|---|---|---|---|---|---|---|
| 1 | f·Re | Cartesian | 1.93 | +0.011 % | 0.338 % | False | False |
| 1 | f·Re | O-H | 0.24 (not meaningful) | -3.263 % | 5.467 % | False | True |
| 1 | u_c | Cartesian | 1.91 | +0.080 % | 0.238 % | False | False |
| 1 | u_c | O-H | 1.97 (not meaningful) | +0.314 % | 0.037 % | True | False |
| 2 | f·Re | Cartesian | 1.94 | +0.008 % | 0.262 % | False | False |
| 2 | f·Re | O-H | 0.13 (not meaningful) | -1.894 % | 2.949 % | True | False |
| 2 | u_c | Cartesian | 1.90 | +0.096 % | 0.169 % | False | False |
| 2 | u_c | O-H | 1.50 (not meaningful) | +0.276 % | 0.055 % | True | False |
| 4 | f·Re | Cartesian | 1.95 | +0.006 % | 0.222 % | False | False |
| 4 | f·Re | O-H | 3.44 | +0.153 % | 0.009 % | False | False |
| 4 | u_c | Cartesian | 1.91 | +0.083 % | 0.131 % | False | False |
| 4 | u_c | O-H | 2.44 (not meaningful) | +0.181 % | 0.012 % | True | False |

### Velocity field on the 5 D_h plane (fraction of exact u_c)

| a/b | k | max, O-H | max, Cartesian | RMS, O-H | RMS, Cartesian | centre-fit bias, O-H / Cartesian |
|---|---|---|---|---|---|---|
| 1 | 1 | 2.419 % | 2.587 % | 0.771 % | 1.307 % | +0.028 % / +0.028 % |
| 1 | 2 | 1.769 % | 0.689 % | 0.407 % | 0.349 % | +0.057 % / +0.057 % |
| 1 | 4 | 1.166 % | 0.175 % | 0.226 % | 0.089 % | +0.065 % / +0.065 % |
| 2 | 1 | 2.277 % | 1.908 % | 0.634 % | 1.023 % | +0.068 % / +0.119 % |
| 2 | 2 | 1.596 % | 0.490 % | 0.355 % | 0.269 % | +0.089 % / +0.084 % |
| 2 | 4 | 1.041 % | 0.124 % | 0.199 % | 0.068 % | +0.095 % / +0.085 % |
| 4 | 1 | 2.412 % | 1.474 % | 0.586 % | 0.884 % | +0.046 % / +0.058 % |
| 4 | 2 | 1.644 % | 0.376 % | 0.311 % | 0.230 % | +0.078 % / +0.061 % |
| 4 | 4 | 1.057 % | 0.095 % | 0.170 % | 0.058 % | +0.065 % / +0.072 % |

### Meshes and solver

| mesh | a/b | k | cells (= checkMesh) | Mesh OK | max non-orth. (°) | max skewness | min SJ | iterations | mass balance | area − 4ab | solver time (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| O-H | 1 | 1 | 2160 | True | 39.8 | 1.145 | 0.707 | 109 | 9.9e-12 | +0.0e+00 | 1 |
| O-H | 1 | 2 | 17280 | True | 42.5 | 1.197 | 0.707 | 217 | 3.8e-13 | +0.0e+00 | 7 |
| O-H | 1 | 4 | 138240 | True | 43.8 | 1.224 | 0.707 | 494 | 3.8e-12 | +0.0e+00 | 213 |
| O-H | 2 | 1 | 3600 | True | 42.5 | 1.171 | 0.707 | 20000 (cap, see below) | 9.4e-10 | -2.4e-16 | 102 |
| O-H | 2 | 2 | 28800 | True | 43.8 | 1.210 | 0.707 | 241 | 1.2e-12 | +1.2e-16 | 16 |
| O-H | 2 | 4 | 230400 | True | 44.4 | 1.230 | 0.707 | 739 | 2.5e-12 | +0.0e+00 | 660 |
| O-H | 4 | 1 | 6480 | True | 43.8 | 1.183 | 0.707 | 124 | 1.3e-10 | +0.0e+00 | 2 |
| O-H | 4 | 2 | 51840 | True | 44.4 | 1.217 | 0.707 | 316 | 1.3e-12 | +0.0e+00 | 55 |
| O-H | 4 | 4 | 414720 | True | 44.7 | 1.233 | 0.707 | 1005 | 5.1e-11 | +0.0e+00 | 1709 |
| Cartesian | 1 | 1 | 2000 | True | 0.0 | 0.000 | 1 (uniform) | 104 | 1.1e-11 | +0.0e+00 | 0 |
| Cartesian | 1 | 2 | 16000 | True | 0.0 | 0.000 | 1 (uniform) | 203 | 1.8e-12 | +1.4e-16 | 6 |
| Cartesian | 1 | 4 | 128000 | True | 0.0 | 0.000 | 1 (uniform) | 520 | 1.6e-14 | +1.4e-16 | 115 |
| Cartesian | 2 | 1 | 3240 | True | 0.0 | 0.000 | 1 (uniform) | 121 | 6.1e-11 | +0.0e+00 | 1 |
| Cartesian | 2 | 2 | 25920 | True | 0.0 | 0.000 | 1 (uniform) | 247 | 1.6e-12 | +0.0e+00 | 13 |
| Cartesian | 2 | 4 | 207360 | True | 0.0 | 0.000 | 1 (uniform) | 760 | 3.6e-12 | +0.0e+00 | 362 |
| Cartesian | 4 | 1 | 6480 | True | 0.0 | 0.000 | 1 (uniform) | 125 | 1.2e-10 | +0.0e+00 | 3 |
| Cartesian | 4 | 2 | 51840 | True | 0.0 | 0.000 | 1 (uniform) | 324 | 2.0e-12 | +0.0e+00 | 45 |
| Cartesian | 4 | 4 | 414720 | True | 0.0 | 0.000 | 1 (uniform) | 1084 | 1.2e-11 | +0.0e+00 | 1099 |

"O-H ÷ Cartesian" is |O-H error| / |control error| at the same level.
The control has the same axial cells and about the same section cells:
100 / 162 / 324 per section at k = 1, against the O-H's 108 / 180 / 324.

## The O-H levels (reported)

- **f·Re converges slowly or not at all.**
  - Square: +2.65 → +1.97 → +1.16 %.  The differences grow (0.68, then
    0.81), so there is no asymptotic range.
  - a/b = 2: +0.45 → +0.70 → +0.48 %, non-monotone.
  - a/b = 4: −0.66 → +0.08 → +0.15 %, a sign change.  Its formal order
    of 3.44 is the sign change, not convergence.
  - The O-H errors and the control's have opposite signs, so the coarse
    O-H levels look better than the control: the corners' error cancels
    part of the discretisation error.  By the finest level the control
    is 2.4–4.5× more accurate on the square and a/b = 2.  At a/b = 4 the
    O-H f·Re is still slightly closer (0.85×), because its error is
    passing through zero, not converging.
- **u_c oscillates at every ratio** (O-H +0.09 → +0.43 → +0.34 % on the
  square), so its Richardson orders aren't meaningful either.  At the
  finest level the control's u_c is 3–9× more accurate.
- **The field.**  The O-H max error falls about 1.4× per level (2.4 →
  1.7 → 1.2 %), the control's about 4× (2.6 → 0.69 → 0.18 %).  The O-H
  RMS error stays low (0.17–0.23 % at the fine level): its error is local.
- **Mesh.**
  - Max non-orthogonality grows with refinement towards 45° (39.8 →
    42.5 → 43.8° on the square; 44.7° at a/b = 4, k = 4).
  - Min scaled Jacobian is 0.707 at every level (the 45° corner cells).
  - This matches the design session's 2-D control, RESEARCH §7.11.
- **Richardson caveat.**  Poiseuille's `richardson()` takes |log(ε32/ε21)|,
  so growing differences still give an order > 0, here 0.24 for the
  square, with an extrapolation in the wrong direction (−3.26 %).
  `extrapolate()` now flags this as `differences_grow`.

## Solver notes

- **O-H a/b = 2, k = 1 stopped at the 20 000-iteration cap.**
  - Ux (2.6e-7) and p (3.5e-5) had settled.  The transverse components
    Uy, Uz stayed at initial residuals ~1e-3.
  - The exact transverse velocity is zero, so OpenFOAM's normalised
    residual of a near-zero field doesn't fall.  The axial field and Δp
    are steady.
  - Reported as is; it is not gated.
- Mass balance ≤ 1.3e-10 everywhere.  The inlet flow rate is Ū·A to
  ≤ 1.2e-13, because the exact inlet is scaled to the discrete flow rate.
- Cost at the finest level:
  - Square: 213 s O-H against 115 s for the control.
  - a/b = 4: 1709 s against 1099 s at the same cell count; the control
    needed 1084 iterations against the O-H's 1005, but its iterations
    are cheaper.
  - Serial, one core.

## Reproduce

```bash
python3 validation/rect_duct/run.py --json out.json      # both meshes, ~75 min serial
python3 -m pytest -m openfoam tests/test_validation.py -k rect_duct
```
