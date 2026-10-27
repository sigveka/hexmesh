# hexmesh API reference

Everything below is importable from the package root (`from hexmesh import …`)
unless a module is named. Lengths are in metres and angles in degrees, unless
stated otherwise.

---

## Session

### `Session(name="hexmesh", verbose=False)`

Context manager around the GMSH lifetime. On enter it calls
`gmsh.initialize()` and adds a model named *name*; on exit it calls
`gmsh.finalize()`, also when an exception is raised. `verbose=False` limits
GMSH output to errors.

- `Session.show()` opens the GMSH GUI on the current model and blocks until
  it is closed.

`Assembly` builds into whatever GMSH model is current. You can manage
`gmsh.initialize()` yourself instead of using `Session`.

---

## Assembly

### `Assembly(spec, position=None, direction=None, up=None, lc=None, inlet_name="inlet")`

An interface-first pipe network ([DESIGN.md](DESIGN.md) §5).

| Parameter | Meaning |
|---|---|
| `spec` | `PipeSpec` of the inlet interface |
| `position`, `direction`, `up` | inlet pose; defaults are the origin, +x and +z. `up` fixes the roll of the cross-section and is made orthogonal to `direction` |
| `lc` | GMSH characteristic length; defaults to outer radius / 4 (it doesn't affect the structured mesh) |
| `inlet_name` | patch name of the inlet |

**Building the graph (pure Python, no GMSH)**

| Method | Does |
|---|---|
| `add(fitting, names=None, label=None)` | Attach *fitting* to the tail and move the tail to its first outlet. Returns the outlet `Interface`, or a list for multi-outlet fittings. *names* names the outlet interfaces; *label* names the fitting (letters, digits, `_`; unique) |
| `add(interface, fitting, names=None, label=None)` | Attach *fitting* to *interface*; the tail does not move. Use the returned outlet to continue that line |
| `close(source, target, fitting, label=None)` | Join two existing open interfaces. *source* must be an outlet and *target* an inlet, so flow runs source → target. Use `Closure` for any gap, or a `Straight` / `Bend` that fits exactly |
| `prepend(straight, label=None)` | Place a `Straight` upstream of the inlet and make its start the new `inlet`; the inlet name moves with it. Returns the new inlet |
| `extend_open_ends(upstream=5.0, downstream=10.0, cells_per_diameter=4.0)` | Straight runs before the inlet and after every open outlet, in diameters of each end's core (hydraulic diameters for a duct); 0 skips a side. Each run gets `round(diameters × cells_per_diameter)` axial cells. Patch names are unchanged. Call before building |
| `interfaces`, `edges` | All interfaces and fitting edges, in creation order |
| `inlet` | The inlet interface |
| `open_interfaces()` | Interfaces touched by one fitting only: the network boundary |

`names` gives one name per outlet. A named open end becomes the patch
`<layer>_<name>`.

**Validation and size (pure Python)**

| Method | Does |
|---|---|
| `validate(max_cells=None)` | Check every interface and fitting; raise `AssemblyError` naming the offender. With `max_cells`, also reject an assembly over budget |
| `cell_count()` | Exact hex count of the whole assembly |
| `cell_counts()` | Exact hex count per fitting (edge index → count) |

**Realisation (GMSH)**

| Method | Does |
|---|---|
| `mesh(dim=3, *, walls_by_fitting=False)` | Build faces, fill all fittings, write physical groups, and mesh. Walls are `{layer}_wall`, after the layer outermost where they are, plus `{layer}_end` for the end faces of a terminated layer. With `walls_by_fitting`, each is split per fitting, `{group}_{name}`; *name* is the fitting's label or `<Type><index>` (`Bend3`) |
| `write(path, dim=3, *, walls_by_fitting=False)` | `mesh()`, then `gmsh.write(path)`; the format follows the extension |
| `write_openfoam(path, *, interfaces=False, walls_by_fitting=False)` | `mesh()`, then write a `.msh` for `gmshToFoam`: MSH 2.2 ASCII, without the material-interface groups unless `interfaces=True` (the split rebuilds them as `mappedWall`; kept, they become faceZones); the GMSH options and groups are restored afterwards.  Also writes the role manifest `<stem>.roles.json` |
| `group_roles()` | Physical-group name → role (`volume`, `open_end`, `wall`, `interface`), from the graph, as last written by `mesh()` |
| `check_quality(quality_name="minSICN", threshold=None, by="material")` | `QualityReport` per material, or per fitting with `by="fitting"` (see Quality) |
| `fitting_volumes()` | Volume tags per fitting (edge index → tags) |
| `build_faces()`, `fill(order=None)` | The individual steps; `fill` takes any order of edge indices (rule A6) |
| `patch_name(interface)` | Patch name of an open interface |

**Saving and loading (no GMSH)**

| Method | Does |
|---|---|
| `to_dict()` / `Assembly.from_dict(d)` | The network description as plain JSON-serialisable data, and back |
| `save(path)` / `Assembly.load(path)` | The same, as a JSON file (indented, sorted keys) |
| `refined(k)` | A new assembly at k× the resolution (integer k ≥ 1), built from `to_dict()`: `nang`, every `nrad`, every `n_layers`, a tee's `n_run` / `n_branch` / `n_turn` and a wye's `n_split` × k, the axial cell index of each `stack_changes` entry × k, and `mprg` and `axial_grading` → their k-th root.  Geometry, topology and `mbmp` stay; `first_cell` specs keep their resolved `mprg`.  **k³× the cells.** |

The file records how the network was built, not its geometry:
- the pose and spec of the first interface;
- every `add`, `close` and `prepend` in order, each with its fitting's
  type and fields, and the index of the interface it starts from
  (`source`) or joins (`close: [source, target]`), or `prepend: true`;
- the interface names, the tail and `lc`.

Replaying it recreates the interfaces in the same order, so interface
indices are stable, and editing a fitting in the file moves everything
downstream of it.  An outlet frame set by hand after `add()` is the one
exception; it is stored as an override under `frames`.

**Units.** Lengths are in your unit, stored unconverted; angles in
degrees, as in the fitting.

The fitting types are a fixed registry, `hexmesh.assembly.intent.FITTING_TYPES`.
An unknown type or field raises `ValueError`.

### `AssemblyError`

A subclass of `ValueError`, raised by validation and graph operations. The
message names the fitting (`fitting #3 Bend(...)`) or interface.

### `Interface`

A node of the graph: `frame` (a `Frame`), `spec` (a `PipeSpec`), `name`,
`index`, `is_open`. Its `face` is set once the assembly is built.

### `Frame(position, normal, up)`

The absolute pose of an interface. `normal` points downstream, `up` fixes the
roll, and `right = normal × up`. `Frame.from_vectors(position, normal, up)`
normalises the vectors and makes `up` orthogonal to `normal`.

---

## Equipment (`hexmesh.assembly.equipment`)

Pure Python: a drum gives nozzle poses and builds no geometry
(decision 0002).

### `Drum(name, diameter, length, position=(0,0,0), axis=(1,0,0), up=(0,0,1), head="ellipsoidal_2_1", crown_radius=None, knuckle_radius=None, nozzles=())`

- **Dimensions:**
  - `diameter` is the inside diameter;
  - `length` is tangent line to tangent line;
  - `position` is the centre of the first tangent plane;
  - `axis` runs from the first tangent plane to the second.  A vertical
    drum is just `axis=(0, 0, 1)`.
- **Head:**
  - `"ellipsoidal_2_1"` (depth D/4);
  - `"hemispherical"` (depth D/2);
  - `"torispherical"`, which needs both `crown_radius` and
    `knuckle_radius`.  There is no default, because the proportions
    depend on the design code.
- **Angles** are in degrees about `axis` from `up`, right-handed.
- `frame(name) -> Frame`: the nozzle face.  `normal` points away from
  the drum; `up` is the drum axis for a shell nozzle, and the head's
  radial direction for a head nozzle (the drum `up` when centred).
- `validate()` raises `EquipmentError` naming the drum and nozzle when:
  - a face lies inside the shell or head over the nozzle footprint;
  - a nozzle is too large for the drum;
  - a footprint crosses a tangent line or leaves the head (the crown
    region, for a torispherical head);
  - two footprints overlap.
- `head_height(rho)`: the head profile.  `to_dict()` / `Drum.from_dict(d)`
  serialise the drum.

### `Nozzle(name, spec, location)`

`location` is one of:
- `OnShell(axial, angle, projection)`: a radial nozzle on the shell.
  `projection` is measured from the drum axis to the face.
- `OnHead(head, offset, angle, projection)`: on the `"first"` or
  `"second"` head, parallel to the axis.  `projection` is measured from
  the tangent plane to the face.

### `Assembly.from_nozzle(drum, nozzle, lc=None)`

Starts a network at the nozzle face.  The drum is validated first, and
the inlet is named `"{drum.name}_{nozzle}"` (patch `fluid_D101_N1`).
Nothing can be prepended upstream of a nozzle; `extend_open_ends` skips
it.  Saved files keep the drum, which sets the pose on load.

A network cannot yet *end* at a nozzle: `close()` needs the target to be
the inlet of a fitting (task 0010, question for design).

## Cross-section specification

### `PipeSpec(nang=None, nang_w=None, nang_h=None, mbmp=1.0, rot=0.0, n_outer=4)`

A builder for a concentric layer stack.

| Parameter | Meaning |
|---|---|
| `nang` | cells per 90° arc, shared by all layers (circular cores) |
| `nang_w`, `nang_h` | cells along the width and the height of a rectangular core |
| `mbmp` | angular bump factor (1 = uniform) |
| `rot` | rotation of the O-H corners, in radians; for a rectangle, of the whole rectangle |
| `n_outer` | structural corners; the assembly supports 4 |

#### `.core(name, radius=..., nrad=..., mprg=1.0, first_cell=None)`

The circular core. A `CircleShape(radius, nang)` can be passed as the second
argument instead of `radius=`. `nrad` is the cells from the inner square to
the circle, and `mprg` the radial progression (above 1 refines toward the
inner side).

`first_cell` replaces `mprg` with the largest radial height of a cell at
the circle, the pipe wall. The core ring is thickest at mid-arc, 0.491 R
from the inner arc to the circle
(`hexmesh.core.shape.oh_core_wall_span`), and the progression is solved
there. So no wall cell is larger than `first_cell`, and the cells at the
corners (span 0.4 R) are about 0.81× it. It needs `n_outer = 4`. It raises
`ValueError` if no progression fits (for example `first_cell` ≥ the span),
and `TypeError` together with `mprg`.

#### `.shell(name, dR, nrad, mprg=1.0, first_cell=None)`

A concentric layer of thickness `dR` on top of the previous one.
`first_cell` sets the radial height of the cell at the layer's outer
boundary in place of `mprg`. It is exact all round. The solver is
`hexmesh.core.grading.progression_for_first_cell(thickness, n_cells, h)`.

#### `.core(name, half_w=..., half_h=..., nrad=..., mprg=1.0)` — rectangular duct

A rectangular core of width `2·half_w` along the frame's `right` and height
`2·half_h` along `up` (needs `PipeSpec(nang_w=…, nang_h=…)`). It has the
same five-patch O-H layout as the circle: a centre rectangle and a ring of
uniform thickness, `0.4·min(half_w, half_h)`, so every corner radial runs at
45° to the walls. `nrad` is the cells across the ring. `first_cell` is not
supported (`TypeError`).

- **Symmetry period** (DESIGN §6.1, `spec.period`): 90° for a square
  (`half_w == half_h` and `nang_w == nang_h`), 180° for any other
  rectangle. Corners match, and loop twist is absorbed, modulo that
  period; a mismatch of exactly half of it is ambiguous and rejected.
- **"Easy way" and "hard way" bends.** `up` sets which side is the
  height; a bend's `roll` sets its plane. `roll=0` bends toward `up`,
  across the height: the easy way for a wide, flat duct. `roll=90` bends
  across the width: the hard way. The centreline radius must exceed the
  duct's half-extent in the bend plane (`half_h` for roll 0, `half_w` for
  roll 90). Splines and closures, whose bend plane varies, are checked
  against the half-diagonal.
