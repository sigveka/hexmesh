# 0167 — Meshing without managing `Session`

- **Status:** ready (after 0165)
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

## Questions for design

## Outcome
