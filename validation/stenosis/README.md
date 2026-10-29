# Smooth cosine constriction, Re = 500

Steady laminar flow through a 75 %-area axisymmetric constriction, meshed
by hexmesh with a profiled `Reducer`, compared with the DNS of Varghese,
Frankel & Fischer (2007), Part 1 (decision 0012, task 0032).

```bash
python3 validation/stenosis/run.py --levels coarse          # one level
python3 validation/stenosis/run.py --np 4 --json out.json   # all levels
python3 -m pytest -m openfoam tests/test_validation.py -k stenosis
```

Needs OpenFOAM v1912 (`/usr/share/openfoam/etc/bashrc`).  Cases go to
`validation/stenosis/work/<level>/` (git-ignored), or to `--work DIR`.

**Status: blocked** (task 0032, *Questions for design*): `simpleFoam`
does not converge on this case at any level tried.  See the task file.

## Case

| | |
|---|---|
| Geometry | D = 1; R(x) = D/2 · [1 − s0 (1 + cos(2πx/L))] for \|x\| ≤ L/2, s0 = 0.25, L = 2 D (paper eq. 2.1); throat at x = 0 |
| Domain | 3 D upstream and 16 D downstream of the throat (paper p. 5) |
| Fluid | Re = 500 on D and the mean inlet velocity Ū = 1, so ν = 1/500 |
| Boundary conditions | inlet `fixedValue` U, parabolic u = 2Ū(1 − r²/R²) per face, scaled to the discrete flow rate (paper eq. 2.3); p `zeroGradient`.  Outlet p = 0, U `zeroGradient`; wall `noSlip` |
| Mesh | straight 2 D (16 layers, graded toward the constriction), `Reducer` with `profile=("cosine", 0.25)` (36 layers), straight 12 D (80 layers, graded from the constriction's spacing), straight 3 D (10 layers) |
| Levels | `Assembly.refined(k)`, k = 1 / 2 / 4: `nang` 6 / 12 / 24, `nrad` 3 / 6 / 12, 142 / 284 / 568 axial layers; 8× cells per level |
| Solver | `simpleFoam`, laminar; the Poiseuille case's schemes and solvers (`div(phi,U) bounded Gauss limitedLinearV 1`); residual control p 1e-6, U 1e-7 |

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
  cells within 0.35 R(x) of the axis; c0 is the centreline value.
- **Separation and reattachment:** sign changes of the axial wall shear
  stress, ν u_t / d from each wall cell, averaged per slab.
- **Comparison:** the centreline at the database stations, as a fraction
  of the DNS peak; reattachment against 11.0 D; Richardson extrapolation
  over the three levels [celik_and_ghia_etal_2008].