- **Fittings.** `Straight`, `Bend`, `MiterBend`, `SplinePipe` and
  `Closure`. `Elbow` (ASME pipe schedules), `Reducer`, `Tee` and `Wye`
  reject ducts; a duct size change is a `Transition` (task 0029).
- **Diameters.** `extend_open_ends` measures a duct in hydraulic
  diameters, 4A / P_w = `4·half_w·half_h / (half_w + half_h)`.
- **Cells.** `nang_w·nang_h + 2·(nang_w + nang_h)·nrad` per section.

`spec.to_dict()` / `PipeSpec.from_dict(d)` serialise a spec.  `mprg` is
stored as resolved, so a spec built with `first_cell=` reloads with the
same grading.

The assembly supports circular cores with circular shells, and
single-layer rectangular cores. Shells around a rectangle and
`.square_shell()` exist in `PipeSpec` but are rejected by validation.

---

## Fittings

**Axial grading.** `Straight`, `Bend`, `Elbow`, `Reducer`, `SplinePipe` and
`Closure` take `axial_grading=1.0`: the ratio of consecutive axial cell
lengths, inlet → outlet (GMSH's "Progression" law). Above 1 refines toward
the inlet, below 1 toward the outlet. `Straight` grades its axial curves.
The other fittings place one station per layer, so they space their
stations by the same law (for `SplinePipe` and `Closure`, in arc length
plus turning angle). The cell count is unchanged. `MiterBend`, `Tee` and
`Wye` are not graded.

Every fitting has three parts:
- `ports(inlet, spec)`: where its outlets go;
- `validate(frames, spec)`: geometry checks;
- `cell_count(frames, spec)`.

All three are pure Python. Fittings never build their own interface faces;
they only fill between the faces the assembly built.

**Layer termination (decision 0006).**  `Straight` and `Bend` take
`stack_changes=((i, spec), …)`: from axial cell `i` on (`0 < i <
n_layers`), the stack is `spec`.  Each change adds or removes whole
outermost layers; the remaining layers must keep their names, radii,
`nrad` and grading.  `validate()` checks this before GMSH and names the
fitting and the layer.
- The station face at a change is built with the fuller stack.  The
  ending layer's annulus there becomes `{layer}_end`.
- `ports()` returns the last stack for the outlet.
- `cell_count()` counts each layer only in the cells where it is present.
- In a `Straight`, a change adds an internal station.  The axial
  progression continues across it, so the nodes are those of the unsplit
  run.

**Switch classes (`hexmesh.assembly.signature`, DESIGN A4).**  Each
fitting declares `strategies`: the switch classes it can bridge between
its inlet and each outlet.  `Straight` and `Bend` declare `{0, 1}`
(layer termination), `Reducer` declares `{0, 2}` (grading-only, below),
and the other fittings declare `{0}`.  A
frozenset applies to every port pair; a tuple gives one per outlet.

- `signature(spec)` is the hashable connectivity signature:
  - per layer: name, layout (`oh_core` or `annulus`), `nrad` and `mprg`;
  - per section: `n_outer`, the symmetry period, `nang` and `mbmp`.

  Radii and `rot` are geometry, not connectivity, so they are left out.
- `classify(a, b)` sorts a pair into a class and lists what differs:

  | Class | Meaning | Bridged by |
  |---|---|---|
  | 0 | equal | any fitting |
  | 1 | whole outermost layers on one side only | layer termination (task 0018) |
  | 2 | same layers, different counts or grading | grading only: a sweep that interpolates grading per station (`Reducer`); counts: a density switch (decision 0003) |
  | 3 | anything else | a topology switch (decision 0003) |

  A class-2 pair whose only differences are per-layer radial `mprg` is
  marked `grading_only` (decision 0016), as class 1 is marked
  `ends="wall"`.  Declaring class 2 bridges those pairs only; a count or
  `mbmp` difference is still rejected:

  > Reducer: outlet spec differs from the inlet in core nrad (3 vs 5); core
  > mprg (1.0 vs 1.2). That is switch class 2 beyond radial grading (counts
  > or mbmp), which needs a density switch (decision 0003); Reducer bridges
  > grading-only class-2 pairs (radial mprg) only

`Assembly.validate` rejects an undeclared class before GMSH, naming the
fitting, the field and the class, for example:

> Reducer: outlet spec differs from the inlet in nang (4 vs 8). That is
> switch class 2 beyond radial grading (counts or mbmp), which needs a
> density switch (decision 0003); Reducer bridges grading-only class-2
> pairs (radial mprg) only

### `Straight(length, n_layers, axial_grading=1.0)`

A straight run with `n_layers` axial cells.

### `Bend(radius, angle, n_layers, roll=0.0, axial_grading=1.0)`

A circular-arc bend with centreline `radius` and `angle` in (0°, 360°). It
places one station per axial layer, joined by exact arcs. `roll` rotates the
bend plane about the pipe axis: 0 bends toward `up`, 90 toward `right`.
`radius` must exceed the outer radius (for a duct, its half-extent in the
bend plane).

### `Elbow(angle=90.0, schedule="long", n_layers=8, roll=0.0, axial_grading=1.0)`

A `Bend` whose radius follows the pipe: 1.5 D for `"long"` and 1 D for
`"short"` (ASME B16.9), where D is the outer diameter of the inlet spec.

### `MiterBend(radius, angle, n_cuts=1, n_layers=2, roll=0.0)`

A segmented bend: straight pieces joined at `n_cuts` planar cuts.

- **Shape.** The centreline is the tangent polygon of `Bend(radius, angle,
  roll=roll)`, so the ports are identical. The end legs are
  `radius·tan(cut/2)` long.
- **Layers.** `n_layers` axial cells per end leg, and `2·n_layers` per inner
  segment.
- **Cuts.** Each cut is the exact ellipse where the two pipes meet, and each
  cut turns `angle / n_cuts`, which must lie in [1°, 90°].
- **Measured quality.** min SICN equals the straight-pipe value up to a 60°
  cut, and is about 0.18 at a single 90° cut.

### `Reducer(outlet, length, n_layers, axial_grading=1.0)`

A concentric cone from the inlet spec to `outlet`; a larger outlet makes it an
expander. **It may change radii and radial grading** (`mprg` per layer). The
outlet must equal the inlet in everything else: the layer names and order,
`nrad`, `nang`, `mbmp`, `n_outer` and `rot`. Validation names the fields that
differ. Wall nodes lie exactly on the cone.

Stations interpolate the radii linearly and each layer's `mprg`
geometrically, `mprg_in^(1−u) · mprg_out^u`, at the same fractions. So a
wall-resolved pipe can change diameter: give both sides the same absolute
`first_cell`, and the solved `mprg` differs (decision 0016):

```python
pipe = lambda r: PipeSpec(nang=8).core("fluid", radius=r, nrad=8, first_cell=1e-3)
asm = Assembly(pipe(0.1))
asm.add(Reducer(pipe(0.06), length=0.2, n_layers=6))
```

### `SplinePipe(points, n_layers, end_tangent=None, axial_grading=1.0)`

A pipe along a cubic spline through `points`, parametrised by chord length.

- **Start.** `points[0]` must be the inlet position; the spline leaves along
  the inlet direction.
- **End.** It ends along `end_tangent` if given, otherwise with zero
  curvature.
- **Stations.** One station per axial layer, spread by arc length plus
  turning angle, with rotation-minimising (Bishop) frames. The outlet roll
  follows from the curve.
- **Validation.** It rejects curvature tighter than the outer radius, and
  more than 30° of turn per layer.

### `Tee(run_length, branch_length, branch_radius, n_run=3, n_branch=3, n_turn=2)`

A perpendicular, centred side-branch tee, built as a block layout.

- **Ports.** It returns `[main, branch]`. The main outlet is `2·run_length`
  downstream of the inlet. The branch leaves along the inlet's `up` and ends
  `branch_length` from the main axis.
- **Layers.** `n_run`, `n_branch` and `n_turn` are the axial layers of the
  runs, the branch, and the turning blocks.
- **Limits.** A single-layer spec, `rot = 0`, and `branch_radius` below the
  main radius.

### `Wye(angle, run_length, branch_length, n_run=3, n_branch=3, n_split=3)`

A symmetric Y-junction, built as a block layout around a hub (prototype,
decision 0017).

- **Ports.** It returns `[left, right]`, both with the inlet's spec. The
  daughters leave the bifurcation point, `run_length` downstream of the
  inlet, at ±`angle`/2 in the inlet's (normal, `right`) plane; `right`
  turns toward the inlet's `right`. Each outlet is `branch_length` from the
  bifurcation point and keeps the inlet's `up`. To split in another plane,
  roll upstream.
- **Layers.** `n_run` and `n_branch` are the axial layers of the straight
  runs (inlet, each daughter); `n_split` those of each daughter's turning
  block.
- **Limits.** A single-layer circular spec, `rot = 0`, `n_outer = 4`, and
  `angle` from 30° to 120°. `run_length` must exceed R·(tan(angle/2) + 0.1)
  and `branch_length` R·(cot(angle/2) + 1); the messages give the numbers.
- **Quality.** Measured, not gated (decision 0017). The worst cells, min
  scaled Jacobian 0.06–0.16 depending on the angle, sit next to the hub's
  back corners. Junction wall nodes are up to about 20 % of R off the
  intended surface, and the crotch is rounded. The numbers are in task 0030.

### `Closure(n_layers, tension=1.0, axial_grading=1.0)`

For `close()` only. It runs a cubic Hermite centreline between two existing
interfaces, leaving and arriving along their normals. The roll mismatch is
taken modulo the cross-section's symmetry period (90° for a circle or a
square, 180° for a rectangle) and spread along the run; exactly half the
period is ambiguous and rejected.
`tension` scales the end tangents. It is rejected if the curve is tighter
than the outer radius, or turns more than 30° per layer.

