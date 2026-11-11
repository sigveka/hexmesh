# Changes

## Unreleased

**`n_outer = 8` is the 4-corner mesh, cut** (decision 0005; task 0088).
- The face is the `n_outer = 4` face cut along its middle grid lines:
  four core blocks around the centre, two per ring patch.  Its nodes and
  cells are the 4-corner mesh's (1e-10 R in faces and one-layer sweeps;
  see the task for multi-layer slabs and second order).  Every sweep
  takes it, with circular and O-H rectangular layers; junctions and the
  H layout still need 4.  `n_outer = 12` is rejected
  (`section_not_supported`).
- `build_oh_circle8` (one 8-sided centre patch, never meshable) is gone;
  `sections.build_oh_split` builds the face.
- `Assembly.corrections` has a `sub_partition` entry: the nodes set to
  the 4-corner mesh's (gmsh's own fill of a sub-patch misses it by up to
  ~1e-4 R).
- The section period is 90° for a circle at every `n_outer` (decision
  0010), in `PipeSpec.period` and the signature; `first_cell=` and
  rectangle stacks take `n_outer = 8`.
- `n_outer = 4` meshes are unchanged (every example, byte for byte).

**A tee branch with its own wall cell** (decision 0028; task 0131).
- `Tee(branch_first_cell=…)` or `branch_mprg=`: the branch port's core
  grading, blended from the main's along the branch run.  Stored as
  `branch_mprg`; `refined(k)` nests it.  Pipe tees with a smaller branch
  only (`branch_grading_unsupported` otherwise).  Without it, meshes are
  unchanged.
- `Tee.strategies` is per port pair: the branch pair also allows
  grading-only class 2.
- GUIDE: the grading-only `Reducer` after a branch, and the fittings
  table's `Reducer` row (grading may change, since task 0027).

**Two errors say where and what to do** (decision 0042; task 0129).
- A `SplinePipe` that bends tighter than the pipe names the place: arc
  length, point, and the segment `points[i]`–`points[i+1]`; `where` is
  `{"field": "points", "index": i}` (was `{"field": "radius"}`, which a
  spline doesn't have), or `end_tangent` when that causes it.  The hint
  names the point to move.  Bends keep their wording.
- `toward_off_allowed`: the hint gives a working straight,
  `Straight(L, n_layers=n)`, instead of `Straight(…, twist=X)`.

**Length units** (decision 0047; task 0128).
- `hexmesh.units`: `m`, `cm`, `mm`, `um`, `inch`, `ft`, plain floats in
  metres (`radius=13.25 * mm`).  Not re-exported from `hexmesh`.  The
  PCF reader, the interchange tolerance floor and the agent's advice take
  their constants from it; meshes unchanged.
- Docs and the agent's `describe` now say lengths are metres: `units`
  is `{"length": "m", …}` (was `"as given"`), as hexmesh isn't
  scale-free (GUIDE, *Current limitations*).

**One density per network, said up front** (decision 0003 note
2026-11-10; task 0132).
- README, GUIDE ("One density per network", with a worked example) and
  API.md state that `nang` and each layer's `nrad` are the same in every
  pipe of a connected network, what that costs, and what to do instead.
- A count change across a fitting (`switch_class_not_declared`, class 2
  beyond grading, or class 3) no longer names "a density switch" or "a
  topology switch (decision 0003)", which don't exist: the message says
  no fitting makes the change, and the error now carries a hint.  Code,
  `where` and `value` unchanged.

**Equal tees** (decision 0043 amendment 2026-11-10; task 0122).
- `Tee(branch_radius=R)`, the branch as wide as the main, builds: the
  oriented junction cube (Bošnjak et al. 2024), every block a transfinite
  hex.  Square and centred only: an equal lateral is
  `equal_lateral_angle_below_min` (`limits.EQUAL_LATERAL_ANGLE_MIN`, 90°),
  an offset `tee_offset_out_of_range`.  `run_length=None` resolves the
  length the cube needs (1.27 R bare); shorter is `run_length_too_short`.
- Meshed min corner SJ 0.511 at nang 8, 0.305 at 48; checkMesh v2406
  passes.  The crease where branch and main meet misses the wall by
  3.7 % R at nang 8 (1.1 % at 32).  First order only:
  `mesh(order=2)` rejects it, as it does the wye.
- `equal_tee_unsupported` is gone: PCF equal tees are read as `Tee`, and
  the README's example error is now an insulated equal tee too short for
  the junction.
- New example `fittings.equal_tee`.
- A PCF junction too short for its layout (`run_length_too_short`,
  `branch_length_too_short`) now hints in the file's terms (tasks 0122,
  0125): which of the component's points to move (its END-POINTs, its
  BRANCH1-POINT, a Y piece's BRANCH1- and BRANCH2-POINTs), how far they
  are from its CENTRE-POINT and how far the junction needs them, or to
  thin its insulation; not `run_length=None`.
- A reduced tee's predicted-quality hint is in plain words (task 0125):
  "a run of X m or more each side of the centre reaches it (now Y)" and
  "no run length reaches it", so a PCF user can act on it too.  Codes
  unchanged.
