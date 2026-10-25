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
| `add(fitting, names=None)` | Attach *fitting* to the tail and move the tail to its first outlet. Returns the outlet `Interface`, or a list for multi-outlet fittings |
| `add(interface, fitting, names=None)` | Attach *fitting* to *interface*; the tail does not move. Use the returned outlet to continue that line |
| `close(source, target, fitting)` | Join two existing open interfaces. *source* must be an outlet and *target* an inlet, so flow runs source → target. Use `Closure` for any gap, or a `Straight` / `Bend` that fits exactly |
| `prepend(straight)` | Place a `Straight` upstream of the inlet and make its start the new `inlet`; the inlet name moves with it. Returns the new inlet |
| `extend_open_ends(upstream=5.0, downstream=10.0, cells_per_diameter=4.0)` | Straight runs before the inlet and after every open outlet, in diameters of each end's core; 0 skips a side. Each run gets `round(diameters × cells_per_diameter)` axial cells. Patch names are unchanged. Call before building |
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
| `mesh(dim=3)` | Build faces, fill all fittings, write physical groups, and mesh |
| `write(path, dim=3)` | `mesh()`, then `gmsh.write(path)`; the format follows the extension |
| `write_openfoam(path, *, interfaces=False)` | `mesh()`, then write a `.msh` for `gmshToFoam`: MSH 2.2 ASCII, without the material-interface groups unless `interfaces=True` (they break `splitMeshRegions`); the GMSH options and groups are restored afterwards |
| `check_quality(quality_name="minSICN", threshold=None, by="material")` | `QualityReport` per material, or per fitting with `by="fitting"` (see Quality) |
| `fitting_volumes()` | Volume tags per fitting (edge index → tags) |
| `build_faces()`, `fill(order=None)` | The individual steps; `fill` takes any order of edge indices (rule A6) |
| `patch_name(interface)` | Patch name of an open interface |

**Saving and loading (no GMSH)**

| Method | Does |
|---|---|
| `to_dict()` / `Assembly.from_dict(d)` | The network description as plain JSON-serialisable data, and back |
| `save(path)` / `Assembly.load(path)` | The same, as a JSON file (indented, sorted keys) |

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

## Cross-section specification

### `PipeSpec(nang, mbmp=1.0, rot=0.0, n_outer=4)`

A builder for a concentric layer stack.

| Parameter | Meaning |
|---|---|
| `nang` | cells per 90° arc, shared by all layers |
| `mbmp` | angular bump factor (1 = uniform) |
| `rot` | rotation of the O-H corners, in radians |
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

`spec.to_dict()` / `PipeSpec.from_dict(d)` serialise a spec.  `mprg` is
stored as resolved, so a spec built with `first_cell=` reloads with the
same grading.

The assembly supports circular cores and circular shells. Rectangular cores
(`half_w`, `half_h`) and `.square_shell()` exist in `PipeSpec` but are
rejected by validation until decision 0009 is implemented.

---

## Fittings

**Axial grading.** `Straight`, `Bend`, `Elbow`, `Reducer`, `SplinePipe` and
`Closure` take `axial_grading=1.0`: the ratio of consecutive axial cell
lengths, inlet → outlet (GMSH's "Progression" law). Above 1 refines toward
the inlet, below 1 toward the outlet. `Straight` grades its axial curves.
The other fittings place one station per layer, so they space their
stations by the same law (for `SplinePipe` and `Closure`, in arc length
plus turning angle). The cell count is unchanged. `MiterBend` and `Tee` are
not graded.

Every fitting has three parts:
- `ports(inlet, spec)`: where its outlets go;
- `validate(frames, spec)`: geometry checks;
- `cell_count(frames, spec)`.

All three are pure Python. Fittings never build their own interface faces;
they only fill between the faces the assembly built.

### `Straight(length, n_layers, axial_grading=1.0)`

A straight run with `n_layers` axial cells.

### `Bend(radius, angle, n_layers, roll=0.0, axial_grading=1.0)`

A circular-arc bend with centreline `radius` and `angle` in (0°, 360°). It
places one station per axial layer, joined by exact arcs. `roll` rotates the
bend plane about the pipe axis: 0 bends toward `up`, 90 toward `right`.
`radius` must exceed the outer radius.

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
expander. The outlet must equal the inlet in everything except its radii (core
radius and shell thicknesses). That covers the layer names and order, `nrad`,
`nang`, gradings, `n_outer` and `rot`. Validation names the first field that
differs. Wall nodes lie exactly on the cone.

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

### `Closure(n_layers, tension=1.0, axial_grading=1.0)`

For `close()` only. It runs a cubic Hermite centreline between two existing
interfaces, leaving and arriving along their normals. The roll mismatch is
taken modulo the cross-section symmetry and spread along the run.
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

## Readers (`hexmesh.io.readers`)

### `pcf.read_pcf(path, unit_scale=1e-3, ignore_types=None) -> NetworkSpec`

Parses an Isogen PCF file into components (pipe, elbow, reducer, and
fittings such as flanges and valves). Unsupported types such as `TEE` are
listed in `NetworkSpec.skipped`, with a warning.

### `NetworkSpec.to_assembly(spec, *, axial_cell=None, kinks="error", tol=1e-4, lc=None) -> Assembly`

**Mapping**

| PCF component | Fitting |
|---|---|
| pipe, flange, valve | `Straight` |
| elbow | `Bend`, rolled into the elbow's plane from its centre point |
| concentric reducer | `Reducer` |
| eccentric reducer | rejected |

**Parameters**

| Parameter | Meaning |
|---|---|
| `spec` | a `PipeSpec`, or a callable `bore → PipeSpec`. With a single spec, a reducer outlet scales the core radius by the bore ratio |
| `axial_cell` | target axial cell length; defaults to the outer radius |
| `kinks` | `"error"` raises on pipes that change direction without a fitting; `"spline"` joins such runs into one `SplinePipe` (bathymetry routes) |
| `tol` | position tolerance, for PCF rounding |

Every component is checked against its PCF end points, and a mismatch raises
`AssemblyError` naming the component.

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
- `<layer>_to_<next>` for material interfaces;
- `<outermost>_wall` for the outer wall.
