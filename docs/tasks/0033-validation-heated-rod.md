# 0033 — Validation: solid rod with uniform heat generation (O-H core, pure diffusion)

- **Status:** done
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md)
- **Category:** V1 (exact)
- **Features:** `section:circle`, `straight`
- **Depends on:** 0025 (exact straight walls).  Uses task 0020's
  pipeline pieces (case writing, Python post-processing).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The cheapest exact check of the O-H core on its own.  Steady
conduction with uniform heat generation is the same Poisson equation as
Poiseuille flow, without pressure–velocity coupling or convection.  So it
answers task 0020's open question directly: does the O-H section (its
inner-square corners) limit the convergence order, or was Δp's low
order only the polygon reference (RESEARCH §7.4)?

**Physics (exact).**  Rod radius R, conductivity k, heat generation q‴,
wall temperature T_w:
- T(r) = T_w + q‴ (R² − r²) / (4k); centre excess ΔT₀ = q‴R²/(4k).
- Heat leaving through the wall = q‴ · V (energy balance; use the
  **meshed** volume V, which is the inscribed-polygon prism).
- Axially uniform: ends `zeroGradient`, so the problem is 2-D in a 3-D
  mesh.

**Setup (suggested; record changes under *Agent notes*).**
- R = 0.01 m, length 2R, 2 axial layers.  Single-layer spec, core named
  e.g. `rod`.  Patches: `rod_inlet`, `rod_outlet` (zeroGradient),
  `rod_wall` (fixedValue T_w).
- Levels: `nang` 6 / 12 / 24 / 48 with `nrad` scaled with `nang`
  (cheap: the axial count stays small).  Use `Assembly.refined(k)` on
  the cross-section if task 0026 is done, but keep the axial count
  fixed (record how).
- A second series with radial grading (`first_cell` = 0.05 R) to check
  that grading doesn't change the order.
- Solver: `laplacianFoam`, steady (`steadyState` ddt, or run to
  convergence), source through `fvOptions` (`scalarSemiImplicitSource`
  on T, specific volume mode, Su = q‴/(ρc) with DT = k/(ρc)).
  **Check first** that v1912's `laplacianFoam` reads `fvOptions` on this
  build, and record it in `docs/integrations/openfoam.md`.  Coded
  sources/BCs need a build environment and fail here (task 0020).

**Measure.**
- Centre temperature excess (fit T = c₀ − c₂r² near the axis as task 0020
  did for u_max, or the cell nearest the axis with its exact value).
- Volume-weighted L2 and max error of T over the cells against the
  exact T at cell centres.
- Wall heat flux total vs q‴ · V_mesh (energy balance).
- Signed errors, observed order, Richardson extrapolation
  [`celik_and_ghia_etal_2008`].
- `checkMesh` max non-orthogonality and skewness per level, including
  `nang` 48 (this also covers task 0020's non-orthogonality trend
  question; cross-reference it).

**Layout.**  `validation/heated_rod/` (`run.py`, `README.md`,
`RESULTS.md`), work directory git-ignored; an opt-in test in
`tests/test_validation.py` (`-m openfoam`) running the coarsest level.

**Accept.**
- "Mesh OK" at all levels.
- Energy balance to solver tolerance at every level.
- L2 error of T: observed order reported for both series.  **Expected
  ≈ 2.**  If below 1.5, report under *Questions for design* with where
  the error concentrates (core corners, ring, wall), and don't tune.
- Centre excess: extrapolated within 0.1 % of exact.
- `RESULTS.md` with versions and date; RESEARCH-ready table in
  *Outcome*.
- Default `pytest` run unchanged.

**Out of scope.**  Transient conduction, multi-layer rods (task 0034).

## Agent notes

- **Setup as suggested,** with DT = k/(ρc) = 1e-5 m²/s and Su = q‴/(ρc)
  = 0.4 K/s, so ΔT₀ = 1 K exactly.
- **Levels** are `Assembly.refined(k)`, k = 1, 2, 4, 8, of the coarse rod
  (`nang` 6, `nrad` 3); the axial count is put back to 2 in the refined
  dictionary (`intent.refined_dict`, then `n_layers` = 2 per fitting)
  before `Assembly.from_dict`.  The graded series sets `first_cell` =
  0.05 R at k = 1; `refined` takes the k-th root of the stored `mprg`, so
  the series stays self-similar radially (the first cell shrinks).
- **fvOptions check:** v1912 `laplacianFoam` reads `constant/fvOptions`;
  `scalarSemiImplicitSource` works with coefficients at the entry's top
  level.  Recorded in `docs/integrations/openfoam.md`.  Steady solve:
  `steadyState`, 10 non-orthogonal correctors per step, `residualControl`
  T 1e-11 (3 steps).
- **Post-processing reuses** the Poiseuille module (readers, `foam`,
  `richardson`) by path.  Cell centres and volumes are recomputed as
  `primitiveMesh` does; the wall heat flow uses `laplacianFoam`'s
  boundary discretisation (delta coefficient 1/max(n·d, 0.05|d|)), and
  closes to 1e-14–1e-13 of Su · V_mesh.
