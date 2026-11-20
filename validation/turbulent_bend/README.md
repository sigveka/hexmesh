# Turbulent flow in a 90° bend (PTB LDA, Re 5 × 10⁴)

The first turbulent case with a fitting (decision 0012, task 0050): k-ω
SST with Spalding wall functions through a 90° bend of curvature radius
1.425 D, against the LDA measurements of Straka et al. (2020) at PTB
Berlin as Ekat et al. (2023) report them: the axial velocity on the
horizontal line through the axis at six planes, 2.43 to 30.82 D after
the bend (`reference/`).

```bash
python3 validation/turbulent_bend/run.py --np 4                    # k = 1, 2, 3
python3 validation/turbulent_bend/run.py --levels 1 --np 4
python3 -m validation.tools.recheck turbulent_bend                 # the table, from results.json
```

OpenFOAM v2406 in Docker by default (`--openfoam`).  Cases go to
`validation/turbulent_bend/work/` (git-ignored), or `--work DIR`, and are
deleted once their level is stored.  k = 3 is 1.6 M cells: about 2.3 h
on 4 processes here, under 6 GB.  k = 4 (3.8 M) is for volunteers (task
0169).

## Method

| | |
|---|---|
| Rig | water at 30 °C, D = 0.1 m, U_b = w_vol = 0.40035 m/s, Re 50 000; ν = U_b D / Re |
| Network | 7 D straight, the `Bend` (r_k = 1.425 D, 90°, toward +y in the plane z = 0), 32 D straight, then 10 D whose axial cells grow 4× to the outlet: the paper's 42 D downstream |
| Section (k = 1) | n_arc 8; the wall cell 50 viscous units at the design u_τ (McKeon's f), n_radial 8 so the ring grows at most 1.15 per cell (task 0049's wall-function meshes); axial cells D/4.  `refined(k)` scales every count by k |
| Inlet | fully developed: task 0049's periodic pipe on the same section at the same k (a slab of R, `meanVelocityForce` to U_b), solved first; its U, k and ω mapped onto the bend's inlet face by face (the sections are identical: each face's centre is a precursor cell's, to 1e-9 m) |
| Model | task 0049's wall-function set: k-ω SST, `kqRWall`, `omegaWall`, `nutUSpaldingWallFunction`; `potentialFoam`, then `simpleFoam` to its residuals |
| Outlet | p = 0; `inletOutlet` for U, k, ω |
| Sampling | w at the 19 LDA points of each plane, linear in 3-D over the cells within 1.5 axial cells of the plane; x/R = −1 the outer wall |
| K | the drop in volume-mean p between slabs 1 D before the bend and 30 D after it, less the precursor's f over the same axial length, over ½ U_b² |
| Gates (finest level) | each plane's RMS of w/U_b − LDA within 0.10; the peak on the measured side (the outer wall) |
| Reported | K and the peak w at 2.43 D and 10.7 D, with Richardson / GCI (k = 1, 2, 3); Ekat et al.'s own SST RMS per plane |

**Not compared:** the profiles normal to the bend plane.  The paper
publishes only the horizontal line (its Fig. 3).
