# 0167 — Meshing without managing `Session`

- **Status:** done
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
- **Step 2, refinements of the answer (2026-11-17)**, each with its reason:
  - **gmsh that hexmesh starts is finalized when its last `Mesh` closes**,
    not only at exit.  A gmsh left running after `asm.write(...)` outside a
    Session would make later code that calls `gmsh.initialize()` itself
    (the test fixture `gmsh_session`, user scripts) look like it is outside
    any session, and `mesh()` would raise `no_gmsh_session` there.  The
    cost is an initialize per build when meshes aren't kept, which the
    spike measured as no more than a model per build.
  - **A `Session` opened while a `Mesh` is open shares that gmsh**: it adds
    its model, and at its end closes the meshes made in it and removes its
    model, instead of finalizing.  So meshes made before it survive it (the
    answer's point 5 said only that a Session closes the meshes made in it).
  - **`_occ`'s records are saved and restored around `to_mesh()`**
    (`_occ.saved()`), so a `to_mesh()` in the middle of a Session's build
    leaves that build's records valid; the spike had found this the one
    thing that can't interleave.  `fallbacks` keeps counting.
  - **A `Mesh` whose model is gone** (the caller finalized gmsh under it)
    reports itself closed (`mesh_closed`) instead of a gmsh error.
  - **`cells` includes `point1`** (gmsh's elements at geometry points):
    every dimension the mesh has, as the answer asked.
  - `write_openfoam` outside a Session checks `order` and the `.msh`
    extension before meshing.

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

**Answers (the design session, 2026-11-17).**  The proposal is accepted,
with these changes:
1. **The name: `Assembly.to_mesh(*, dim=3, order=1, incomplete=False)
   -> Mesh`.**  `meshed()` beside `mesh()` would put two names on two
   different behaviours that differ by a suffix (DESIGN §3.1).  `to_mesh`
   reads like `to_dict`: a value made from the assembly, which stays as
   it was.  No module-level function.
2. **The copy must not need `to_dict()`.**  `to_dict()` raises
   `TypeError` for an assembly it can't describe (`_output._stamp`
   handles that case), and `write` works on such an assembly today.  So
   `to_mesh()` copies the assembly's unbuilt intent internally (the
   graph and fittings, before `build`), not through the description.
   `Mesh.description` is `to_dict()` when it works, else `None`, as the
   `.msh` stamp does.  Test with an assembly that has no description.
3. **gmsh options are global, not per model.**  The options a build sets
   (element order, `Mesh.ScalingFactor`, MSH version, and the others
   `mesh()` and the writers set) are set for each `to_mesh()` and each
   `Mesh.write*`, and restored after.  So interleaving a second-order
   `Mesh` with a first-order one gives each one's bytes alone.  Add
   that test: write A (order 2) and B (order 1), interleaved, against
   each alone.
4. **Arrays, so the format is frozen at 1.0:**
   - `nodes`: (N, 3) float array, in the built unit;
   - `cells`: element type name → (M, k) int array of 0-based node rows,
     **for every dimension the mesh has** (`"hex8"`, `"quad4"`, …), in
     gmsh's node order per type, which the docstring states;
   - `groups`: physical name → `{type name: row indices into
     cells[type]}`.  One shape for volumes and boundaries.
   Type names are listed in one public mapping (gmsh type number → name),
   so a new element type is an addition.
5. **Closing:** `close()`, the context manager and `weakref.finalize`,
   not `__del__`, so that interpreter shutdown, with gmsh possibly
   finalized first, never raises.  After `close()`, `description` still
   works; everything else raises `mesh_closed`.  A `Session` that ends
   closes the `Mesh`es made in it.
6. **`write` and `write_openfoam` outside a `Session`:** yes, they become
   `to_mesh(...).write(...)` and close.  They loosen today's
   `no_gmsh_session` error, so this isn't breaking; note it in the
   CHANGELOG.  Inside a `Session` they behave as today.  `mesh()` and
   `check_quality()` on the assembly still need a `Session`; the
   `no_gmsh_session` hint names `to_mesh()`.
7. **Not thread-safe:** say so in the docstring and API.md, with the
   process pool as the way to run builds in parallel (one example in the
   GUIDE).  `Mesh` isn't picklable; it raises a coded error naming
   `write` or the arrays, not pickle's own.
8. **The tests:** the spike's checks, plus 2, 3 and 5's.  The examples
   stay byte-identical, and `docs/api-1.0.json` gains `Mesh` and
   `to_mesh`.
Set the task `ready` again.

## Outcome

- **Done, 2026-11-17.**  `Assembly.to_mesh(*, dim=3, order=1,
  incomplete=False) -> Mesh`, as the answer to Q1 has it, with the
  refinements in *Agent notes*.
- **Files:** new `hexmesh/assembly/mesh.py` (`to_mesh`, `Mesh`,
  `ELEMENT_TYPES`); `hexmesh/_gmsh.py` (who started gmsh, the open
  sessions and meshes, a model made current for a block, finalizing when
  the last `Mesh` closes); `session.py` (a `Session` shares gmsh that
  hexmesh started); `_occ.saved()`; `_realise.unbuilt_copy`;
  `_output.check_openfoam` split out; `assembler.py` (`to_mesh`, and
  `write`/`write_openfoam` outside a Session); `_checks.py` (the
  `no_gmsh_session` hint names `to_mesh()`); errors `mesh_closed`,
  `mesh_not_picklable`; exports.  Docs: API.md (*Meshing without a
  Session*, the method and error tables), GUIDE (*Without a Session*,
  with a process-pool example, run), CHANGELOG, `docs/api-1.0.json`,
  `docs/integrations/gmsh.md`.
- **Tests:** new `tests/test_to_mesh.py`, 17: the spike's checks
  (Session's bytes, OpenFOAM's and the roles'; interleaved order 2 and 1
  give each one's bytes alone; models freed by close, by collection and
  over repeated builds) and the answer's (the assembly stays unmeshed;
  the arrays; the caller's model and build records untouched mid-build;
  a Session closes only its own meshes; closed and finalized-under
  meshes raise `mesh_closed`; not picklable; no description; a failed
  build leaves no model; the hint; checks before meshing).
  `test_assembly_guards.py`: `write` and `write_openfoam` outside a
  Session need none.  The files touched, with architecture and
  inventory: 390 passed (`-n 1`).
- **Examples byte-identical:** 35 of 35 (`example_hashes.py` against
  the base).  **Full suite:** on one worker beside the OpenFOAM job it
  timed out at 2 h, at 81%, with no failure; CI runs it whole.
- **Measurement (the design's second ask):** gmsh started and finalized
  per call costs 0.6-0.9 ms (4.12.1, 4.15.2); a loop of
  `to_mesh().write()` is as fast as one with a `Mesh` held open or in a
  `Session`, within the noise.  So the GUIDE's many-builds example needs
  no warning.  Table in `gmsh.md`.
- **Surprises:** gmsh left running after `asm.write()` outside a
  Session made later code that calls `gmsh.initialize()` itself look
  sessionless (hence finalizing on the last close); and a caller
  finalizing gmsh under an open `Mesh` had left hexmesh thinking it
  still owned gmsh (hence `_gmsh.started()` checking a live model).
- **Follow-ups:** none.
