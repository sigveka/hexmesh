# Results: Womersley flow, α = 7.5, A = 0.667, Re = 600

**Status: accepted** (task 0067; gates of decision 0012 as set in the
task).  Every gate passes at the finest level, k4.

Run 2026-10-30: hexmesh 75e9f27 plus this driver, gmsh 4.12.1, OpenFOAM
v2406 (`opencfd/openfoam-default:2406` in Docker), k2 and k4 on 4 MPI
processes (`decomposePar` method simple).  Reference: the exact solution
(README.md).

## Levels

`nang`/`nrad`/axial layers ×k; Δt ∝ 1/k (Co ≈ 0.47 on every level).

| Level | Cells | min SJ | max non-orth. (°) | steps per period | periods to periodic | last change | solver time per period (s) | inlet applied error |
|---|---|---|---|---|---|---|---|---|
| k1 | 7 680 | 0.773 | 28.1 | 240 | 3 | 3.7e-08 | 30 | 2.4e-10 |
| k2 | 61 440 | 0.741 | 36.0 | 480 | 3 | 3.5e-08 | 140–240 | 2.4e-10 |
| k4 | 491 520 | 0.724 | 40.4 | 960 | 2 | 6.7e-04 | 8 500–9 700 | 1.9e-10 |
| k2, Δt/2 | 61 440 | | | 960 | 2 (warm) | 3.7e-04 | 250–370 | |

- **Periodic:** the centreline velocity and pressure gradient at the six
  phases change by less than 0.1 % (of u_c, and of the gradient
  amplitude) between consecutive periods.  Starting from the exact field
  at t₀, this takes 2–3 periods.
- **Inlet:** the face values OpenFOAM applied, in every written field,
  match the formula to 2e-10 (`timeVaryingMappedFixedValue`, boundaryData
  at every solver step).
- **Flow rate:** the mid-plane flow rate matches the exact one to 2e-5
  (k1), 8e-7 (k2), 2e-8 (k4), relative to the peak.

## Profile at the mid plane, by phase

Max and RMS error as % of u_c; centreline error in units of 10⁻³ u_c.

| t/T | k1 max | k1 RMS | k2 max | k2 RMS | k4 max | k4 RMS | centreline k1 / k2 / k4 |
|---|---|---|---|---|---|---|---|
| 0.09 | 0.91 | 0.36 | 0.25 | 0.09 | 0.07 | 0.02 | 9.1 / 2.5 / 0.50 |
| 0.26 (peak) | 1.63 | 0.69 | 0.53 | 0.20 | 0.15 | 0.05 | 5.3 / 1.4 / 0.36 |
| 0.42 | 2.11 | 1.03 | 0.65 | 0.27 | 0.26 | 0.07 | 5.3 / 1.4 / 0.35 |
| 0.59 | 1.42 | 0.76 | 0.51 | 0.18 | **0.31** | 0.05 | 3.5 / 0.74 / 0.14 |
| 0.76 (min.) | 0.87 | 0.40 | 0.41 | 0.10 | 0.23 | 0.03 | 1.7 / 0.13 / −0.05 |
| 0.92 | 0.89 | 0.48 | 0.30 | 0.12 | 0.11 | 0.03 | 3.4 / 0.57 / 0.03 |

The peak and minimum of the exact centreline velocity fall on the phase
samples 0.26 and 0.76.

- **Gate: max ≤ 1 % of u_c at every phase, finest level: passes,** worst
  0.31 % (t/T 0.59).
- **RMS errors converge at second order** (observed order 1.8–2.1 per
  refinement at every phase).  **The max error converges more slowly:**
  the worst over all phases goes 2.11 → 0.65 → 0.31 %, orders 1.7 and 1.1,
  and the worst phase moves from 0.42 (k2) to 0.59 (k4).  It is a local
  error, at one location.  Its position isn't recorded and the cause
  isn't established.  One candidate: the wall grading (`mprg` 0.85^(1/k))
  changes with the level, so the near-wall cells don't halve exactly.

## Pressure gradient (planes at 4 D and 6 D)

Least-squares fit c₀ + c₁ cos ωt + s₁ sin ωt over the last period.
Exact amplitude ω u_c A = 0.250125; exact mean 4νu_c/R² = 0.02667.

| Level | amplitude | error | phase (°) | mean error |
|---|---|---|---|---|
| k1 | 0.250854 | +0.29 % | 0.35 | −1.6 % |
| k2 | 0.250327 | +0.081 % | 0.089 | −0.47 % |
| k4 | 0.250174 | **+0.020 %** | **0.022** | −0.15 % |

**Gates: amplitude within 1 %, phase within 2°, finest level: pass.**

## Convergence (decision 0015)

| Quantity | k1 | k2 | k4 | order | extrapolated | GCI (k4) |
|---|---|---|---|---|---|---|
| centreline velocity at peak, error (u_c) | 5.32e-3 | 1.42e-3 | 3.63e-4 | 1.89 | **−2.9e-5** | 4.9e-4 |
| pressure-gradient amplitude | 0.250854 | 0.250327 | 0.250174 | 1.79 | 0.250113 (**−0.005 %**) | 0.031 % |

**Gate: extrapolated within 0.3 %: passes.**  The centreline value is
the mean of the four faces nearest the axis.  Those faces move with the
level, so the signed error against the exact profile at the same points
is extrapolated (exact limit 0), not the raw velocity.  The raw velocity
extrapolates 0.04 % off, from the sampling points alone.

## Time step (k2, Δt halved)

k2 at 960 steps per period (Co 0.23), warm-started from k2's periodic
state.  Second order in time, so the time error at k2's Δt ≈ 4/3 × the
change on halving.

| Quantity | change on halving Δt | time error at k2's Δt | space error at k2 |
|---|---|---|---|
| centreline velocity at peak (u_c) | 2.1e-5 | 2.8e-5 | 1.42e-3 |
| pressure-gradient amplitude | 0.0042 % | 0.0055 % | 0.081 % |
| max profile error, all phases | 0.650 → 0.649 % | | |

**Gate: time error below space error: passes,** at about 2 % (centreline)
and 7 % (amplitude) of the space error.  k4 wasn't run with Δt halved
(about 5 h per period, so roughly 10 h more).  Both errors are second order and Δt ∝ h, so the split
should be the same there.

## Reproduce

```bash
python3 validation/womersley/run.py --np 4 --dt-halved k2 --json out.json
```
