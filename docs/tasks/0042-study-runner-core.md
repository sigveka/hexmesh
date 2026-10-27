# 0042 — Study runner: study file, sampling, preflight, mesh stage, manifest

- **Status:** ready
- **Decision:** [0025 — Study runner](../decisions/0025-study-runner.md)
- **Depends on:** —  (0043 and 0044 build on it)

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Every study today is a hand-written script.  Decision 0025:
one study file → many variants, checked in seconds, meshed in parallel
jobs, recorded in one manifest.

**Where.**  New package `hexmesh/study/` (`__init__.py`, `__main__.py`
for the CLI, `definition.py`, `sampling.py`, `stages.py`,
`manifest.py`).  Public API only: `Assembly`, `to_dict`/`from_dict`,
`validate`, `cell_count`, `check_quality`, `refined`.  `docs/gallery/build.py`
already runs examples in subprocesses: reuse its pattern.  Tests in
`tests/test_study.py`; docs in `README.md` ("Running studies") and
`API.md`.

**Do.**
1. **Study file** (JSON; schema documented in the module docstring and
   `API.md`):
   - `template`: `{"python": "module:function"}` (called with a dict of
     parameters) or `{"json": "path"}` (a `to_dict` description with
     `"$name"` placeholders; whole-value substitution only; an unknown or
     unused placeholder is an error);
   - `parameters` and `sampling`: `table` (CSV or inline rows), `grid`
     (lists per parameter), `lhs` (ranges, `n`, `seed`);
   - `budget`: `max_cells_variant`, `max_cells_total`;
   - `output`, `jobs`, `walls_by_fitting`, mesh format (`.msh`, or the
     OpenFOAM `.msh` of `write_openfoam`).
2. **Variant identity:** a short stable hash of the resolved parameters
   (sorted keys, canonical floats) names `output/variants/<hash>/`.
3. **preflight:** every variant in-process, no GMSH: build, `validate()`,
   `cell_count()`, budgets.  Report a table of failures (variant,
   parameters, error text; the fitting is named in the text) and the
   totals.  Stop before meshing on any failure unless `--keep-going`.
4. **mesh:** a subprocess per variant, at most `--jobs` at once (default
   1).  Writes the mesh, `network.json`, and `result.json` (cells
   predicted/meshed, min SICN, min scaled Jacobian and its fitting,
   build time, group roles).  Skips variants whose outputs exist and
   whose network JSON is unchanged.  A crash in one variant is recorded,
   not fatal.
5. **Topology key:** a hash over the port signatures (task 0019) of
   every interface plus every fitting's counts, in creation order.
   Record it per variant.
6. **Manifest:** `output/study.csv` (one row per variant: hash,
   parameters, status, cells, quality, times, topology key, error) and
   `output/study.json` (the same plus the study file and versions:
   hexmesh commit, gmsh, Python).
7. **Aligned export:** `python3 -m hexmesh.study export study.json`:
   for each topology key, `output/aligned/<key>.npz` with `coords`
   (variants × nodes × 3, nodes in tag order), `hexes` (shared
   connectivity), and the variant hashes.
8. CLI: `python3 -m hexmesh.study run study.json [--stage …] [--jobs N]
   [--keep-going]`; `… status study.json` prints counts per status.

**Accept.**
- A 3 × 3 grid over a bend's radius and angle (fixed counts): preflight
  in under 2 s; meshed = predicted for all; one topology key; the
  exported `hexes` equal each variant's own connectivity read back from
  its mesh file, and `coords` differ.
- **Topology key vs. reality:** variants that change a count (e.g.
  `n_layers`) get a different key; across a mixed study, equal keys ⇔
  identical connectivity, checked by reading the meshes.
- Same study file twice: the same hashes, rows and keys; the second run
  meshes nothing.  Adding a row meshes only that row.
- A variant violating a limit fails preflight, naming the variant and
  the fitting; `--keep-going` meshes the rest.
- JSON template: placeholder errors (unknown, unused) are reported.
- `--jobs 2` gives the same manifest as `--jobs 1` (apart from times).
- Full suite: no new failures; the study tests are small (< 30 s).

**Out of scope.**  OpenFOAM cases and runs (task 0043); expressions in
JSON templates; distributed (multi-machine) execution.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
