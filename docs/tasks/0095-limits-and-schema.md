# 0095 — Limits with units, and a JSON Schema generated from the registries

- **Status:** done
- **Decision:** [0040 — Agents for users](../decisions/0040-user-agents-network-design-and-resolution.md) (foundation B); [0019](../decisions/0019-future-agent-sdk.md) items 3 and constraint 6
- **Depends on:** 0094 (done: its errors name `limits.py` constants in
  `limit`).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  An agent, or a person writing JSON by hand, needs to know
what fields a spec or fitting takes, their units and their limits,
without reading the source.  Today:
- `assembly/limits.py` has 19 named constants, documented in comments
  only.  Other limits are inline in the checks (for example the bend
  radius against the outer radius, and `nang % (n_outer // 4)`).
- Fittings are frozen dataclasses registered in
  `intent.FITTING_TYPES` (11 types).  `PipeSpec.to_dict`,
  `Equipment.to_dict` and `Assembly.to_dict` define the saved format,
  but nothing describes it.
- `jsonschema` 4.10 is already in the `gallery` extra (case.json).

**Where.**
- `assembly/limits.py`;
- the fitting dataclasses, `core/spec.py` and `core/shape.py`, and
  `assembly/equipment.py`: field metadata;
- new `hexmesh/agent/__init__.py` and `hexmesh/agent/schema.py`, the
  start of decision 0040's tool layer;
- `tests/`; `API.md`; DESIGN §3.1's leaves, through the architecture
  test.

**Do.**
1. **Limits as data.**
   - In `limits.py`, a registry `LIMITS: dict[str, Limit]`, with
     `Limit(value, unit, kind, doc)`:
     - `kind`: `"error"` or `"warn"`;
     - `unit`: `"deg"`, `"m"`, `"1"` (a ratio) and the like;
     - `doc`: one line.
   - Keep every module constant (`PREDICTED_SJ_WARN = …`), so callers
     don't change.  The registry is built from them, or they from it.
   - Find the user-facing limits written inline in checks and move them
     into `limits.py` as named constants, with the check using the
     name.  List them in *Agent notes*, with the file and line where
     each was.
   - Leave alone what is a rule rather than a number, such as "radius
     greater than the outer radius".  It becomes a schema description
     (step 3), not a constant.
   - Where 0094's errors pass a limit's value, pass its name instead
     once it's in the registry.
2. **Field metadata.**  On every field of every registered fitting,
   the `PipeSpec.core` and `shell` arguments, the shapes, and the
   equipment:
   - `unit`;
   - `doc` (one line);
   - and where one applies, `limit` (the name of a registry entry) or a
     plain range (`minimum`, `exclusiveMinimum`, `enum`).
   Use `dataclasses.field(metadata=…)` for dataclasses, and a
   table next to the signature for methods.  No behaviour change.
3. **`hexmesh.agent.schema()`.**  It generates a JSON Schema (draft
   2020-12) for:
   - the `PipeSpec` description;
   - each fitting and equipment description;
   - the `Assembly` description (`format`, `version`, inlet, the
     operation list).
   Each field gets its type, unit (`"x-unit"`), doc (`description`),
   range and default.  Rules that aren't ranges go into the field's or
   fitting's `description`, from its docstring.  The schema carries the
   description's current `version`, and `$defs` per fitting type.
   - It is generated at call time, deterministic (sorted keys), and
     never hand-edited.  `hexmesh.agent` imports the public API only.
     Nothing in the library imports `hexmesh.agent`; add that to the
     architecture test.
   - `python3 -m hexmesh.agent.schema` prints it.  The full CLI is
     foundation D's.
4. **Tests:**
   - The schema validates against the draft 2020-12 metaschema.
   - Every `hexmesh/examples` assembly's `to_dict()` validates against
     it.  So do the saved fixtures (`tests/data/saved_before_*.json`)
     after `upgrade()`.
   - Every field of every registered fitting has `unit` and `doc`.  A
     new field without them fails the test, which plants a case.
   - Every `LIMITS` entry has a unit, kind and doc, and every name that
     0094's errors pass as `limit` is a key in `LIMITS`.
   - The schema is byte-identical across two runs.
   - Use `jsonschema` from the `gallery` extra, or move it to a test
     extra, and say which in *Outcome*.