---

## Quality

### `Assembly.check_quality(quality_name="minSICN", threshold=None, by="material")`

**Metric.** `quality_name` is either a GMSH element quality (`"minSICN"`,
`"minSIGE"`, `"gamma"`, …) or a hex metric from `hexmesh.quality_hex.METRICS`:

| Metric | Ideal | Better | Default bad limit |
|---|---|---|---|
| `scaled_jacobian` | 1 | higher | ≤ 0 (folded corner) |
| `nes` | 0 | lower | ≥ 1 (degenerate angle) |
| `mean_ratio_min`, `shape_regularity_knupp`, … | 1 | higher | ≤ 0 |
| `skewness` | 0 | lower | ≥ 1 |

- **`scaled_jacobian`** is the minimum over the 8 corners of
  det(J)/(|e1||e2||e3|) (Knupp).  Verdict also counts a ninth Jacobian
  at the element centre.
- **`nes`** is the normalized equiangle skewness,
  max((θmax − 90°)/90°, (90° − θmin)/90°) over the 24 face angles
  (GAMBIT/Fluent EquiAngle skewness).

Both are the metrics of RESEARCH §4.2, which suggests targets of
scaled Jacobian > 0.6 and NES < 0.5.  Pass those as `threshold` to
enforce them.

**Grouping.** `by="fitting"` gives one row per fitting, named
`"#<index> <Type>"` (for example `#1 Tee`), so a failure names the
fitting.

