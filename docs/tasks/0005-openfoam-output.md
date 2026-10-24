# 0005 — OpenFOAM-compatible output

- **Status:** ready
- **Decision:** [0001 — Complete A5/A7 in the assembly prototype](../decisions/0001-complete-assembly-prototype.md)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `Assembly.write()` (`assembler.py:315`) calls `gmsh.write(path)`
with no format options, and nothing in the repo sets
`Mesh.MshFileVersion`.

**Do.**
1. **Verify first:** check which MSH versions the target OpenFOAM's
   `gmshToFoam` reads (expected MSH 2.2 ASCII, but confirm).  Record the
   result in the docstring.
2. Add `Assembly.write(path, format=None)`, or a `write_openfoam(path)`
   helper, that sets `Mesh.MshFileVersion` (and `Mesh.Binary = 0`) for
   `.msh` output, restoring the previous option values afterwards.
3. Add `docs/OPENFOAM.md` with the CHT recipe: `gmshToFoam` →
   `splitMeshRegions -cellZones -overwrite` for multi-material meshes.
   Physical volumes are already per material.  Mark any step you could not
   run as unverified.

**Accept.**
- Test: the written `.msh` header has the expected version.  Parse the
  `$MeshFormat` line; OpenFOAM is not needed in CI.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
