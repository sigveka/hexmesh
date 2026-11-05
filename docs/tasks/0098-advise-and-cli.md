# 0098 — `advise` (the resolution advisor) and the `hexmesh` CLI

- **Status:** done (2026-11-05; Q5–Q7 for design, none blocking)
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
   - **Geometry units.**  hexmesh doesn't convert lengths: the
     schema's unit is `length` (task 0095).  The advisor needs metres
     for Re and y⁺, so it takes `length_unit` (default `"m"`; also
     `"mm"`).  Every report states the unit it assumed.  A geometry
     whose diameters look like millimetres read as metres (D > 5) gets a
     coded warning.
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
   - **Cost** (design answer to 0097's question, 2026-11-05; the user
     agreed):
     - Inside the budget loop, count cells with `cell_count()` /
       `cell_counts()`, which are pure and fast.  Don't call `describe`
       or `validate()` there: `validate()`'s junction predictions take
       up to 4.3 s on `insulated_network`.
     - Run `validate()` once, on the final result, and return its
       warnings and errors with the report.
     - `describe` gets no `validate=False` switch.
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

## Questions for design

Raised 2026-11-05, before any code was written.  Step 3, the
calibration, can't be written as specified from the committed data.

**What the data has.**
- `results.json` has per-level cells and errors.  It does not have each
  level's counts across D (`nang`, `nrad`, `nang_w`, `nang_h`).
- Those come from the run scripts: `BASE × factor`
  (`validation/poiseuille/run.py:89–108`, `rect_duct/run.py:87–212`).
- The flow cases that fit (laminar, steady, straight):
  - `poiseuille` (circle, O-H, k = 1, 2, 4);
  - `rect_duct` (H, graded H, O-H and a Cartesian control; aspect
    ratios 1, 2 and 4; k = 1, 2, 4).

**The measured errors against the classes** (|error|, at k = 1, 2, 4):

| case, quantity | k = 1 | k = 2 | k = 4 | observed order |
|---|---|---|---|---|
| poiseuille Δp | 0.451 % | 0.207 % | 0.104 % | 0.99 |
| poiseuille u_max | 0.935 % | 0.254 % | 0.073 % | 1.80 |
| rect H a/b 1, f·Re | 3.92 % | 1.02 % | 0.258 % | ≈ 2 |
| rect H a/b 2, f·Re | 3.09 % | 0.798 % | 0.202 % | ≈ 2 |
| rect H a/b 4, f·Re | 2.65 % | 0.681 % | 0.171 % | ≈ 2 |
| rect H a/b 1, u_c | 2.62 % | 0.637 % | 0.110 % | |
| rect graded H a/b 2, f·Re | 3.33 % | 0.867 % | 0.218 % | |

- **"fine" (≤ 0.1 %) is reached by no measured level** on either
  pressure-drop quantity.  Only u_max (circle) and u_c (a/b 2 and 4)
  reach it.
- **"coarse" (≤ 1 %) isn't reached at k = 1 by any H duct quantity**,
  and on f·Re at a/b 1 not even at k = 2 (1.02 %).
- The O-H duct levels don't converge monotonically (f·Re a/b 1: 2.6,
  2.0, 1.2 %), which is why they aren't gated (decision 0015,
  amendment 2).

**Q1. Which quantity sets a class?**  The gated quantity per case
(poiseuille Δp and u_max; rect_duct f·Re and u_c), or the worse of
the two?
- Proposal: the worse of the two pressure and velocity quantities,
  since they are the ones gated.
- With that rule, poiseuille is coarse at k = 2 and medium at k = 4,
  and has no fine.

**Q2. May the script go past the finest level?**
- Option (a): extrapolate along the observed order.  With order 1, Δp
  reaches 0.1 % at k ≈ 4.2.  With order 2, f·Re a/b 1 reaches 0.1 % at
  k ≈ 6.4.
- Option (b): a class no measured level reaches is
  `"validated": false`, with the nearest measured level and its error.
