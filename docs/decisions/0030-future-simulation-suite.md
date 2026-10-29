# 0030 — Future expansion: hexmesh as one generator in a multi-domain study and surrogate suite

- **Status:** proposed (future expansion; no tasks)
- **Date:** 2026-10-29 (recorded at the user's direction: "hexmesh can
  be one tool in a more generic simulation suite focussing on studies
  and surrogate modelling in multiple domains")
- **Tasks:** none.

## Context

Several pieces built so far are suite pieces that happen to live in
hexmesh:
- the study runner `hexmesh.study` (decision 0025, tasks 0042/0043):
  study file, sampling, preflight, parallel jobs, manifest, OpenFOAM case
  and run stages;
- the aligned dataset export (topology key, node-aligned arrays): the
  capability no unstructured mesher offers (decision 0025, verified
  2026-10-27);
- the validation pipeline (`hexmesh.study.openfoam`, Richardson / GCI,
  RESULTS pages, gallery);
- the agent SDK plan (decision 0019: tools over a JSON description).

Today `hexmesh.study` reaches hexmesh through three things only:
`Assembly.load` (the variant's network JSON), `assembly.signature` (the
topology key) and `AssemblyError` (`stages.py`).  That narrow surface is
what keeps a later split cheap.

## The layers

| Layer | Owns | Today |
|---|---|---|
| Generators | parameters → mesh + manifest (cells, quality, boundary roles, topology key) | hexmesh (structured pipe networks); later unstructured gmsh, blockMesh templates, CAD-driven |
| Solver adapters | mesh + case template → results; post-processing to fields and scalars | OpenFOAM (`hexmesh.study.openfoam`); later Elmer / GetDP (electromagnetics, heat), structural FEA |
| Study engine | sampling, budgets, parallel jobs, resumability, provenance, manifest | `hexmesh.study` |
| Datasets | fields + parameters in a documented, versioned format; aligned when the topology key matches, interpolated or graph-based otherwise | the aligned `.npz` export |
| Surrogates | ROM / regression / neural or graph surrogates, with held-out error | none (the stenosis surrogate idea) |
| V&V | convergence and uncertainty estimates, reference comparisons, reports | the validation cases |

**Build or integrate:** sampling, UQ and regression exist as mature open
tools (e.g. Dakota, OpenTURNS, the Surrogate Modelling Toolbox,
scikit-learn, workflow managers such as Snakemake).  The suite's own
value is likely the glue and the conventions: generator and solver
interfaces, aligned datasets, verification.  It is not more samplers or
regressors.  To be decided when the suite is tasked.

## Constraints for decisions going forward

1. **hexmesh stays a generator.**  No sampling, surrogate or
   solver-control logic in `hexmesh` core (`assembly`, `core`, `faces`,
   `io`).
2. **The study engine talks to generators through one interface:**
   "template + parameters → mesh files + manifest".  Keep `hexmesh.study`'s
   reach into hexmesh to that surface (today: load, signature,
   `AssemblyError`), so it can move to its own package without a
   rewrite.
3. **The contracts are versioned, with schemas:** the network JSON, the
   boundary-role manifest (decision 0013), the topology key, the study
   manifest and the aligned-dataset format.  They are the suite's API.
4. **Provenance in every manifest:** tool versions and input hashes.
5. **Domain-neutral names in shared pieces:** "boundary roles", not
   OpenFOAM patch types; "fields", not U and p, outside the OpenFOAM
   adapter.
6. **Solver-specific code stays in adapters** (`hexmesh.study.openfoam`
   today), never in the generator.

## Open questions (for when it's tasked)

- **Which domains first.**  Structural analysis of pipe networks can
  reuse hexmesh meshes unchanged.  Electromagnetics needs an exterior
  domain hexmesh doesn't mesh (2026-10-27/28 discussion).
- **Primary interface:** study file, Python API, or the agent SDK
  (decision 0019).
- **Repository:** sub-packages here, or a separate suite repository that
  depends on hexmesh.

## Effect on existing decisions

- **0025 (study runner):** consistent; constraints 2, 4 and 6 describe
  how it is already built.
- **0019 (agent SDK):** the SDK's build jobs are this suite's study
  engine; the two should share the manifest and error formats.
- **0018 (vascular), 0021 (flow restrictions):** domain plug-ins of the
  generator layer, unaffected.

## Verified vs. assumed

- **Verified (code, 2026-10-29):** `hexmesh.study`'s imports from
  hexmesh (`stages.py`: `Assembly`, `Session`, `assembly.signature`,
  `AssemblyError`).
- **Assumed:** that the layer split holds once a second generator or
  solver appears (nothing tests it yet).
