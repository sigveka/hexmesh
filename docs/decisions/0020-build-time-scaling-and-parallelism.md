# 0020 — Build time grows linearly with the model; parallelism only across jobs

- **Status:** accepted
- **Date:** 2026-10-26 (accepted 2026-10-26 by the user: "write them up")
- **Tasks:** 0036

## Context

The user asked whether hexmesh should be parallelised, e.g. for
estimating cell counts.  Profile of `examples/smooth_bend` (6 528 cells,
415 surfaces, 126 volumes), 2026-10-26, measured while another session
ran OpenFOAM, so **proportions only**:

| Part | Share |
|---|---|
| `validate()` + `cell_count()` | 7 ms in total |
| GMSH meshing (`generate`) | 1 % of `mesh()` |
| `occ.synchronize`, 251 calls | 42 % |
| `addSurfaceFilling` (plates), 240 calls | 23 % |
| `addVolume` + `addSurfaceLoop` | 18 % |

- **Validation and counting are already instant.**  Nothing to gain.
- **Geometry construction dominates, and it scales badly.**
  `synchronize` rebuilds the GMSH model from the whole OCC model, so
  each call costs more as the model grows.  It is called about twice per
  volume (per slab in `corners.py`, per station in `sweep.py`), so total
  cost grows roughly with the square of the model size.
  - Consistent with the examples: `pipe_rack` (576 volumes, 4.6× more)
    took 118 s, about 14–24× `smooth_bend`'s time (contended
    measurements, 2026-10-26).
  - Why the calls exist: some code reads the model back between steps,
    e.g. `corners.curve_endpoints` (`getBoundary`,
    `getParametrizationBounds`, `getValue`), and `addCurveLoop` needs
    synchronized curves in places (comments in `corners.py`).
- **Plate fillings** are the second cost.  Task 0025 already replaces
  them with ruled surfaces on straight slabs.  One-layer slabs carry no
  interior nodes on their side surfaces (DESIGN §6), so a cheaper valid
  surface may serve there too.

## Options

### A. Parallelise inside one mesh
- GMSH has one global model and its API is not thread-safe.
- Fittings built in separate processes would need their meshes merged,
  i.e. node merging, which P2 forbids (the legacy failure mode).
- GMSH's own threading only affects meshing, which is 1 %.
- Rejected.

### B. Make the build linear
Synchronize once per fitting (or per assembly), with hexmesh keeping
what it needs (point and curve tags it created, curve start/end points)
instead of reading the model back.  Measure cheaper surface fills where
§6 allows.

### C. Parallelise across jobs
Independent builds (refinement levels, parameter sweeps, design
variants, validation cases, tests) run in separate processes with no
shared state.  Embarrassingly parallel and safe.

## Decision

**B now; C at the job level only; A rejected.**

- Build time must grow roughly linearly with the number of volumes.
  Task 0036 restructures `synchronize` use and records a benchmark.
- Job-level parallelism (C) belongs to the tooling around hexmesh: the
  agent SDK's build jobs (decision 0019), validation scripts, tests.
  When added, it follows the shared-machine rules (CLAUDE.md) and takes
  a worker count; no hidden process pools inside `Assembly`.

## Consequences

- **Task 0036:** fewer synchronizes, surface-fill measurement, and a
  build-time benchmark in RESEARCH.
- Large networks (PCF imports, vascular trees, decision 0018) become
  practical; the examples and the test suite get faster.
- Effect on future expansions: supports 0018 (large networks) and 0019
  (faster build jobs; job-level parallelism lives there).

## Verified vs. assumed

- **Verified:** the profile above (proportions, call counts); the
  locations of `synchronize` calls.
- **Assumed:** that the growth is quadratic (two contended data points;
  task 0036 measures it properly), and that every read-back can be
  replaced by hexmesh's own records.
