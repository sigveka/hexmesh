# Laminar Hagen–Poiseuille validation

Steady laminar flow in a straight pipe meshed by hexmesh, compared with the
exact solution at three refinement levels (decision 0012, task 0020).

```bash
python3 validation/poiseuille/run.py                       # all levels (~22 min)
python3 validation/poiseuille/run.py --levels coarse       # one level (~5 s)
python3 validation/poiseuille/run.py --json out.json       # results as JSON
python3 -m pytest -m openfoam tests/test_validation.py     # acceptance checks
```

Needs OpenFOAM v1912 (`/usr/share/openfoam/etc/bashrc`).  Cases go to
`validation/poiseuille/work/<level>/` (git-ignored), or to `--work DIR`.

## Case

| | |
|---|---|
| Pipe | D = 0.02 m, length 30 D, inlet at x = 0, flow along +x |
| Fluid | ν = 1e-6 m²/s, Re = 100, Ū = 5e-3 m/s |
| Boundary conditions | inlet `fixedValue` U = Ū, p `zeroGradient`; outlet p = 0, U `zeroGradient`; wall `noSlip` |
| Mesh | three `Straight`s (15 D, 10 D, 5 D), so interfaces lie on the measurement planes at 15 D and 25 D; profile plane at 20 D |
| Levels | `nang` 6 / 12 / 24, `nrad` 3 / 6 / 12, axial layers 48 / 96 / 192: 8× cells per level |
| Solver | `simpleFoam`, laminar; pipeCyclic's schemes (`div(phi,U) bounded Gauss limitedLinearV 1`) and solvers; residual control p 1e-6, U 1e-7 |

## Pipeline

1. `Assembly.write_openfoam` → `gmshToFoam` → `apply_boundary_roles`
   (walls from the `.roles.json`) → `checkMesh`.
2. `topoSet` makes face zones at 15 D, 25 D and 20 D (`boxToFace` +
   `setToFaceZone`).
3. `simpleFoam` until converged.
4. **Post-processing in Python** from the ASCII case files.  OpenFOAM
   function objects abort on this install (`docs/integrations/openfoam.md`).
   - **Δp:** area-averaged `p` on the 15 D and 25 D zones.  Face values are
     ½(owner + neighbour), exact for the uniform axial spacing.
   - **Flow rates:** `phi` summed on the inlet and outlet patches.
   - **u_max:** u = c₀ − c₂ r² fitted to the 20 D faces within R/3, taking
     c₀.  No face centre lies on the axis; the nearest are 0.12 R off it at
     the coarse level, a 1.5 % offset in the exact profile.

Exact values: Δp = 32 ν Ū L / D² = 8.0e-5 m²/s² over L = 10 D, and
u_max = 2 Ū = 1.0e-2 m/s.

Results: [RESULTS.md](RESULTS.md).
