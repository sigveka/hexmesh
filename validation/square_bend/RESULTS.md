# Results: laminar flow in a 90° square-duct bend, Re 790

**Status: in progress** (task 0072, blocked on its questions for design):
the RMS gate fails at five of the seven stations.  Run 2026-11-06,
OpenFOAM v2406 (Docker `opencfd/openfoam-default:2406`), gmsh 4.12.1,
hexmesh 42357ca plus this task's uncommitted changes, 4 MPI processes.
Reference: Taylor, Whitelaw & Yianneskis (1981), NASA CR-3367, Table I
(`data/`).  `python3 -m validation.tools.recheck square_bend` recomputes
the gates.

## Inlet

A plug inlet 12.6 D_h upstream of the bend: the distance whose developing
profile, in a straight duct at k = 2, best matches X_H = −0.50 (RMS
0.048 V_c).  The rig's 7.5 D_h from the contraction gives 0.089 V_c
there: the measured flow is more developed than a plug at the
contraction exit.

## Gates (finest level, k = 3: 36 cells per side, 622 080 cells)

| station | U/V_c RMS diff | max diff | flux-matched RMS | V/V_c RMS diff | peak g, measured | peak g, computed |
|---|---|---|---|---|---|---|
| X_H = −0.50 | **0.047** | 0.127 | 0.047 | — | 0.5 | 0.5 |
| X_H = −0.25 | 0.076 | 0.233 | 0.072 | 0.018 | 0.5 | 0.5 |
| θ = 30° | **0.048** | 0.099 | 0.041 | 0.074 | 0.5 | 0.5 |
| θ = 60° | 0.093 | 0.250 | 0.093 | 0.039 | 0.3 | 0.3 |
| θ = 77.5° | 0.098 | 0.189 | 0.095 | 0.043 | 0.1 | 0.1 |
| X_H = +0.25 | 0.082 | 0.205 | 0.076 | 0.030 | 0.1 | 0.1 |
| X_H = +0.40 | 0.081 | 0.192 | 0.078 | — | 0.1 | 0.1 |

- **RMS within 5 % of V_c:** pass at X_H = −0.50 and θ = 30°, **fail**
  elsewhere (0.076–0.098).
- **Outward shift of the peak** on the symmetry plane: **pass**.  It
  sits at the measured gapwise point at every station: g = 0.5 upstream
  and at 30°, 0.3 at 60°, 0.1 (near the outer wall) from 77.5°.

## By level

| station | RMS k = 1 | k = 2 | k = 3 |
|---|---|---|---|
| X_H = −0.50 | 0.081 | 0.048 | 0.047 |
| X_H = −0.25 | 0.114 | 0.082 | 0.076 |
| θ = 30° | 0.098 | 0.050 | 0.048 |
| θ = 60° | 0.084 | 0.077 | 0.093 |
| θ = 77.5° | 0.168 | 0.109 | 0.098 |
| X_H = +0.25 | 0.203 | 0.114 | 0.082 |
| X_H = +0.40 | 0.197 | 0.109 | 0.081 |

## Convergence: peak U/V_c on the symmetry plane

| station | k = 1 | k = 2 | k = 3 | status | order | extrapolated | GCI (fine) |
|---|---|---|---|---|---|---|---|
| θ = 60° | 1.5720 | 1.6168 | 1.6195 | converging | 3.84 | 1.6202 | 0.05 % |
| θ = 77.5° | 1.6250 | 1.6774 | 1.6786 | converging | 5.25 | 1.6788 | 0.01 % |

Levels k = 1, 2, 3 (ratios 2, 1.5).  The orders are high because the
k = 1 level is coarse; the fine-level GCIs are what matter.  At k = 3 the
peak is mesh-converged, so the remaining RMS differences are not
discretisation error.

## Measurement context

The report's errors (§2.3) are V_c ±0.8 %, and U/V_c up to 3 %
systematic near velocity gradients (under 1 % elsewhere).  By the
trapezoid rule on the measured points, the measured grid carries 0–3 %
more flux than the computation at k = 3.  The largest differences are
at θ = 60°–77.5° and just downstream, near the inner wall, where the
secondary flow carries low-velocity fluid (task Agent notes).
