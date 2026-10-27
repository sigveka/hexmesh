# 0001 — Complete A5/A7 in the assembly prototype

- **Status:** accepted
- **Date:** 2026-10-24
- **Tasks:** 0000–0009

## Context

The interface-first prototype in `hexmesh/assembly/` implements the
pipeline of DESIGN §5 for `Straight`, `Bend`, `Closure` and `Tee`.  Several
things DESIGN already promises are missing or incomplete:

- **A5:** "axial grading belong[s] to the individual fitting".  Curve
  records carried no grading, and radial `mprg` was silently dropped at
  meshing (task 0000, measured).
- **A7:** volumes "optionally also by fitting".  Walls and quality are
  only grouped by material.
- **P4:** validation could check more before GMSH: the exact cell count.
- **§3:** the Intent layer is defined as a graph but has no data form.

The target uses rely on these: CHT pipe networks, junction-flow CFD, and
parametric or surrogate studies, which need a fixed topology across
geometry variants.

## Options

### A. Complete the prototype now, in small tasks
Each gap is local, has a clear test, and follows existing rules.  Low
risk; builds on the conformance kit.

### B. Defer until the junction templates (wye, multi-layer tee) exist
Avoids touching fill code twice.  But grading and per-fitting quality are
needed to *measure* those templates (wall-layer cells, junction quality),
so deferring makes the junction work harder.

## Decision

Option A.  Tasks 0000–0009, in the order given in
[`tasks/README.md`](../tasks/README.md#index).  No DESIGN.md rules change:
every task implements an existing rule.

## Consequences

- Curve records become `(tag, nodes, kind, coef)`.  Every fitting must
  orient its gradings by endpoint tags (DESIGN §6.1).
- The conformance kit gains checks: predicted cell count = meshed cell
  count (0003), and topology invariance across variants (0007).  Every
  future fitting must pass them.
- `Assembly` gains a serializable Intent form (0006), which equipment
  boundaries (decision 0002) build on.

## Verified vs. assumed

- Verified: `mprg` is lost at meshing (coding agent measured a last/first
  radial cell ratio of 1.000 for `mprg = 1.3`).  `Assembly.mesh()` set
  transfinite curves without progression.  `check_quality` grouped by
  material only.  `quality_hex` was unused by `Assembly`.
- **Verified in task 0005 (2026-10-25), correcting the assumption below:**
  `gmshToFoam` v1912 reads MSH **2.2 and 4.1**.  Internal physical
  surfaces become an empty patch plus a faceZone, and their `<a>_to_<b>`
  names clash with `splitMeshRegions` (see `docs/integrations/openfoam.md`).
- *Original assumption:* `gmshToFoam` reads MSH 2.2
  ASCII.  Also: how `gmshToFoam` treats internal physical surfaces (task
  0009 avoids depending on it).