- Proposal: (b) for this task.  (a) would be a number no case
  measured.  A finer validation level (k = 8) is a separate task with
  OpenFOAM runs.

**Q3. Which rect_duct series calibrates the H rectangle?**
- `h_*`, the accepted hexmesh H result (task 0084), and the library
  default since task 0087.  It is identical to `cart_*`.
- `hg_*` is graded, a/b 2 only.
- Proposal: `h_*` at every aspect ratio, giving one class each for a/b
  1, 2 and 4.  `advise` takes the nearest aspect ratio, or the worst of
  the two around it.
- O-H rectangles are not calibrated: `advise` gives the H layout for
  rectangles anyway (step 2, "Layout").

**Q4. Reading the counts from the run scripts.**
- Option (a): `_calibrate.py` imports `validation/<case>/run.py` and
  calls each level's `assembly(factor)` to read the counts.  This is
  pure Python, with no OpenFOAM.
- Option (b): the run scripts write `nang`/`nrad`/`nang_w`/`nang_h`
  into each level of `results.json`.  The committed files are
  backfilled without re-running, since the meshes are deterministic.
- Proposal: (b).  It keeps `results.json` the single source the task
  names, and the calibration then reads data only.  It touches
  `validation/*/run.py` and two `results.json` files, so I'm asking
  first.

I'm stopping 0098 here.  The rest of the task (steps 1, 2 and 4–7, and
the CLI) doesn't depend on these answers in structure, but the core
counts and the classes' `validated` flags do, so I haven't started it.

### Answers (design session, 2026-11-05; the user: "yes, your answers are fine")

- **Q1:** the worse of the two gated quantities (pressure and velocity)
  sets the class.  The report still gives each quantity's own expected
  error at the chosen counts.
- **Q2: extrapolate, within limits, and label it.**
  - Extrapolate along the observed order, only from a series whose
    0089 status is `converging`.  Go at most 2× in k past the finest
    measured level (k ≤ 8 today).
  - Such a class gets `"validated": false` and
    `"basis": "extrapolated at order p from k = 4"`, with the real p
    and k.  It also gives the nearest measured level and its error.
  - Beyond 2×, the class is reported as out of range, with no counts.
    `advise` falls back to the best class in range, and says so.
  - Today that gives poiseuille fine at k ≈ 4.2, and rect H a/b 1 fine
    at k ≈ 6.4.  Both are in range.
- **Q3:** the uniform `h_*` series at a/b 1, 2 and 4.
  - Between measured aspect ratios, use the worse of the two
    neighbours.  Above 4, use a/b 4's class with `"validated": false`.
  - No O-H rectangle calibration.
  - **Laminar flow** gets a uniform H core (no wall grading), and for
    circles the plain O-H ring grading of the calibrated runs, so the
    advice matches what was measured.  Wall grading only comes in for
    turbulent wall-resolved flow, which is unvalidated anyway.
  - The graded `hg_*` a/b 2 series measured about 8 % more error.
    Record it in the reasons as a check, not as a class.
- **Q4: (b).**
  - The run scripts write `nang`, `nrad`, `nang_w` and `nang_h` into
    each level of `results.json`.  The two committed files are
    backfilled without a rerun.
  - A pure-Python test checks that each stored level's counts equal the
    run script's `assembly(factor)`.
  - If `results.json` has a schema, extend it, backward-compatible.
- **Also, in every `advise` report, coded, and in API.md:**
  "calibrated on developed flow in straight runs; bends, junctions and
  switches may be less accurate at the same counts".

Status set back to ready.  The coding session was on 0076 (the user's
"start") when the answers came.

### Questions raised while coding (2026-11-05; none blocks this task)

- **Q5. PCF input to the CLI.**
  - Step 7 asks for PCF files with `--spec`.  That needs
    `hexmesh.agent` to import `hexmesh.io.readers`.
  - `tests/test_architecture.py` forbids anything importing
    `io.readers`.  Adding agent → io.readers to `ALLOWED_EDGES` would
    be a new deviation, which CLAUDE.md rules out.
  - So the CLI takes `Assembly` descriptions only.  A `.pcf` gets a
    coded error (`cli_input_unreadable`) that points at task 0066, which
    moves the readers into `interchange.importers`.
  - Proposal: add the PCF input to 0066's acceptance, or as a follow-up
    once 0066 is done.
