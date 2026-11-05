# Changes

## Unreleased

**Structured errors** (decision 0040; task 0094).

- Every error that bad input can cause is now a `hexmesh.HexmeshError`.
  It is still a `ValueError`, and it carries `code`, `where`, `value`,
  `limit` and `hint`.  `err.to_dict()` gives them as JSON data.
- The layers raise their own subclasses: `SpecError`, `AssemblyError`,
  `EquipmentError`, `LayoutError`, `ReaderError` and `StudyError`.
  Former `TypeError`s stay `TypeError`s (`SpecTypeError`,
  `AssemblyTypeError`, `StudyTypeError`).
- Warnings are `hexmesh.HexmeshWarning` (a `UserWarning`), with the same
  fields.
- Messages are unchanged.  The codes are listed in
  [API.md](API.md#errors-hexmesherrors).

## 0.4.0 (2026-11-05)

**Breaking: rectangular cores default to the H face** (decision 0036;
task 0087).

- A rectangular core is now one Cartesian patch (`layout="h"`), its
  walls graded by `first_cell=` or `mprg=` (the second cell from each
  wall over the first).  Circles keep the O-H face.
- Why: on the O-H rectangle the friction factor does not converge with
  refinement, and a Cartesian grid of the same cells converges at second
  order ([RESEARCH §7.11](docs/RESEARCH.md)).
- `nrad=` on a rectangular core without `layout="oh"` is now an error
  that names both fixes.
- Saved descriptions (`to_dict`, `Assembly.save`, study files) written
  before 0.4.0 have no `layout` key.  They still load as O-H and
  reproduce their meshes exactly.

**Migration.**  For each rectangular core with `nrad=`, either:

    .core("air", half_w=0.1, half_h=0.05, first_cell=0.001)     # H: grade the walls
    .core("air", half_w=0.1, half_h=0.05, nrad=3, layout="oh")  # keep the O-H face

Also in this release: H ports on duct taps and `Transition`s, shells
around an H core, the `Switch` length rule, and meshed non-orthogonality
in `mesh()`'s safety net (tasks 0084–0086).
