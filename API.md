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

### `Assembly(spec, position=None, direction=None, up=None, lc=None, inlet_name="inlet", axial_cell=None)`

An interface-first pipe network ([DESIGN.md](DESIGN.md) §5).

| Parameter | Meaning |
|---|---|
| `spec` | `PipeSpec` of the inlet interface |
| `position`, `direction`, `up` | inlet pose; defaults are the origin, +x and +z. `up` fixes the roll of the cross-section and is made orthogonal to `direction` |
| `lc` | GMSH characteristic length; defaults to outer radius / 4 (it doesn't affect the structured mesh) |
| `inlet_name` | patch name of the inlet |
| `axial_cell` | target axial cell length. A sweep fitting added with `n_layers=None` (`Straight`, `Bend`, `Elbow`, `MiterBend`, `Reducer`, `Transition`, `SplinePipe`, `Closure`) gets `ceil(L / axial_cell)` layers, `L` its centreline length (for `MiterBend`, one end leg, since `n_layers` counts those), or the fewest above that which pass its own checks: a bend's turn below 180° per layer, a spline's or closure's 30° per layer, a profiled reducer's `chord_tol`. Resolved in `add()` (in `close()` for `Closure`) and stored in the fitting, so `to_dict()`, `cell_count()` and `refined(k)` see an ordinary count. `n_layers=None` without `axial_cell` is an `AssemblyError` naming the fitting, and so are `stack_changes` with `n_layers=None` (their indices need the count). Saved in the file; `refined(k)` divides it by k |

**Building the graph (pure Python, no GMSH)**

| Method | Does |
|---|---|
| `add(fitting, names=None, label=None)` | Attach *fitting* to the tail and move the tail to its first outlet (a tee's `main`, a wye's `left`). Returns the outlet `Interface`, or a list in port order for multi-outlet fittings. *names* names the outlet interfaces; *label* names the fitting (letters, digits, `_`; unique) |
| `add(interface, fitting, names=None, label=None)` | Attach *fitting* to *interface*; the tail does not move. Use the returned outlet to continue that line |
| `close(source, target, fitting, label=None)` | Join two existing open interfaces. *source* must be an outlet and *target* an inlet, so flow runs source → target. Use `Closure` for any gap, or a `Straight` / `Bend` that fits exactly |
| `prepend(straight, label=None)` | Place a `Straight` upstream of the inlet and make its start the new `inlet`; the inlet name moves with it. Returns the new inlet |
| `extend_open_ends(upstream=5.0, downstream=10.0, cells_per_diameter=4.0)` | Straight runs before the inlet and after every open outlet, in diameters of each end's core (hydraulic diameters for a duct); 0 skips a side. Each run gets `round(diameters × cells_per_diameter)` axial cells. Patch names are unchanged. Ends marked `equipment` are skipped. Call before building |
| `interfaces`, `edges` | All interfaces and fitting edges, in creation order |
| `inlet` | The inlet interface |
| `open_interfaces()` | Interfaces touched by one fitting only: the network boundary |

`names` is a list with one name per outlet, in port order, or a dict keyed
by port name, which may name only some: `names={"branch": "tap1"}`. Port
names are `fitting.port_names`: `Tee` `main`, `branch`; `Wye` `left`,
`right`; every one-outlet fitting `outlet`. An unknown key is an
`AssemblyError` listing the valid ones. A named open end becomes the patch
`<layer>_<name>`.

`add()` also resolves input-only fields from the inlet frame: `toward=`
becomes `roll`, and only `roll` is stored and saved. A bend angle below
2π° (6.28°) gives a `UserWarning` ("looks like radians?"): every angle is
in degrees. The thresholds are data, in `hexmesh.assembly.limits`.

**Validation and size (pure Python)**

| Method | Does |
|---|---|
| `validate(max_cells=None)` | Check every interface and fitting; raise `AssemblyError` naming the offender. With `max_cells`, also reject an assembly over budget |
| `cell_count()` | Exact hex count of the whole assembly |
| `cell_counts()` | Exact hex count per fitting (edge index → count) |

**Realisation (GMSH)**

| Method | Does |
|---|---|
| `mesh(dim=3, *, walls_by_fitting=False)` | Build faces, fill all fittings, write physical groups, and mesh. Between the surface and volume mesh, junction wall nodes are projected onto their analytic walls (decision 0029); `projection_report` holds each fitting's largest move, absolute and in local wall radii, and its cells' min corner scaled Jacobian. A move beyond `limits.WALL_PROJECTION_WARN_MOVE` (1) wall radii warns; a folded cell (corner SJ ≤ 0) in a projected fitting or its neighbours raises `AssemblyError`, naming the fitting. An OCC or GMSH error inside a fitting's fill also becomes an `AssemblyError` naming the fitting and quoting the original message. Projected nodes keep stale parametric coordinates, so leave GMSH's mesh optimisers off. Walls are `{layer}_wall`, after the layer outermost where they are, plus `{layer}_end` for the end faces of a terminated layer. With `walls_by_fitting`, each is split per fitting, `{group}_{name}`; *name* is the fitting's label or `<Type><index>` (`Bend3`) |
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
| `refined(k)` | A new assembly at k× the resolution (integer k ≥ 1), built from `to_dict()`: `nang`, every `nrad`, every `n_layers`, a tee's `n_run` / `n_branch` / `n_turn` and a wye's `n_run` / `n_branch` × k (a wye's `n_split` × k up to `WYE_N_SPLIT_MAX` = 6, never below its own value: more turning layers fold the wye, task 0056), the axial cell index of each `stack_changes` entry × k, and `mprg` and `axial_grading` → their k-th root.  Geometry, topology and `mbmp` stay; `first_cell` specs keep their resolved `mprg`.  **k³× the cells.** |

The file records how the network was built, not its geometry:
- the pose and spec of the first interface;
- every `add`, `close` and `prepend` in order, each with its fitting's
  type and fields, and the index of the interface it starts from
  (`source`) or joins (`close: [source, target]`), or `prepend: true`;
- the interface names, the tail, `lc` and `axial_cell`.

Replaying it recreates the interfaces in the same order, so interface
indices are stable, and editing a fitting in the file moves everything
downstream of it.  An outlet frame set by hand after `add()` is the one
exception; it is stored as an override under `frames`.

**Units.** Lengths are in your unit, stored unconverted; angles in
degrees, as in the fitting.

**Versions.** The format is version 2: `PipeSpec.rot` in degrees.
Version-1 files stored it in radians; `from_dict` and `load` convert them.

The fitting types are a fixed registry, `hexmesh.assembly.intent.FITTING_TYPES`.
An unknown type or field raises `ValueError`.

### `AssemblyError`

A subclass of `ValueError`, raised by validation and graph operations. The
message names the fitting (`fitting #3 Bend(...)`) or interface.

### `Interface`

A node of the graph: `frame` (a `Frame`), `spec` (a `PipeSpec`), `name`,
`index`, `is_open`, `equipment`. Its `face` is set once the assembly is built.
`equipment` marks an end attached to equipment (`from_nozzle`'s inlet, a PCF
equipment connection): nothing is prepended to it and `extend_open_ends`
skips it.  Saved files list the marked interfaces under `"equipment"`.

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
The inlet is marked `equipment`: nothing can be prepended upstream of
it, and `extend_open_ends` skips it.  Saved files keep the drum, which sets the pose on load.

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
| `rot` | rotation of the O-H corners, in degrees; for a rectangle, of the whole rectangle |
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

#### `.shell(name, dR=None, nrad, mprg=1.0, *, outer=None, first_cell=None)`

A layer on top of the previous one, from that layer's outline to its own
(decision 0026). Give exactly one of:

- `dR`: the previous outline grown by `dR` (a circle's radius + `dR`; a
  rectangle's `half_w` and `half_h` + `dR`, sharp corners kept);
- `outer`: a new outline, `CircleShape(radius, nang)` or
  `RectShape(half_w, half_h, nang_w, nang_h)`.

So a circle can sit in a rectangle, a rectangle in a circle, and a
rectangle in a rectangle, in any order and number of layers:

```python
from hexmesh.core.shape import CircleShape, RectShape

# cable in a square filler in a round sheath
(PipeSpec(nang=4).core("copper", radius=0.01, nrad=3)
 .shell("filler", outer=RectShape(0.016, 0.016, 4, 4), nrad=2)
 .shell("sheath", outer=CircleShape(0.028, 4), nrad=2))

# a duct with a wall and lagging
(PipeSpec(nang=4).core("air", RectShape(0.1, 0.05, 4, 4), nrad=3)
 .shell("wall", dR=0.002, nrad=2).shell("lagging", dR=0.03, nrad=3))
```

- **Ring.** Each shell is four blocks, one per side. Its corner lines
  leave the previous layer's corners away from the centre and end at the
  new outline: radially on a circle, at the corner in that quadrant on a
  rectangle. A circle in a flat rectangle has skewed corner lines; a
  rectangle in a circle splits it into unequal arcs.
- **Counts.** Every outline in a stack with a rectangle has the same count
  on every side (`nang = nang_w = nang_h`), and `n_outer = 4`.
  `ValueError` names the layer.
- **Containment.** Each outline lies inside the next all round, by at
  least `limits.OUTLINE_MIN_GAP` (10⁻³) of the outer one's largest
  extent. `validate()` names the layer, the gap and its direction.
- **Symmetry period.** That of the least symmetric outline: a circle in a
  2:1 rectangle has period 180°.
- **`first_cell`** sets the radial height of the cell at the layer's outer
  boundary in place of `mprg`. For a circle grown by `dR` it is exact all
  round. Otherwise it is solved on the ring's longest radial, so no wall
  cell is larger: the corner lines (`√2·dR` for a rectangle grown by `dR`),
  or, for a shell that changes shape, the longest line between
  corresponding points of the two outlines
  (`hexmesh.core.shape.longest_radial`). The solver is
  `hexmesh.core.grading.progression_for_first_cell(thickness, n_cells, h)`.

`.square_shell()` is gone: use `.shell(name, outer=RectShape(...))`.
Spec files that contain one still load, as that ring.

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
- **Fittings.** `Straight`, `Bend`, `MiterBend`, `SplinePipe`,
  `Closure`, `Reducer` (to another size) and `Transition` (to a circle,
  or to another rectangle). `Elbow` (ASME pipe schedules), `Tee` and
  `Wye` reject ducts.
- **Diameters.** `extend_open_ends` measures a duct in hydraulic
  diameters, 4A / P_w = `4·half_w·half_h / (half_w + half_h)`.
- **Cells.** `nang_w·nang_h + 2·(nang_w + nang_h)·nrad` per section.

`spec.to_dict()` / `PipeSpec.from_dict(d)` serialise a spec.  `mprg` is
stored as resolved, so a spec built with `first_cell=` reloads with the
same grading.

The assembly supports any stack of circle and rectangle outlines through
the sweep fittings (`Straight`, `Bend`, `MiterBend`, `SplinePipe`,
`Closure`, `Reducer`); bend radii are checked against the outermost
outline. `Elbow`, `Tee`, `Wye` and drum nozzles need every outline
circular.

---

## Fittings

**Axial grading.** `Straight`, `Bend`, `Elbow`, `Reducer`, `SplinePipe` and
`Closure` take `axial_grading=1.0`: the ratio of consecutive axial cell
lengths, inlet → outlet (GMSH's "Progression" law). Above 1 refines toward
the inlet, below 1 toward the outlet. `Straight` grades its axial curves.
The other fittings place one station per layer, so they space their
stations by the same law (for `SplinePipe` and `Closure`, in arc length
plus turning angle). The cell count is unchanged. `MiterBend`, `Tee` and
`Wye` are not graded; `Transition` spaces its stations like `Reducer`.

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

### `Straight(length, n_layers=None, axial_grading=1.0)`

A straight run with `n_layers` axial cells.

### `Bend(radius, angle, n_layers=None, roll=0.0, axial_grading=1.0, toward=None)`

A circular-arc bend with centreline `radius` and `angle` in (0°, 360°). It
places one station per axial layer, joined by exact arcs. `roll` rotates the
bend plane about the pipe axis: 0 bends toward `up`, 90 toward `right`.
`radius` must exceed the outer radius (for a duct, its half-extent in the
bend plane).

`toward=(x, y, z)` is an absolute direction to turn toward, instead of
`roll`, which is relative to an `up` that changes after every fitting.
`add()` turns its component across the inlet into `roll`. It must be at
least 1° from the inlet axis (`limits.TOWARD_MIN_ANGLE`), and needs a
positive `angle`; giving both `roll` and `toward` is an error. The same
holds for `Elbow` and `MiterBend`.

### `Elbow(angle=90.0, schedule="long", n_layers=8, roll=0.0, axial_grading=1.0, toward=None)`

A `Bend` whose radius follows the pipe: 1.5 D for `"long"` and 1 D for
`"short"` (ASME B16.9), where D is the outer diameter of the inlet spec.

### `MiterBend(radius, angle, n_cuts=1, n_layers=2, roll=0.0, toward=None)`

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

### `Reducer(outlet, length, n_layers=None, axial_grading=1.0, profile=None, chord_tol=1e-3)`

A concentric cone from the inlet spec to `outlet`; a larger outlet makes it an
expander. **It may change sizes and radial grading** (radii, half-widths,
`dR`, and `mprg` per layer). The outlet must equal the inlet in everything
else: the layer names and order, each layer's outline shape (a circle stays
a circle; use `Transition` to change shape), `nrad`, counts, `mbmp`,
`n_outer` and `rot`. Validation names the fields that differ. Wall nodes
lie exactly on the cone, or on the planes of a rectangle's sides.

Stations interpolate the sizes linearly and each layer's `mprg`
geometrically, `mprg_in^(1−u) · mprg_out^u`, at the same fractions. So a
wall-resolved pipe can change diameter: give both sides the same absolute
`first_cell`, and the solved `mprg` differs (decision 0016):

```python
pipe = lambda r: PipeSpec(nang=8).core("fluid", radius=r, nrad=8, first_cell=1e-3)
asm = Assembly(pipe(0.1))
asm.add(Reducer(pipe(0.06), length=0.2, n_layers=6))
```

**Profiles** (decision 0008).  `profile` replaces the cone by a radius
ratio `r(s) = R(s)/R_in` along the axis, `s` from 0 to 1.  Every radius of
the stack scales by `r(s)`, so `outlet` must be the inlet scaled by `r(1)`.
All forms are plain tuples, so they save and load:

| `profile` | shape |
|---|---|
| `("cosine", s0)` | smooth constriction (`s0 > 0`) or bulge (`s0 < 0`): `1 − s0·(1 + cos 2π(s − ½))`, `1 − 2·s0` at the middle, back to the inlet radius (RESEARCH §7.3).  `limits.COSINE_S0_MIN ≤ s0 < limits.COSINE_S0_MAX`, i.e. −1 (a bulge to 3 R) up to 0.5 (a closed throat); `s0 = 0` is a plain pipe |
| `("venturi", beta, divergent)` | classical venturi (ISO 5167-4): 21° convergent to `beta·D`, throat of length `d`, `divergent` 7°–15° back to `D`, then straight.  Lengths follow from `D`; too short a `length` is rejected with the length needed.  Corners are sharp and always land on stations |
| `((0, 1), (s, r), …, (1, r_out))` | a table, interpolated by a monotone cubic (PCHIP): no overshoot |

There is one station per axial layer, and every wall node at a station is
exactly on R(s).  Between stations the wall is a straight chord.
`validate()` rejects a chord further than `chord_tol · R_in` from the
profile, before GMSH, and names the `n_layers` needed:

```python
pipe = PipeSpec(nang=6).core("fluid", radius=0.05, nrad=3)
asm = Assembly(pipe)
asm.add(Reducer(pipe, length=0.2, n_layers=40, profile=("cosine", 0.25)))
```

A cosine constriction with `s0 = 0.25` needs 36 layers at the default
tolerance.  Each layer adds a full cross-section of cells, so a fine
profile is cheap compared with refining `nang` (doubling `nang` and `nrad`
quadruples the cells per layer).

### `Transition(outlet, length, n_layers=None, axial_grading=1.0)`

A straight transition that changes outline shapes: a circle to a
rectangle (either way), or a rectangle to one of another size or aspect
(decision 0009, task 0029), in every layer of a stack at once (decision
0026, task 0046): an insulated round pipe into an insulated duct, say.
`outlet` is the outlet spec.

- **Specs.** Equal in everything but each layer's outline: the same
  layers (names, order, `nrad`, `mprg`), the same counts per side in
  every layer (a circle's `nang` equals a rectangle's `nang_w` and
  `nang_h`), `mbmp` and `rot`. Then the two faces have the same mesh
  connectivity (switch class 0). A layer can't start or end in one (use
  `stack_changes`). Circles at both ends in every layer is a `Reducer`:
  **`Reducer` changes sizes, `Transition` shapes.**
- **Stations.** One per axial layer, spaced by `axial_grading` as for
  `Straight`. Each layer's station outline is the point-by-point blend of
  its two end outlines at equal arc-length fractions; a shell's corner
  lines blend with them. So wall and interface nodes lie on the station
  curves, and the end faces are the exact end outlines.
- **Nesting.** Each station's outlines must nest with the containment gap
  of `.shell()`, checked before GMSH at every station and 33 fractions
  between; the error names the station and the layer. (Measured: when the
  ends nest, the blend has kept every station nested.)
- **Corners.** Corner k meets corner k: a circle's corners at 45° + k·90°
  go to the rectangle's corners, with no twist.

### `SplinePipe(points, n_layers=None, end_tangent=None, axial_grading=1.0)`

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

### `Tee(run_length=None, branch_length, branch_radius, n_run=3, n_branch=3, n_turn=2, roll=0.0, toward=None, branch=None, face=None, margin=None, dome=None, sheet=None, n_wall=None)`

A perpendicular, centred side-branch tee, built as a block layout.

- **Ports.** `port_names = ("main", "branch")`; it returns `[main, branch]`.
  The main outlet is `2·run_length` downstream of the inlet and keeps the
  inlet's `up`. The branch leaves along the inlet's `up` rolled by `roll`
  about the main axis (0: `up`; 90: `right`) and ends `branch_length` from
  the main axis.
- **Orientation.** `roll` must be a multiple of the section's period (90°
  for a circle), so the junction's corners land on the inlet face's: 45° is
  rejected, naming 90°. `toward=(x, y, z)` gives the branch direction
  instead; `add()` picks the nearest allowed roll and rejects a direction
  more than 1° off it (`limits.JUNCTION_TOWARD_TOL`), naming the angle.
  Other branch angles need a twisting fitting (decision 0024).
- **Run length.** `run_length=None` (or omitted) is resolved by `add()` to
  `branch_radius + T + R/2` (T the total shell thickness), or the shortest
  run whose predicted quality reaches the warning tier below, whichever is
  longer; the number is stored, so `to_dict()` stays explicit.
  `branch_length` and `branch_radius` are required.
- **Layers.** `n_run`, `n_branch` and `n_turn` are the axial layers of the
  runs, the branch, and the turning blocks.
- **Shells.** Any stack of circular shells runs through the junction
  (decision 0028). The branch copies the main's shells: same names,
  thicknesses, `nrad` and `mprg`. Each interface group (`interface_fluid_steel`
  …) and the outer wall continue from the main through the junction into
  the branch. Wall and shell-boundary nodes lie on their offset cylinders
  to rounding: the faces are plates through cylinder points (3e-4 of the
  radius), and `mesh()` projects the nodes the rest of the way (decision
  0029, task 0051).
- **Limits.** Circular layers, `rot = 0`, and `branch_radius` below the
  main radius. With T the total shell thickness, `run_length` must exceed
  `branch_radius + T`, and `branch_length` the turning station's height,
  `R + T + (branch_radius + T)/2`. Both are checked before GMSH.
- **Predicted quality.** `validate()` computes the layout's min corner
  scaled Jacobian before GMSH (`Tee.predicted_sj`). Below
  `limits.PREDICTED_SJ_MIN` (0.1) it raises; below
  `limits.PREDICTED_SJ_WARN` (0.3) it warns and records the warning in
  `Assembly.warnings`. Both messages give the shortest `run_length` that
  reaches the tier (`Tee.shortest_run`), or say that none does: the
  junction core's quality is set by the branch ratio, about 0.26 at
  r/R 0.5 at any run. **Tees with r/R below about 0.57 always warn** (task
  0052).
- **Duct taps** (decision 0033, task 0070). On a rectangular main the tee
  is a duct tap: `branch=RectShape(half_w, half_h, nang_w, nang_h)` or
  `branch=CircleShape(radius, nang)` (`branch_radius` is the pipe
  shorthand; on a pipe, `branch=CircleShape` is the same as it).
  - **Face and side.** `face="wide"` (default) or `"narrow"`; `roll` 0 puts
    the tap on the +`up` face (wide face of a duct wider than deep) or the
    +`right` face (narrow), 180 on the opposite one. `toward` is rejected.
  - **Branch frame.** The branch keeps the main's counts per side (a
    class-0 port), so its section must have the main's `(nang_w,
    nang_h)`, or for a round tap the main must have equal counts and
    `nang` match them. On an up/down face the branch's `up` is the main's
    axis, so its `half_w`/`nang_w` run across (along the main's `right`)
    and `half_h` along the main; on a right/left face its `up` is the
    main's `up`, so `half_w` runs along the main and `half_h` across.
  - **Size.** The tap must reach at most `limits.DUCT_TAP_MAX_RATIO`
    (0.93) of the face's half-width across; a tap as wide as the face is a
    full-width tap (task 0057, not yet supported) and is rejected; in
    between is rejected with the largest tap that fits.
  - **Tunables.** `margin`, `dome`, `sheet` (layout shape) and `n_wall`
    (cells from a station to the hole) are resolved by `add()` to the best
    predicted quality and stored, so `to_dict()` stays explicit; give them
    to override. `run_length=None` resolves to the tap's reach along the
    main plus 4 ring thicknesses.
  - **Quality.** The predicted-SJ tiers as above. A round tap's prediction
    can overestimate by up to 0.11, so `mesh()` also applies the tiers to
    its meshed cells, naming the fitting. A narrow-face tap on a duct of
    aspect ≥ `limits.DUCT_TAP_NARROW_ASPECT_WARN` (3) warns and suggests
    the wide face (min SJ about 0.13, non-orthogonality up to 82°).
  - **Limits.** Single-layer ducts, `rot = 0`, `n_outer = 4`;
    `branch_length` beyond the face.

### `Wye(angle, run_length, branch_length, n_run=None, n_branch=None, n_split=None, roll=0.0, toward=None)`

A symmetric Y-junction, built as a block layout around a hub (prototype,
decision 0017).

- **Ports.** `port_names = ("left", "right")`; it returns `[left, right]`,
  both with the inlet's spec. The daughters leave the bifurcation point,
  `run_length` downstream of the inlet, at ±`angle`/2 in the inlet's
  (normal, `right`) plane rolled by `roll`; `right` turns toward the
  rolled `right`. Each outlet is `branch_length` from the bifurcation
  point and keeps the rolled `up`.
- **Orientation.** `roll` is a multiple of the period, as for `Tee`;
  `toward` is the direction the `right` daughter turns toward, snapped the
  same way.
- **Layers.** `n_run` and `n_branch` are the axial layers of the straight
  runs (inlet, each daughter); `n_split` those of each daughter's turning
  block.  A count left `None` is resolved in `add()`: the fewest layers
  that keep every edge it divides, the hub cap's arcs included, no longer
  than the angular cell at the wall, (π/2)·R / `nang` (or `axial_cell` if
  shorter).  A resolved `n_split` is capped at `limits.WYE_N_SPLIT_MAX`
  (6), because more turning layers degrade the turning blocks and fold
  120° wyes; so the knee arcs stay coarser than the angular cell, about
  2–3× at `nang` 8.  An explicit count above the cap is allowed, and a
  fold is caught by `mesh()`'s inversion check, which names the wye.
  `refined(k)` holds `n_split` at the cap too (task 0056).
- **Limits of the cap.**  Default wyes are reliable to about `nrad` 6;
  at 120° with `nrad` 12 only `n_split` 3 is safe (4 folds).  So
  `refined(k)` of a wye may fold beyond k = 2; `mesh()` raises
  `AssemblyError` naming the wye.  The wall error at the knee, 3–6 % of R
  away from the creases, doesn't fall with `nang` (the knee arcs stay at
  6 layers), so grid studies over wyes stop at k = 2.
- **Limits.** Circular core and shells, `rot = 0`, `n_outer = 4`, and
  `angle` from 30° to 120°. `run_length` must exceed R·(tan(angle/2) + 0.1)
  and `branch_length` R·(cot(angle/2) + 1); the messages give the numbers.
- **Shells** (task 0053).  Each shell boundary is the wall's level set at
  R + T_l, built and projected like the wall.  Checked before gmsh:
  - `angle` ≥ 40° (`limits.WYE_SHELL_MIN_ANGLE`; the shell cells' min
    corner SJ is 0.11–0.13 at 40°, 0.04 at 30°);
  - total shell thickness T ≤ R · min(0.65 tan(angle/2), 0.55)
    (`WYE_SHELL_TAN_FACTOR`, `WYE_SHELL_MAX`): 0.27 / 0.38 / 0.55 R at
    45° / 60° / 90°–120°.  The measured limits are 0.28 / 0.40 / 0.59 /
    0.84 R at 45° / 60° / 90° / 120°; past them the daughters' shells fold.
  A pipe wall (T ≈ 0.04 R) is well inside.
- **Quality warning.** `validate()` warns when the layout's predicted min
  corner SJ is below `PREDICTED_SJ_MIN` (0.1): single-layer wyes at 30°
  and 35°.  There is no reject tier for the wye until its layout redesign.
- **Wall.** The union of the inlet and daughter tubes, with a sharp crotch
  crease. `mesh()` projects the junction's wall nodes onto it (decision
  0029), so they lie on it to rounding; the faces between them are
  chords. At the crease the chord error is about 3 %, 1 % and 0.3 % of R at
  `nang` 4, 8 and 16 (task 0051). The hub's spherical cap is resolved by
  `n_run`, not `nang`: chords there stay about 10 % of R.
- **Quality.** Measured, not gated (decision 0017). The worst cells, min
  scaled Jacobian 0.06–0.16 depending on the angle, sit next to the hub's
  back corners. The numbers are in task 0030; projection leaves them
  within 0.04 (task 0051).

### `Closure(n_layers=None, tension=1.0, axial_grading=1.0)`

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
(`docs/integrations/pcf.md`).  `path` may be a list of files, read into
one network: components in list order, each file with its own units.

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
- **Insulation and equipment.**  `INSULATION` and keypoint
  `INSULATION-*` words are read per component (`insulation`,
  `end_insulation`, `branch_insulation`); `INSULATION-THICKNESS` per
  pipeline, in metres, goes to `NetworkSpec.insulation_thickness`.
  `EQUIPMENT-REFERENCE` blocks (also before the first pipeline) keep their
  repeated `NOZZLE` entries as a list under `"NOZZLES"`.
- **Junctions.**  `TEE` (`kind="tee"`; the branch may also be a third
  `END-POINT`), `TEE-SET-ON` / `TEE-STUB` / `OLET` (`"seton"`) and
  `Y-PIECE-FABRICATED` (`"ypiece"`) are read with `branch`, `branch2`,
  their bores and `skey`.  Crosses and `Y-PIECE-FITTING` are read as
  `"junction?"` and rejected by `to_assembly`.
- Other unsupported types are listed in `NetworkSpec.skipped`, with one
  warning each.

### `NetworkSpec.to_assembly(spec, *, axial_cell=None, kinks="error", tol=None, lc=None, inlet=None, insulation=False, insulation_nrad=2) -> Assembly`

**Mapping**

| PCF component | Fitting |
|---|---|
| pipe, flange, valve, cap | `Straight`, from the placed outlet to the component's end point |
| elbow, bend | `Bend`.  `CENTRE-POINT` is the corner where the tangent legs meet: θ = 180° − ∠(start − C, end − C), R = \|start − C\| / tan(θ/2).  Checked against `ANGLE` (hundredths of a degree) and `BEND-RADIUS` (`nD` × nominal size, or absolute) when present |
| concentric reducer | `Reducer` |
| eccentric reducer | rejected |
| `TEE` | `Tee`: run from the two `END-POINT`s, branch `CENTRE-POINT` → `BRANCH1-POINT`, its radius from the branch bore (`spec(bore)`, or the main radius × bore ratio) |
| `TEE-SET-ON`, `TEE-STUB`, `OLET` | the host `PIPE` through `CENTRE-POINT` is split: straight + `Tee` + straight.  The tee's run on each side of `CENTRE-POINT` is the `Tee`'s own default (`run_length=None`: r + T + R/2, or longer to reach `PREDICTED_SJ_WARN`; task 0054), from the spec's radii and shells; a host too short for it is rejected, naming the length needed |
| `Y-PIECE-FABRICATED` | its stem `PIPE` (ending at `CENTRE-POINT`) is cut back by the `Wye`'s inlet run, r·(tan h + 0.6) with r the nominal radius, h half the angle; then `Wye`, `BRANCH1-POINT` as the right daughter |
| rejected, naming the component and the limit | crosses, `Y-PIECE-FITTING`, tangential / offset set-ons (`TTSO`, `TTRF`, `TOSO`, `TORF`), equal tees, branches not perpendicular, asymmetric or non-coplanar Y pieces, daughters of another size, and the junctions' own limits (a wye's shell thickness and angle, a tee's predicted quality) |
| joint | absorbed: the preceding straight run is extended over it, or else the following one starts at it; dropped at an open end next to a non-straight fitting; rejected between two non-straight fittings |

**Parameters**

| Parameter | Meaning |
|---|---|
| `spec` | a `PipeSpec`, or a callable `bore → PipeSpec` (nominal size in metres). With a single spec, a reducer outlet scales the core radius by the bore ratio |
| `axial_cell` | target axial cell length; defaults to the outer radius. Passed to the `Assembly` (`Assembly(axial_cell=…)`), which sets every component's `n_layers` from it |
| `kinks` | `"error"` raises on pipes that change direction without a fitting; `"spline"` joins such runs into one `SplinePipe` (bathymetry routes) |
| `tol` | position tolerance in metres.  Default: 1e-4 × the model diagonal, at least 0.11" (2.79 mm), just above the weld gap |
| `inlet` | the root: an open end's name or a point (metres).  Default below |
| `insulation` | add a shell named `insulation` to insulated components (below).  Off: the spec alone decides the layers |
| `insulation_nrad` | radial cells across that shell |

**Insulation** (`insulation=True`)

A component is insulated when it says `INSULATION ON` (absent counts as
off); an `INSULATION-ON` / `-SINGLE` / `-OFF` word on an `END-POINT` or
branch point overrides that end.  The shell is the pipeline's
`INSULATION-THICKNESS` (coordinate units).  Where the insulation starts or
stops, the change sits one cell inside the straight component next to it,
the bare one when both are straight: a bare valve between insulated pipes
gets insulation one cell in at each side.  A straight whose two ends
differ switches at its middle.  Each switch is an `insulation_end` wall.

A junction with any insulated leg is insulated throughout: the `Tee` or
`Wye` carries the shell (task 0054), and a bare leg ends it one cell into
its first straight.  The runs into the junction get the shell before it.
Rejected, naming the component or pipeline: a junction whose legs have
two insulation thicknesses, a switch with no straight neighbour, a
thickness change between two insulated components, an insulated pipeline
without `INSULATION-THICKNESS`, and a spec that already has an
`insulation` shell.

**Equipment**

An open end at an `END-CONNECTION-EQUIPMENT` (or column-1 `NOZZLE`)
record is named `<equipment>_<nozzle>` and marked `equipment`.  The
`CONNECTION-REFERENCE` is a nozzle `REFERENCE` from an
`EQUIPMENT-REFERENCE` block, whose `CO-ORDS` must agree with the
connection, or `<equipment>/<nozzle>`.  A connection with no open end
within `tol` raises `AssemblyError`.  No equipment geometry is built.

**Graph, root and names**

Components join where their end points meet within `tol`, across
pipelines and files (`END-CONNECTION-PIPELINE` is informational).  The
network must be one tree: three components at one point, a loop or a
disconnected part raises `AssemblyError` naming a component.  Joints are
absorbed on the run they sit on.

Every junction must be entered through its inlet (a tee's run end, a Y
piece's stem).  The default root is the first open end in file order from
which that holds, trying first the ends a `FLOW` attribute marks as
upstream; if none qualifies, the error names a junction.  The root's `up`
is rolled so the first junction's branch lands on a multiple of 90°.

Fittings are labelled `<TYPE>_<n>` (`n` counts that PCF type in file
order, e.g. `TEE_SET_ON_1`), or `<TYPE>_<COMPONENT-IDENTIFIER>`.  A split
host keeps its label with `_1` / `_2`.  Open ends are named
`<pipeline>_end<k>` (`k` in file order).  The same files give the same
`to_dict()`.

Every component is checked against its PCF end points (and branch points), and a mismatch raises
`AssemblyError` naming the component.  Lateral offsets within `tol` are
accepted, a documented deviation: exporters offset components by up to the
weld gap.  `NetworkSpec.report` records the tolerance, the joints absorbed or
dropped, and the largest lateral offset absorbed.

### `bathymetry.read_bathymetry(surface_path, route, burial_depth=0.0, surface_format="xyz", route_format=None, unit_scale=1.0, max_segment_length=None) -> NetworkSpec`

Projects a 2-D route onto a seabed surface (XYZ, GeoTIFF or NetCDF). Build the
result with `to_assembly(spec, kinks="spline")`. Needs `scipy`
(`pip install -e ".[io]"`).

---

## Study runner (`hexmesh.study`)

One study file gives many variants (decision 0025).  Usage is in
[README.md](README.md#running-studies).

**Study file** (JSON; paths relative to it; every key but `template` is
optional):

| key | value |
|---|---|
| `template` | `{"python": "module:function"}`: `function(params: dict) -> Assembly`, imported from the study file's directory; or `{"json": "path"}`: a `to_dict()` description with `"$name"` placeholders |
| `parameters` | fixed values, in every variant |
| `sampling` | one of `{"table": {"rows": [...]}}`, `{"table": {"csv": "path"}}`, `{"grid": {name: [values]}}` (Cartesian product, first name slowest), `{"lhs": {"ranges": {name: [lo, hi]}, "n": N, "seed": S}}` (Latin hypercube) |
| `budget` | `max_cells_variant` (each variant's `validate(max_cells=…)`), `max_cells_total` |
| `output` | output directory (default `study`) |
| `jobs` | mesh processes at once (default 1; `--jobs` overrides) |
| `format` | `"msh"` (`Assembly.write`) or `"openfoam"` (`write_openfoam`, with its `.roles.json`) |
| `walls_by_fitting` | passed to the mesh writer |
| `case` | `{"template": "dir", "split_regions": false}`: an OpenFOAM case without a mesh, copied per variant (needs `"format": "openfoam"`) |
| `run` | `{"command": "./Allrun", "cores_per_job": 1, "post": "module:function", "timeout": 3600}` (needs `case`) |

- A variant's parameters are `parameters` updated by one sample.  Its
  directory is `output/variants/<hash>/`, where the hash is taken over
  the canonical parameters (sorted keys; `90.0` and `90` are the same).
- **JSON placeholders** replace the whole value; there are no expressions,
  and `"$$x"` is the literal `"$x"`.  A placeholder with no parameter, or
  a parameter that no placeholder uses, is a `StudyError`.

**Stages.**
- **preflight**: in-process, no GMSH.  For every variant: build,
  `validate()`, `cell_count()`, the topology key, and quality warnings
  (`Assembly.warnings`).  Then the total budget.
- **mesh**: one subprocess per variant, at most `jobs` at once.
  - Writes `mesh.msh`, `network.json`, `params.json` and `result.json`.
  - `result.json` holds: cells predicted and meshed, `all_hex`, min SICN,
    min scaled Jacobian and its fitting, mesh time, group roles.
  - Skips a variant whose mesh and result exist and whose
    `network.json` is unchanged.
  - A crash is recorded as `mesh_failed`, with the error.

- **case**: for every meshed variant, `variants/<hash>/case`.
  - A copy of the template, with its `$name` tokens replaced by the
    variant's parameters.
  - The mesh converted (`gmshToFoam`, then `splitMeshRegions -cellZones`
    with `split_regions`) and its patches retyped from the role manifest.
  - Whole tokens only: `$D` is a placeholder, `$Dmax` another name, and
    `$$` a literal `$`.
  - OpenFOAM's own references are left alone: a keyword defined on
    another line of the same file (`$internalField`), or `$FOAM_…` /
    `$WM_…`.
  - Any other unknown `$name` fails the case with an error naming the
    file.
  - Redone when the network, the template's files or the parameters
    change.
- **run**: `command` runs in each ready case with the OpenFOAM
  environment, at most `jobs` at once.
  - `jobs × cores_per_job` must not exceed the machine's cores.
  - Output goes to `case/log.run`.
  - Then `post(case_path, params) -> dict` gives the variant's `result`;
    in `study.csv` its keys become `result.<key>` columns.
  - A non-zero exit, a timeout or a failing `post` is recorded as
    `run_failed`, not raised.
  - Redone only when the case or the command changes.
  - It refuses while another session's pytest, `*Foam` or `mpirun`
    processes run (`hexmesh.study.other_runs`), unless `--force`.

**Statuses:**
- `checked`: preflight passed, not meshed.
- `preflight_failed`, `meshed`, `mesh_failed`.
- `case_ready`, `case_failed`.
- `done`, `run_failed`.

**OpenFOAM helpers** (`hexmesh.study.openfoam`, shared with the
validation scripts):
- `header`, `foam(cmd, case, log)`, `convert(case, msh, split_regions)`
  and `check_mesh`;
- readers: `read_points`, `read_faces`, `read_labels`, `read_zone`,
  `read_internal`, `read_patch_faces`, `read_patch_values`;
- `latest_time`, `face_geometry` / `cell_geometry` (OpenFOAM's own
  constructions) and `substitute_case`.

Post-processing works from ASCII case files.  Function objects abort on
v1912 here (`docs/integrations/openfoam.md`).

**Topology key**: a hash, in creation order, over:
- every interface's connectivity: its port signature without the grading
  floats `mprg` and `mbmp`;
- every fitting's type, ports and integer counts, as resolved
  (`n_layers`, `n_cuts`, a tee's `n_run`…), with its stack changes.

Equal keys mean node-aligned meshes: the same node tags and hex
connectivity.  `export` checks this when it reads the meshes back.

**Manifest**:
- `output/study.csv`: hash, status, parameters, cells, `cells_meshed`,
  `min_sicn`, `min_sj`, `min_sj_fitting`, times, topology, warnings,
  error.
- `output/study.json`: the same rows, the study file, and the versions
  of hexmesh, gmsh and Python.

**Aligned export** (`export`): `output/aligned/<key>.npz` holds
- `coords` (variants × nodes × 3, in node-tag order);
- `hexes` (node indices);
- `node_tags`;
- `variants` (hashes).

**Python:**

```python
from hexmesh.study import load_study, run, status, export
study = load_study("study.json")
rows = run(study, jobs=2)        # stages up to the study's last; PreflightFailed on failures
```

---

## Physical groups

The naming convention is in [README.md](README.md#physical-groups). It
follows from the graph (rule A7):
- volumes per material;
- `<layer>_<patch>` for each open interface;
- `interface_<inner>_<outer>` for material interfaces;
- `<outermost>_wall` for the outer wall.
