# Results: laminar flow in a 90° square-duct bend, Re 790

**Status: in progress.**  Task 0072 is blocked on Q3: design's gates
(answers of 2026-11-06) fail in part on the rig inlet.

- **Run:** 2026-11-06, with OpenFOAM v2406 (Docker
  `opencfd/openfoam-default:2406`) and gmsh 4.12.1, on 4 MPI processes.
- **Reference:** Taylor, Whitelaw & Yianneskis (1981), NASA CR-3367,
  Table I (`data/`).
- **Recheck:** `python3 -m validation.tools.recheck square_bend`.

## Inlets

- **Rig (gated):** a plug at the contraction exit, 7.5 D_h before the
  bend, as in the experiment.
- **Matched (a reported sensitivity):** a plug 12.6 D_h before the bend.
  This is the distance whose developing profile, in a straight duct at
  k = 2, best matches X_H = −0.50 (RMS 0.048 V_c).  The rig length gives
  0.089 V_c there.

## Gates (rig inlet)

| quantity | value | gate | verdict |
|---|---|---|---|
| peak U/V_c on the symmetry plane, θ = 60°, k = 1, 2, 3 | 1.5123, 1.5220, 1.5358 | Richardson converging | **fail** (the fine-pair difference, 0.0138, exceeds the coarse pair's, 0.0097) |
| the same, θ = 77.5° | 1.5154, 1.5838, 1.5877 | converging | pass (order 3.89, GCI 0.08 %) |
| peak position g, X_H = −0.50 (k = 3) | 0.7 (measured 0.5) | at the measured point | **fail** |
| X_H = −0.25 | 0.7 (0.5) | | **fail** |
| θ = 30° | 0.5 (0.5) | | pass |
| θ = 60° | 0.3 (0.3) | | pass |
| θ = 77.5° | 0.3 (0.1) | | **fail** |
| X_H = +0.25 | 0.1 (0.1) | | pass |
| X_H = +0.40 | 0.1 (0.1) | | pass |

Upstream, 7.5 D_h from a plug at Re 790, the flow is still developing.
Its profile has off-centre maxima, so the symmetry-plane peak sits at
g = 0.7, against the more developed measured profile's 0.5.  At θ =
77.5°, the peak hasn't yet reached the outer wall.  The matched inlet
passes the same position checks at every station, and its peak U
converges at both stations (GCI 0.05 % and 0.01 %).

## Reported: U/V_c RMS difference against the measurements (V_c)

The comparison is at 5 %, and its floor is the upstream mismatch.

| station | rig k = 1 | k = 2 | k = 3 | matched k = 1 | k = 2 | k = 3 |
|---|---|---|---|---|---|---|
| X_H = −0.50 | 0.101 | 0.089 | 0.091 | 0.081 | 0.048 | 0.047 |
| X_H = −0.25 | 0.123 | 0.101 | 0.100 | 0.114 | 0.082 | 0.076 |
| θ = 30° | 0.118 | 0.081 | 0.079 | 0.098 | 0.050 | 0.048 |
| θ = 60° | 0.130 | 0.083 | 0.075 | 0.084 | 0.077 | 0.093 |
| θ = 77.5° | 0.186 | 0.114 | 0.085 | 0.168 | 0.109 | 0.098 |
| X_H = +0.25 | 0.215 | 0.137 | 0.101 | 0.203 | 0.114 | 0.082 |
| X_H = +0.40 | 0.206 | 0.126 | 0.086 | 0.197 | 0.109 | 0.081 |

- **Cells:** the rig mesh has 18 576, 148 608 and 501 552; the matched
  mesh has 23 040, 184 320 and 622 080.
- **The 5 % comparison is missed** at every station on the rig inlet,
  and at five of seven on the matched inlet.
- **Measurement errors** (report §2.3): V_c ±0.8 %.  U/V_c has up to 3 %
  systematic error near velocity gradients, and under 1 % elsewhere.
- **The measured grid's flux:** by the trapezoid rule on the measured
  points, the measured values carry 0–3 % more flux than the computed
  field (matched inlet, k = 3).
