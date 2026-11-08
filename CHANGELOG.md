# Changes

## Unreleased

**No validation result went through a hex that gmshToFoam turned inside
out** (task 0108).
- The audit rebuilt every level of every case (199 meshes and side
  meshes, 128 distinct) and counted the hexes gmshToFoam's orientation
  test would flip.  Four MMS wye levels would be flipped (32 hexes), and
  all four were converted with `-keepOrientation`.  Everything else
  counts zero, and every mesh's worst scaled Jacobian is positive.
  `validation/tools/orientation_audit.py`, results in its JSON.
- **`hexmesh.study.openfoam`:** new `would_invert(msh)`, which counts
  those hexes on a written `.msh` without gmsh, and `foam_would_invert`
  and `msh_hexes`.  OpenFOAM v1912 and v2406 run the same test.
- **The validation drivers** pass `keep_orientation=True` whenever the
  worst scaled Jacobian is positive.  Each `case.json` says so, under
  `toolchain.conversion`.  `convert()`'s default is unchanged.  The
  GUIDE's OpenFOAM section says when to pass it.
- **A study's case stage does the same.**  It converts with
  `-keepOrientation` when the variant's worst scaled Jacobian is
  positive.  Otherwise it converts with the test on and warns
  `mesh_sj_not_positive`: the mesh has an inverted corner.

**The manufactured-solution study is accepted** (task 0074; V1,
`validation/mms/`).
- **Verified:** the straight, bend, spline, stack change and
  rectangular duct converge at the straight's order, and the wyes outside
  their split region.  The other fittings are reported.
- **The miter's first order is the scheme on its kinked grid lines:**
  least-squares gradients lift it to 1.67, the straight's 1.83 under the
  same scheme.
- **The reducer, transition and tees stay near first order with either
  gradient.**  Their wall faces keep a non-orthogonality that refinement
  doesn't shrink (reducer median 21–24°), and `fixedValue` doesn't
  correct for it.  Their geometry tightens (reducer, second order) or is
  exact (transition).
- **The duct taps' cell aspect doesn't grow under refinement.**
  `laplacianFoam`'s stall beyond k = 2 has a stopgap note in
  `docs/integrations/openfoam.md`.
- `study.openfoam.check_mesh` also returns `max_aspect_ratio`.

**The README's numbers are generated** (task 0078).

- `docs/gallery/build.py` rewrites two marked blocks of `README.md` on
  every run, `--markdown-only` included, and nothing else in the file:
  - the `insulated_tee` metrics, from `metrics.json`;
  - the validation table, one row per `case.json`.
- **`case.json` gains an optional `headline`**: the result in one line,
  with its numbers from RESULTS.md.  All 12 cases have one.
- **The validation table had drifted:**
  - it listed `rect_duct`, `square_bend` and `turbulent_pipe` as planned
    (they are accepted), and left out `mms` and `helical_pipe` (in
    progress);
  - the stenosis line quoted an older reattachment length (11.12 D); the
    accepted result is 10.97 D against the database's 11.03 D (−0.5 %);
  - the heated rod and Womersley lines quoted their gates (0.1 %, 1 %),
    not the results (0.01 %, 0.31 %).
- **A cut-away hero image** (`docs/gallery/img/hero.png`,
  `build.py --hero`): `insulated_network` with a quarter removed, so the
  fluid core, the steel and the insulation show through the tee and the
  wye.
- **New tests** (`tests/test_readme.py`):
  - the README's first code block builds the gallery's `insulated_tee`,
    with the cell count the metrics table quotes; a slow variant runs it
    as written, meshing included;
  - every relative link and image in `README.md`, `docs/WHY.md` and
    `docs/GUIDE.md` resolves, anchors included;
  - `CITATION.cff`'s version matches `pyproject.toml`'s.

**The light commands load neither gmsh nor scipy** (decision 0040,
amendment 2026-11-07; task 0107).

- gmsh is imported on first use, through `hexmesh._gmsh`; `Session`
  imports it when it starts.  `scipy.interpolate` is imported only where a
  spline edge is meshed.
- `import hexmesh.agent` takes 0.27 s, down from 0.52 s.  `hexmesh
  validate` on a small network takes 0.37 s, down from 0.64 s.
- Where gmsh can't load, `import hexmesh` and every command but `build`
  still work.  `build` and `Session` raise `GmshUnavailable` (an
  `ImportError`, code `gmsh_unavailable`); its hint gives the install
  command and, on Linux, the system libraries.
- Meshes are unchanged: all 28 gallery examples are byte-identical.

**Every user-facing error coded, internal errors marked** (decision 0040;
task 0106).

- The last 21 user-reachable bare `ValueError`, `TypeError`,
  `RuntimeError` and `NotImplementedError` raises now carry codes.  Each
  keeps its built-in class, so existing `except` clauses still work:
  - `SpecUsageError` (a `RuntimeError`) for `PipeSpec.core()` twice,
    `shell()` before `core()`, and a spec with no core;
  - `ReaderFileNotFound` (a `FileNotFoundError`) for a missing PCF file;
  - `study.openfoam.FoamCommandFailed` (a `RuntimeError`) for a failed
    OpenFOAM command;
  - `agent_input_type`, `fitting_declares_no_strategies`,
    `quality_mode_unknown` and `openfoam_value_uniform`;
  - `check_supported` raises `section_not_supported` itself.
