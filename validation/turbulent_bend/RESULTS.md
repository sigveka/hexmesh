# Results: turbulent flow in a 90° bend

**Status: in progress.**  At the finest level (k = 3, 1.6 M cells) both
gates pass at all six planes: the RMS difference from the LDA is 0.020
to 0.072 of U_b (gate 0.10), and every peak is on the outer wall, as
measured.  But the three levels don't converge asymptotically.  The
wall cell shrinks with `refined(k)`, so the wall functions move from
the log layer (first-cell y⁺ 23 at k = 1) into the buffer layer (7.8 at
k = 3): the precursor's f drifts from McKeon by +0.6 %, +6.1 %, +9.0 %,
and K is oscillatory.  Whether the case is accepted on these gates is a
question for design (task 0050, Q2).  Run on 2026-11-19 with OpenFOAM
v2406 (Docker) and gmsh 4.12.1, at hexmesh e64ff49.  The numbers below
are recomputed from `results.json` by `python3 -m validation.tools.recheck
turbulent_bend`.

<!-- graphs:start -->
## Graphs

_Drawn from `results.json` by `python3 -m validation.tools.plots`; don't edit between the markers._

<img src="figure.png" width="100%" alt="The axial velocity across the bend plane at the six LDA planes: the measurements, each level, and the paper's own k-ω SST.">

The axial velocity across the bend plane at the six LDA planes: the measurements, each level, and the paper's own k-ω SST.

<!-- graphs:end -->

## Gate: RMS of w/U_b against the LDA, per plane

| plane | k = 1 | k = 2 | **k = 3** | Ekat et al.'s SST |
|---|---|---|---|---|
| 2.43 D | 0.0875 | 0.0492 | **0.0719** | 0.0554 |
| 5.56 D | 0.0817 | 0.0658 | **0.0285** | 0.0654 |
| 10.7 D | 0.0614 | 0.0580 | **0.0317** | 0.0504 |
| 15.69 D | 0.0714 | 0.0740 | **0.0267** | 0.0718 |
| 20.82 D | 0.0929 | 0.0982 | **0.0197** | 0.1032 |
| 30.82 D | 0.0984 | 0.1002 | **0.0365** | 0.1086 |

Ekat et al.'s SST (their mesh 3c, a half domain with a symmetry plane,
OpenFOAM v1812) is read from the same figure at the LDA points
(`reference/README.md`).  The full domain here showed none of the
asymmetry they report for SST on full domains.

## Gate: the side of the peak (x/R; negative is the outer wall)

| plane | LDA | k = 1 | k = 2 | **k = 3** |
|---|---|---|---|---|
| 2.43 D | −0.828 | −0.748 | −0.748 | **−0.748** |
| 5.56 D | −0.828 | −0.828 | −0.899 | **−0.828** |
| 10.7 D | −0.657 | −0.309 | −0.309 | **−0.163** |
| 15.69 D | −0.555 | −0.439 | −0.555 | **−0.309** |
| 20.82 D | −0.439 | −0.555 | −0.555 | **−0.309** |
| 30.82 D | −0.163 | −0.439 | −0.439 | **−0.309** |

## Reported: K and the convergence

| k | cells | f (precursor) vs McKeon | first-cell y⁺ (mean) | K | peak w/U_b at 2.43 D | at 10.7 D | steps |
|---|---|---|---|---|---|---|---|
| 1 | 59 200 | +0.55 % | 23.2 | 0.222 | 1.222 | 1.083 | 708 |
| 2 | 473 600 | +6.1 % | 11.6 | 0.261 | 1.239 | 1.089 | 1 880 |
| 3 | 1 598 400 | +9.0 % | 7.8 | 0.254 | 1.247 | 1.126 | 1 586 |

Richardson (k = 1, 2, 3): K **oscillatory** (within 0.222–0.261); the
peak at 10.7 D **diverging** (no asymptotic range); the peak at 2.43 D
converging at order 0.64 (extrapolated 1.271, GCI 2.5 %).  No cited
bend-loss correlation is in the references yet (Q2).

## Mesh

| k | min scaled Jacobian | min SICN | max non-orthogonality | max skewness | max aspect ratio |
|---|---|---|---|---|---|
| 1 | 0.770 | 0.051 | 28.1° | 0.61 | 49.7 |
| 2 | 0.740 | 0.048 | 36.0° | 0.56 | 51.6 |
| 3 | 0.730 | 0.048 | 38.9° | 0.55 | 52.3 |

`checkMesh` passes at every level.

## Cost (4 processes)

| k | precursor | bend solve |
|---|---|---|
| 1 | 26 s | 85 s |
| 2 | 13 min | 44 min |
| 3 | 34 min | 1 h 50 min |

These levels ran before task 0185, so they record the two solves
(`precursor.wall_s`, `bend_wall_s`), not the whole level's time.