**Note.** SICN is aspect-sensitive: it rates long, thin cells as poor.
The two shape metrics are not, because a stretched box scores ideal.

### `QualityReport`

Returned by `check_quality`. It holds one `RegionQuality` per group, under
`regions` (each has `name`, `fitting`, `worst`, `best`, `mean_quality`,
`n_bad`), and these attributes:
- `ok`: no bad element;
- `worst`, and `worst_region`, the row holding it;
- `min_quality`, `total_elements`, `total_bad`;
- `quality_name`, `threshold`, `higher_is_better`.

`print(report)` gives a table.

### `HexVolumeQuality`, `hex_all_metrics`

Element-level hex metrics (warping, skewness, scaled Jacobian, …) from
`hexmesh.quality_hex`.

---

## OpenFOAM boundary roles (`hexmesh.io.writers.openfoam_boundary`)

The manifest, `<stem>.roles.json`, looks like this:

```json
{"format": 1,
 "groups": {"fluid": "volume", "fluid_inlet": "open_end", "fluid_wall": "wall",
            "interface_fluid_steel": "interface"},
 "not_written": ["interface_fluid_steel"]}
```

- **`groups`** gives each physical group's role, taken from the network
  graph, never from the name.
- **`not_written`** lists groups in the manifest that `write_openfoam`
  left out of the `.msh`.