- Above `limits.EQUAL_TEE_NANG_CLEAN` (48) an equal tee warns in
  `validate()`, before gmsh (task 0127): its meshed SJ falls with nang
  (0.293 at 64, measured; unmeasured above 64), which the predicted SJ
  doesn't see.

**What hexmesh changes in gmsh's mesh** (decision 0046 rule 5; task 0123).
- `Assembly.corrections`, after `mesh()`: for every fitting, the wall
  nodes projection moved and the second-order wall nodes placed (count,
  largest move absolute, in wall radii and in edge lengths), or "none",
  and the elements hexmesh wrote (0 today).  In `QualityReport.corrections`
  and its printed table, and in the CLI's `build` result.
- Notices: `Assembly.notices` (`HexmeshNotice`, not a warning) from
  `validate()`, and `notices` in the CLI's `validate` result.  The one
  notice, `elements_written_by_hexmesh`, waits for task 0124's opt-in.
- `limits.CORRECTION_MIN_MOVE` (1e-9 wall radii): the smallest move the
  record counts.
- `second_order_arc_nodes` (task 0130; decision 0046 amendment
  2026-11-10): a bend's high-order nodes placed on its arcs at
  `order=2`, in the same form.  A bend at order 2 no longer says "none".
- Second order is verified with FEniCSx (task 0077) on straights, bends
  and tees (Hex27); API.md and GUIDE say so, and what it isn't verified
  for.

