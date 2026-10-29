# 0065 — Network interchange, stage 1a: the network model, and the builder out of `pcf.py`

- **Status:** ready (after 0064)
- **Decision:** [0032 — Network interchange](../decisions/0032-network-interchange.md) (stage 1; items 1–4, 6–8)
- **Depends on:** 0064 (PCF robustness touches the same code; do it
  first).  0066 builds on this.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `hexmesh/io/readers/pcf.py` (1600 lines) mixes PCF parsing
with a generic builder (graph, tree check, root choice, junction entry,
insulation, equipment ends, placement).  Bathymetry borrows it through
PCF-shaped `NetworkSpec` / `ComponentSpec`.  IFC and VMTK importers
need the builder without PCF's shape.  **No behaviour change**: this is
a refactor with a new public data model.

**Where.**  New package `hexmesh/interchange/`: `model.py` (the network
model), `build.py` (the builder), `importers/` (or keep
`hexmesh/io/readers/` as the importers' home; choose, and say why).
`pcf.py`, `bathymetry.py`, `API.md`, tests.

**Do.**
1. **The network model** (decision 0032, item 3), as dataclasses:
   - `Port`: id, position, direction, flow direction (optional),
     section, insulation, equipment tag (optional), provenance;
   - `Part`, a closed hierarchy: `Straight`, `Bend`,
     `Reducer`/`Transition`, `Junction`, `Joint`, `InlineEquipment`,
     `Terminal`, `Polyline`.  Each references its ports in order, and
     carries attributes and provenance;
   - `Connection`: port ↔ port, `origin` ("declared" | "inferred"),
     distance;
   - `Network`: name plus a set of parts;
   - `NetworkModel`: ports, parts, connections, networks;
   - `Section`: circle (nominal and/or actual) or rectangle;
   - `Provenance`: source, format, record id, line, GUID (optional).
   - Name the classes so they don't clash with `hexmesh.assembly`'s
     fittings (e.g. `model.Straight` vs `assembly.Straight`: decide
     whether a prefix or the module namespace distinguishes them, and
     record it).
2. **The builder:** `build(model, selection=None, spec, *, axial_cell,
   kinks, tol, lc, inlet, insulation, insulation_nrad) → Assembly`.
   - Move, don't rewrite: graph and tolerance, joint absorption, tree
     check, root choice (prefer declared flow direction when present),
     junction entry, insulation planning, equipment ends, placement, error
     messages.
   - It **never branches on the source format** (constraint 1); format
     facts reach it only as model content.
   - `to_assemblies` (task 0064) becomes `build` per connected piece.
3. **`spec(section)`:** the spec callable receives a `Section`; a
   callable of one float (today's `spec(bore)`) is detected and given
   `section.bore`.  A plain `PipeSpec` keeps working.
4. **Importers:** `read_pcf` and `read_bathymetry` return a
   `NetworkModel` (PCF: ports from END-POINTs and BRANCH points;
   connections inferred within the tolerance or declared by
   `END-CONNECTION-PIPELINE`; equipment tags from
   `END-CONNECTION-EQUIPMENT`; provenance from records and lines).
   Keep `NetworkSpec.to_assembly(…)` working as a thin compatibility
   wrapper (or a deprecation alias) so no caller breaks; say which.
5. **Errors** name provenance through the importer's formatting hook
   (decision 0032, item 2).  The texts the tests check stay the same
   where possible; list any that change.

**Accept.**
- **No behaviour change:** every reader test passes unchanged (or with
  listed message changes only); for every PCF and bathymetry fixture,
  the built `Assembly.to_dict()` is identical before and after, and the
  meshes too (node coordinates to 1e-12 on a sample).
- `NetworkModel` built by hand in a test (no importer) builds an
  `Assembly`.
- The builder module imports nothing from `pcf.py` or `bathymetry.py`.
- `API.md`: the model's classes and `build`.
- Full suite: no new failures.

**Out of scope.**  The operations (0066); the JSON-LD document (stage
2); IFC (stage 3).

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
