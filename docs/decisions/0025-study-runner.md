# 0025 — Study runner: many variants from one template, in parallel jobs

- **Status:** accepted
- **Date:** 2026-10-27 (accepted by the user: "Yes, write up the study
  runner")
- **Tasks:** 0042 (definition, preflight, mesh stage, manifest), 0043
  (OpenFOAM case and run stages), 0044 (demonstration study)

## Context

The immediate use cases discussed on 2026-10-27 are high-throughput and
configuration-driven:
- parametric fitting studies (loss coefficients, design charts);
- datasets for surrogate models;
- automated grid-convergence reports;
- insulation-thickness and manifold-balancing sweeps;
- PCF lines to CFD.

hexmesh already gives the pieces:
- an exact cell count and full validation before GMSH;
- a JSON description;
- `refined(k)`;
- builds of 1–8 s for 10–15 k cells (task 0036);
- OpenFOAM output with a role manifest (decision 0013).

What's missing is the loop around them.  Today every study is a
hand-written script: `validation/poiseuille/run.py` and
`validation/heated_rod/run.py` each have their own case writer, OpenFOAM
runner and field readers.

**Verified 2026-10-27 (design session): aligned connectivity.**  A
straight + bend + tee + straight network was meshed four times with the
pipe radius, lengths, branch radius, bend angle and bend radius changed
and every count held fixed.  Node tags and hex connectivity were
identical in all four; only the coordinates moved (by up to 0.97 m).
So geometry-only variants give **node-aligned** meshes: field data line
up across a study with no interpolation, which suits POD/ROM and
graph or neural-operator surrogates.

## Options

### Where it lives
- **A. Inside `Assembly`.**  Rejected by decision 0020 (no hidden
  process pools in `Assembly`).
- **B. A separate package, `hexmesh.study`, with a CLI.**  It uses only
  the public API and the JSON description.  **Chosen.**

### How a variant is defined
- **Python:** a function `build(params) -> Assembly`.  Anything goes,
  including derived values (`R = ratio * D`).
- **JSON:** a network description (`to_dict` format) with `"$name"`
  placeholders, replaced by plain substitution.  No expressions and no
  `eval`.  Derived values need the Python form.  This form is what
  agents and non-programmers edit (decision 0019).
- **Chosen: both.**  A study file (JSON) names one of them.

### Sampling
- **Chosen:** an explicit table (CSV or JSON rows), a full grid
  (Cartesian product) and seeded Latin hypercube.  The same study file
  always gives the same variants.

## Decision

1. **Study file** (JSON): template (module:function or a JSON
   description), parameters and sampling, stages, worker count, output
   directory.  CLI: `python3 -m hexmesh.study run study.json --jobs N
   [--stage preflight|mesh|case|run]`.
2. **Stages**, each resumable and skipped when its output is up to date:
   - **preflight** (pure Python, all variants, seconds): build and
     `validate()` each variant, `cell_count()`, a total budget
     (`max_cells_total`), and a failure report naming variant, fitting and
     limit.  Nothing is meshed if preflight fails, unless `--keep-going`.
   - **mesh:** one process per variant (one GMSH session each), up to
     `--jobs` at once: the mesh, the network JSON, quality, timing.
   - **case:** an OpenFOAM case per variant from a user case template
     directory, with patches typed from the role manifest.
   - **run:** a user command per case (e.g. `Allrun`), up to `--jobs` at
     once, then a user post-processing function → one result row.
3. **Variant identity:** a hash of the resolved parameters names each
   variant directory, so re-running after adding rows only does the new
   ones.
4. **Manifest** (`study.csv` + `study.json`): one row per variant with
   parameters, status, cell count, min SICN / scaled Jacobian, timings,
   errors, results, and a **topology key**: the hash of the
   connectivity, from the port signatures and counts.  Variants with
   equal keys are node-aligned.
5. **Aligned export:** for a group with one topology key, one array file
   per group: coordinates per variant, the shared connectivity, and
   result fields where the post-processing provides them.
6. **Shared-machine rules** (CLAUDE.md): `--jobs` defaults to 1; no
   oversubscription (a run stage's command may itself be parallel, so
   the study declares cores per job).
7. The validation scripts' case writing, running and reading become a
   shared module (`hexmesh.study.openfoam`); the validation cases move
   onto it when next touched.

## Consequences

- New package `hexmesh/study/`, CLI, docs page "Running studies", a
  demonstration study (task 0044).
- **Claims need validation.**  A turbulent loss-coefficient study is
  only as good as the RANS validation it rests on (decision 0012:
  turbulent cases planned, not done).  The demonstration study is
  laminar.
- **Effect on future expansions:**
  - 0019 (agent SDK): the study file is the SDK's "build job" for many
    variants.  It uses the same JSON (constraint 2), deterministic
    sampling (constraint 5) and machine-readable failure rows
    (constraint 3).
  - 0018 (vascular): parameter studies over idealised trees
    (bifurcation angle, radius ratios) are a direct use.  Imported
    centrelines are a table-driven template.
  - 0021 (flow restrictions): meter studies (β ratio, Re, upstream bend
    distance) are the showcase study of stage 1.
  - 0020: this is where job-level parallelism lives.

## Verified vs. assumed

- **Verified:** node alignment for geometry-only variants (above); build
  times (task 0036; gallery 2026-10-27).
- **Assumed:**
  - that the topology key from signatures and counts predicts
    alignment exactly (task 0042 tests it against meshed connectivity);
  - that the two validation scripts' OpenFOAM code generalises to a
    user case template.
