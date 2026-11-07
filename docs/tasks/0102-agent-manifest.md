# 0102 — `hexmesh manifest`: one machine-readable account of the suite

- **Status:** done (2026-11-07; three findings for design, none blocking)
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

## Agent notes

- **Step 4, why `hexmesh` isn't on PATH:** hexmesh isn't installed in
  this environment at all.  `pip show hexmesh` finds no package, and
  `import hexmesh` fails outside the checkout.  The code runs only
  because the repository root is the working directory.
  `pyproject.toml` declares the script (`[project.scripts] hexmesh =
  "hexmesh.agent.cli:main"`), and `pip install -e .` would create it.  I
  left the environment as it is.  API.md, the CLI docstring and the
  manifest's `invocation` name both forms.
- **The support matrix is stored, not computed per call.**  The probe
  takes about 1.3 s, most of it the wye's layout, and `hexmesh manifest`
  must run under 2 s.  So `python3 -m hexmesh.agent._probe` writes
  `hexmesh/agent/support.json` (package data, like `calibration.json`).
  `test_the_stored_support_matrix_is_the_library_s` probes again and
  fails, naming that command, if any entry differs.  So it is still
  probed, not declared.  `hexmesh manifest` takes about 0.6 s.
- **The probe:** each fitting is built after a 0.1 m `Straight` on seven
  specs, then run through `Assembly.validate()`, with no GMSH session.
  The specs are: circle, circle with a shell, H rectangle, O-H
  rectangle, H rectangle with a shell, a circle in a rectangle, and a
  circle with `n_outer = 8`.  Each fitting is built as it is meant to
  be used on that shape:
  - a Reducer to the same spec at 0.8×;
  - a Transition to the other shape;
  - a Tee as a duct tap (`branch=RectShape`) on rectangles;
  - a Switch from H with an O-H outlet.
  `Closure` is `"probed": false`: it joins two existing interfaces of a
  loop.  Of the 70 entries, 43 are supported.
- **Found by the probe (for design):**
  - **A Switch on a circular section raises an uncoded
    `AttributeError`** ("'CircleShape' object has no attribute
    'nang_w'"), not a `HexmeshError`.  The manifest records it as code
    `null`.  It should be a coded error such as `switch_needs_rect`.
    That needs a new code, so it is proposed, not done.
  - **A duct tap on a rectangle with a shell is rejected with
    `switch_changes_shells`**, a Switch's message, so the tap's error
    names the wrong fitting.
  - **A Tee on `n_outer = 8` raises `block_vertices_not_distinct`**
    before `section_not_supported`.  The probe records what the library
    raises first, as specified.
- **Import cycle:** `cli` runs `agent.manifest()` and the manifest reads
  the CLI's parser, which made a cycle (cli → agent → _manifest → cli),
  and `test_architecture` rejects cycles.  The command table (COMMANDS,
  RESULTS, NEEDS_GMSH, the exit codes) and the parser moved into a leaf
  module, `hexmesh/agent/_commands.py`; `cli` re-exports what it used to
  define.  `RESULTS` (each command's `result`, one line) is new, and a
  test checks it covers `COMMANDS`.
- **`errors` "with their hints":** `CODES` holds one line per code, the
  rule.  Hints are per raise, with the values of that error, so there is
  no per-code hint to list.  The manifest gives the rule.
- **`validation`:** per case, the title, status, category, task, gates,
  and from `results.json` the number of levels and the cell range.  Per
  feature tag, the cases.  No orders: per §7.12 they belong to the
  recheck, from k.
- **`advise`:** the classes' basis comes per calibrated series (circle;
  rectangle a/b 1, 2, 4), since each has its own: measured,
  interpolated or extrapolated, and validated or not.

## Outcome

**Done.**

**Files:**
- new: `hexmesh/agent/_manifest.py`, `_probe.py`, `_commands.py`,
  `support.json` and `validation.json` (package data, in
  `pyproject.toml`); `validation/tools/summary.py`;
  `tests/test_agent_manifest.py` (8 tests);
- changed: `hexmesh/agent/cli.py` (`manifest`; the table moved out),
  `hexmesh/agent/__init__.py`, `API.md` (a Manifest section, both
  invocation forms), `CHANGELOG.md`.

**Acceptance:**
- Every subcommand, code, limit and fitting type is in the manifest,
  checked against its registry.
- `n_outer = 8` is unsupported, with `section_not_supported` and the
  library's message.  The stored matrix equals a fresh probe.
- The validation summary equals a fresh one, and a planted `case.json`
  change shows.
- Two runs give identical output, strict JSON, with no GMSH session.
- The CLI takes about 0.6 s (tested at < 2 s).

**Suite:** 3591 passed, 15 skipped, no failures.

**Follow-ups (proposed):**
- a coded error for a Switch on a circle;
- the duct tap's error on shelled rectangles should name the tap;
- decision 0040's plugin (E) can read `hexmesh manifest`.