- **Q6. Classes between measured levels are interpolated, and kept
  `"validated": true`.**
  - The answers cover extrapolation past the finest level only.  Using
    measured levels alone would put rect a/b 1's **coarse** class at
    k = 4: k = 2 misses 1 % by 0.02 % (f·Re 1.018 %).  That costs 8×
    the cells for 0.02 %.
  - So between two measured levels the error follows each quantity's
    order between them, and the class's `basis` says "interpolated
    between measured k = 2 and 4".
  - Please confirm, or say if interpolated classes should be
    `"validated": false` too.
- **Q7. The axial aspect limits are my choice:**
  - `MAX_AXIAL_ASPECT_STRAIGHT` 6: the calibrated runs had 5–7.5;
  - `MAX_AXIAL_ASPECT_FITTING` 2: judgement, no case;
  - `MAX_AXIAL_ASPECT_BUDGET` 12;
  - `MAX_WALL_GROWTH` 1.2: the ERCOFTAC guidelines.
  All are `info` limits.  A design decision on them (or a bend
  validation case) would replace the judgement.

## Agent notes

- **One density per assembly.**
  - Density is shared by every section (a reducer changes radii only).
    So the resolution table is one `density` (`nang`, `nrad`, `nang_w`,
    `nang_h`, `mprg`, `wall_bump`) and per-fitting axial counts.
  - The design's "one count per connected group" is the whole assembly:
    the largest count any section needs.
