# Validation cases

Each case meshes a flow or heat problem with hexmesh, solves it with
OpenFOAM (one case with FEniCSx), and compares the answer with a
reference: an exact solution, a published simulation, or an experiment.
Each case is judged on several meshes, finer and finer, against
pass/fail limits ("gates") written down before any run.  A case that
misses a gate is reported as a miss, not tuned until it passes.

The gallery's [Validation page](../docs/gallery/VALIDATION.md) shows
every case with its mesh and verdict, and which hexmesh features each one
covers.  This page is about running them yourself.

**Contents:** [What you need](#what-you-need) ·
[The cases](#the-cases) · [Running a case](#running-a-case) ·
[Reading the results](#reading-the-results) ·
[Sending results back](#sending-results-back) · [Tools](#tools)

## What you need

1. **hexmesh**, from a checkout: `pip install -e .` (Python 3.11 or later).
   This brings gmsh; nothing else to install for meshing.
2. **OpenFOAM v2406**, one of three ways:

   | | How | Then |
   |---|---|---|
   | **Docker** (easiest; Linux, macOS, Windows) | Install [Docker](https://docs.docker.com/get-started/get-docker/).  The image `opencfd/openfoam-default:2406` downloads itself on the first run (about 1.5 GB of disk) | nothing: most cases use it by default |
   | **Apptainer / Singularity** (clusters) | [Apptainer](https://apptainer.org/docs/user/latest/quick_start.html) | `export HEXMESH_OPENFOAM=apptainer:docker://opencfd/openfoam-default:2406` |
   | **Installed OpenFOAM** | [precompiled packages](https://develop.openfoam.com/Development/openfoam/-/wikis/precompiled) | `export HEXMESH_OPENFOAM=native` (and `HEXMESH_OPENFOAM_RC=/path/to/etc/bashrc` if it isn't `/usr/share/openfoam/etc/bashrc`), or load it yourself and use `path` |

   `HEXMESH_OPENFOAM` sets the runner for every case; a driver's
   `--openfoam RUNNER` sets it for one run.  Without either, a case uses
   the default in the table below.  Every run records the OpenFOAM
   version it used.
3. **FEniCSx** (only for `fenicsx_second_order`): Docker; the image
   `dolfinx/dolfinx:v0.11.0` downloads itself (about 3.4 GB of disk).  It isn't a hexmesh
   dependency.
4. **Disk and memory:** each level's case is built in the case's
   `work/` folder (not committed) and deleted once its numbers are
   stored.  The coarse levels need well under 1 GB; the finest levels of
   the large cases need several GB of memory and disk.

## The cases

Run times are wall time on one 8-core desktop, from the case READMEs
and the stored results; "quick" is the coarsest level alone.  Times
marked * were measured on 2026-11-11 while other jobs shared the
machine, so they are upper bounds.  Each finer level costs roughly 8×
the one before.

| Case | Checks | Reference | OpenFOAM default | Quick | Everything |
|---|---|---|---|---|---|
| [poiseuille](poiseuille/README.md) | laminar pipe flow | exact (V1) | native | 5 s | 22 min |
| [heated_rod](heated_rod/README.md) | conduction in a heated rod | exact (V1) | native | 2 s | 3 min* |
| [layered_conduction](layered_conduction/README.md) | conduction through pipe, wall and insulation | exact (V1) | native | 1 min per variant | 45 min |
| [womersley](womersley/README.md) | pulsating pipe flow | exact (V1) | Docker v2406 | 2 min | 6 h (`--np 4`) |
| [rect_duct](rect_duct/README.md) | laminar flow in rectangular ducts | exact (V1) | Docker v2406 | 1 s (solver) | 1.5 h of solver time, 30 meshes |
| [mms](mms/README.md) | conduction on every fitting, manufactured solutions | exact (V1) | Docker v2406 | 7 min* (16 fittings) | not recorded |
| [heated_pipe](heated_pipe/README.md) | flow and heat through a pipe wall and insulation (CHT) | exact (V1) | Docker v2406 | 15 min | 17 h (`--np 4`) |
| [fenicsx_second_order](fenicsx_second_order/README.md) | second-order meshes, end to end | exact (V1) | FEniCSx in Docker | 4 min* | not recorded |
| [stenosis](stenosis/README.md) | steady flow through a constriction | simulation (V2) | native | 13 min of solver time (k2) | 7 h (`--np 4`) |
| [stenosis_pulsatile](stenosis_pulsatile/README.md) | pulsating flow through the constriction | simulation (V2) | Docker v2406 | 5 min (one period) | about a day (`--np 4`) |
| [turbulent_pipe](turbulent_pipe/README.md) | turbulent pipe flow, wall-resolved and wall functions | simulation (V2) | Docker v2406 | 45 s* (lowre_550) | not recorded |
| [square_bend](square_bend/README.md) | laminar flow round a square-duct bend | experiment (V3) | Docker v2406 | 13 min* (matched inlet) | not recorded |
| [helical_pipe](helical_pipe/README.md) | laminar flow in a coil | experiment (V3) | Docker v2406 | — | 5–6 h per Reynolds number on the finest mesh (`--np 4`); Re 3000 is [a volunteer run](VOLUNTEERS.md) |

## Running a case

From the repository root:

```bash
python3 validation/poiseuille/run.py --help                     # every option, explained
python3 validation/poiseuille/run.py --levels coarse --no-trend # one quick level
python3 validation/poiseuille/run.py                            # every level
```

Each case's README starts with its own commands.  The options most
drivers share:

| Option | What it does |
|---|---|
| `--levels …` | which meshes to run; the coarsest is quick, each finer one costs about 8× more |
| `--np N` | MPI processes per solve (default 1) |
| `--openfoam RUNNER` | `native`, `path`, `docker:IMAGE` or `apptainer:IMAGE`, for this run |
| `--json FILE` | where results go (default: the case's `results.json`); levels already in the file are **reused, not rerun**, so pass a new file to run them again |
| `--work DIR` | where the OpenFOAM cases are built (default: the case's `work/`) |
| `--keep-work` | keep each level's OpenFOAM case, to inspect it in ParaView |

A run that stops can be started again: finished levels are in the
results file and are skipped.

**Quick checks in the test suite.**  `python3 -m pytest -m openfoam
tests/test_validation.py` runs the cheap levels of poiseuille (all three
levels, about 22 min), heated_rod, layered_conduction, stenosis (coarse),
womersley, the pulsating stenosis (one period) and rect_duct, and asserts
their gates.  It needs an **installed** OpenFOAM (`native`): with only
Docker it skips.

## Reading the results

A run writes `results.json`: every level's numbers at full precision,
and the environment it ran in (date, hexmesh commit, gmsh, OpenFOAM,
runner).  Then:

```bash
python3 -m validation.tools.recheck poiseuille   # the verdict table, from results.json
python3 -m validation.tools.plots poiseuille     # the graphs in RESULTS.md and the gallery
```

`recheck` prints one row per gate:

| Column | Meaning |
|---|---|
| quantity | what is measured, e.g. the pressure drop `dp` or the peak velocity `u_max` |
| status | how the error behaves as the mesh gets finer: `converging` (the change shrinks steadily), `oscillatory` (it changes sign), `diverging` (it doesn't shrink), `zero_difference` (the meshes agree exactly) |
| order | how fast it shrinks: order 2 means halving the cell size quarters the error |
| gate | the limit, fixed before the run |
| value | what the run gave, e.g. the error of the value extrapolated to an infinitely fine mesh (Richardson extrapolation) |
| verdict | `pass` or `miss` |

Some cases also report a GCI (grid convergence index): an error band on
the finest mesh's answer, from the same extrapolation.

`RESULTS.md` in each case is written by people: it explains the verdicts
and the history.  Its graphs come from `plots`, and its tables match
`recheck`; `tests/test_validation_meta.py` fails if a graph is out of
date and names the command that refreshes it.

## Sending results back

- **A heavy level we can't run ourselves:** see
  [VOLUNTEERS.md](VOLUNTEERS.md).  You send one small file, which is
  checked mechanically; you can run the same check yourself first.
- **Anything else** (a rerun, another OpenFOAM version, a finer level):
  open a pull request with the case's updated `results.json`, the
  regenerated graphs (`plots`) and gallery text
  (`python3 docs/gallery/build.py --markdown-only`).  Say in the pull
  request what you ran and where.  The environment is already recorded
  in `results.json`.  Don't change a case's gates: they were fixed
  before the runs, and changing them is a design decision
  ([CONTRIBUTING](../CONTRIBUTING.md)).

## Tools

From the repository root, with no OpenFOAM and no gmsh:

```bash
python3 -m validation.tools.recheck [case …]   # the gates, recomputed from results.json
python3 -m validation.tools.plots [case …]     # figure.png, img/*.png and RESULTS.md's graphs
```

Regenerate the graphs whenever a case's `results.json` changes, then
commit them, and rebuild the gallery's text:
`python3 docs/gallery/build.py --markdown-only`.

Each case folder holds `README.md` (the case), `case.json` (title,
status, gates, the features it covers), `run.py` (the driver),
`results.json` (every level's numbers) and `RESULTS.md` (tables, gates
and graphs).
