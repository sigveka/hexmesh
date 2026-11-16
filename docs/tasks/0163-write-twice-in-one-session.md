# 0163 — Writing an assembly twice in one session

- **Status:** done
- **Decision:** [0042](../decisions/0042-road-to-1-0.md) (the 0.8 → 1.0
  soak is fixes only; this is one).  Found by task 0150 (the coding
  session, 2026-11-16).
- **Depends on:** 0150 (`scale=` on the writers).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  A user writes the same mesh twice: a `.msh` and an OpenFOAM
file, or one file at two scales.  Today the second write fails on a
meshed tee ("Surface 1 is transfinite but has 8 corners"), with or
without `scale=`.  `Assembly.write` and `write_openfoam` call
`Assembly.mesh()`, and `mesh()` always builds and generates again, on a
model already meshed and with its wall nodes projected.

**Do.**
1. **A failing test first,** for each writer pair: `write` then
   `write`, `write` then `write_openfoam`, and the reverse, on a tee and
   a bend (one fitting with a transfinite surface of more than four
   corners, one without).
2. **`mesh()` runs once per option set.**  Record the options it meshed
   with (`dim`, `order`, `incomplete`, `walls_by_fitting`).
   - The same options again: do nothing (the mesh is current).
   - Only `walls_by_fitting` differs: rewrite the physical groups,
     without re-meshing, if that is all it changes (check).
   - Anything else differs: a coded `AssemblyError`
     (`remesh_with_other_options`) naming both option sets, with the
     hint to start a new session, or `Session` per mesh.  Clearing and
     re-meshing in place is out of scope: the projection and the
     recorded corrections assume one mesh.
3. **The writers' side effects** stay undone after each write (the
   OpenFOAM writer already restores the interface groups and the file
   options; `scale=` restores the coordinates): assert it in the tests,
   by writing the `.msh` before and after a `write_openfoam` and
   comparing the two files byte for byte, the comment block aside.
4. API.md and GUIDE: one sentence: writing again is cheap; meshing with
   other options needs a new session.

**Accept.**
- The tests of step 1 pass; the new code and its hint are in the error
  table.
- The second write of an unchanged assembly takes no meshing time
  (measure it: under 1 % of the first).
- Full suite green; examples byte-identical.

**Out of scope.**  Re-meshing in place with other options.

## Agent notes

- **2026-11-16, done in a worktree** while 0150's suite ran, then
  fast-forwarded onto main (6fe1b4f, b6fe00e).
  - **Step 1:** `tests/test_write_twice.py`, written first; all 13 tests
    failed before the fix.
    - The 4 writer pairs × {tee, bend}.  The check is that
      `gmsh.model.mesh.generate` isn't called the second time, and a
      same-writer pair gives the same file, the recipe block aside.
    - The `.msh` before and after a `write_openfoam(scale=1e-3)`.
    - The walls toggle (merged → split → merged).
    - `order=2` and `dim=2` refused.
  - **Step 2:** `_realise._meshed_already`:
    - It compares `{dim, order, incomplete}`, with `incomplete`
      counting only at order 2 (it changes nothing at order 1).
    - A different `walls_by_fitting` removes every group and its name,
      then writes the groups again, tagged from 1
      (`_output.write_physical_groups(renumber=True)`).  The merged →
      split → merged file is then byte-identical to the first.
    - New code `remesh_with_other_options`; the inventory lists it.
  - **A gmsh quirk:** a removed group's name survives, and a new group
    with that name is unnamed.  Its automatic tags also continue past
    the removed ones.  Recorded in `docs/integrations/gmsh.md`.
  - **Step 3:** the OpenFOAM writer (interface groups, file options,
    `scale`) leaves the `.msh` byte-identical, the recipe block aside,
    on the tee and the bend.
  - **Step 4:** a sentence in API.md's `mesh()` row, in GUIDE's OpenFOAM
    section, and in the CHANGELOG (Fixed).
  - **Timing** (indicative: the 0162 CFD run had 3 of the 4 cores):
    the README tee's first `mesh()` took 3.3 s, the second 9 µs
    (3e-6 of the first).  `write_openfoam` itself took 0.06 s both
    times.

## Questions for design

## Outcome

- **Files:** `hexmesh/assembly/_realise.py` (`_mesh_options`,
  `_meshed_already`), `_output.py` (`write_physical_groups(renumber=)`),
  `assembler.py` (state, `mesh` docstring), `errors.py`
  (`remesh_with_other_options`); `tests/test_write_twice.py` (13);
  API.md (the `mesh()` row and the Errors table), GUIDE, CHANGELOG,
  `docs/integrations/gmsh.md`, `docs/api-1.0.json`.
- **Suite (2026-11-16, with 0150's step 4):** all files pass.  It ran in
  chunks of one to ten files, because two whole-suite runs were stopped
  by Claude Code when memory ran low.  Two stale artefacts from 0150
  were found and fixed: `hexmesh/agent/support.json` (the Tee repr
  gained `branch_shells=None`) and API.md's Errors table (missing
  `branch_shells_reserved`, and this task's code).
  `tests/test_validation.py` collects nothing by default, as before.
- **Examples:** `test_msh_recipe`'s round trip (write → `from_msh` →
  write, both writers) passes for all 47 examples, and
  `test_examples`/`test_h_examples` pass.
- **Timing:** see the notes; a second `mesh()` is ~10 µs.
- **Surprise:** gmsh keeps a removed physical group's name (recorded in
  the integration notes).
- **Follow-up, proposed:** none needed for the fix.  The full suite now
  needs more than 10 min per chunk on 2–3 workers for
  `test_fitting_conformance` (8 min on 3) and `test_second_order` (17
  min on 2, shared); a `slow` marker or a CI-only split could be
  considered by design.

