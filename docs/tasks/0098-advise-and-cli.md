# 0098 — `advise` (the resolution advisor) and the `hexmesh` CLI

- **Status:** ready (after 0095 and 0097)
- **Decision:** [0040 — Agents for users](../decisions/0040-user-agents-network-design-and-resolution.md) (foundation D; settled: wall-resolved only at first)
- **Depends on:** 0095 (the schema, limits), 0097 (`describe`).  The
  network-document input waits for decision 0032's stage 2; until then
  the CLI takes `Assembly` descriptions, and PCF files through the
  importer.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Choosing `nang`, `nrad`, `first_cell`, the layout and
`n_layers` takes CFD and hexmesh expertise.  Users from unstructured
meshing are surprised that doubling the counts gives 8× the cells.
Decision 0040 puts that knowledge in a tested function, so an agent can
explain each choice and a user can override one value and re-run.  The
CLI is the one tool surface that the plugin's skills (and a later MCP
server) call.

**Where.**  `hexmesh/agent/advise.py`, `hexmesh/agent/calibration.json`
(generated, committed), `hexmesh/agent/cli.py`; `pyproject.toml` (the
`hexmesh` console script); `docs/references.bib`; tests; `API.md`.

**Do.**
1. **Inputs** (one JSON object, validated, units SI):
   - `fluid`: `{density, viscosity}`, or a named preset from a small
     shipped table (water and air at 20 °C, with their source);
   - `flow`: one bulk velocity or flow rate, or one per open inlet;
   - `wall`: `"wall-resolved"`, with a y⁺ target (default 1).
     `"wall-function"` is rejected with a coded error naming task 0049
     (decision 0040).  Keep the field.
   - `accuracy`: `"coarse"`, `"medium"` or `"fine"` (default
     `"medium"`);
   - `budget`: the maximum cells (optional).
2. **Per section, the rules**, each one recording the rule and its
   inputs in a `reasons` list:
   - **Re and regime:** laminar below 2300, transitional 2300–4000 (a
     warning), turbulent above.  D_h for rectangles.
   - **First cell:**
     - turbulent: from y⁺, using u_τ from the Darcy friction factor (the
       Blasius correlation for Re < 10⁵, Haaland's explicit form
       above, smooth walls).  Cite both in `docs/references.bib`.
     - laminar: there is no y⁺ target; the first cell follows from the
       accuracy class.
   - **Core and angular counts:** from the accuracy class, as cells
     across D (or D_h).  Read from `calibration.json` (step 3).
   - **Ring** (O-H) or **wall grading** (H): `nrad` and `mprg`, or
     `first_cell`, so the growth from the first cell to the core cell
     stays within a growth limit.  Add the limit to `LIMITS` (task
     0095) with its unit and source.  Use `core.grading`'s solvers.
   - **Layout:** H for rectangles and O-H for circles, following the
     library's defaults (task 0087).
   - **Constraints:** `nang` a multiple of what `n_outer` requires, and
     equal counts where fittings join (a switch's counts, a reducer's
     topology).  Enforce them across the network: one count per
     connected group, the largest any member needs.
3. **The calibration**, generated rather than guessed.
   - A script (`hexmesh/agent/_calibrate.py`, not imported at run
     time) reads the committed `validation/*/results.json`.
   - For each validated case it records the cells across D at each
     level, with that level's error in the gated quantity.  From those
     it derives the classes:
     - **coarse:** the error ≤ 1 %;
     - **medium:** ≤ 0.3 %;
     - **fine:** ≤ 0.1 %.
   - It writes `calibration.json`, with each class's source cases and
     their errors.
   - A test checks that the script reproduces the committed file.
   - Classes come per regime and section shape.  Where no validated
     case covers a combination (turbulent flow today), the class is
     marked `"validated": false` and `advise` says so in its output.
     It doesn't invent a number without saying where it came from.
4. **Axial counts** per fitting: from a maximum axial aspect ratio of
   the core cell, with one limit for developed straights and a tighter
   one in bends, junctions and switches.  Both go into `LIMITS`.
   Fittings that set their own counts (wye `n_split`, the switch's
   length rule) keep their rules; `advise` respects them.
5. **The budget.**  When the result exceeds it, lower the resolution in
   a fixed order, recording each step and its cost:
   1. axial counts in straights;
   2. the accuracy class, one step;
   3. axial counts in fittings, down to their minima.
   - Never move the first cell off the y⁺ target.  If the budget still
     isn't met, return the closest result and a coded error saying by
     how much it misses.
   - The 8× rule is stated in every report.
6. **Outputs:**
   - `advise(network_or_description, inputs) → report`: per section
     (Re, regime, first cell, the spec description, reasons), per
     fitting (`n_layers`, reasons), the totals (cells, exact, against
     the budget), the steps the budget took, and the calibration
     classes used.
   - It includes a **resolution table**: section → `PipeSpec`
     description, plus `n_layers` per fitting.
   - `apply(description, table) → description`: the `Assembly`
     description with those specs and counts.  It is then built as
     usual.  Decision 0032's stage 2 makes the same table the builder's
     `spec=` for network models.
7. **The `hexmesh` CLI**, a console script (`hexmesh.agent.cli:main`).
   `hexmesh-study` stays as it is.
   - Subcommands: `schema`, `validate`, `estimate`, `describe`,
     `preview`, `advise`, `apply`, `build`.
   - Inputs: an `Assembly` description file, or a PCF file with
     `--spec` (a resolution table, or a single spec).
   - Output: JSON on stdout with a `version` field, written with
     `newline="\n"` (decision 0039).  Exit code 0 when `ok`, 1 for
     invalid input, 2 for a failure.
   - **`validate` returns `{ok, errors: [...]}`.**  Collect errors where
     task 0094's notes say it's easy, and set `"complete": false` when
     validation stopped at the first error of a kind.
   - Only `build` needs GMSH.  `build` writes the `.msh` with its
     recipe block (decision 0038).

**Accept.**
- **Hand-worked cases**, each against numbers worked out in the test
  with their source:
  - laminar Poiseuille water at Re 100;
  - turbulent smooth pipe air at Re 5·10⁴ (the first cell from y⁺ = 1
    to 2 %);
  - a 2:1 duct.
- **Calibration:** reproducible; its classes cite their cases.  A
  turbulent request reports `"validated": false`.
- **Budget:** a request 4× over the budget reduces in the stated order,
  never moves the first cell, and reports each step.  An impossible
  budget gives the coded error with the shortfall.
- **Round trip:** `advise` → `apply` → build meshes for three examples
  (circle, duct, branched).  The exact cell count equals the meshed
  count.  The meshed first cell equals the advised one to 1e-6
  relative.
- **The CLI:** every subcommand on one example gives valid JSON, the
  same bytes on two runs, and the stated exit codes.  `validate` on a
  description with two independent errors reports both (or
  `"complete": false`).
- The architecture test: `hexmesh.agent` is a leaf; `calibration.json`
  is read with `encoding="utf-8"`.
- Full suite: no new failures.

**Out of scope.**
- Wall functions (wait for task 0049's validation).
- Pulsatile or non-Newtonian flows (decision 0018).  The input format
  leaves room: a flow waveform, and a viscosity model.
- The network-document input (decision 0032 stage 2).
- The plugin (decision 0040, E).
