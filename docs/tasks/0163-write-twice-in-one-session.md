# 0163 — Writing an assembly twice in one session

- **Status:** ready
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

## Questions for design

## Outcome