- **`InternalError`** (code `internal_invariant`, a `RuntimeError`) marks
  a failed internal check: a bug in hexmesh, not in the input.  Its
  message asks for a report.  21 former bare raises use it.
- **Three rejections fixed** (found by the manifest's probe, task 0102):
  - a `Switch` on a circle now raises `switch_needs_rectangle`; it used
    to raise an `AttributeError`;
  - a duct tap on a shelled H rectangle now raises
    `junction_shells_unsupported`; it used to raise the internal Switch's
    `switch_changes_shells`;
  - an unsupported section (`n_outer = 8`) now raises
    `section_not_supported` in `add()`, before a `Tee` or `Wye` builds its
    layout.
- The support matrix now shows that a `Switch` on a shelled rectangle is
  supported; the probe had given it a shell-less outlet.
- **Hints:** 58 of 443 coded raises had one; now 134 of 464 do.  They are
  in spec and section errors, the fittings' fit checks (each with the
  length, angle, count or `rot` to use), the PCF and network builder, and
  the CLI.  For example, `nang_not_divisible` suggests "nang=4 or nang=6
  (a multiple of 2)".

**Laterals: `Tee(angle=…)`** (decision 0031 stage 1; task 0060).

- `angle` (degrees, default 90) leans the branch from the run's
  downstream direction: 45 is a 45° lateral.  The saddle is the exact
  cylinder–cylinder intersection, shells included; walls stay on their
  cylinders.  `angle=90` meshes identically to before.
- The room checks are measured on the acute side: `run_length` must
  exceed the hole's reach downstream, `branch_length` the turning
  station's distance along the leaning axis.
- The predicted-quality tiers are unchanged and set the range: a 45°
  lateral needs r/R ≥ 0.50, 35° needs 0.875, and 30° is rejected at every
  ratio.  Laterals below about 57° always warn.  A lateral's message
  names the smallest r/R that reaches the tier at its angle, and
  `run_length=None` falls back to the shortest run passing the minimum
  when none reaches the warning tier.
- **New limit `TEE_MAX_RATIO` (0.95).**  A pipe tee with r/R above it is
  rejected (`tee_ratio_above_max`), and r = R is `equal_tee_unsupported`.
  Up to 0.95 the meshed corner SJ is within 0.025 of the prediction; at
  0.99 it was 0.30 against 0.57.
- New codes `tee_angle_out_of_range` and `angle_on_duct_tap`.  Saved
  tees now write `"angle"`.

**Structured errors** (decision 0040; task 0094).

- Every error that bad input can cause is now a `hexmesh.HexmeshError`.
  It is still a `ValueError`, and it carries `code`, `where`, `value`,
  `limit` and `hint`.  `err.to_dict()` gives them as JSON data.
- The layers raise their own subclasses: `SpecError`, `AssemblyError`,
  `EquipmentError`, `LayoutError`, `ReaderError` and `StudyError`.
  Former `TypeError`s stay `TypeError`s (`SpecTypeError`,
  `AssemblyTypeError`, `StudyTypeError`).
- Warnings are `hexmesh.HexmeshWarning` (a `UserWarning`), with the same
  fields.
