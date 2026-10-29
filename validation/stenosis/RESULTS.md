# Results: smooth cosine constriction, Re = 500

**Status: accepted** (task 0032, gates of decision 0012 as revised in the
task).  Steady state reached by `pimpleFoam` from rest (`simpleFoam`
doesn't converge on this case: `docs/integrations/openfoam.md`).

Run 2026-10-29/30: hexmesh a92840c plus this driver, gmsh 4.12.1,
OpenFOAM v1912, 4 MPI processes (`decomposePar` method simple).
Reference: Purdue database, `Axi_stdy/Re500/vel.dat`: DNS peak centreline
4.596 U (at the x = 0 station); reattachment 11.025 D by the database's
measure (axial velocity at r = 0.48 D turning positive, between the 1 D
stations).

## Levels

`Assembly.refined(k)`, k = 2, 3, 4.  k = 1 (15 336 cells) has no steady
axisymmetric state: its jet drifts off the axis (task 0032).  That's a
minimum resolution for this case, not a solver failure.

| Level | Cells | min SJ | max non-orth. (°) | max skewness | steady from t | time steps | wall time (s) | mass balance |
|---|---|---|---|---|---|---|---|---|
| k2 | 122 688 | 0.732 | 34.7 | 0.484 | 10 | 4328 | 760 | 1.5e-10 |
| k3 | 414 072 | 0.718 | 38.3 | 0.504 | 15 | 8891 | 5647 | 2.0e-11 |
| k4 | 981 504 | 0.710 | 40.2 | 0.515 | 15 | 11 972 | 17 705 | 3.8e-11 |

- **Steady:** the centreline (largest change, of the peak) and both
  reattachment measures change by less than 0.1 % over 5 time units
  (D/U); "steady from t" is the first state of the pair that passed.
  At the last check every change is below 5e-4, and the final initial
  residuals are at most 1.1e-4 (p) and 3.3e-6 (U).
- **Wall time:** the whole run from rest, on 4 cores.  Each level ran
  to t = 15 (k2) or 20 (k3, k4).

## Flow

| Level | u_peak / U | x_peak / D | x_sep / D | x_reatt / D, τ_w = 0 | x_reatt / D, u(0.48 D) = 0 | same, at 1 D stations | max centreline err. (of DNS peak) |
|---|---|---|---|---|---|---|---|
| k2 | 4.7038 | 0.181 | 0.225 | 11.123 | 10.981 | 10.982 | 1.32 % at x = 0 |
| k3 | 4.7237 | 0.139 | 0.213 | 11.405 | 11.019 | 11.020 | 1.25 % at x = 2 |
| k4 | 4.7168 | 0.146 | 0.211 | 11.402 | 10.970 | 10.972 | 0.93 % at x = 3 |
| DNS | (4.596 at x = 0) | | | | | 11.025 | |

Centreline error at the database stations, % of the DNS peak (k2 / k3 /
k4): −0.22 / −0.10 / −0.06 at −2 D; −1.32 / −0.31 / −0.15 at 0;
+1.06 / +1.23 / +0.87 at 1 D; +0.82 / +1.19 / +0.93 at 3 D;
+0.34 / +0.91 / +0.79 at 6 D; +0.10 / +0.71 / +0.56 at 10 D;
+0.13 / +0.62 / +0.45 at 15 D.  Past the throat the computed jet is
slightly faster than the DNS at every level.

Richardson extrapolation [celik_and_ghia_etal_2008], ratios 4/3 and 3/2
(the non-constant-ratio form, §2.1):

| Quantity | observed order | extrapolated | GCI fine | oscillatory |
|---|---|---|---|---|
| u_peak | 2.84 | 4.7113 | 0.14 % | True |
| x_sep | 3.53 | 0.2093 | 0.81 % | False |
| x_reatt, τ_w = 0 | (10.8) | 11.4017 | 0.002 % | True |
| x_reatt, u(0.48 D) = 0 | 1.18 | 10.849 | 1.4 % | True |

Most quantities converge oscillatorily (k3 overshoots k2 → k4), so the
extrapolated values are reported, not used, except the separation point.
- **τ_w = 0 reattachment** has converged: k3 and k4 agree to 0.03 %.
  The "order" 10.8 only says the k3–k4 change is tiny.
- **u(0.48 D) = 0 reattachment** varies within ±0.025 D (0.2 %) over
  the three levels.
- **Centreline:** extrapolated at the 3 stations where the order is
  defined and not oscillatory, the finest level elsewhere: largest
  error 0.93 % of the DNS peak, at x = 3 D.

## Gates

| Gate | Value | |
|---|---|---|
| Reattachment within 5 % of the database's 11.03 D, like with like (u(0.48 D) = 0) | 10.970 D, −0.50 % (k4) | **pass** |
| … and by wall shear stress | 11.402 D, +3.4 % (k4, converged) | **pass** |
| Centreline within 2 % of the DNS peak, x/D = −2 … 15 | 0.93 % at 3 D | **pass** |

The two reattachment measures differ by 0.43 D, and they should.  The
dividing streamline approaches the wall gradually, so the velocity 0.02 D
from the wall turns positive before the wall shear stress does.  The
paper's "≈ 10 D" (§3.1) is read off a figure and carries no gate.

## Cost per variant (for the planned surrogate study)

k2 is the cheapest steady level: 13 min on 4 cores from rest, 122 688
cells.  A variant started from a neighbouring variant's steady state
would need fewer time units; not measured.

## Measures

- **Centreline:** per axial slab, u = c0 + c2 r² fitted to the cells
  within 0.2 R(x) of the axis.  A wider window biases the axis value
  high past the throat, where the jet has a flat core and a shear layer:
  0.35 R gave up to +0.06 U at k3 (2.85 % of the DNS peak against the
  gate's 2 %); 0.2 R and 0.12 R agree to 0.004 U, and a quartic over
  0.35 R to 0.015 U (0.3 % of the peak), which bounds the measure's own
  uncertainty.
- **Near-wall probe:** per slab past the constriction,
  u = (R − r)(a + b(R − r)) fitted to the cells in the outer quarter of
  the radius, so it vanishes at the wall, evaluated at r = 0.48 D.
- **Wall shear stress:** ν u_t / d from each wall cell, averaged per
  axial position.
