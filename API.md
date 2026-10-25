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
| `check_quality(quality_name="minSICN", threshold=0.0)` | Per-material `QualityReport` |
| `build_faces()`, `fill(order=None)` | The individual steps; `fill` takes any order of edge indices (rule A6) |
| `patch_name(interface)` | Patch name of an open interface |

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

#### `.core(name, radius=..., nrad=..., mprg=1.0)`

The circular core. A `CircleShape(radius, nang)` can be passed as the second
argument instead of `radius=`. `nrad` is the cells from the inner square to
the circle, and `mprg` the radial progression (above 1 refines toward the
inner side).

#### `.shell(name, dR, nrad, mprg=1.0)`

A concentric layer of thickness `dR` on top of the previous one.

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

### `QualityReport`

Returned by `Assembly.check_quality()`. It holds one `RegionQuality` per
material, under `regions`, and these attributes:
- `ok`: no element below `threshold`;
- `min_quality`, `total_elements`, `total_bad`;
- `quality_name`, `threshold`.

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
