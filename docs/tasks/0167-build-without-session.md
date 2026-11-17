# 0167 — Meshing without managing `Session`

- **Status:** blocked (the spike is done; the API needs design's answer)
- **Decision:** [0053](../decisions/0053-api-hardening-before-freeze.md), amendment item 7
- **Depends on:** 0163 (mesh once per option set), 0165.
- **Blocks:** the 0.8.0 tag.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Today a mesh lives in gmsh's process-global model: a script
opens a `Session`, meshes one assembly, writes it.  Many builds (a study,
an agent, the simulation suite) need meshing as a call that returns a
result and leaves no state behind.

**Do.**
1. **Spike, then stop for design.**  Find how gmsh (4.12.1 and the
   latest) allows independent builds: a named model per call within
   one `gmsh.initialize()` (`gmsh.model.add`, `setCurrent`, `remove`),
   with OCC's state per model or shared; or a worker process per call.
   Measure: correctness (two assemblies meshed alternately give the
   same bytes as each alone), the overhead per call, memory released
   after `remove`.  Record in `docs/integrations/gmsh.md`.  Write the
   proposed API under *Questions for design* (the call's name and
   place, the result type's members: nodes, cells, groups, quality,
   `write(path, scale=…)`, `write_openfoam(…)`; how it relates to
   `Session` and `Assembly.mesh`) and set the task `blocked`.
2. After the design's answer: implement, test (the spike's checks as
   tests), document (API.md, GUIDE), inventory, CHANGELOG.

**Accept.**  Step 1's findings in `gmsh.md`; the design's answer; then
the tests, examples byte-identical, full suite and CI green.

## Agent notes

- **The spike (step 1), 2026-11-17:** findings in
  `docs/integrations/gmsh.md`, the two 0167 entries.  In short, on gmsh
  4.12.1 and 4.15.2:
  - a named model per build within one `gmsh.initialize()` is correct
    (sequential and interleaved builds give each one's bytes alone),
    OCC's state is per model, and `gmsh.model.remove()` releases the
    memory (RSS flat over 20 builds);
  - its cost is a `Session`'s; a worker process adds about 0.5-0.6 s of
    imports per build;
  - hexmesh's `_occ` record is module-global but only read while
    building, so whole builds interleave safely, their steps don't;
  - a merged `.msh` doesn't write back byte for byte (entities lose
    their bounding boxes; write-time groups), so the result keeps its
    model to write exactly as `Assembly.write` does.

## Questions for design

- **Q1 (2026-11-17, coding session). The build call's API.**  A proposal
  from the spike, every point open:
  1. **The call:** `Assembly.meshed(*, dim=3, order=1, incomplete=False)
     -> Mesh` (`Assembly.build` is taken: it is pipeline step 3).  It
     meshes a copy of the assembly (`from_dict(to_dict())`), so the
     assembly itself stays unmeshed: it can be meshed again with other
     options, refined, saved, and `remesh_with_other_options` never
     applies to it.  Alternative: a function, `hexmesh.mesh(assembly,
     …)`.
  2. **Where it runs:** in a fresh, uniquely named gmsh model.  gmsh is
     initialized on first use if nothing has, and finalized at exit
     (`atexit`) if hexmesh initialized it.  The caller's current model,
     and a `Session`'s, is restored afterwards.  Not thread-safe (gmsh
     isn't); parallel builds are a process pool's job, one build per
     worker, which the docs show and hexmesh doesn't wrap in 1.0.
  3. **`Mesh`, the result** (`hexmesh.Mesh`): it owns its model until
     `close()` (also a context manager; garbage collection closes it as
     a fallback).  Members:
     - `nodes`: (N, 3) array in the built unit; `cells`: element type →
       (M, k) array of 0-based node indices (`"hex8"`, `"hex27"`, …);
       `groups`: physical name → `(dim, element indices)`;
     - `cell_count`, `check_quality(name="minSICN")` (the
       `QualityReport` that `Assembly.check_quality` gives today);
     - `description`: the assembly's `to_dict()` it was built from;
     - `write(path, *, walls_by_fitting=False, provenance=True,
       scale=1.0)` and `write_openfoam(path, *, interfaces=False,
       walls_by_fitting=False, provenance=True, scale=1.0)`: the bytes
       `Assembly.write` and `write_openfoam` give today;
     - after `close()`, every member but `description` raises a coded
       `mesh_closed`.
     Not picklable (it owns a model); a worker returns the file it wrote,
     or the arrays.
  4. **`Session` and `Assembly.mesh`/`write`:** kept, unchanged, for
     scripts that drive gmsh themselves (the GUI, raw gmsh calls).
     Proposed simplification: `Assembly.write` and `write_openfoam`
     outside a `Session` become `meshed(…).write(…)` and close, so the
     common script needs no `Session` at all; inside one they behave as
     today.  A `Session` that ends closes the `Mesh`es made in it.
  5. **Tests** (step 2): the spike's checks: two assemblies meshed and
     written interleaved give each one's bytes alone; RSS flat over
     repeated builds; the caller's model untouched; `meshed()` twice
     with different `order` on one assembly; `mesh_closed`.

## Outcome
