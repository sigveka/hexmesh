# 0164 — Keyword-only arguments, copy-on-write specs, named outlets

- **Status:** done
- **Decision:** [0053](../decisions/0053-api-hardening-before-freeze.md)
- **Depends on:** 0150 (the inventory and its test), 0163.
- **Blocks:** the 0.8.0 tag (task 0150's release prep is redone after
  this).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Three things about how the public API is called become
permanent at 1.0 and are cheap to change now (decision 0053's context).
No users yet: break directly, with CHANGELOG *Breaking* lines; no
deprecation shims.

**Do.**
1. **Measure first:** count the call sites that break under each point
   (positional calls past the new limit, in `hexmesh/`, `tests/`,
   `docs/`, `validation/`, the examples and README/API/GUIDE code
   blocks; `PipeSpec` uses that rely on mutation; unpacking of `add`).
   Record the counts in *Agent notes*.
2. **Copy-on-write `PipeSpec`** (decision rule 2): failing test first
   (the snippet in the decision), then `core()`, `shell()` and any other
   public mutating method return a new spec.  Fix the call sites that
   relied on mutation (`spec.shell(...)` without keeping the result).
3. **Keyword-only arguments** (rule 1): apply the defaults; list every
   exception you make in a table (callable, positional arguments kept,
   why).  Add an architecture test over `docs/api-1.0.json`: no public
   callable has more than two positional arguments besides `self`, apart
   from the table's exceptions, named in the test.
4. **Named outlets** (rule 3): a named tuple type per multi-outlet
   fitting, exported with it (or one generic type with fitting-specific
   field names: your choice, say which).  Tests: unpacking works as
   before; the fields name the right ports; `describe` and the agent's
   output are unchanged.
5. **README *Stability*:** rule 4's paragraph on limits.
6. **Rewrite the docs and examples** to keyword calls; examples stay
   byte-identical (the meshes, not the files' text).
7. **Regenerate** `docs/api-1.0.json`, the CHANGELOG (the 0.8.0 entry's
   *Breaking* section), then redo 0150's release prep on top.

**Accept.**
- The new architecture test and the tests of steps 2 and 4 pass.
- The exception table, under *Agent notes*.
- All examples byte-identical; full suite green; CI green on `next`.
- The 0.8.0 tag still waits for the user's OK (RELEASING.md).

**Out of scope.**  Renaming the jargon arguments (`mbmp`, `mprg`, `lc`,
`nang`, `nrad`); the deferred 1.x items in the decision's
*Consequences*.

## Agent notes

- **2026-11-16, step 1, the measurement** (an AST scan of `.py` files and
  of the ```` ```python ```` blocks in `.md` files, `build/` left out;
  names matched by the called name or method, so method counts are an
  upper bound):
  - **Calls past the new limits:** 662.  tests 539, `hexmesh/` 87,
    `validation/` 15, API.md 8, `benchmarks/` 8, docs 5.  The most:
    `RectShape(w, h, nw, nh)` 155, `.core(name, shape, …)` 138,
    `CircleShape(r, nang)` 58, `Switch` 52, `Reducer(outlet, length)` 47,
    `Nozzle(name, spec, location)` 46, `Transition` 41, `SplinePipe` 36,
    `OnShell` 29, `Wye` 28, `OnHead` 19, `Tee` 18, `Bend` 16.
  - **`PipeSpec` mutation:** 33 `.core`/`.shell` calls whose result is
    dropped.  4 relied on the mutation, all in `hexmesh/`:
    `PipeSpec.from_dict` (3) and the tee's branch spec
    (`tee.py`, `out.shell(...)`).  The others raise inside
    `pytest.raises`, or are one-line doc examples.
  - **`add` unpacking:** 68 sites unpack a multi-outlet `add`; a named
    tuple unpacks the same, so none breaks.
- **Step 2, copy-on-write:** `core()` and `shell()` start with
  `self = self._copy()` (a shallow copy with its own shell list); nothing
  else on `PipeSpec` mutates.  `PipeSpec` has no `__eq__` (identity), so
  "equality unaffected" holds trivially; the saved form is unchanged.
  `tests/test_spec_copy_on_write.py`: 6 tests, the decision's snippet
  first.
- **Step 3, keyword-only:** the call sites were rewritten mechanically
  from the old signatures (999 arguments in about 90 files), before the
  signatures changed.  By hand: `interchange/_build.py` (it imports the
  interchange `Bend`/`Reducer`/`Straight` and, inside a function, the
  fittings of the same names), the part factory `NetworkModel.add_part`,
  `Port(...)` in `add_port`, `graph.py`'s `describe(...)`, and the tests'
  `BlockStraight`, a `Straight` subclass.
  - Dataclasses take `_: KW_ONLY` after the kept fields, or
    `kw_only=True` when none is kept; functions a bare `*`.
  - **The limits applied** (positional kept): the decision's defaults,
    plus `Elbow(angle, schedule)`, `CircleShape(radius)`,
    `RectShape(half_w, half_h)`, `LayerSpec(name)`, `BundleSpec(pipe)`,
    `Drum(name)`, `Nozzle(name)`, `OnHead(head)`, `OnShell(axial)`,
    `Study(path)`, `study.run(study, stage)`,
    `run_stage`/`mesh`/`case_stage(study, rows)`, `read_pcf(path)`,
    `read_bathymetry(surface_path, route)`,
    `interchange.build(model, spec)`, `interchange.describe(part)`,
    `write_openfoam_case(path)`, `MaterialGraph.add_interface(a, b)`,
    `Assembly.from_nozzle(drum, nozzle)`, `prepend(fitting)`,
    `extend_open_ends(upstream, downstream)`,
    `check_quality(quality_name)`, `write(path)` (`dim` too), and
    `Tee.smallest_ratio`/`shortest_run`/`predicted_sj(inlet, spec)`.
  - **Interchange parts:** users build them (API.md: `ix.Network("L-1")`,
    `ix.Section(nominal=0.1)`), so they are keyword-only after their id:
    `Port(id)`, the parts `(id)`, `Connection(a, b)`, `Network(name)`,
    `Provenance(source)`; `Section` and `NetworkModel` keywords only.
  - **The exception table** (`tests/test_architecture.py`,
    `POSITIONAL_EXCEPTIONS`; the test fails on a new one, and on one no
    longer needed):

    | callable | positional kept | why |
    |---|---|---|
    | `Assembly.close` | `source, target, fitting` | the decision: as before |
    | `Frame`, `Frame.from_vectors` | `position, normal, up` | a frame is these three, in this order everywhere |
    | the fittings' `path`, `layers_ok`, `centreline_length`, `fill`, `resolve`; `SplinePipe.tight_spot`, `Closure.stations` | all | the fitting protocol: the assembler calls them positionally, a fitting implements them |
    | `CrossSection`, `QualityReport`, `RegionQuality`, `HexVolumeQuality`, `NetworkSpec` | all | results users read and never build (the decision: unchanged) |
- **Step 4, named outlets:** one type per fitting, exported with it:
  `TeeOutlets(run, branch)`, `WyeOutlets(left, right)` (`hexmesh` and
  `hexmesh.assembly`).  A fitting names its type as `Outlets`; `_graph.add`
  returns `Outlets(*outlets)`, or a plain tuple for a fitting without one
  (it returned a list before).  `Switch` has one outlet, so it returns the
  `Interface`, as every one-outlet fitting.
  - **The tee's run port is renamed `main` → `run`** (`Tee.port_names`),
    so `names={…}` keys and the tuple's fields are one vocabulary, as the
    decision names them.  Only a docstring used the `"main"` key; interface
    names users chose (`names=["main", …]`) are unaffected.  No migration: a saved
    description stores `names` as interface index → name
    (`intent.py`, `{"2": "main"}`), never by port key; port names appear
    only in `port_name_unknown`'s message and `limit`, which aren't
    saved.  The design session approved this, the interchange parts'
    limits and every exception in the table (2026-11-16).
  - `tests/test_named_outlets.py`: 5 tests (unpacking; the fields name the
    right ports by geometry; `names=` keys; one outlet; `describe`
    unchanged).
- **Step 5:** README *Stability*: *Limits may move*, rule 4's wording.

## Questions for design

## Outcome

- **Done** (2026-11-17): the decision's four rules.  Keyword-only arguments
  past at most two positional ones (the exceptions in the table above);
  `PipeSpec.core` and `.shell` copy on write; `add` returns `TeeOutlets` /
  `WyeOutlets`; README *Stability* says limits may move.
- **Files:** 46 in `hexmesh/` (signatures, `_graph.add`, `spec.py`, the
  fittings' `Outlets`, exports), 51 in `tests/`, the 35 examples, API.md,
  GUIDE, README, CHANGELOG (0.8.0 section), `docs/api-1.0.json`.  About
  1000 call arguments were rewritten to keywords by an AST script that
  read the old signatures; the rest (aliases, subclasses, code in string
  literals) by hand.
- **Tests:** new `test_spec_copy_on_write.py` (6),
  `test_named_outlets.py` (5), and two in `test_architecture.py` (no
  public callable takes more than two positional arguments, outside the
  exception table; a planted one is caught).  The whole suite passes: the
  fast part in one run, the slow files one at a time (fitting
  conformance 1052, refined 1041 + 14 skipped, second order 46, msh
  recipe 54, examples 39, h examples 6, units 12).
- **Examples unchanged:** all 35 examples give byte-identical meshes
  (recipe block left out) and identical saved descriptions, against a
  worktree at fcb5d42.
- **Surprises:** `PipeSpec.from_dict` relied on mutation (fixed with the
  rest); the rename `main` → `run` of the tee's run port (approved, see
  step 4).
- **Follow-ups:** 0166 (the renames) next; the 0.8.0 release prep is
  redone after 0165–0167.
