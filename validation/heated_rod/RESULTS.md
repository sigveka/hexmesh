# Heated rod: results

hexmesh `faddea0`, gmsh 4.12.1, OpenFOAM v1912, 2026-10-27 (task 0033).
Exact centre excess ΔT₀ = 1 K.  Errors are relative to ΔT₀, signed where
marked.  Judged per decision 0015 as amended 2026-10-27: on O-H sections
the observed order is reported, not gated.

## Levels

| series | nang | nrad | cells | Mesh OK | max non-orth. (°) | max skewness | energy balance | ΔT₀ error | L2 error | max error (at r/R) |
|---|---|---|---|---|---|---|---|---|---|---|
| uniform | 6 | 3 | 216 | yes | 23.5 | 0.422 | 1.2e-14 | −1.377 % | 1.324e-02 | 1.544e-02 (0.46) |
| uniform | 12 | 6 | 864 | yes | 33.2 | 0.484 | 3.2e-14 | −0.459 % | 3.873e-03 | 5.272e-03 (0.51) |
| uniform | 24 | 12 | 3 456 | yes | 38.9 | 0.515 | 3.5e-14 | −0.176 % | 1.307e-03 | 2.083e-03 (0.53) |
| uniform | 48 | 24 | 13 824 | yes | 41.9 | 0.529 | 6.2e-14 | −0.076 % | 5.160e-04 | 9.131e-04 (0.54) |
| uniform | 96 | 48 | 55 296 | yes | 43.4 | 0.534 | 2.0e-15 | −0.035 % | 2.286e-04 | 5.633e-04 (0.60) |
| graded | 6 | 3 | 216 | yes | 23.5 | 0.564 | 5.0e-14 | −1.716 % | 1.256e-02 | 1.862e-02 (0.43) |
| graded | 12 | 6 | 864 | yes | 33.2 | 0.675 | 9.0e-14 | −0.559 % | 3.875e-03 | 6.286e-03 (0.49) |
| graded | 24 | 12 | 3 456 | yes | 38.9 | 0.729 | 2.7e-13 | −0.205 % | 1.271e-03 | 2.389e-03 (0.52) |
| graded | 48 | 24 | 13 824 | yes | 41.9 | 0.754 | 2.0e-13 | −0.086 % | 5.122e-04 | 1.700e-03 (0.59) |
| graded | 96 | 48 | 55 296 | yes | 43.4 | 0.762 | 5.7e-13 | −0.040 % | 2.411e-04 | 1.239e-03 (0.60) |

Energy balance: |heat out − Su · V_mesh| / (Su · V_mesh), solver tolerance
at every level.  Every level converged in 2–3 steps (initial residual
≤ 1e-14).

## Observed orders (log₂ of successive error ratios)

| series | L2 | max | ΔT₀ |
|---|---|---|---|
| uniform | 1.77, 1.57, 1.34, **1.17** | 1.55, 1.34, 1.19, 0.70 | 1.58, 1.38, 1.22, 1.12 |
| graded | 1.70, 1.61, 1.31, **1.09** | 1.57, 1.40, 0.49, 0.46 | 1.62, 1.45, 1.25, 1.12 |

**The order does not level off near 1.3: it keeps falling, toward 1.**

Richardson on ΔT₀ (three finest levels, k = 4, 8, 16):

| series | order | extrapolated ΔT₀ | − exact | GCI fine |
|---|---|---|---|---|
| uniform | 1.30 | 0.999930 | −0.007 % | 0.035 % |
| graded | 1.35 | 0.999902 | −0.010 % | 0.037 % |

Gate (decision 0015, amended): extrapolated ΔT₀ within 0.1 % of exact:
**met**.  The local order is not constant (1.22 then 1.12), so the
three-level Richardson order is an average; GCI's safety factor covers
that.

## Where the error is

Volume-weighted L2 by region (normalised by the whole volume).  Core =
inside the O-H square, half-side 0.6 R/√2; diagonal = ring cells within
10° of 45°, the sector of the core corners.

| series | region | orders 1→2, 2→4, 4→8, 8→16 | L2 at k = 16 |
|---|---|---|---|
| uniform | core square | 1.79, 1.41, 1.23, 1.13 | 1.67e-04 |
| uniform | ring, diagonals | 2.65, 1.67, 1.73, **1.01** | 4.47e-05 |
| uniform | ring, elsewhere | 1.56, 1.66, 1.41, 1.24 | 1.50e-04 |
| graded | core square | 1.83, 1.47, 1.25, 1.13 | 1.88e-04 |
| graded | ring, diagonals | 2.41, 1.50, 1.39, **0.91** | 6.00e-05 |
| graded | ring, elsewhere | 1.35, 1.80, 1.41, 1.04 | 1.39e-04 |

- The error is a near-uniform **negative bias** at every level (volume
  mean ≈ −L2; uniform k = 16: mean −1.76e-04, L2 2.29e-04).
- From k = 8 to 16 **every region** converges at about first order; the
  diagonal ring sector, next to the core corners, is now the slowest
  (1.01 / 0.91), and the largest error sits **at** the corner (r/R 0.60).
- **Max non-orthogonality keeps growing** (23.5° → 43.4°), toward the
  45° of the core-square corner (cell angles 90° / 135° / 135°); max
  skewness levels off at 0.53 (uniform) / 0.76 (graded).  The mesh family
  is not self-similar at the corners.
- The meshed volume is the inscribed polygon; its effect on T is second
  order and does not explain the falling order.

This is consistent with a local error at the core-square corners that
does not shrink with the cells, spreading through the elliptic solution
(decision 0022).  It is still a correlation: decision 0022's option B (a
corner-free control mesh) would establish the cause.
