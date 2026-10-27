# 0019 — Future expansion: an agent SDK (hexmesh driven by AI tool calls)

- **Status:** proposed (future expansion; no tasks)
- **Date:** 2026-10-26 (recorded at the user's request: "record it as
  decision 0019")
- **Tasks:** none.  Decisions until then are checked against the
  constraints below (decisions README, "Future expansions").

## Context

An AI agent (for example Claude, through tool calls) could design and
build hexmesh networks from a plain-language request or plant data.
hexmesh already has the properties such an interface needs, because
DESIGN required them for other reasons:

- **The network is plain JSON** (`Assembly.to_dict`, task 0006): the
  inlet pose and spec, then every `add` / `close` / `prepend` in order,
  each fitting from a fixed registry (`intent.FITTING_TYPES`).
- **Every check runs before GMSH** (P3, P4): `validate()` and the exact
  `cell_count()` are pure Python, so an agent can draft, check and
  correct in a loop without meshing.
- **Errors name the offender**, e.g. `fitting #1 Bend(radius=0.05, …):
  path bends with radius 0.05, tighter than the pipe outer radius 0.1`
  (checked 2026-10-26).

DESIGN §10 asks "Library or tool?".  An agent SDK is a library driven
through a tool interface, which fits either answer.

## Sketch

```
agent ── tool calls (JSON) ──> MCP server ──> hexmesh.agent ──> hexmesh
```

`hexmesh.agent` is a stateless API over the network JSON: the JSON is
the state.  Only meshing is slow; it runs as a job with an id.

| Tool | Does | GMSH |
|---|---|---|
| `get_schema()` | JSON Schema for specs and every fitting type, from the registry, with units, limits and one-line docs | no |
| `validate_network(network)` | `{ok, errors}` with structured errors (below) | no |
| `estimate(network)` | exact cells per fitting and total; rough mesh time | no |
| `describe_network(network)` | open ends (position, direction, patch name), bounding box, lengths | no |
| `render_preview(network)` | PNG of centrelines and outlines, drawn from frames in Python | no |
| `build_mesh(network, outputs)` → job; `job_status(job)` | `.msh`, or OpenFOAM `.msh` + `.roles.json` | yes |
| `quality_report(job)` | per-fitting quality and worst-cell locations | — |
| `import_pcf`, `import_route` | the existing readers → network JSON | no |

A structured error:

```json
{"code": "bend_radius_below_outer_radius",
 "at": {"edge": 1, "label": "elbow_A", "field": "radius"},
 "value": 0.05, "limit": {"min_exclusive": 0.1},
 "message": "Bend radius 0.05 is tighter than the pipe outer radius 0.1",
 "hint": "Use radius > 0.1, e.g. Elbow(schedule='long')"}
```

## What hexmesh would need (likely order)

1. **Error codes and fields** on `AssemblyError` (and `EquipmentError`,
   reader errors): code, location (edge, label, interface, field),
   value, limit, message, hint.  Useful to people too; the one piece
   worth doing early.
2. **Named references** in the JSON: fittings attach by interface index
   (`"source": 4`), which is fragile under edits.  Accept names and
   labels (`"from": "main_end"`) as well.
3. **Schema generation** from the fitting dataclasses, with units and
   limits as field metadata.
4. **Geometry summary and preview** without GMSH.
5. **A short agent guide** generated from `API.md`, small enough for a
   model's context.
6. **Build safety:** jobs follow the shared-machine rules (CLAUDE.md)
   and a cell budget (`validate(max_cells=…)` exists).
7. The MCP server itself: a thin wrapper.

## Constraints for decisions going forward

1. **Every check before GMSH.**  Keep P3/P4: a new fitting or rule must
   be checkable in `validate()` and countable in `cell_count()`.
2. **The network JSON stays complete and editable.**  Anything that
   shapes a mesh is in the saved description (task 0006); no state that
   exists only in Python objects or in GMSH.  New fitting fields are
   serialisable (as decision 0008 required: no callables).
3. **Errors stay machine-readable.**  New validation errors name the
   fitting, the field and the limit; once item 1 exists, every new
   error gets a code.
4. **Stable names.**  Fitting labels, interface names and patch names
   are stable identifiers (A7); don't make an agent depend on creation
   order where a name could be used.
5. **Deterministic output.**  The same JSON gives the same mesh and the
   same names (A6 fill-order independence already requires this).
6. **Limits as data.**  Validation limits (angles, ratios, tolerances)
   should be defined where a schema can read them, not only inside
   `if` statements.

## Verified vs. assumed

- **Verified (2026-10-26):** the JSON format and fitting registry; that
  validation and cell counts need no GMSH; the error message example.
- **Assumed:** that MCP is the right transport (others: a CLI, a plain
  Python API); preview quality of a frames-only sketch; mesh-time
  estimates from volume counts.
