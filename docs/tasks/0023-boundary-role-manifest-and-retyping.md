# 0023 — Boundary-role manifest and OpenFOAM patch retyping

- **Status:** done
- **Decision:** [0013 — OpenFOAM output: group names and boundary roles](../decisions/0013-openfoam-group-names-and-boundary-roles.md)
- **Depends on:** 0022 (interface names), and 0009 (per-fitting wall
  names; in progress)

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `gmshToFoam` writes every boundary patch as type `patch`.
Walls left as `patch` silently lose wall treatment.  hexmesh knows each
group's role from the graph (DESIGN A7), so it should export that role
and apply it.

**Where.**
- `hexmesh/assembly/assembler.py`: `write_physical_groups`,
  `write_openfoam`, `open_interfaces`, `patch_name`, `_fitting_walls`.
- New module, e.g. `hexmesh/io/writers/openfoam_boundary.py` (or next to
  `openfoam.py`).
- `tests/test_openfoam_output.py`.

**Do.**
1. **Role manifest.**  `write_openfoam(path, …)` also writes
   `<path stem>.roles.json` next to the `.msh`:

   ```json
   {"format": 1,
    "groups": {"fluid_inlet": "open_end", "fluid_wall": "wall",
               "interface_fluid_steel": "interface", "fluid": "volume"}}
   ```

   - Roles: `wall`, `open_end`, `interface`, `volume`.
   - Build it from the same data `write_physical_groups` uses (walls, or
     per-fitting walls; open interfaces; `fill.interfaces`; volumes).
     **Never infer roles from names.**
   - List interface groups even when they are omitted from the `.msh`;
     mark them `"written": false`, or use a separate list.  Record the
     choice under *Agent notes*.
   - Keep the format small and versioned.  It is also the input for a
     future command-line tool.
2. **Retyping.**  `apply_boundary_roles(case_dir, roles, region=None)` in
   plain Python, no OpenFOAM process:
   - parse `constant/polyMesh/boundary`, or
     `constant/<region>/polyMesh/boundary` after a split;
   - set patches whose role is `wall` to `type wall;` with
     `inGroups 1(wall);`;
   - leave `open_end` patches as `patch`;
   - leave any patch already typed `mappedWall` untouched (made by
     `splitMeshRegions`);
   - patches not in the manifest: leave them and warn once, naming them;
   - preserve everything else in the file byte-for-byte (comments,
     ordering, `nFaces`, `startFace`), and write atomically.
   - Also a convenience that applies to every region found under
     `constant/` after a split.
3. **Check the `boundary` syntax** against a case made by OpenFOAM's own
   tools.  For example, run `blockMesh` on a copy of
   `/usr/share/doc/openfoam-examples/examples/incompressible/simpleFoam/pipeCyclic`
   and read its walls' entries.  Record the exact form used under
   *Agent notes* and in `docs/integrations/openfoam.md`.

**Accept.**
- Unit tests on text fixtures, no OpenFOAM:
  - walls retyped, open ends unchanged, `mappedWall` untouched;
  - an unknown patch warns;
  - the file round-trips unchanged apart from the retyped entries.
- OpenFOAM test (skipped without OpenFOAM), single material (the tee):
  `write_openfoam` → `gmshToFoam` → `apply_boundary_roles` →
  `checkMesh` "Mesh OK".  `foamDictionary` reads `wall` for every wall
  patch, and `patch` for inlets and outlets.
- OpenFOAM test, CHT (insulated pipe): split, then apply per region.
  Outer walls are `wall`, interfaces stay `mappedWall`, and inlets and
  outlets are `patch`.
- With `walls_by_fitting=True`, every per-fitting wall patch becomes
  `wall`.
- `docs/integrations/openfoam.md`: "Features used" recipe updated with
  the retyping step; the "walls must be retyped by hand" note removed.
- Full suite: no new failures.

**Out of scope.**  `0/` boundary-condition files and the
`write_openfoam_case` successor (decision 0013).  A command-line tool.

