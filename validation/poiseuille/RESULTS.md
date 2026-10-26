# Results: laminar Hagen–Poiseuille

**Status: not accepted.**  Task 0020 is blocked on a mesh finding (below).

Versions: hexmesh `82147f4`, gmsh 4.12.1, OpenFOAM v1912
(Ubuntu `openfoam` 1912.200626-2build3).  Run 2026-10-26.

Exact: Δp = 8.000000e-05 m²/s² (15 D → 25 D), u_max = 1.000000e-02 m/s.

## As meshed by hexmesh

| Level | Cells | min SJ | max non-orth. (°) | max skewness | Iterations | Δp (m²/s²) | e(Δp) | u_max (m/s) | e(u_max) | mass balance |
|---|---|---|---|---|---|---|---|---|---|---|
| coarse | 5184 | 0.793 | 23.3 | 0.430 | 107 | 8.207188e-05 | 2.590% | 1.001405e-02 | 0.141% | 1.8e-12 |
| medium | 41472 | 0.752 | 32.9 | 0.479 | 327 | 8.210301e-05 | 2.629% | 1.009291e-02 | 0.929% | 1.3e-11 |
| fine | 331776 | 0.730 | 38.3 | 0.508 | 941 | 8.207951e-05 | 2.599% | 1.011352e-02 | 1.135% | 8.3e-11 |

Observed order: Δp -0.02, 0.02; u_max -2.72, -0.29.

Supporting values:

| Level | inlet flow vs Ū·πR² | max profile error / u_max | mean of 4 faces nearest axis | exact profile at those faces vs u_max |
|---|---|---|---|---|
| coarse | 1.138% | 2.47% | 9.863683e-03 | 1.46% |
| medium | 0.285% | 1.94% | 1.005468e-02 | 0.37% |
| fine | 0.071% | 1.98% | 1.010392e-02 | 0.09% |

What passes:
- "Mesh OK" at all levels;
- predicted cells = `gmshToFoam` cells;
- patches `fluid_inlet`, `fluid_outlet`, `fluid_wall`, with the wall retyped;
- mass balance to 1e-10.

What fails:
- the **Δp error stays at +2.6 %** at every level;
- the **u_max error grows** (0.14 → 0.93 → 1.14 %).

**Cause: the wall inside a `Straight` is not the cylinder.**
- Interface faces are exact.  But a `Straight`'s outer side surfaces are
  OCC plate fillings, and its interior wall nodes land on them, up to
  **1.08 % of R** inside the circle.
- The sag is the same at every level: it is the surface's shape, not
  resolution.
- For the medium and fine meshes, the sagged cross-section predicts the
  measured Δp (Poiseuille at fixed Q, Δp ∝ 1/A²) within 0.1 %:
  1.0262 vs 1.0263, and 1.0246 vs 1.0260.

## Diagnostic: exact walls (not a fix)

The same run, with the `Straight` side surfaces built as ruled B-spline
fillings (`sweep._ruled`, patched in at run time).  All wall nodes are
then on the cylinder to 4e-16 R.

| Level | Cells | min SJ | max non-orth. (°) | max skewness | Iterations | Δp (m²/s²) | e(Δp) | u_max (m/s) | e(u_max) | mass balance |
|---|---|---|---|---|---|---|---|---|---|---|
| coarse | 5184 | 0.793 | 23.5 | 0.422 | 125 | 8.036058e-05 | 0.451% | 9.906548e-03 | 0.935% | 1.2e-11 |
| medium | 41472 | 0.752 | 33.2 | 0.484 | 333 | 8.016547e-05 | 0.207% | 9.974559e-03 | 0.254% | 1.1e-10 |
| fine | 331776 | 0.730 | 38.9 | 0.515 | 1092 | 8.008353e-05 | 0.104% | 9.992713e-03 | 0.073% | 6.9e-11 |

Observed order: Δp 1.12, 0.99; u_max 1.88, 1.80.

| Level | inlet flow vs Ū·πR² | max profile error / u_max | mean of 4 faces nearest axis | exact profile at those faces vs u_max |
|---|---|---|---|---|
| coarse | 1.138% | 1.50% | 9.759179e-03 | 1.47% |
| medium | 0.285% | 0.42% | 9.937181e-03 | 0.37% |
| fine | 0.071% | 0.14% | 9.983340e-03 | 0.09% |

With exact walls:
- the errors fall monotonically;
- both fine-level errors are below 1 %;
- u_max converges at about second order.

But **Δp converges at about first order** (below the 1.5 threshold).

Max non-orthogonality and skewness *grow* with refinement (23 → 33 →
39°, 0.42 → 0.52), so the O-grid core corners are the first suspect.
That is open (task 0020, *Questions for design*).
