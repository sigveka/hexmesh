# 0009 — Per-fitting wall patches

- **Status:** done
- **Decision:** [0001 — Complete A5/A7 in the assembly prototype](../decisions/0001-complete-assembly-prototype.md)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  All walls go into one `"{outer}_wall"` group (`assembler.py:292`).
Per-fitting wall patches give per-fitting wall shear, heat flux and
erosion results in post-processing.  DESIGN A7 already allows "optionally
also by fitting" for volumes.

**Do.**
1. `Assembly.write_physical_groups(walls_by_fitting=False)`.  When true,
   emit `"{outer}_wall_{fitting_name}"` per edge instead of one wall group,
   with each surface still in exactly one group (A7).
2. Fitting names: an optional `label` on `add()`, defaulting to
   `f"{type}{index}"`.  Not `name`: `add(..., names=...)` already names
   the outlet interfaces.

**Accept.**  The kit's "each surface belongs to exactly one physical group"
check passes with the option on.  The wall groups' union equals the
original wall group.

**Do not** add internal interface surfaces as physical groups in this
task.  How `gmshToFoam` treats internal physical surfaces is unverified.

## Agent notes

- **Option threading.**  `walls_by_fitting` is a keyword on
  `write_physical_groups`, and also on `mesh`, `write` and
  `write_openfoam`, because `mesh()` is what calls
  `write_physical_groups`.  Default off: output is unchanged.
- **Walls per fitting.**  `Assembly.fill` now keeps each edge's
  `part.walls` (`_fitting_walls`), next to `_fitting_volumes` (0004),
  before merging.
- **Names.**  `Edge.label` comes from `add(..., label=)`, `close(...,
  label=)` or `prepend(..., label=)`.  `Edge.name` is the label, or
  `<Type><index>` (`Bend3`); the groups are `{outer}_wall_{name}`.
  - A label must match `[A-Za-z0-9_]+`, since it becomes part of a patch
    name, and be unique; `add` checks both.
  - A label can still equal a *later* fitting's default name (`label=
    "Straight1"` on edge 0, then an unlabelled edge 1), so the group
    writer re-checks uniqueness and raises `AssemblyError`.
  - A fitting with no wall surfaces gets no group.
- **Intent format:** edges carry `label` when it is set (0006 format,
  still version 1).
- **Kit.**  New `TestConformance.test_walls_by_fitting`, run for all 25
  cases:
  - every surface is in at most one group, and every boundary face is in
    one (A7);
  - no single `{outer}_wall` group is written;
  - the union of the per-fitting groups equals the fill's walls;
  - every group name belongs to a fitting.
- **Bug found in task 0005's `write_openfoam`.**  For a single-material
  mesh there are no interface groups to drop, and
  `gmsh.model.removePhysicalGroups([])` removes **all** groups (see
  `docs/integrations/gmsh.md`).  The file then held every element with
  physical tag 0, and `gmshToFoam` made one `patch0`.  0005's tests only
  used a three-material pipe.  Fixed with a guard; the regression test is
  `test_single_material_keeps_every_group`.
- **Checked through OpenFOAM.**  The tee example, with
  `write_openfoam(walls_by_fitting=True)` and `gmshToFoam` v1912, gives
  patches `fluid_wall_Straight0` 192, `Tee1` 372, `Bend2` 288,
  `Straight3` 144 and `Straight4` 144.  That is 1140 faces, the single
  `fluid_wall` before, and "Mesh OK".

## Questions for design

_None._

## Outcome

- **Files:**
  - `assembly/assembler.py`: `Edge.label` / `name`, `label=` on `add`,
    `close` and `prepend`, `_check_label`, `_fitting_walls`,
    `walls_by_fitting` on `write_physical_groups`, `mesh`, `write` and
    `write_openfoam`, and the `removePhysicalGroups` guard;
  - `assembly/intent.py`: `label`;
  - tests: `test_fitting_conformance.py` (+25 kit cases),
    new `tests/test_wall_patches.py` (11 tests), and
    `tests/test_openfoam_output.py` (+1 regression test);
  - docs: `API.md`, `README.md`, and `docs/integrations/gmsh.md`
    (untracked).
- **Accept:**
  - the kit's single-group check passes with the option on, for all 25
    cases;
  - the wall groups' union equals the original wall group (the kit, and
    `test_labels_and_union`);
  - no internal interface surfaces were added as groups.
- **Tests:** 489 passed, 0 failed.