5. **API.md:** a "Schema and limits" section with how to get the
   schema, and the limits table (name, value, unit, kind, doc),
   generated from `LIMITS` or checked against it by a test.

**Accept.**
- Steps 1–4 hold.  The examples and fixtures validate.
- No behaviour change: every mesh, message and `to_dict` is identical
  (the 0094 recorder method), apart from any `limit` field in errors
  that moved from a value to a name (list those).
- Full suite: no new failures.
- *Outcome*: the schema size, the number of fields described, the
  inline limits moved, and any field whose unit or range was unclear.

**Out of scope.**
- **The network model's schema.**  It has no JSON form yet: that is
  decision 0032's stage 2, the network document, which has no task
  yet.  Decision 0040's network designer writes the network model, so
  the design session will propose that stage next.  Design the
  generator so that adding the network-model part classes later is a
  new entry, not a rewrite.
- The CLI (foundation D), and `describe` / `preview` (foundation C).

## Agent notes

- **Registry.**  `limits.LIMITS` is built from the constants: each
  constant is `NAME = _limit("NAME", value, unit, kind, doc)`, so the
  value is written once and callers don't change.
- **A third kind, `info`.**  Two constants are neither an error nor a
  warning bound:
  - `SWITCH_SHEAR_SJ`, a table of measurements for reports;
  - `WYE_N_SPLIT_MAX`, a cap that resolution applies itself.
  Calling either one `error` would misdescribe it.  `KINDS` is
  `("error", "warn", "info")`.
- **Limit units.**  Besides `deg` and `1`, limits use `t` (ring
  thicknesses, `SWITCH_MIN_LENGTH`), `R` (radii, `WYE_SHELL_MAX` and
  `WALL_PROJECTION_WARN_MOVE`) and `layers`.  No limit is in `m`: every
  length limit is relative.
- **Inline limits moved into `limits.py`** (file:line at d2b9908):
  - `fittings.py:254–255` `MAX_MITER_CUT`, `MIN_MITER_CUT`: already
    named by 0094's errors, now registered.  `fittings` keeps aliases.
  - `fittings.py:199` the bend's per-layer 180° in `Bend.layers_ok`,
    now `MAX_SLAB_TURN`.
  - `sweep.py:281` `MAX_CHORD_TURN` and `sweep.py:284`
    `MAX_RESOLVED_LAYERS`: `sweep` keeps aliases.
  - `wye.py:71` `ANGLE_RANGE` (30, 120), now `WYE_ANGLE_MIN` and
    `WYE_ANGLE_MAX`: `ANGLE_RANGE` is kept, built from them.
  - `profile.py:57` `VENTURI_DIVERGENT` (7, 15), now
    `VENTURI_DIVERGENT_MIN` and `VENTURI_DIVERGENT_MAX`: the tuple is
    kept.
  - Left alone as rules, not numbers:
    - `nang % (n_outer // 4)`;
    - `0 < |angle| < 360`;
    - the bend radius against the outer radius;
    - `n_outer` a positive multiple of 4.
    They are schema ranges or descriptions instead.
  - Left alone as internal:
    - the reducer's search cap, `100_000` in `fittings.py:617`;
    - `wye.py`'s `_IN_MARGIN`… layout constants;
    - `duct_tap.FULL_WIDTH_RUN`;
    - the PCF reader's tolerances;
    - `interchange.build`'s `TOL_*`.
- **Errors' `limit` that moved from a value to a name** (step 1, last
  point):
  - `sweep.py:459` `n_layers_unresolvable`: `100000` →
    `"MAX_RESOLVED_LAYERS"`;
  - `wye.py:308` `angle_out_of_range`: `{"min": 30.0, "max": 120.0}`
    → `{"min": "WYE_ANGLE_MIN", "max": "WYE_ANGLE_MAX"}`;
  - `profile.py:113` `profile_parameter_out_of_range` (cosine `s0`): `{"min": -1.0, "max_exclusive": 0.5}`
    → the names `COSINE_S0_MIN` and `COSINE_S0_MAX`;
  - `profile.py:127` `profile_parameter_out_of_range` (venturi divergent): `{"min": 7.0, "max": 15.0}` →
    the names `VENTURI_DIVERGENT_MIN` and `VENTURI_DIVERGENT_MAX`.
  - The messages are unchanged.