- Messages are unchanged.  The codes are listed in
  [API.md](API.md#errors-hexmesherrors).

**A JSON Schema of the saved description, and limits as data**
(decision 0040; task 0095).

- `hexmesh.agent.schema()` returns a JSON Schema (draft 2020-12) of
  `Assembly.to_dict()`.  `python3 -m hexmesh.agent.schema` prints it.
  It is generated from the registries, and every field has a type,
  unit (`x-unit`), description, range and default.
- `hexmesh.assembly.limits.LIMITS` holds every limit as
  `Limit(value, unit, kind, doc)`; the module constants are unchanged.
  The limits inline elsewhere moved into it: the miter cuts, the sweep
  caps, the wye angle range and the venturi divergent range.
- Four errors now name their limit in `limit` instead of giving its
  value: an unresolvable `n_layers`, the wye angle, and the cosine and
  venturi profile ranges.  Messages are unchanged.

**`describe` and `preview`** (decision 0040; task 0097).

- `hexmesh.agent.describe(x)` summarises an `Assembly`, its saved
  description or a `NetworkModel` as JSON data, without GMSH:
  - for an assembly: fittings, open ends with their patch names,
    junction angles, totals, and `validate()`'s warnings and error;
  - for a model: parts, connections, and the parts the builder would
    reject.
- `hexmesh.agent.preview(x, path)` draws it to a deterministic PNG, in
  three orthographic views and an isometric one.  It needs the new
  `preview` extra (matplotlib).

**Resolution advice and the `hexmesh` command** (decision 0040; task 0098).

- `hexmesh.agent.advise(asm, inputs)` chooses the counts from the flow:
  the fluid, a velocity or flow rate, an accuracy class, and a budget.
  It explains each choice and returns a resolution table.
  `apply(description, table)` writes the table into a description.
  - The counts come from `hexmesh/agent/calibration.json`, generated
    from the validation results.  A class no case measured says
    `"validated": false`.
  - Turbulent flow is graded to y⁺; it isn't validated yet.
- The `hexmesh` command: `schema`, `validate`, `estimate`, `describe`,
  `preview`, `advise`, `apply` and `build`.  It writes JSON with exit
  codes 0, 1 and 2.
- Validation results now record each level's `nang`, `nrad`, `nang_w`
  and `nang_h`.

**`hexmesh manifest`: one account of the suite for agents** (decision 0040;
task 0102).

- `hexmesh.agent.manifest()` and `hexmesh manifest`: the commands (from
  the CLI's parser), the workflow, a probed support matrix per fitting
  and section, `LIMITS`, `CODES`, the advisor's classes and their basis,
  the validation status per feature, and the conventions.
- The support matrix and the validation summary are package data,
  regenerated by `python3 -m hexmesh.agent._probe` and `python3 -m
  validation.tools.summary`; tests fail when either is stale.
- `hexmesh` is the console script a `pip install` creates; `python3 -m
  hexmesh.agent.cli` runs the same command without one.

**Cut, join and merge network models** (decision 0032; task 0066).

- `NetworkModel.select`, `cut`, `cut_at`, `join` and
  `NetworkModel.merge`: break a network at a valve, build each side, and
  join it back.  Or merge two files and join them at their shared end.
- Every cut, join and merge is logged in `model.log`, after the
  importer's entry.  `replay` re-applies the log to a fresh import, and
  `undo` reverts the last operation.
- The builder leaves cut ports as open ends.  It names an end at a cut,
  or at a selection's boundary, from its port.  Other names are
  unchanged.
- The readers moved to `hexmesh.interchange.importers`, and
  `hexmesh.interchange` exports `read_pcf` and `read_bathymetry`.
  `hexmesh.io.readers` still re-exports them.
- `hexmesh validate | estimate | describe | preview | advise | build`
  read a `.pcf` with `--spec SPEC.json`.

**Shells around a rectangle keep unequal counts** (decision 0041,
option B; task 0101).

- A stack of rectangular outlines no longer needs `nang_w = nang_h`.
  Every outline takes the core's `(nang_w, nang_h)`, so a 2:1 duct with
  a wall and lagging can be 8 × 4 throughout.
- A stack with a circle and a rectangle, a circle ↔ rectangle
  `Transition`, a round duct tap and `BundleSpec` keep equal counts per
  side: a circle carries one count.
- `advise` no longer ties a stack of rectangles, and names the fitting
  or layer that ties the counts.  `lagged_duct` at "medium" goes from
  936 000 to 526 500 cells.
- Nothing that built before changes.

**Second-order export** (decision 0034; task 0076).

- `Assembly.mesh(order=2)` (and `write(..., order=2)`) writes Hex27, or
  Hex20 with `incomplete=True`, with the high-order nodes on the true
  walls:
  - junction walls are re-projected;
  - bends are placed exactly on their arcs.
  Volume and wall area converge at order 4, against 2 for linear.
- An inverted second-order hex is an error naming the fitting.
- A `Wye` is rejected at order 2.
- `write_openfoam(order=2)` is refused, because `gmshToFoam` reads
  first-order elements only.

## 0.4.0 (2026-11-05)

**`convert(..., keep_orientation=True)`** (task 0074).

- `hexmesh.study.openfoam.convert` can pass `-keepOrientation` to
  `gmshToFoam`.  Without it, gmshToFoam (v2406) turned 6 valid hexes of
  a refined 90° wye inside out, and `checkMesh` failed.  It is off by
  default.

**Breaking: rectangular cores default to the H face** (decision 0036;
task 0087).

- A rectangular core is now one Cartesian patch (`layout="h"`), its
  walls graded by `first_cell=` or `mprg=` (the second cell from each
  wall over the first).  Circles keep the O-H face.
- Why: on the O-H rectangle the friction factor does not converge with
  refinement, and a Cartesian grid of the same cells converges at second
  order ([RESEARCH §7.11](docs/RESEARCH.md)).
- `nrad=` on a rectangular core without `layout="oh"` is now an error
  that names both fixes.
- Saved descriptions (`to_dict`, `Assembly.save`, study files) written
  before 0.4.0 have no `layout` key.  They still load as O-H and
  reproduce their meshes exactly.

**Migration.**  For each rectangular core with `nrad=`, either:

    .core("air", half_w=0.1, half_h=0.05, first_cell=0.001)     # H: grade the walls
    .core("air", half_w=0.1, half_h=0.05, nrad=3, layout="oh")  # keep the O-H face

Also in this release: H ports on duct taps and `Transition`s, shells
around an H core, the `Switch` length rule, and meshed non-orthogonality
in `mesh()`'s safety net (tasks 0084–0086).