| Function | Does |
|---|---|
| `apply_boundary_roles(case_dir, roles, region=None)` | Retype `constant[/<region>]/polyMesh/boundary` in place (plain Python, atomic write). `wall` patches get `type wall;` and `inGroups 1(wall);`; `open_end` patches stay `patch`; `mappedWall` patches are untouched. Patches missing from the manifest are left alone, with one warning naming them. *roles* is the manifest dict or its path. Returns the retyped patch names |
| `apply_boundary_roles_to_regions(case_dir, roles)` | The same for every `constant/<region>` after `splitMeshRegions`, or for `constant/polyMesh` if there are no regions. Returns region → retyped names |
| `retype_boundary_text(text, groups)` | The text transformation: `(new_text, retyped, unknown)` |
| `roles_path(msh)`, `write_roles(path, groups, not_written)`, `read_roles(path_or_dict)` | Manifest helpers |

## Readers (`hexmesh.io.readers`)

### `pcf.read_pcf(path, unit_scale=None, ignore_types=None, joint_max=1.6e-3) -> NetworkSpec`

Parses an Isogen PCF file, following the *PCF Reference Guide*
(`docs/integrations/pcf.md`).

- **Header and units.**  Header keywords go to `NetworkSpec.header`.
  - Coordinates scale from `UNITS-CO-ORDS` (`MM`, `MM-HUNDREDTHS`, `INCH`).
  - Bore scales from `UNITS-BORE` (`MM`, `INCH`, `INCH-SIXTEENTH`),
    independently of the coordinates.
  - `unit_scale` (metres per coordinate unit) overrides the header, with a
    warning if they disagree.
  - A file without `UNITS-CO-ORDS` is read as mm, with one warning.
