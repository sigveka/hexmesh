# 0065 — Network interchange, stage 1a: the network model, and the builder out of `pcf.py`

- **Status:** done
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

- **Where.**  `hexmesh/interchange/` holds `model.py` and `build.py`.  The
  importers stay in `hexmesh/io/readers/`, which is already the input
  formats' home (with `io/writers/` for output).  An `interchange/importers/`
  package would only move files.
- **Naming.**  The module namespace tells the classes apart:
  `interchange.Straight` is a part, `assembly.Straight` a fitting.
  `hexmesh` doesn't re-export the parts.  The docs use
  `from hexmesh import interchange as ix`.
- **Importer return type (deviation from step 4).**  `read_pcf` still
  returns `NetworkSpec`, the file's records, and
  `NetworkSpec.to_model()` gives the `NetworkModel`.  The reader tests
  inspect `net.components`, `kind`, `record_type`, `skipped` and `header`,
  and they had to pass unchanged.  `to_assembly` / `to_assemblies` are thin
  wrappers, `build(self.to_model(), …)`, not deprecated.
  `read_bathymetry` returns a `NetworkModel` (one `Polyline`).  Its only
  caller calls `to_assembly`, which `NetworkModel` has.
- **Format facts as model content.**
  - `ANGLE` / `BEND-RADIUS` → `Bend.stated_angle` / `stated_radius`, parsed
    by the importer, plus `stated_names` so the cross-check message still
    says "ANGLE 46°".
  - Offset and tangential SKEYs → `Junction.offset`.  It is checked where
    the SKEY was, so the order of errors is unchanged.
  - Eccentric reducers → `Reducer.eccentric`.
  - Crosses and angled inline components → `Part.reject` (the importer
    words the reason).
  - `FLOW` → `Port.flow`.  Root choice tries ends with `flow="in"` first.
  - Pipelines → `Network(kind="pipeline", insulation_thickness=…)`.
    `kind` words the messages ("pipeline L-1").
  - Insulation status → parts and ports.
  - Equipment connections → `Terminal` parts (name, `Port.equipment`,
    `check_point` = the nozzle's CO-ORDS).
- **Formatter hook.**  `register_formatter(format, fn(part, at, name))`.
  `name` is there because a split host pipe's pieces are labelled
  `PIPE_2_1` / `PIPE_2_2`.  The PCF formatter keeps "component N (TYPE
  LABEL, SKEY … at […])", with N the part id (= component index).
- **Connections.**  The importer records `END-CONNECTION-PIPELINE` points
  where two ports meet (within `TOL_FLOOR`) as declared `Connection`s.
  The builder still infers connectivity by position, as before.  **For
  0066:** when cuts exist, the builder has to honour the model's
  connections and stop inferring across a cut.
- **The builder's internal record.**  `build` turns parts into a private
  `_Comp` (positions by role, `Section`s) and runs the moved algorithms on
  it.  The algorithms were copied from `pcf.py` and edited in place: field
  names, `dataclasses.replace` for the copies, and messages through the
  formatter.  The model is never mutated except `model.report`.
- **Spec adapter.**  A callable whose first parameter is named `section`
  or annotated `Section` gets the `Section`.  Any other callable gets
  `section.nominal` (0 when unknown, as `spec(bore)` got 0 before).
- **Edge kept as before, noted.**  A set-on or Y piece with two
  END-POINTs: only the first END-POINT's keypoint insulation reaches the
  model (the junction's port 0).  The guide gives these records no
  END-POINTs.

## Questions for design

_None._

## Outcome

**Files.**
- New: `hexmesh/interchange/{__init__,model,build}.py`,
  `tests/test_interchange.py` (9 tests).
- Changed: `hexmesh/io/readers/pcf.py` (1836 → 888 lines; parser, PCF →
  model translation, formatter, wrappers), `hexmesh/io/readers/bathymetry.py`,
  `API.md` (new *Network interchange* section; `to_model`; bathymetry's
  return type), `docs/integrations/pcf.md` (role line), and two message
  expectations in the reader tests.

**No behaviour change, measured.**  Before the refactor, a pytest plugin
recorded every `to_assembly` / `to_assemblies` call in the four reader
test files: the result's `to_dict()` or the error text, plus the meshed
nodes.  After it, the same run was compared.
- 87 tests, 72 calls.
- All **38 successful builds give an identical `to_dict()`**.
- The **5 meshes have identical node tags, and coordinates within
  1e-12**.
- 24 errors are identical.  10 differ in wording only, listed below.

**Messages that changed** (the builder no longer speaks PCF; names via
the formatter are unchanged):
- "elbow's incoming leg (start → CENTRE-POINT)" → "bend's incoming leg
  (start → corner)"; "elbow has no CENTRE-POINT" → "bend has no corner
  point …".
- Pieces hint: "The file holds N unconnected pieces" → "The model holds
  …"; "no pipeline reference" → "no network".
- "the pipeline has no INSULATION-THICKNESS" → "… no insulation
  thickness" (test updated).
- "loops are not read from PCF" → "loops are not built from a network".
- "no PIPE passes through its CENTRE-POINT" → "no straight pipe passes
  through its centre" (test updated).  Likewise "needs CENTRE-POINT and
  BRANCH1-POINT", "needs a size on BRANCH1-POINT", "stem PIPE ending at
  its CENTRE-POINT, BRANCH1-POINT and BRANCH2-POINT", "on each side of
  CENTRE-POINT", "run END-POINTs are not symmetric about CENTRE-POINT"
  and "misses its PCF point" now use centre / branch / port.
- "a junction must be a TEE, set-on or Y piece" → "a tee, a tap or a
  wye".
- An equipment connection with no position: "no CO-ORDS or END-POINT to
  attach it by" → "no position to attach it by".
- Bathymetry routes: segments are named "part route (PIPE PIPE_k …)",
  not "component k (PIPE PIPE_k …)".

**Accept.**
- Hand-built models build and mesh: Straight, Bend, tee Junction,
  Terminal; predicted = meshed cells.
- Covered by tests: declared flow moves the root; `spec(section)` and
  `spec(bore)` give the same assembly; `reject` and a registered formatter
  name the part; `build_pieces` / `selection`; `Polyline`, straight or
  spline.
- The builder and the model import nothing from the readers: an AST check,
  plus `import hexmesh.interchange` loads no `hexmesh.io.readers` module.
- Full suite: 2165 passed, 15 skipped (before: 2156 passed; +9 new).

**Follow-ups.**
- 0066: the builder honours declared connections and cuts, instead of
  inferring across them.
- `Section` rectangles reach the spec callable but nothing builds
  rectangular networks from a model yet: duct taps and transitions as
  model parts.  That would serve IFC (stage 3).
- `Transition` exists in the model; the builder treats it as a `Reducer`
  (sizes only).