- Files: `validation/heated_rod/run.py`, `README.md`, `RESULTS.md`;
  `tests/test_validation.py` (opt-in `-m openfoam`, coarsest level of
  both series).

## Questions for design

1. **Observed order of T falls below 1.5 (expected ≈ 2).**  L2 order per
   refinement: uniform 1.77, 1.57, **1.34**; graded 1.70, 1.61, **1.31**.
   Not tuned.  Where the error is (uniform, k = 4 → 8, RESULTS.md):
   - a near-uniform negative bias (volume mean ≈ −L2), not a local spike;
   - slowest in the **core square** (order 1.23; ring 1.44; ring near the
     diagonals 1.73);
   - **max non-orthogonality grows** with refinement (23.5°, 33.2°,
     38.9°, 41.9°), and the worst faces move onto the **core-square
     corners** (r/R 0.50 → 0.59, toward 0.6 on the diagonals), so the
     mesh family is not self-similar there.
   This is a correlation, consistent with the O-H corners limiting the
   order (task 0020's open question), not a proof.  Options I can see,
   for design to choose: (a) accept ≈ 1.3–1.5 as the O-H family's order
   with `Gauss linear corrected` and judge validation by extrapolated
   values (ΔT₀ extrapolates to −0.020 % / −0.026 %, within the 0.1 %
   gate); (b) a corner-free control mesh to establish cause; (c) a
   core-square design that refines self-similarly (e.g. a curved or
   ratio-dependent inner square).  Task blocked on this.

   **Design answer (2026-10-27, accepted by the user): (a), plus one
   level.**
   - Decision 0015 is amended: on O-H sections the observed order is
     reported, not gated.  Gates: extrapolated ΔT₀ within 0.1 % of
     exact (met: −0.020 % / −0.026 %) and the fine-level error; report
     GCI with the observed order.
   - **Add k = 16** (`nang` 96, `nrad` 48; about 55 k cells at 2 axial
     layers) to both series, and report the orders for k = 8 → 16.
     The question is whether the order levels off (near 1.3) or keeps
     falling toward 1.  Report Richardson on the three finest levels
     too.  Run it on an idle machine; if a level is too slow, say so and
     skip it for the graded series.
   - Keep the regional breakdown (core / ring / diagonals) for k = 8 → 16.
   - (b) and (c) are recorded as decision 0022 (proposed, no task).
   - Then write *Outcome* and set the task `done`; 0034 is unblocked.

## Outcome

**Done** (design answer to question 1: order reported, not gated; one
more level).  Final run 2026-10-27, hexmesh `faddea0`, gmsh 4.12.1,
OpenFOAM v1912; five levels per series (`validation/heated_rod/RESULTS.md`).

- **Mesh OK at all 10 levels** (cells 216 / 864 / 3 456 / 13 824 /
  55 296, predicted = converted).  Max non-orthogonality 23.5 / 33.2 /
  38.9 / 41.9 / 43.4° (task 0020's trend question: still rising at
  `nang` 96, toward 45°); max skewness levels off at 0.53 (uniform),
  0.76 (graded).
- **Energy balance** to solver tolerance at every level (≤ 5.7e-13).  ✔
- **ΔT₀ gate:** Richardson on k = 4, 8, 16 extrapolates to −0.007 %
  (uniform) and −0.010 % (graded) of exact, GCI 0.035 % / 0.037 %;
  gate 0.1 %.  ✔
- **Order (reported):** L2 1.77, 1.57, 1.34, **1.17** (uniform) and
  1.70, 1.61, 1.31, **1.09** (graded).  **It does not level off near 1.3;
  it keeps falling toward 1.**  ΔT₀ order 1.12 at k = 8 → 16.
- **Regions, k = 8 → 16:** core 1.13, ring near the diagonals 1.01 /
  0.91, rest of the ring 1.24 / 1.04: every region is about first order
  now, the corner sector slowest, and the largest error sits at the
  core-square corner (r/R 0.60).
- Default `pytest` unchanged; `-m openfoam -k heated` (coarsest level)
  passes.

RESEARCH-ready table (uniform series; graded in RESULTS.md):

| nang | cells | max non-orth. | ΔT₀ error | L2 error | order (L2) |
|---|---|---|---|---|---|
| 6 | 216 | 23.5° | −1.377 % | 1.32e-02 | — |
| 12 | 864 | 33.2° | −0.459 % | 3.87e-03 | 1.77 |
| 24 | 3 456 | 38.9° | −0.176 % | 1.31e-03 | 1.57 |
| 48 | 13 824 | 41.9° | −0.076 % | 5.16e-04 | 1.34 |
| 96 | 55 296 | 43.4° | −0.035 % | 2.29e-04 | 1.17 |
| extrapolated (k = 4, 8, 16) | | | −0.007 % | | Richardson 1.30, GCI 0.035 % |

**For decision 0022:** its open point ("does the order level off near
1.3, or fall toward 1?") is answered: it falls toward 1 in every region,
consistent with a corner error that does not shrink with the cells.  The
gate still passes comfortably, so option A holds for this case; B (a
corner-free control) would show whether the corners are the cause.

Proposed follow-ups: decision 0022 option B if a validation case needs
second order; task 0034 reuses this pipeline as is.
