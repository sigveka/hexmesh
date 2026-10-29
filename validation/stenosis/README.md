# Smooth cosine constriction, Re = 500

Steady laminar flow through a 75 %-area axisymmetric constriction, meshed
by hexmesh with a profiled `Reducer`, compared with the DNS of Varghese,
Frankel & Fischer (2007), Part 1 (decision 0012, task 0032).

```bash
python3 validation/stenosis/run.py --levels k2 --np 4      # one level
python3 validation/stenosis/run.py --np 4 --json out.json   # k = 2, 3, 4 (about 7 h)
python3 validation/stenosis/run.py --repost out.json --json new.json  # re-measure
python3 -m pytest -m openfoam tests/test_validation.py -k stenosis
```

Needs OpenFOAM v1912 (`/usr/share/openfoam/etc/bashrc`).  Cases go to
`validation/stenosis/work/<level>/` (git-ignored), or to `--work DIR`.

**Status: accepted** ([RESULTS.md](RESULTS.md)): reattachment 10.97 D
against the DNS's 11.03 D, centreline within 0.93 % of the DNS peak.

## Case

| | |
|---|---|
| Geometry | D = 1; R(x) = D/2 · [1 − s0 (1 + cos(2πx/L))] for \|x\| ≤ L/2, s0 = 0.25, L = 2 D (paper eq. 2.1); throat at x = 0 |
| Domain | 3 D upstream and 16 D downstream of the throat (paper p. 5) |
| Fluid | Re = 500 on D and the mean inlet velocity Ū = 1, so ν = 1/500 |
| Boundary conditions | inlet `fixedValue` U, parabolic u = 2Ū(1 − r²/R²) per face, scaled to the discrete flow rate (paper eq. 2.3); p `zeroGradient`.  Outlet p = 0, U `zeroGradient`; wall `noSlip` |
| Mesh | straight 2 D (16 layers, graded toward the constriction), `Reducer` with `profile=("cosine", 0.25)` (36 layers), straight 12 D (80 layers, graded from the constriction's spacing), straight 3 D (10 layers) |
| Levels | `Assembly.refined(k)`, k = 2 / 3 / 4: `nang` 12 / 18 / 24, `nrad` 6 / 9 / 12, 284 / 426 / 568 axial layers.  k = 1 (`coarse`) has no steady axisymmetric state and is only for the pipeline test |
| Solver | `pimpleFoam` from rest, laminar, Euler, Co 0.8, 2 pressure correctors; the Poiseuille case's schemes (`Gauss limitedLinearV 1`) and solvers, no relaxation.  It runs in chunks of 5 time units until the centreline and both reattachment measures change by less than 0.1 % over one chunk.  `simpleFoam` doesn't converge on this case: its iteration is unstable around the steady state (`docs/integrations/openfoam.md`) |

## Reference

The [Purdue CFD Lab database](https://engineering.purdue.edu/CFDLAB/DNS_stenoticflow_database/main.html),
axisymmetric steady flow, Re = 500 (`Axi_stdy/Re500/vel.dat`): radial
profiles of (u, v, w) at x/D = −2 … 15, 1 D apart, normalised by 0.5.
It carries no licence, so it isn't in the repository.  `run.py`
downloads it into the work directory once; `--reference FILE` takes a
local copy, `--no-reference` skips the comparison.

The database has no wall shear stress.  The reference reattachment point
is where the axial velocity at r = 0.48 D (the last point before the
wall) turns positive, interpolated between stations: 11.0 D.

## Post-processing (Python, from the ASCII case files)

OpenFOAM function objects abort on this build (`docs/integrations/openfoam.md`).

- **Centreline velocity:** per axial slab, u = c0 + c2 r² fitted to the
  cells within 0.2 R(x) of the axis; c0 is the centreline value.  A
  wider window biases it high past the throat (RESULTS.md, *Measures*).
- **Separation and reattachment:** sign changes of the axial wall shear
  stress, ν u_t / d from each wall cell, averaged per slab.
- **Reattachment as the database measures it:** where the axial velocity
  at r = 0.48 D turns positive, from a fit to the outer cells that
  vanishes at the wall; continuous in x and sampled at the 1 D stations.
- **Comparison:** the centreline at the database stations, as a fraction
  of the DNS peak; reattachment against 11.0 D like with like; Richardson
  extrapolation over the three levels at the ratios 4/3 and 3/2
  [celik_and_ghia_etal_2008].