- **Bore is the nominal size in metres** (4" → 0.1016), not an inside
  diameter.  Map it to a cross-section with `to_assembly(lambda bore: …)`.
- **Sections.**  `PIPELINE-REFERENCE` attributes go to
  `NetworkSpec.pipelines`; each component records its `pipeline`.
  `END-CONNECTION-*` and `EQUIPMENT-REFERENCE` blocks go to
  `NetworkSpec.connections`.  `MATERIALS` (the last section) is skipped.
- **Joints.**  `GAP`, and `WELD`, `COUPLING` or `GASKET` no longer than
  `joint_max` (just above the 1/16" weld gap), become `kind="joint"`.
  Longer ones are fittings.
- Unsupported types such as `TEE` are listed in `NetworkSpec.skipped`, with
  one warning each.

### `NetworkSpec.to_assembly(spec, *, axial_cell=None, kinks="error", tol=None, lc=None) -> Assembly`

**Mapping**

| PCF component | Fitting |
|---|---|
| pipe, flange, valve, cap | `Straight`, from the placed outlet to the component's end point |
| elbow, bend | `Bend`.  `CENTRE-POINT` is the corner where the tangent legs meet: θ = 180° − ∠(start − C, end − C), R = \|start − C\| / tan(θ/2).  Checked against `ANGLE` (hundredths of a degree) and `BEND-RADIUS` (`nD` × nominal size, or absolute) when present |
| concentric reducer | `Reducer` |
| eccentric reducer | rejected |
| joint | absorbed: the preceding straight run is extended over it, or else the following one starts at it; dropped at an open end next to a non-straight fitting; rejected between two non-straight fittings |

**Parameters**

| Parameter | Meaning |
|---|---|
| `spec` | a `PipeSpec`, or a callable `bore → PipeSpec` (nominal size in metres). With a single spec, a reducer outlet scales the core radius by the bore ratio |
| `axial_cell` | target axial cell length; defaults to the outer radius |
| `kinks` | `"error"` raises on pipes that change direction without a fitting; `"spline"` joins such runs into one `SplinePipe` (bathymetry routes) |
| `tol` | position tolerance in metres.  Default: 1e-4 × the model diagonal, at least 0.11" (2.79 mm), just above the weld gap |

Every component is checked against its PCF end points, and a mismatch raises
`AssemblyError` naming the component.  Lateral offsets within `tol` are
accepted, a documented deviation: exporters offset components by up to the
weld gap.  `NetworkSpec.report` records the tolerance, the joints absorbed or
dropped, and the largest lateral offset absorbed.

### `bathymetry.read_bathymetry(surface_path, route, burial_depth=0.0, surface_format="xyz", route_format=None, unit_scale=1.0, max_segment_length=None) -> NetworkSpec`

Projects a 2-D route onto a seabed surface (XYZ, GeoTIFF or NetCDF). Build the
result with `to_assembly(spec, kinks="spline")`. Needs `scipy`
(`pip install -e ".[io]"`).

---

## Physical groups

The naming convention is in [README.md](README.md#physical-groups). It
follows from the graph (rule A7):
- volumes per material;
- `<layer>_<patch>` for each open interface;
- `interface_<inner>_<outer>` for material interfaces;
- `<outermost>_wall` for the outer wall.