## Agent notes

- **Roles from the graph.**  `write_physical_groups` records each
  group's role as it adds it: volumes, open interfaces, walls (single or
  per fitting) and `fill.interfaces`.  `Assembly.group_roles()` returns
  them.  No role is inferred from a name.
- **Manifest** (`<stem>.roles.json`, written by `write_openfoam`):
  `{"format": 1, "groups": {name: role}, "not_written": [...]}`.
  - **Choice for omitted interfaces:** a separate `not_written` list,
    not a per-group flag, so `groups` stays a plain name → role map for
    tools.
  - Indented JSON with sorted keys, written atomically.
- **Boundary syntax, checked against OpenFOAM's own tools.**  `blockMesh`
  on a copy of the `pipeCyclic` tutorial (v1912) writes a wall as
  `type            wall;` then `inGroups        1(wall);`, keywords
  padded to 16 columns.  `gmshToFoam` adds `physicalType    patch;`;
  `splitMeshRegions` writes `mappedWall` with `inGroups 1(wall);`.
  Recorded in `docs/integrations/openfoam.md`.
- **Retyping** (`hexmesh/io/writers/openfoam_boundary.py`):
  - a small scanner finds each patch dictionary (brace depth; comments
    skipped), and only the typing lines of `wall` patches change:
    - `type` becomes `wall`;
    - `inGroups 1(wall);` is inserted after it, aligned to the `type`
      value, or `wall` is added to an existing `inGroups` list;
    - `gmshToFoam`'s `physicalType` is also set to `wall`, so the entry
      doesn't contradict itself (not named in the task; noted here);
  - every other byte is kept (a fixture test strips the typing lines and
    compares), and retyping is idempotent;
  - the file is written via a temp file in the same directory and
    `os.replace`.
- **Unknown patches.**  `mappedWall` patches are skipped *and not
  reported*: `splitMeshRegions` makes them (`fluid_to_steel`), so they
  are never in the manifest and would warn on every split case.  Any
  other unknown patch triggers one `UserWarning` naming all of them.
- **Regions.**  `apply_boundary_roles_to_regions` retypes every
  `constant/<region>/polyMesh/boundary`.  If there are none (an unsplit
  case), it retypes `constant/polyMesh`.  After a split, the base mesh is
  left alone.
- **Tests:**
  - `foam_case` / `run_foam` helpers were factored out of
    `test_openfoam_output.py`;
  - the tee test checks types with `foamDictionary <boundary> -entry
    entry0/<patch>/type -value`.

## Questions for design

_None._

## Outcome

- **Files:**
  - new `hexmesh/io/writers/openfoam_boundary.py`;
  - `assembly/assembler.py`: roles recorded in `write_physical_groups`,
    `group_roles()`, and the manifest in `write_openfoam`;
  - new `tests/test_openfoam_boundary.py`: 12 tests run everywhere, and
    3 OpenFOAM tests (the tee ×2, the CHT split);
  - `tests/test_openfoam_output.py` (helpers);
  - docs: `README.md`, `API.md`, and `docs/integrations/openfoam.md`
    (the recipe gains the retyping step, and the "retype by hand" note
    is removed; the file is untracked).
- **Accept:**
  - **text fixtures:** walls retyped, open ends and `mappedWall`
    unchanged, an unknown patch warns once, and the rest round-trips
    byte for byte;
  - **tee** (`write_openfoam` → `gmshToFoam` → `apply_boundary_roles`
    → `checkMesh`): "Mesh OK", and `foamDictionary` reads `wall` for
    every wall patch (1, or 4 per fitting) and `patch` for the 3 open
    ends;
  - **CHT:** after the split and per-region retyping, the outer wall is
    `wall`, all four interface sides stay `mappedWall`, inlets and
    outlets are `patch`, and all 3 regions report "Mesh OK".
- **Tests:** 555 passed (default run) + 5 passed (`-m openfoam`), 0 failed.
