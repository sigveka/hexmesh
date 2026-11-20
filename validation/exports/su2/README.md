# SU2: the .su2 export checked end to end

An export check (decision 0057; task 0183): hexmesh's `.su2`
(`write("….su2")`) read by SU2 v8.6.0, which then solves laminar
Poiseuille on it.  It passes or fails, with no V-category.  The `.su2`
export stays **experimental** (the README, the GUIDE's *Other solvers*).

```bash
docker build -t hexmesh-su2:8.6.0 validation/exports/su2       # once
python3 validation/exports/su2/run.py --threads 4              # k = 1, 2, 3
python3 -m validation.tools.recheck su2_poiseuille             # the table, from results.json
```

SU2 publishes no container image, so `Dockerfile` here builds one from
the v8.6.0 release zip (OpenMP build), with the zip's SHA-256 and the
Ubuntu base's digest pinned (`docs/integrations/su2.md`).  SU2 isn't a
hexmesh dependency.  Cases go to `validation/exports/su2/work/`
(git-ignored), or `--work DIR`, and are deleted once their level is
stored.

## Method

| | |
|---|---|
| Import | SU2's log at each level: its hexahedra must equal `cell_count()`, every boundary group be a marker by name, and every volume element be correctly oriented |
| Mesh | OpenFOAM Poiseuille's pipe (`validation/poiseuille/run.py`, `assembly(k)`): D = 0.02 m, 30 D, interfaces at 15 D and 25 D; n_arc 6, n_radial 3 at k = 1 |
| Flow | `INC_NAVIER_STOKES`, laminar, ρ = 1, ν = 1e-6 m²/s, Re 100; a uniform inlet velocity, the outlet at p = 0, no-slip walls; 2000 iterations (stationary from about 1000) |
| U_b | SU2's mass flow through the outlet (`MARKER_ANALYZE`) over ρπR² |
| Δp | the axis nodes' pressure at 15 D minus 25 D, against 32 ν U_b ΔX / D² |
| u_max | the axis node at 20 D, against 2 U_b |
| Gates | Δp and u_max within 2 % at the finest level; orders over k = 1, 2, 3 reported |
| Levels | `refined(k)`, k = 1, 2, 3: 5 184, 41 472, 139 968 cells |

**Why U_b, not the inlet's velocity.**  SU2 is vertex-based: the
inlet's nodes on the wall take the wall's no-slip, so a uniform inlet
velocity U passes less than U·A, by a fraction of order h/R (16 % at
k = 1).  The exact values are Poiseuille's at the flow SU2 actually
carries.

**SU2 has no cell zones:** a layered mesh's materials arrive as one
volume; the format test (`tests/test_export_formats.py`) checks that the
volume group's name is not in the file.
