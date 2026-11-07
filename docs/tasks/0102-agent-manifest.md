# 0102 — `hexmesh manifest`: one machine-readable account of the suite

- **Status:** ready
- **Decision:** [0040 — Agents for users](../decisions/0040-user-agents-network-design-and-resolution.md), amendment 2026-11-07 (foundation D2)
- **Depends on:** 0095, 0097, 0098 (done).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  An agent using hexmesh has to piece the tool together from
`hexmesh schema`, the docs and the errors it meets.  `essens describe`
shows the alternative: one JSON document that says what the tool does,
how its commands chain, and what it accepts.  hexmesh's registries
already hold most of it.

**Where.**  `hexmesh/agent/_manifest.py` (the `_name` pattern of 0095 and
0097); `hexmesh/agent/cli.py`; `hexmesh/agent/validation.json` (package
data); a generator for it under `validation/tools/`; tests; `API.md`;
`CHANGELOG.md`.

**Do.**
1. **`manifest() → dict`**, JSON-safe, deterministic, no GMSH.  Sections:
   - `version`, and the versions of the schema and of the advisor's
     data contract;
   - `commands`: each CLI subcommand with its arguments, input kinds,
     output (the `result` shape), the envelope `{command, ok, result,
     version}`, and the exit codes 0/1/2.  Read them from the
     `argparse` parser and `COMMANDS`, not a copy;
   - `workflow`: the steps from a description or a PCF file to a mesh,
     each naming its command and what it hands to the next;
   - `support`: per fitting type (`FITTING_TYPES`), which section
     shapes, layouts (`oh`, `h`) and stacks (single layer, rectangular
     shells, a circle in a rectangle, …) it accepts.
     - **Probe, don't declare:** build each fitting on a fixed set of
       small specs and run the library's own checks (`validate()`,
       `check_supported`), without GMSH.  Record "supported" or the
       error code.
     - If a fitting can't be probed without GMSH, note it under *Agent
       notes* and mark it `"probed": false`.
   - `limits`: `LIMITS`, with units and kinds;
   - `errors`: `CODES`, with their hints;
   - `advise`: the accuracy classes from `calibration.json`, each
     class's basis (measured, interpolated, extrapolated), and the
     scope caveat (developed flow in straight runs);
   - `validation`: per feature tag (`case.json` `tags.features`), the
     cases, their status (accepted, undecided, …), category and gates;
   - `conventions`: lengths as given (no conversion), angles in
     degrees, the 8× rule, and topology vs density (CLAUDE.md).
2. **`validation.json`** (package data): generated from
   `validation/*/case.json` and `results.json` by a script in
   `validation/tools/`, and committed.  A test regenerates it and fails
   if it differs, with the command to refresh it.
3. **CLI:** `hexmesh manifest`, emitting the manifest in the usual
   envelope.
4. **The console script.**  In the design session's environment
   `hexmesh` isn't on PATH; only `python3 -m hexmesh.agent.cli` works
   (2026-11-07).  Check why (an install without scripts?), and make
   sure the docs and the manifest name both forms.
5. **API.md:** a short "Manifest" section, saying an agent should read it
   first.

**Accept.**
- Every CLI subcommand, error code, limit and fitting type appears in
  the manifest; a test checks each against its registry.
- The support matrix agrees with the library: a planted case (a spec
  with `n_outer = 8`, which `check_supported` rejects today) shows as
  unsupported, with what the library raises.  A test fails if the
  matrix and a direct check of the library disagree for any entry.
- The validation summary matches the cases; the staleness test fails on
  a planted change to one `case.json`.
- Byte-identical output across two runs; no GMSH session; valid JSON
  (`allow_nan=False`).
- `hexmesh manifest` runs in under 2 s.
- Full suite: no new failures.

**Out of scope.**  The plugin (E) and an MCP server, which read the
manifest; prose documentation beyond API.md.