- **Field metadata** lives in `hexmesh/core/params.py`: `param()` for
  dataclass fields, `describe()` for table entries.  It is in `core`
  because the shapes and the spec need it and `core` is the bottom
  layer, so it isn't a new leaf.
  - `param(..., input=True)` replaces `fittings._input_field()` and the
    `field(default=None, metadata={"input": True})` spelled out in `tee`,
    `wye` and `switch`.  The `"input"` flag is unchanged.
- **Field units** (`params.UNITS`): `length` (the user's unit: hexmesh
  never converts, so not `m`), `deg`, `1`, `cells`, and `-` for what
  isn't a quantity (names, choices, specs, shapes).  `-` keeps "every
  field has a unit" checkable.
- **The `PipeSpec` tables** are class attributes next to their methods:
  - `PARAMS` (`__init__`), `CORE_PARAMS` and `SHELL_PARAMS`;
  - a test checks that each table's keys equal its method's arguments;
  - input-only arguments (`radius`, `half_w`, `first_cell`…) are
    described as inputs and left out of the saved schema.
- **`-m` and the package.**  `hexmesh.agent.schema()` (a function) and
  `python3 -m hexmesh.agent.schema` (a module) share a name.  If the
  package imported `schema.py`, `-m` would load it twice, and runpy
  warns about that.  So:
  - the generator is `hexmesh/agent/_schema.py`;
  - `schema.py` is the command and re-exports `schema` and `dumps`;
  - the package imports `_schema`.
- **The architecture test** puts `agent` after `study` in `ORDER`.  A
  new rule says no module outside `hexmesh.agent` imports it, root and
  examples included, with planted cases.
- **The schema describes the saved form**, not the constructors:
  - fields without a default are `required`;
  - input fields are optional and say they are left out while unset;
  - `additionalProperties: false`, so a typo fails;
  - `Shell.type` also accepts `square_shell`, the pre-0026 form that
    `from_dict` still reads.
  The schema checks shapes and ranges only.  Cross-field rules stay in
  the descriptions, and `validate()` stays the real check.
- **The ranges are enforced by the code.**  Checked by planting the
  first out-of-range value of every fitting field through `Assembly.add`
  and `validate()`.  Every one was rejected except `Reducer.chord_tol=0`,
  which only a profile uses.

## Outcome

**Files.**
- New:
  - `hexmesh/core/params.py`;
  - `hexmesh/agent/__init__.py`, `_schema.py` and `schema.py`;
  - `tests/test_agent_schema.py`.
- Changed:
  - `assembly/limits.py` (the registry, plus 11 new entries);
  - field metadata in `assembly/fittings.py`, `tee.py`, `wye.py`,
    `switch.py` and `equipment.py`, and in `core/shape.py` and
    `core/spec.py`;
  - aliases and limit names in `sweep.py` and `profile.py`;
  - `tests/test_architecture.py`;
  - `API.md`: "Schema and limits";
  - `CHANGELOG.md`;
  - `pyproject.toml`: a comment only.

**Measurements.**
- Schema: 69,650 bytes, with 28 `$defs` and 153 properties.
- 115 fields described:
  - 67 fitting fields across the 11 types;
  - 6 shape fields;
  - 20 equipment fields;
  - 22 entries in the `PipeSpec` tables.
- `LIMITS`: 30 entries.  Before this task, 19 were constants in
  `limits.py`.  11 are new or moved: 2 miter, 3 sweep, 2 wye angle,
  2 venturi, and the bend's 180°.
- `jsonschema` comes from the `dev` extra, which already had it for
  `case.json` and which CI installs.  It needs no new extra; the tests
  skip without it.

