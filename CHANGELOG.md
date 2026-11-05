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

**A JSON Schema of the saved description, and limits as data**
(decision 0040; task 0095).

- `hexmesh.agent.schema()` returns a JSON Schema (draft 2020-12) of
  `Assembly.to_dict()`.  `python3 -m hexmesh.agent.schema` prints it.
  It is generated from the registries, and every field has a type,
  unit (`x-unit`), description, range and default.
- `hexmesh.assembly.limits.LIMITS` holds every limit as
  `Limit(value, unit, kind, doc)`; the module constants are unchanged.
  The limits inline elsewhere moved into it: the miter cuts, the sweep
  caps, the wye angle range and the venturi divergent range.
- Four errors now name their limit in `limit` instead of giving its
  value: an unresolvable `n_layers`, the wye angle, and the cosine and
  venturi profile ranges.  Messages are unchanged.

**`describe` and `preview`** (decision 0040; task 0097).

- `hexmesh.agent.describe(x)` summarises an `Assembly`, its saved
  description or a `NetworkModel` as JSON data, without GMSH:
  - for an assembly: fittings, open ends with their patch names,
    junction angles, totals, and `validate()`'s warnings and error;
  - for a model: parts, connections, and the parts the builder would
    reject.
- `hexmesh.agent.preview(x, path)` draws it to a deterministic PNG, in
  three orthographic views and an isometric one.  It needs the new
  `preview` extra (matplotlib).

**Second-order export** (decision 0034; task 0076).

- `Assembly.mesh(order=2)` (and `write(..., order=2)`) writes Hex27, or
  Hex20 with `incomplete=True`, with the high-order nodes on the true
  walls:
  - junction walls are re-projected;
  - bends are placed exactly on their arcs.
  Volume and wall area converge at order 4, against 2 for linear.
- An inverted second-order hex is an error naming the fitting.
- A `Wye` is rejected at order 2.
- `write_openfoam(order=2)` is refused, because `gmshToFoam` reads
  first-order elements only.

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
