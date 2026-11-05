# 0095 — Limits with units, and a JSON Schema generated from the registries

- **Status:** ready
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
