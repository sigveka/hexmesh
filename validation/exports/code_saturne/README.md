# code_saturne: the .unv export checked end to end

An export check (decision 0057; task 0181): hexmesh's I-DEAS universal
file (`write("….unv")`) read by code_saturne 9.2.0, which then solves
laminar Poiseuille on it.  It passes or fails, with no V-category.  The
`.unv` export stays **experimental** (the README, the GUIDE's *Other
solvers*): this checks code_saturne, not Fluent or STAR-CCM+.

```bash
python3 validation/exports/code_saturne/run.py                    # the tee's import, k = 1, 2, 3, the 16 MMS fittings
python3 validation/exports/code_saturne/run.py --levels 1 --mms   # the import and k = 1 alone
python3 validation/exports/code_saturne/run.py --levels --mms tee --mms-levels 1 2
python3 -m validation.tools.recheck code_saturne_poiseuille       # the table, from results.json
```

code_saturne runs in Docker: `simvia/code_saturne:9.2.0`, pinned by
digest, run as the host user (`docs/integrations/code_saturne.md`).  It
isn't a hexmesh dependency.  Studies go to
`validation/exports/code_saturne/work/` (git-ignored), or `--work DIR`,
and are deleted once their level is stored.

## Method

| | |
|---|---|
| Import | `cs_preprocess` on the equal tee (`hexmesh.examples.fittings.equal_tee`) and on each level: its cells and `hexa8` must equal `cell_count()`, every group arrive by name (the tee: with its size) |
| Mesh | OpenFOAM Poiseuille's pipe (`validation/poiseuille/run.py`, `assembly(k)`): D = 0.02 m, 30 D, interfaces at 15 D and 25 D; n_arc 6, n_radial 3 at k = 1 |
| Flow | laminar, ρ = 1, ν = 1e-6 m²/s, Re 100; a uniform inlet velocity, a free outlet, no-slip walls; C++ user sources in `src/` (the zones are the mesh's groups) |
| Time | constant dt = 1/k s for 400 s (four diffusive times R²/ν), to steady state |
| Δp | the slope of the cell-layer mean pressure between 15 D and 25 D |
| Exact | 32 ν U_b / D², U_b the outlet's mass flow over ρπR² |
| Gate | within 2 % at the finest level; the order over k = 1, 2, 3 reported (Richardson) |
| Levels | `refined(k)`, k = 1, 2, 3: 5 184, 41 472, 139 968 cells |
| MMS | `validation/mms`'s 16 fittings at k = 1, 2, 4, its field and wave numbers: a user scalar, diffusivity 1, with the flow frozen at rest (`src/cs_user_mms.cpp`); the source at the cell centres, T = T_m at every boundary face's centre; the import gated (every group by name and size), the L2 order in the fitting under test reported beside OpenFOAM's |

U_b over the circle's area makes the error include the inscribed
polygon's: at k = 1 the mesh's section is 0.9886 πR².  Against the
inlet's velocity (the polygon's own bulk velocity) the error is smaller;
both are in RESULTS.md.
