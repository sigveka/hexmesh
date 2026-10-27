# Heated rod: results

hexmesh `d71d0d8`, gmsh 4.12.1, OpenFOAM v1912, 2026-10-27 (task 0033).
Exact centre excess ΔT₀ = 1 K.  Errors are relative to ΔT₀, signed where
marked.

## Levels

| series | nang | nrad | cells | Mesh OK | max non-orth. (°) | max skewness | energy balance | ΔT₀ error | L2 error | max error (at r/R) |
|---|---|---|---|---|---|---|---|---|---|---|
| uniform | 6 | 3 | 216 | yes | 23.5 | 0.422 | 1.2e-14 | −1.377 % | 1.324e-02 | 1.544e-02 (0.46) |
| uniform | 12 | 6 | 864 | yes | 33.2 | 0.484 | 3.2e-14 | −0.459 % | 3.873e-03 | 5.272e-03 (0.51) |
| uniform | 24 | 12 | 3456 | yes | 38.9 | 0.515 | 3.5e-14 | −0.176 % | 1.307e-03 | 2.083e-03 (0.53) |
| uniform | 48 | 24 | 13824 | yes | 41.9 | 0.529 | 6.2e-14 | −0.076 % | 5.160e-04 | 9.131e-04 (0.54) |
| graded | 6 | 3 | 216 | yes | 23.5 | 0.564 | 5.0e-14 | −1.716 % | 1.256e-02 | 1.862e-02 (0.43) |
| graded | 12 | 6 | 864 | yes | 33.2 | 0.675 | 9.0e-14 | −0.559 % | 3.875e-03 | 6.286e-03 (0.49) |
| graded | 24 | 12 | 3456 | yes | 38.9 | 0.729 | 2.7e-13 | −0.205 % | 1.271e-03 | 2.389e-03 (0.52) |
| graded | 48 | 24 | 13824 | yes | 41.9 | 0.754 | 2.0e-13 | −0.086 % | 5.122e-04 | 1.700e-03 (0.59) |

Energy balance: |heat out − Su · V_mesh| / (Su · V_mesh), solver tolerance
at every level.

## Observed orders (log₂ of successive error ratios)

| series | L2 | max | ΔT₀ |
|---|---|---|---|
| uniform | 1.77, 1.57, **1.34** | 1.55, 1.34, 1.19 | 1.58, 1.38, 1.22 |
| graded | 1.70, 1.61, **1.31** | 1.57, 1.40, 0.49 | 1.62, 1.45, 1.25 |

Richardson on ΔT₀ (three finest levels):

| series | order | extrapolated ΔT₀ | − exact | GCI fine |
|---|---|---|---|---|
| uniform | 1.49 | 0.999802 | −0.020 % | 0.070 % |
| graded | 1.58 | 0.999736 | −0.026 % | 0.075 % |

**The L2 order falls below 1.5 at the finest pair (expected ≈ 2).**  Per
the task, not tuned; reported to design (task 0033, *Questions for design*).

## Where the error is

Volume-weighted L2 by region, uniform series, k = 4 → 8 (core = inside
the O-H square, half-side 0.6 R/√2; diagonal = within 10° of 45°):

| region | L2, k = 4 | L2, k = 8 | order |
|---|---|---|---|
| core square | 8.55e-04 | 3.65e-04 | 1.23 |
| ring, near the diagonals | 2.99e-04 | 9.03e-05 | 1.73 |
| ring, off the diagonals | 9.42e-04 | 3.54e-04 | 1.41 |
| all | 1.31e-03 | 5.16e-04 | 1.34 |

- The error is a near-uniform **negative bias** (volume mean ≈ −L2 at
  every level): T is low everywhere, as a global (elliptic) effect of a
  local error would be, not a local spike.
- The **core square** converges slowest (1.79 → 1.41 → 1.23).
- **Max non-orthogonality grows with refinement** (23.5° → 41.9°), and
  the worst faces converge onto the four **core-square corners** (r/R
  0.497 → 0.553 → 0.578 → 0.589, toward 0.6 on the 45° diagonals), the
  valence-3 points of the O-H grid.  The mesh family is therefore not
  geometrically self-similar near those corners, which is what a
  Richardson analysis assumes.
- The meshed volume is the inscribed polygon (−0.29 % at nang 12); its
  effect on T is second order and does not explain the falling order.

For task 0020's open question this points at the O-H core: the order
falls here too, without pressure–velocity coupling or the Poiseuille
polygon reference, and fastest in the core, whose corners are the one
place where the mesh does not refine self-similarly.  That is a
correlation; a corner-free control (e.g. a mesh whose core corners are
smoothed or a polar grid with an axis treatment) would be needed to show
cause.