**Volunteer runs** (decision 0044; task 0119).
- `python3 -m validation.volunteer`: `list`, `prepare`, `run`, `collect`
  and `check`, so someone with cluster time can run a held validation
  level and send back one `.contrib.json`, checked mechanically (schema,
  mesh hash, the level's own numbers, the stored level) and merged with
  the contributor's credit. `validation/VOLUNTEERS.md` is generated from
  the cards; the helical pipe's Re 3000, nang 24 level is the first.
- OpenFOAM runners: `path` (OpenFOAM already loaded) and
  `apptainer:<image>` (unverified until a first run), and the `native`
  runner's bashrc from `HEXMESH_OPENFOAM_RC`. `require_version` refuses
  another OpenFOAM version (`openfoam_version_mismatch`).

**Shoe taps on ducts** (decision 0031 stage 4; task 0063).
- `Tee(angle=…)` on a rectangular main: the branch leans downstream, its
  hole the branch section cut by the face (stretched by 1/sin α; an
  exact ellipse for a round branch). Rectangular, round and full-width
  taps, either face, O-H and H mains. Walls stay exact, with no node
  projection. `angle=90` meshes exactly as before.
- The room checks measure the hole's acute end, with hints;
  `run_length=None` resolves it. Below about 45° the quality tiers warn,
  naming a larger angle.
- `angle_on_duct_tap` is retired; an angle outside (0, 90] raises
  `tee_angle_out_of_range`, as on pipes.

**Twisted straights, and junctions at any roll** (decision 0031 stage 3;
task 0062).
- `Straight(twist=…)` rotates the section about the axis, linearly from
  inlet to outlet, with a station per axial layer: every node is on an
  exact station face. Shells, ducts, grading and `stack_changes` work.
  `twist=0` meshes exactly as before.
- Limits (proposed to design): the roll per axial layer warns above
  `STRAIGHT_TWIST_WARN` (15°) and raises above `STRAIGHT_TWIST_MAX` (30°,
  `twist_per_layer_above_maximum`), naming the `n_layers` that passes.
  The wall shear (twist per length) is predicted before GMSH
  (`section_quality.twist_quality`) and goes through the usual SJ and
  non-orthogonality tiers, naming the length or twist that passes.
- A `Tee` or `Wye` with `toward=` between the period's rolls now twists
  the untwisted `Straight` before it by the rest, and the stored network
  holds both numbers. Otherwise `add()` names the twist needed and where.
- PCF: a set-on at an odd roll twists its host's upstream piece.

**Offset taps** (decision 0031 stage 2; task 0061).
- `Tee(offset=…)` moves the branch axis off the main axis, along the
  main's right after the roll, for tees and laterals. The saddle is the
  exact intersection of the offset cylinders. `offset=0` meshes exactly
  as before (bit-identical nodes).
- Range: `|offset| + branch_radius < R`, and `|offset| ≤
  limits.TEE_MAX_OFFSET_RATIO × branch_radius` (1.0, proposed to
  design). Past h = r OCC's face fills fail erratically. Both raise
  `tee_offset_out_of_range`. Duct taps reject `offset`
  (`offset_on_duct_tap`).
- Quality falls slowly with the offset: at 90°, r/R 0.5, the predicted
  min SJ is 0.258 at h/R 0 and 0.209 at 0.4.
- PCF: offset set-ons (`TOSO`, `TORF`) now build, their offset measured
  from the branch straight. Tangential ones (`TTSO`, `TTRF`) are
  rejected by the offset range. `seton_offset_unsupported` is retired;
  `seton_offset_branch` names a set-on without a branch straight, or
  whose branch axis misses its centre.

**Hints for equipment and study errors** (decision 0040; task 0111).
- 14 of the drum's 23 errors and 8 of the study file's 18 now carry a
  `hint` saying what to change. Examples: the axial range a shell nozzle
  fits in, the largest head offset, a Klöpper head's radii for a
  torispherical drum, and "rename 'paramters' to 'parameters'". Messages
  are unchanged.
- **12 codes retired.** A block layout that breaks its own rules
  (topology, cell counts, binding) is a bug in a fitting, not the user's
  input, so it is now an `InternalError` (`internal_invariant`) asking
  for a report. No shipped fitting reaches these errors: they come only
  from hand-built layouts. The retired codes: `block_vertices_not_distinct`,
  `block_division_conflict`, `block_grading_conflict`,
  `block_division_missing`, `block_layout_empty`, `block_vertex_unplaced`,
  `block_face_shared`, `block_port_face_unused`,
  `block_port_face_interior`, `block_port_faces_unbound`,
  `block_h_core_in_ring` and `port_roll_not_a_period`. `block_inverted`
  stays a `LayoutError`.

**Junctions predict non-orthogonality** (decision 0031; task 0104).
- `validate()` predicts a tee's, a duct tap's or a wye's worst
  non-orthogonality before GMSH, from its block layout. It warns above
  `OUTLINE_NONORTH_WARN` (70°) and rejects above `OUTLINE_NONORTH_MAX`
  (80°) with the new code `predicted_nonorth_above_maximum`. The message
  names the block and what lowers it.
- The prediction can be up to 3.4° optimistic at r/R ≥ 0.6, so
  `mesh()` also checks each junction's meshed non-orthogonality on the
  same tiers, as for switches. It adds a warning only where the
  prediction didn't already give one.
- The wye only warns, as for its scaled Jacobian, until its layout
  redesign.
- **New warnings on existing networks.** Every wye warns (72–82°), so
  these examples now warn: `fittings.wye`, `fittings.junction_walls`
  (its 30° wye, 81.8°), `sections.insulated_network`,
  `networks.bifurcation_tree` and `applications.cooling_channels`.
  Tees with r/R about 0.3 and narrow-face duct taps also warn. No
  example newly errors.

**The network builder reads angled tees** (decision 0031; task 0103).
- A PCF `TEE` whose branch leans becomes a lateral, `Tee(angle=…)`, at
  the angle measured between the branch and the downstream run.  Set-ons
  (`TEE-SET-ON`, `OLET`) lean the same way, and their host is split
  around the run the lean needs.
- Within 1° of square a tee is a plain 90° tee, as before.  Every
  existing network builds the same assembly.
- The `Tee` rejects what it can't mesh at `validate()`, by its quality
  tiers.  The message gives the angle, the smallest r/R that passes
  there and the file's line: a 35° lateral needs r/R 0.876.
- `tee_branch_angled` now means a branch leaning **upstream** of the
  build direction, which no `Tee` builds.  Its hint is to build from the
  other end (`inlet=`).  The code stays.

## 0.5.0 (2026-11-08)

The launch release.
- **For agents:** structured, coded errors, and the `hexmesh` command
  (`manifest`, `validate`, `estimate`, `describe`, `advise`, `apply`,
  `build`).  It answers in JSON, and only `build` needs gmsh.
- **From plant data:** PCF networks, with cut, join and merge, a shipped
  sample and `--insulation`.
- **Validation:** the manufactured-solution study is accepted, and no
  published result went through a hex that gmshToFoam inverted.
- **Fittings:** lateral tees (`Tee(angle=…)`) and second-order export.
- **Breaking:** Python 3.11 is the oldest supported.

**Breaking:** Python 3.10 is no longer supported (end of life, October
2026); 3.11 is the oldest (task 0113, decision 0039).  CI tests 3.11 and
the newest 3.x.

**A PCF sample ships with the package, and the commands read its
insulation** (task 0114).
- `hexmesh.examples.applications.pcf_line`: an insulated line, written
  for hexmesh, from a vessel nozzle through a reducing tee, an elbow, a
  concentric reducer and a bare valve.  `SAMPLE` is its path, and it's in
  the gallery.  The README's PCF code reads it, so it runs as written:
  35 712 cells, 28 800 bare.
- `--insulation` on every `hexmesh` command that reads a network: on a
  PCF file it means `to_assembly(insulation=True)`.  On a description it
  is `cli_input_unreadable`, since a description says where its
  insulation is.
- The README's quoted `equal_tee_unsupported` error is now what an
  equal-tee variant of the sample gives, checked by a test.

**Networks with a wye are faster to check** (task 0112).
- `Wye.layout` keeps its last 32 layouts, keyed on the wye's, the
  frames' and the spec's values, and returns a copy of each.
- `hexmesh advise` on the hero network halves, 2.9 s → 1.35 s: it builds
  2 layouts instead of 5.  Run as separate commands, `validate` and
  `estimate` are unchanged, at one layout each.
- In one Python process, the README's agent session (`validate`,
  `estimate`, `advise`, `apply`, `validate`) drops from about 6 s to
  3.7 s, since the repeats no longer rebuild the wall.
- Meshes are unchanged, byte for byte.

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