**Checks.**
- New tests: 40 in `test_agent_schema`, run on all 28 examples:
  - the metaschema;
  - determinism;
  - every example's `to_dict()` validates;
  - both `saved_before_*` fixtures validate after `upgrade()`;
  - bad input is rejected: a typo, a wrong type, an out-of-range value,
    an unknown type and a future version;
  - unit and doc on every field, with a planted case;
  - the tables match their signatures;
  - field and error limit names are registered;
  - `API.md`'s table equals `LIMITS`.
- Architecture: 3 new planted cases.
- Recorder over the full suite, d2b9908 against the working tree:
  - no message or type changed (the 5 that differ embed pytest's
    `tmp_path`);
  - the same 404 records.
  The recorder doesn't capture `limit`; the four errors whose `limit`
  became a name are listed in *Agent notes*.
- The 28 example meshes: `$Nodes`, `$Elements` and the recipe hash are
  identical, so `to_dict` is unchanged too.
- Full suite: 3245 passed, 15 skipped.

**Unclear units or ranges** (my choice; check them):
- `Tee.margin`, `dome` and `sheet`: `1`, with no range.  They are
  `DuctTap` layout fractions, resolved by search; I didn't trace their
  bounds.
- `Reducer.chord_tol`: `1` (a fraction of R_in), `> 0`.  The code
  accepts 0 without a profile.
- `MiterBend.n_cuts`: unit `1` (a count of welds), not `cells`.
- `toward` is `-`, while `end_tangent`, `Drum.axis` and `up` are `1`.
  Both are directions; `toward` is only an input, used for its
  direction.
- Equipment ranges are not probed against the code, because a drum
  needs a nozzle to check them:
  - `OnShell.projection > 0`;
  - `OnHead.offset >= 0`;
  - `OnHead.projection > 0`.
- `PipeSpec.mbmp > 0` and the `wall_bump` coefficients `> 0`: from the
  meaning, not from a check.

**Follow-ups.**
- The network document's part classes (decision 0032 stage 2, task
  0097/0098) can add a builder to `_schema._defs()`.
- `describe` and `preview` (0097) can reuse `hexmesh.core.params`.

### Follow-up: the schema claims only what the code enforces (design answer, 2026-11-05)

The design session accepted points 1–4 (the user: "i agree").  For
point 5, the Outcome's "Unclear" list:
- **New coded checks:**
  - `PipeSpec(mbmp=…)` must be positive: `SpecError`,
    `value_not_positive`.
  - In `Drum.__post_init__`, with the drum and nozzle named:
    `OnShell.projection > 0`, `OnHead.offset >= 0` and
    `OnHead.projection > 0`.  These are `EquipmentError`s,
    `size_not_positive`, with `where = {part, nozzle, field}`.  They
    live with the drum's other nozzle checks, because a location alone
    has no drum to name.
- **Already checked:** the `wall_bump` coefficients
  (`wall_bump_invalid`, `PipeSpec.core`).  No change.
- **`direction`**, a new unit in `params.UNITS`: a 3-vector that hexmesh
  normalises.  It applies to `toward` (Bend, MiterBend, Elbow, Tee, Wye),
  `SplinePipe.end_tangent`, `Drum.axis` and `Drum.up`.  The saved
  `Frame` vectors keep unit `1`: they are stored orthonormal and read
  back bit for bit, not normalised.
- **`Reducer.chord_tol`:** the range is now `minimum: 0`.
- **API.md:**
  - "Schema and limits" lists `direction`;
  - it says every schema range is enforced;
  - it documents `hexmesh.core.params` (`UNITS`, `RANGES`, `param`,
    `describe`) and `hexmesh.core.shape.SHAPES` as public.  0097's
    `AGENT_IMPORTS` relies on that.
- **Tests:** `test_schema_ranges_are_enforced` (the four new errors,
  with codes and `where`) and `test_directions_share_one_unit`.
- **Checked:**
  - recorder over the full suite, 1a10d13 + 0097 against the working
    tree: no existing message or type changed (the 5 that differ embed
    pytest's `tmp_path`);
  - the only new records are the new tests' (the four new errors, and
    0097's `TypeError` test);
  - the 28 example meshes are identical;
  - full suite: 3313 passed, 15 skipped.
