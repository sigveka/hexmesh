# 0005 — OpenFOAM-compatible output

- **Status:** done
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

Measured on OpenFOAM v1912 (Debian 1912.200626) and gmsh 4.12.1,
2026-10-25, with `examples/insulated_pipe` (3 materials) and
`examples/tee`.  Full details are in `docs/integrations/openfoam.md`.

- **MSH version.**  `gmshToFoam` reads **both 2.2 and 4.1** ASCII, with
  identical cells, patches, face counts and `checkMesh` results.  The
  helper writes 2.2 anyway, since every OpenFOAM line reads it.
- **cellZones.**  Physical volumes become cellZones named by material.
- **Orientation.**  `checkMesh` reports "Mesh OK" with and without
  `-keepOrientation`; it is not needed.
- **Found: the material-interface groups break the CHT split.**
  - `gmshToFoam` makes each internal physical surface an empty `patch`
    plus a faceZone, with one warning per face.
  - Their names, `<a>_to_<b>`, are exactly what `splitMeshRegions`
    calls its interface patches, so it reuses the empty ones.  The
    result: `steel_to_insulation` held both steel interfaces (1728
    faces), the steel/insulation interface was merged into
    `insulation_wall`, and nothing became `mappedWall`.
  - Every region still passed `checkMesh`.
  - With the groups left out, the split gives correct `mappedWall` pairs
    of 864 faces each.
- **Step 2, refined.**  `Assembly.write_openfoam(path, *,
  interfaces=False)`:
  - meshes, then writes MSH 2.2 ASCII;
  - restores `Mesh.MshFileVersion` and `Mesh.Binary` afterwards;
  - removes the material-interface groups only for the write, then
    re-adds them with the same tags and names, so the model is
    unchanged;
  - accepts only `.msh` paths.
- The "Found N undefined faces … defaultFaces" warning is harmless: N is
  every boundary face, and the patch ends up empty and is dropped.
- `docs/integrations/openfoam.md`:
  - Features used: the verified single-material and CHT recipes;
  - Known quirks: the four findings above;
  - open questions: settled, except AMI.

## Questions for design

1. **Interface group names.**  The A7 material-interface groups
   (`fluid_to_steel`) collide with `splitMeshRegions`' own patch names.
   This task works around the clash by leaving them out of OpenFOAM
   output.  Should DESIGN rename them instead (for example
   `fluid|steel`), so they could stay in the file as faceZones?  Not
   blocking.
2. **Wall patch types.**  `gmshToFoam` writes every patch as `patch`.
   Should hexmesh retype walls to `wall` in the generated case (a
   `write_openfoam_case` successor; see the "Gaps" section of
   `openfoam.md`), or leave that to the user?

## Outcome

- **Files:**
  - `assembly/assembler.py`: `write_openfoam`;
  - new `tests/test_openfoam_output.py` (6 tests): the header parse
    (`2.2 0 8`), option restore, the interface groups left out of the
    file and kept in the model, `interfaces=True`, the extension check,
    and a real `gmshToFoam` → `splitMeshRegions` → `checkMesh` run that
    asserts the `mappedWall` pairs (skipped without OpenFOAM);
  - docs: `README.md`, `API.md`, and `docs/integrations/openfoam.md`
    (untracked; left for the design session to commit).
- **Measurements:**

  | Example | Cells (hex) | checkMesh | Max non-orthogonality | Max skewness |
  |---|---|---|---|---|
  | tee | 7464 | OK | 60.8° | 2.41 |
  | insulated_pipe | 10800 | OK | 23.5° | 0.77 |

  After the split, the insulated pipe gives fluid 5616, steel 1728 and
  insulation 3456 cells, each "Mesh OK".
- **Follow-up:** retype walls, from the Q2 answer.
- **Correction (found in task 0009).**  As first committed,
  `write_openfoam` emptied *every* physical group on single-material
  meshes, because `removePhysicalGroups([])` removes all groups.  The
  tee figures above came from a plain `gmsh.write` of MSH 2.2, not from
  `write_openfoam`.  Fixed in 0009, with a regression test.

- **Tests:** 440 passed, 0 failed (the OpenFOAM test ran, not skipped).
