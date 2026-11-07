# Results: manufactured solutions for conduction on every fitting

**Status: in progress** (task 0074, blocked on its questions for design).
Run on 2026-11-06 with OpenFOAM v2406 (Docker `opencfd/openfoam-default:2406`)
and gmsh 4.12.1, at hexmesh 42357ca with this task's uncommitted changes.
k = 4 ran on 4 MPI processes.  Error = T − T_m at the cell centres; the
field's amplitude is 1.  The numbers below are recomputed from
`results.json` by `python3 -m validation.tools.recheck mms`.

<!-- graphs:start -->
## Graphs

_Drawn from `results.json` by `python3 -m validation.tools.plots`; don't edit between the markers._

<img src="figure.png" width="100%" alt="The L2 error of the manufactured solution on every fitting against cell size.">

The L2 error of the manufactured solution on every fitting against cell size.

<!-- graphs:end -->

## Gate: the error falls with refinement

It falls in every case, over its converged levels.  For the duct taps,
those are k = 1 and 2 only (see below).

## Orders (reported, not gated; decision 0015 as amended)

"Fitting" means the cells of the fitting under test; the rest is the
straight run around it.  **Flag:** the fitting's last L2 order is more
than 0.3 below the straight's last order (1.60).

| case | k | cells (finest) | L2 | order L2 (all) | order L2 (fitting) | order max (fitting) | max error at | flag |
|---|---|---|---|---|---|---|---|---|
| straight | 1, 2, 4 | 55296 | 0.0134, 0.00351, 0.00116 | 1.93, 1.60 | 1.93, 1.60 | 1.19, 1.34 | Straight0 (boundary cell) |  |
| bend | 1, 2, 4 | 82944 | 0.0139, 0.00368, 0.00103 | 1.92, 1.83 | 2.06, 1.72 | 2.10, 0.99 | Straight0 (boundary cell) |  |
| miter | 1, 2, 4 | 110592 | 0.00971, 0.00259, 0.000948 | 1.90, 1.45 | 1.84, 1.14 | 1.33, 0.57 | MiterBend1 | **yes** |
| spline | 1, 2, 4 | 124416 | 0.0246, 0.00717, 0.00193 | 1.78, 1.89 | 1.77, 1.90 | 1.21, 1.49 | SplinePipe1 (boundary cell) |  |
| reducer | 1, 2, 4 | 82944 | 0.0133, 0.00442, 0.00181 | 1.59, 1.28 | 0.93, 0.95 | 0.71, 0.91 | Reducer1 (boundary cell) | **yes** |
| transition | 1, 2, 4 | 66816 | 0.0284, 0.0113, 0.00524 | 1.33, 1.11 | 0.97, 0.97 | 0.71, 0.50 | Transition1 | **yes** |
| tee | 1, 2, 4 | 152064 | 0.0132, 0.00471, 0.00199 | 1.49, 1.24 | 1.28, 1.03 | 0.72, 0.83 | Tee1 | **yes** |
| tee_shells | 1, 2, 4 | 284160 | 0.0146, 0.00519, 0.0022 | 1.49, 1.24 | 1.29, 1.04 | 0.57, 0.71 | Tee1 | **yes** |
| stack_change | 1, 2, 4 | 92160 | 0.0166, 0.00421, 0.0012 | 1.98, 1.81 | 1.98, 1.81 | 1.36, 1.37 | Straight0 (boundary cell) |  |
| wye60 | 1, 2, 4 | 193536 | 0.0126, 0.00588, 0.00393 | 1.10, 0.58 | 0.81, 0.46 | 0.69, −0.07 | Wye1 | **yes** |
| wye90 | 1, 2, 4 | 221184 | 0.0117, 0.00536, 0.00344 | 1.13, 0.64 | 0.80, 0.51 | 0.17, 0.24 | Wye1 | **yes** |
| wye60_shell | 1, 2, 4 | 278016 | 0.0119, 0.00545, 0.00389 | 1.13, 0.48 | 0.79, 0.34 | −0.10, −0.08 | Wye1 | **yes** |
| wye90_shell | 1, 2, 4 | 317952 | 0.0114, 0.00523, 0.00354 | 1.13, 0.56 | 0.76, 0.42 | −0.09, 0.01 | Wye1 | **yes** |
| duct_tap_rect | 1, 2 | 63488 | 0.0351, 0.0153 | 1.20 | 0.78 | 0.71 | Tee1 | **yes** |
| duct_tap_round | 1, 2 | 75776 | 0.0353, 0.0152 | 1.22 | 0.79 | 0.71 | Tee1 | **yes** |
| duct | 1, 2, 4 | 36864 | 0.0391, 0.00966, 0.00244 | 2.02, 1.99 | 2.02, 1.99 | 1.86, 1.67 | Straight0 (boundary cell) |  |

## Readings

- **The straight reproduces the heated rod (task 0033).**  At the same
  levels (nang 6, 12, 24) the rod's L2 orders are 1.77 and 1.57; here they
  are 1.93 and 1.60.  In both, the order falls with refinement and the
  max error sits in boundary cells.
- **Smooth sweeps converge like the straight.**  The bend, the spline,
  the stack change and the rectangular duct have fitting orders of
  1.7–2.0.
- **The wyes don't refine everywhere.**  `refined(k)` holds a wye's
  `n_split` at `WYE_N_SPLIT_MAX` = 6 at every k (task 0056).  So the
  split region gets no finer across its turning layers, and its error
  stalls: the max error doesn't fall at all.  The order is therefore the
  cap's, not the scheme's.
- **The tees, the transition and the reducer converge at about first
  order** (0.93–1.28).  Their fitting cells keep a constant worst scaled
  Jacobian under refinement (tee 0.258, transition 0.577).  Gauss-linear
  gradients on skewed faces are first order.
- **The duct taps don't converge at k = 3 or 4.**  `laplacianFoam`'s
  explicit non-orthogonal correction stops contracting: about 0.92 per
  corrector at k = 2, and 1.04 at k = 3, where the residual grows 1.43×
  per 10-corrector step.  The meshes pass `checkMesh` (non-orthogonality
  64°, worst scaled Jacobian 0.42), but the tap's 7552 hexes at k = 1 have
  edge ratios of 12–13 throughout, with 60°+ non-orthogonality.  The wyes,
  at 80° but with lower aspect, converge.  A pseudo-transient (Euler,
  Δt 1e-3) gives the same solution and barely damps the iteration.
  `limited corrected 0.5` (the `*_lim` levels in `results.json`) is
  worse at k = 1 (L2 0.0425 against 0.0351) and didn't converge at k = 2.

## gmshToFoam

Every level ran `gmshToFoam -keepOrientation`: every mesh's worst scaled
Jacobian is positive.  `gmshToFoam_would_invert` counts the hexes its own
orientation test would have turned inside out:
- 6 in wye90 at k = 4;
- 4 in wye60_shell at k = 4;
- 4 and 18 in wye90_shell at k = 2 and 4.

Without the option, those levels failed `checkMesh`.  See
`docs/integrations/openfoam.md`.
