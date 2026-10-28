# 0042 — Study runner: study file, sampling, preflight, mesh stage, manifest

- **Status:** done
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

Refinements of the steps:
- **Topology key (step 5).**
  - *Port signatures without the grading floats.*  `mprg` and `mbmp` move
    nodes but don't renumber them.  With them in, grading-only variants
    would get different keys although they are node-aligned.
  - *A fitting's counts are its integer-typed dataclass fields, as
    resolved*: `n_layers`, `n_cuts`, and a tee's or wye's
    `n_run`/`n_branch`/`n_turn`/`n_split`.  Integers in the JSON can't be
    used: a bend's `"angle": 90` is a JSON int.
  - The key also covers each fitting's type, how it entered the graph
    (`kind`), its port interface indices, and its stack changes (cell
    index and spec).
- **`parameters`** are fixed values present in every variant; each
  sample updates them.
- **`--stage`** is the last stage to run.  Preflight always runs: the
  mesh stage needs its network descriptions.
- **`max_cells_total`** over budget stops the study even with
  `--keep-going`; that is the budget's purpose.
- **The mesh worker** is `python3 -m hexmesh.study _mesh <dir>`.  It
  rebuilds the variant from the `network.json` that preflight wrote, so a
  Python template is imported only once, in preflight.
- **Statuses:** `checked` (passed preflight, not meshed),
  `preflight_failed`, `meshed`, `mesh_failed`.
- **Quality warnings** (task 0047) are recorded per variant (`warnings`
  column).  Preflight doesn't print them.
- **Two samples with the same parameters** are rejected: they would
  share a directory.
- Parallelism follows the gallery's pattern: a thread pool, each thread
  running one subprocess.

## Questions for design

_None._

## Outcome

**Files.**
- New package `hexmesh/study/`:
  - `__init__.py`: `run`, `status`, `PreflightFailed`;
  - `__main__.py`: the CLI, `run | status | export`, and the `_mesh`
    worker;
  - `definition.py`: study file, templates, placeholders, canonical hash;
  - `sampling.py`: table (rows or CSV), grid, seeded LHS;
  - `stages.py`: preflight, mesh, topology key;
  - `manifest.py`: `study.csv` / `study.json`, versions, aligned export.
- Docs: `README.md` "Running studies"; `API.md` "Study runner".
- Tests: `tests/test_study.py`, 25 tests, about 17 s with `-n 4`.

**Acceptance.**
- **3 × 3 grid** over a bend's radius and angle:
  - preflight takes 0.5 s for the 9 variants (CLI, imports included);
  - meshed = predicted (432 cells each), all hex;
  - one topology key;
  - the exported `hexes` and `node_tags` equal each variant's own mesh
    read back, and `coords` differ.
- **Topology key against the meshes:** a mixed study of five variants
  (geometry, `n_layers` of the straight, `n_layers` of the bend) gives
  three keys.  Equal keys ⇔ identical node tags and connectivity, checked
  pairwise on the meshes.  Geometry and `mprg` leave the key unchanged;
  `nang` changes it.
- **Re-running** gives the same hashes, keys and rows, and no mesh file
  is rewritten.  Adding a row meshes only that row.
- **A failing variant** (a bend tighter than the pipe) makes preflight
  fail.  The report names the variant hash and `fitting #1 Bend`, and
  nothing is meshed.  `--keep-going` meshes the rest.  The CLI exits
  with 2.
- **Budgets:** `max_cells_variant` fails each variant;
  `max_cells_total` stops the study.
- **JSON template:** unknown and unused placeholders are reported by
  name.
- `--jobs 2` gives the same rows as `--jobs 1`, apart from times.

**Suite:** 1796 passed, 5 skipped (was 1771; +25).

**Follow-ups.**
- 0043: case and run stages, and `hexmesh.study.openfoam`.
- Result fields in the aligned export, once 0043's post-processing
  gives them.
- No `cores per job` yet; it belongs with the run stage (decision 0025,
  item 6).
