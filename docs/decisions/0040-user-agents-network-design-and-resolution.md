# 0040 — Agents for users: network design and resolution first

- **Status:** accepted (2026-11-04 by the user: "accept 0040 with your
  recommendations")
- **Date:** 2026-11-04 (the user: "I am thinking network designer and
  resolution is where I want to start", for agents that serve users of
  the framework, not its development)
- **Tasks:** 0094 (foundation A, structured errors; done), 0095
  (foundation B, limits and schema), 0096 (PCF line numbers).  To be
  written: foundations C and D, then the plugin (E).
- **Builds on:** decision 0019 (agent SDK, proposed): this decision is
  its first stage.  Decision 0032 (network interchange): the network
  model is what an agent writes.

## Context

hexmesh's users want a mesh of their network: plant piping, HVAC ducts,
later vessels (decision 0018).  Two steps take expertise today:

1. **Describing the network:** writing `Assembly` code or JSON fitting
   by fitting, or preparing a PCF file.
2. **Choosing the resolution:** `nang`, `nrad`, `first_cell` / `mprg`,
   `n_layers` per fitting, and the layout (O-H or H, decision 0036).
   Users from unstructured meshing expect cell counts to scale linearly
   and are surprised by the 8× rule (CLAUDE.md).

An agent can do both in a loop with the user, because hexmesh already
has what decision 0019 asked for: JSON descriptions, every check before
GMSH, exact cell counts, errors that name the fitting, and deterministic
output (since task 0091, every `.msh` also carries its recipe).

**What exists (checked 2026-11-04, `50b7292`):**
- **The network model** (`hexmesh.interchange`, task 0065): ports,
  parts, connections, provenance; one builder to an `Assembly`.  Task
  0066 (model operations, public API) is `ready`.
- **Readers:** PCF and bathymetry.
- **Grading solvers** (`core/grading.py`): `progression_for_first_cell`,
  `bump_for_first_cell`, `first_cell_height`.
- **Limits** are mostly named constants in `assembly/limits.py`, but
  with no units, docs or schema around them.
- **Missing:**
  - error codes on `AssemblyError` (decision 0019 item 1);
  - a JSON Schema of specs and fittings;
  - a geometry summary or preview without GMSH;
  - a general CLI (only `hexmesh-study` exists);
  - anything that turns flow conditions into a resolution.

## Options

### Where the logic lives

- **A. In the library; the agent is a thin layer (recommended).**  The
  resolution advice is a pure, tested Python function.  The network
  design loop calls library functions (validate, estimate, describe).
  The agent's skill holds the workflow and the questions to ask, not
  the engineering.  The same functions then serve people without an
  agent, the MCP server later, and tests.
- **B. In the agent's instructions.**  Fast to write, but untestable,
  model-dependent, and duplicated if a second front-end appears.

### What the network designer writes

- **A. The network model** (points, parts, sections; decision 0032)
  **(recommended).**  It describes the physical network the way a user
  thinks of it: where pipes run, what joins what.  The builder then
  chooses fittings, junction entries and insulation.  It has
  provenance, so errors point back to the user's own words ("the branch
  to pump P2").  PCF and IFC users already arrive this way.
- **B. The `Assembly` JSON** (`to_dict`).  It's complete and already
  works, but it is fitting by fitting in creation order.  Parts attach
  by interface index, which decision 0019 item 2 calls fragile under
  edits.  Keep it for fine edits after the build.

### How users get the agents

- **A. A Claude Code plugin shipped with hexmesh (recommended first).**
  Two skills plus, later, a background agent for long builds.  It
  calls a `hexmesh` CLI.  No server, quick to build, and it works where
  users already run Claude.
- **B. The MCP server of decision 0019** for every MCP client (Claude
  Desktop, other agents).  More general and more work.  It wraps the
  same CLI or Python functions, so it can follow without rework.

## Decision

**Accepted 2026-11-04: A / A / A.**  Library first, the network model as
what the agent writes, and a Claude Code plugin first.  MCP comes later,
over the same tool layer.

**Settled at acceptance:**
1. **Wall treatment: `wall-resolved` (y⁺ ≈ 1) only** at first.
   `wall-function` waits for a validated turbulent case (task 0049) to
   calibrate against.  `advise` rejects it with an error naming that
   task.  The input format keeps the field, so adding it later changes
   no interface.
2. **The plugin lives in this repo**, `agents/claude-code/`, versioned
   with the library.  The CLI's JSON and the skills change together, so
   one test run covers both.

### The tool layer: `hexmesh.agent` and the `hexmesh` CLI

- Stateless functions over JSON (the JSON is the state, as in decision
  0019).
- Each one has a CLI subcommand that prints JSON, so a skill can call it
  in a shell.
- No GMSH needed except in `build`.

| function / subcommand | does | GMSH |
|---|---|---|
| `schema` | JSON Schema for the network model, specs and fittings, with units, limits and one-line docs, generated from the registries | no |
| `validate` | `{ok, errors}`, errors structured (item A below) | no |
| `estimate` | exact cells per part and in total; a rough mesh time | no |
| `describe` | open ends, bounding box, lengths, sections, the parts list | no |
| `preview` | PNG of centrelines and outlines from frames | no |
| `advise` | the resolution (below) | no |
| `build` | `.msh` (with its recipe block), or the OpenFOAM `.msh` | yes |

### The resolution advisor: `hexmesh.agent.advise`

- **Inputs:**
  - the network, or a single section;
  - the fluid (density, viscosity);
  - the flow (velocity or flow rate per branch);
  - the wall treatment: `wall-resolved` (y⁺ ≈ 1) or `wall-function`
    (y⁺ 30–100);
  - a cell budget, and optionally an accuracy class.
- **Outputs, per section:**
  - Re and the regime (laminar, transitional, turbulent);
  - the first-cell height from y⁺ (skin friction from a stated
    correlation: laminar exact, Blasius, or Colebrook for rough pipes);
  - `first_cell`, `nrad`, `nang` / `nang_w` / `nang_h`, and the layout;
  - `n_layers` per fitting from an axial aspect-ratio rule;
  - the exact cell count against the budget.
  - Each choice carries the rule that produced it, so the agent can
    explain it, and a user can override one value and re-run.
- **Budget:** when the budget is short, the advisor lowers resolution
  in a stated order, coarsest effect first, and says what each step
  costs.  It never silently breaks the y⁺ target.  The 8× rule is in
  every report.
- **Evidence:** the accuracy classes come from the validated cases in
  `validation/` (observed orders and errors per level, decision 0015).
  The advisor cites the case behind each class.  Classes with no
  validated case are marked as unvalidated.

### Foundations, in order (each one useful without an agent)

- **A. Structured errors** (decision 0019 item 1): `code`, location
  (part, label, interface, field), value, limit, message, hint, on
  `AssemblyError`, `EquipmentError`, reader and builder errors.  Every
  existing message keeps its text.  This touches many files, but no
  geometry, so it can run alongside the H-section tasks.
- **B. Limits and schema:**
  - each constant in `limits.py` gets units and a one-line doc as data;
  - `schema()` is generated from the fitting registry, the
    network-model part classes, and the limits.
- **C. `describe` and `preview` without GMSH.**  Also decision 0019
  item 4.  The preview takes an optional extra (matplotlib), not a core
  dependency.
- **D. `advise`**, with tests against hand-worked cases (laminar
  Poiseuille, a turbulent smooth pipe, a 2:1 duct), and the `hexmesh`
  CLI around A–D.
- **E. The plugin** (`agents/claude-code/` in the repo):
  - skill `hexmesh-network-design`: gather the network from the user's
    words, a sketch or a PCF; write the network model; loop on
    `validate`, `describe` and `preview`; hand off to resolution;
  - skill `hexmesh-resolution`: ask for fluid, flow, wall treatment and
    budget; call `advise`; explain; apply to the network;
  - a short agent guide generated from API.md (decision 0019 item 5).
  - The skills call only the CLI.  The plugin carries no engineering
    logic.

## Consequences

- **DESIGN.md:** a short "Agent tool layer" paragraph under §10
  ("Library or tool?"): `hexmesh.agent` is a leaf over the public API,
  imported by nothing in the library, and its functions are pure except
  `build`.  `tests/test_architecture.py` then covers it.
- **Depends on task 0066** (model operations) for editing the network
  model in place.  Foundation A doesn't.
- **Harder:**
  - every new error needs a code (a test enforces it);
  - the CLI's JSON output becomes a compatibility surface, so it gets a
    `version` field, like `to_dict`;
  - the advisor's correlations need sources in `docs/references.bib`.
- **Future expansions:**
  - **0018 (vascular):** the advisor takes the fluid as data.  It will
    need pulsatile flow (the Womersley number), so the input format
    leaves room for a flow waveform.  No conflict.
  - **0019 (agent SDK):** this is its first stage.  When this decision
    is accepted, 0019 records that its items 1, 3, 4 and 5 are taken
    here.
  - **0021 (flow restrictions):** the advisor treats restrictions as
    parts with their own resolution rule; deferred, but the input
    format allows it.
  - **0030 (simulation suite):** `advise`'s output is a versioned data
    contract, which suits a generator in a study suite.
  - **0035 (multi-core sections):** the advisor works per layer; a
    multi-core section adds layers, not a new interface.

## Verified vs. assumed

- **Verified (2026-11-04):**
  - what exists and what's missing (the list in *Context*): no error
    codes, no schema, only the `hexmesh-study` CLI;
  - the grading solvers;
  - the network model and the builder (task 0065 done).
- **Assumed:**
  - that agents write the network model more reliably than the
    `Assembly` JSON (reasoning; to check with the first skill on a few
    test networks);
  - that the validated cases are enough to calibrate a few accuracy
    classes (laminar and conduction cases exist; turbulent ones, 0049,
    don't yet);
  - that a Claude Code plugin reaches the first users.