- **Tied counts.**  `nang = nang_w = nang_h` where:
  - a Transition joins a circle to a rectangle;
  - a layer stack has a rectangle and shells (the spec's own rule).
  This makes the rectangles' short side as fine as the long side, so
  those examples get many cells: `duct_transition`, `lagged_duct` and
  the hvac examples (below).
- **Even `nang` for circles.**  The first cell is defined mid-arc
  (`core_wall_span`), and an odd `nang` has no node there.  The
  calibrated runs used 6, 12 and 24.
- **The flow split** at junctions is by downstream open area, a
  stand-in for a flow solve; the report says so in its reasons.
  - An assembly has one inlet, so "one flow per open inlet" waits for
    network models (decision 0032 stage 2).
- **The fluid is the core layer.**  An example whose core is solid
  (`layer_outlines`, copper) gets advice for flow in the copper; the
  reasons name the layer.
- **Rectangles in the O-H layout** are `advice_layout_unsupported`: no
  calibration, and the default is H.
- **Turbulent grading:**
  - circles: `mprg` from `progression_for_first_cell`, with `nrad`
    raised until the growth ≤ `MAX_WALL_GROWTH`.  The section with the
    smallest first cell against its ring sets the shared `mprg`; the
    others' first cells and y⁺ are reported.
  - H rectangles: `wall_bump`, with both counts raised ×1.25 until the
    bump's largest neighbour ratio ≤ the limit.
- **Axial counts:**
  - a tee's `n_run` and `n_branch` from `run_length` and
    `branch_length`, with `n_turn` kept;
  - MiterBend from 2·`n_cuts` legs;
  - wye and switch keep their rules;
  - minima from each field's `minimum` and `layers_ok`.
  - `apply` scales a straight's `stack_changes` indices with its
    `n_layers`, and resets duct taps' `n_wall`, `nrad` and `mprg` to
    None, so they are derived again.
- **Notes and errors** are `HexmeshWarning(...).to_dict()` and
  `AdviceError`.  The code-literal rule in `tests/test_architecture.py`
  counts a code as used only where a coded class is built with it.
- **`calibration.json` scope string:** "calibrated on developed laminar
  flow in straight runs; …": I added "laminar" to the design's wording.
- **Validation results:** `validation/tools/results.py` has `counts()`.
  - Both run scripts store the counts per level.
  - The two committed files were backfilled by a one-off script, which
    rebuilt each level's assembly and checked its cell count against the
    stored one: all 24 matched.
  - `results.schema.json` gains four optional properties.
  - `tests/test_validation_counts.py` is the drift test.

## Outcome

**Files.**
- New:
  - `hexmesh/agent/advise.py`: `advise`, `apply`, `AdviceError`,
    `friction_factor`, `first_cell_for_y_plus`;
  - `hexmesh/agent/_calibrate.py` (the generator, not imported at run
    time);
  - `hexmesh/agent/calibration.json`;
  - `hexmesh/agent/cli.py`.
- Changed:
  - `hexmesh/agent/__init__.py`;
  - `hexmesh/assembly/limits.py`: 4 limits;
  - `hexmesh/errors.py`: 11 codes;
  - `pyproject.toml`: the `hexmesh` script, and package data for the
    calibration;
  - `validation/tools/results.py`, both run scripts, both
    `results.json`, `results.schema.json`;
  - `docs/references.bib`: blasius_1913, haaland_1983, white_2011,
    casey_and_wintergerste_2000;
  - `API.md`: the section, codes and limits; `CHANGELOG.md`.
- Tests:
  - `tests/test_agent_advise.py` (30 tests);
  - `tests/test_validation_counts.py` (2);
  - the architecture whitelist gains `hexmesh.core.grading`.

**The calibration** (cells across D or D_h; k is the validation level):

| series | coarse ≤ 1 % | medium ≤ 0.3 % | fine ≤ 0.1 % |
|---|---|---|---|
| circle (poiseuille) | 12, measured k = 1 | 22.0, interpolated | 50.1, extrapolated at order 0.99 (Δp), not validated |
| rect a/b 1 | 20.2, interpolated | 37.1, interpolated | 65.3, extrapolated at order 1.93, not validated |
| rect a/b 2 | 21.4, interpolated | 39.3, interpolated | 68.9, extrapolated at order 1.94, not validated |
| rect a/b 4 | 23.7, interpolated | 43.5, interpolated | 75.9, extrapolated at order 1.95, not validated |

- The graded H check (`hg_ar2`) is 7.7–8.5 % worse than uniform at
  each level, matching the design's "about 8 %".
- **Rectangles cost far more than circles at the same class.**  Medium
  is 30 × 60 per section at a/b 2, against 12² + 4·12·6 = 432 cells for
  a circle.  This is the data: the H duct's f·Re error is 3–4 % at
  k = 1, against 0.9 % for poiseuille.

**Examples** (water at 2 mm/s, medium):
- All 28 advise, apply and validate without error, in 0.02–3.4 s each.
  `insulated_transition` takes 3.4 s, its `validate()` run once.
- Circle networks: 22k–117k cells.
- `rect_duct`: 270k.
- Tied stacks: `lagged_duct` 0.9M, `duct_transition` 2.6M,
  `hvac_supply` 2.7M, `hvac_branched` 10M, `cooling_channels` 20M.
  Their long runs at 6 aspect, with counts tied to the long side, are
  what the budget is for.

**Round trip** (`test_round_trip_meshes_as_advised`): three examples
mesh with the advised exact cell count, and the meshed wall cell of
fitting 0 equals the advised first cell to 1e-6:
- `graded_bend`, turbulent water at 0.5 m/s, y⁺ 1;
- `rect_duct`, coarse;
- `distribution_tree`, coarse.

**Full suite:** 3384 passed, 15 skipped (3352 before, plus 32 new).  The preview timing gate (< 2 s, task 0097) missed once at 2.0–2.3 s while other tests ran in parallel, and passed alone and in the full suite.

**Proposed follow-ups.**
- The PCF input to the CLI, after task 0066 (Q5).
- A bend or tee validation case, so that the fittings' axial limit and
  the scope caveat rest on data (Q7).
- Turbulent validation (a smooth pipe at Re ~10⁴–10⁵ with y⁺ 1), so
  `"validated": false` can go from the wall grading.
