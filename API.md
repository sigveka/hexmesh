# hexmesh API Reference

Compact reference for all public classes. Read README.md first for concepts and context.

---

## Session management

### `Model(name, verbose=False, subdivide=True)`
GMSH session context manager. Always use as `with Model(...) as m:`.

```python
with Model("my_mesh") as m:
    net = Network(...)
    ...
    net.write("output.msh")
```

| Method | Description |
|---|---|
| `m.mesh(dim=3)` | Generate mesh only. **Do not use** when network contains Reducer/SplinePipe/TJunction — use `net.mesh()` instead. |
| `m.write(path)` | Write mesh to file (`.msh`, `.vtk`, `.cgns`). |
| `m.show()` | Open GMSH GUI (blocking). |

---

## Network

### `Network(spec, direction=None, up=None, position=None, cursor=None, lc=None)`
Pipe network builder.

```python
net = Network(pipe)                                      # origin, +X direction
net = Network(pipe, direction=[0,1,0], up=[0,0,1])       # +Y direction, up=+Z
net = Network(pipe, direction=[1,0,0], position=[2,0,0]) # offset start
```

| Method | Returns | Description |
|---|---|---|
| `net.add(connector)` | `Node` | Append connector to current tail |
| `net.add(node, connector)` | `Node` | Append connector to a specific node (DAG branching) |
| `net.mesh(dim=3)` | — | Write physical groups, apply deferred constraints, generate mesh |
| `net.write(path, dim=3)` | — | `net.mesh()` then `gmsh.write(path)` |
| `net.write_physical_groups()` | — | Emit Physical Volume / Surface declarations only |

`net.add()` returns a `Node` (single-outlet connectors) or `list[Node]` (junction connectors).
Each `Node` has `.cursor` (position/direction/up) and `.face` (outlet `LayeredCrossSection`).

---

## Cross-section specification

### `PipeSpec(nang=None, nang_w=None, nang_h=None, mbmp=1.0, rot=0.0)`
Builder for concentric-layer circular or rectangular pipe cross-sections.

```python
# Circular
pipe = PipeSpec(nang=6).core("fluid", radius=0.05, nrad=4)

# Multi-layer circular
pipe = (
    PipeSpec(nang=6)
    .core("fluid",      radius=0.05, nrad=4)
    .shell("pipe_wall", dR=0.01,     nrad=2)
    .shell("insulation",dR=0.02,     nrad=3)
)

# Rectangular duct
duct = PipeSpec(nang_w=6, nang_h=4).core("air", half_w=0.2, half_h=0.1, nrad=4)

# Circular pipe ending in a square outer shell (for bundle arrays)
cell = (
    PipeSpec(nang=6)
    .core("fluid",      radius=0.05, nrad=4)
    .shell("wall",      dR=0.01,     nrad=2)
    .square_shell("shell", half_w=0.08, half_h=0.08, nrad=3)
)
```

#### `.core(name, radius=None, half_w=None, half_h=None, nrad, mprg=1.0)`
Set the innermost layer. Called exactly once.

| Param | Type | Description |
|---|---|---|
| `name` | str | Material label |
| `radius` | float | Circular outer radius [m]. Requires `nang` on PipeSpec. |
| `half_w`, `half_h` | float | Rectangular half-dimensions [m]. Requires `nang_w`, `nang_h`. |
| `nrad` | int | Radial mesh divisions |
| `mprg` | float | Radial progression factor (default 1.0 = uniform) |

#### `.shell(name, dR, nrad, mprg=1.0)`
Add a concentric circular shell. Stacks on the previous layer's outer boundary.

| Param | Type | Description |
|---|---|---|
| `name` | str | Material label |
| `dR` | float | Radial thickness [m] |
| `nrad` | int | Radial mesh divisions |

#### `.square_shell(name, half_w, half_h, nrad, mprg=1.0)`
Add a square outer shell (terminates the concentric stack). Enables bundle tiling.

---

## Connectors

All connectors are dataclasses — construct, then pass to `net.add()`.

---

### `Straight(length, n_layers)`
Linear extrusion along the current pipe axis. Uses OCC `extrude()`.

```python
Straight(length=0.4, n_layers=5)
```

| Param | Type | Description |
|---|---|---|
| `length` | float | Extrusion length [m] > 0 |
| `n_layers` | int | Axial hex layers ≥ 1 |

---

### `Elbow(angle, schedule="long", n_layers=8, roll=0.0)`
ASME standard elbow. Centreline radius derived from inlet pipe diameter.

```python
Elbow(90)                              # long-radius (R=1.5D), 90°
Elbow(45, schedule="short")            # short-radius (R=1D), 45°
Elbow(90, roll=90)                     # long-radius, bending upward
Elbow(180, schedule="long", n_layers=12)  # 180° return
```

| Param | Type | Description |
|---|---|---|
| `angle` | float | Deflection in degrees. Standard: 45, 90, 180. |
| `schedule` | str | `"long"` → R=1.5D (default); `"short"` → R=1D |
| `n_layers` | int | Hex layers along the arc |
| `roll` | float | Rotate bend plane around pipe axis (degrees). 0=sideways, 90=upward. |

---

### `Bend(angle, n_layers, radius=None, radius_factor=None, roll=0.0)`
General smooth bend. Exactly one of `radius` or `radius_factor` must be supplied.

```python
Bend(radius=0.15, angle=90, n_layers=8)         # absolute centreline radius
Bend(radius_factor=1.5, angle=90, n_layers=8)   # long-radius equivalent
Bend(radius_factor=3.0, angle=45, n_layers=6)   # 3D pipe bend
Bend(radius_factor=5.0, angle=90, n_layers=10)  # 5D pipe bend
```

| Param | Type | Description |
|---|---|---|
| `angle` | float | Deflection in degrees |
| `n_layers` | int | Hex layers along the arc |
| `radius` | float | Absolute centreline radius [m] |
| `radius_factor` | float | Radius as multiple of D (D = 2 × R_pipe) |
| `roll` | float | Rotate bend plane (degrees) |

**Industry radius guide:**

| `radius_factor` | Name | Notes |
|---|---|---|
| 1.0 | Short-radius elbow | ASME B16.9, compact |
| 1.5 | Long-radius elbow | ASME B16.9, most common |
| 3.0–5.0 | Pipe bend | Low ΔP, needs more space |

---

### `MiterBend(angle, roll=0.0, n_layers=1)`
Abrupt flat-cut miter joint. Angles > 30° are auto-subdivided into ≤30° cuts.

```python
MiterBend(angle=90)                # single 90° miter
MiterBend(angle=30, roll=90)       # 30° upward miter
MiterBend(angle=90, n_layers=2)    # more layers for better quality
```

| Param | Type | Description |
|---|---|---|
| `angle` | float | Direction change in degrees |
| `roll` | float | Rotate miter plane (degrees). 0=sideways, 90=upward. |
| `n_layers` | int | Revolution layers (default 1) |

---

### `Reducer(outlet, length, n_layers)` / `Expander(outlet, length, n_layers)`
Taper between two `PipeSpec` diameters. Both must have matching `nang`.
Uses manually-built volumes — requires `net.mesh()` not `m.mesh()`.

```python
small = PipeSpec(nang=6).core("fluid", radius=0.03, nrad=3)
Reducer(outlet=small, length=0.1, n_layers=4)
Expander(outlet=large, length=0.15, n_layers=4)
```

| Param | Type | Description |
|---|---|---|
| `outlet` | PipeSpec | Target cross-section |
| `length` | float | Taper length [m] |
| `n_layers` | int | Axial hex layers |

---

### `TJunction(approach_length, branch_length, departure_length=0.0, branch_r=None, roll=0.0, n_layers=2)`
Perpendicular T-junction. Returns `(main_node, branch_node)`.

```python
n_main, n_branch = net.add(TJunction(
    approach_length  = 0.2,   # cursor-entry to T-point; must be >= branch_r
    branch_length    = 0.15,  # T-point to branch outlet; must be > R_main
    departure_length = 0.2,   # T-point to main outlet (0 = exit at T-point)
    branch_r         = 0.03,  # branch outer radius; must be < R_main
    roll             = 0.0,   # 0=branch goes right, 90=branch goes up
))
```

| Param | Type | Description |
|---|---|---|
| `approach_length` | float | Inlet run to T-point [m]. Typical: 1–2 × D_main. |
| `branch_length` | float | T-point to branch face [m]. Must be > R_main. |
| `departure_length` | float | T-point to main outlet [m]. 0 = exit at T-point. |
| `branch_r` | float | Branch outer radius [m]. Must satisfy 0 < branch_r < R_main. |
| `roll` | float | Branch direction (degrees). 0=cursor.right, 90=cursor.up. |
| `branch_direction` | list[float] | Global branch direction vector (alternative to roll). |
| `n_layers` | int | Hex layers (default 2) |

Requires `net.mesh()` not `m.mesh()`.

---

### `YJunction(length, half_angle=45, roll=0.0, n_layers=2)`
Symmetric Y-split into two equal legs. Returns `(branch_1_node, branch_2_node)`.

```python
n1, n2 = net.add(n_in, YJunction(length=0.15, half_angle=45))
net.add(n1, Straight(0.4, n_layers=4))   # +half_angle leg
net.add(n2, Straight(0.4, n_layers=4))   # -half_angle leg
```

| Param | Type | Description |
|---|---|---|
| `length` | float | Branch leg length [m] |
| `half_angle` | float | Half-opening angle (degrees). Must be in (0, 90). |
| `roll` | float | Rotate split plane (degrees). 0=horizontal, 90=vertical. |
| `n_layers` | int | Hex layers (default 2) |

---

### `SplinePipe(waypoints, n_stations=20, n_layers=1)`
Pipe following a cubic spline through 3D waypoints. Uses parallel-transport (Bishop) frames to eliminate roll. Requires `net.mesh()` not `m.mesh()`.

```python
net.add(SplinePipe(
    waypoints  = [[0,0,0], [0.1,0.2,0.05], [0.2,0.4,0]],
    n_stations = 12,    # cross-section planes along spline (not counting inlet)
    n_layers   = 1,     # hex layers per slab
))
```

| Param | Type | Description |
|---|---|---|
| `waypoints` | list of [x,y,z] | Control points. ≥ 2 required. First should match cursor position. |
| `n_stations` | int | Cross-section planes along path (default 20). More = smoother bend. |
| `n_layers` | int | Axial hex layers per slab (default 1) |

Constraints: Only `CircleShape` layers supported. Each inter-station slab's cross-section spacing must exceed the pipe outer radius to avoid self-intersection.

---

## Cursor

### `Cursor(position, direction, up)`
Tracks pipe axis position and orientation.

```python
from hexmesh.core.cursor import Cursor
c = Cursor(position=[0,0,0], direction=[0,1,0], up=[0,0,1])
c.right        # = direction × up (unit vector)
c.advanced(L)  # new cursor moved L along direction
c.rotated(axis, angle_rad)  # new cursor with rotated direction and up
```

Cursors are read from `node.cursor` after `net.add()`. Rarely constructed manually.

---

## Physical groups

`net.write_physical_groups()` (called automatically by `net.mesh()` / `net.write()`) emits:

For each material layer `"name"`:

| Physical group | Dim | Content |
|---|---|---|
| `name` | 3 | All volumes of this material |
| `name_inlet` | 2 | System inlet face(s) — surfaces that appear as inlets but never as outlets |
| `name_outlet` | 2 | System outlet face(s) — surfaces that appear as outlets but never as inlets |
| `name_wall` | 2 | Outer lateral boundary surfaces |
| `name_to_next` | 2 | Conformal interface between adjacent materials |

---

## Connector compatibility matrix

| Connector | CircleShape | RectShape | Multi-layer | Uses `net.mesh()` |
|---|---|---|---|---|
| `Straight` | ✅ | ✅ | ✅ | optional |
| `Elbow` | ✅ | ❌ | ✅ | optional |
| `Bend` | ✅ | ❌ | ✅ | optional |
| `MiterBend` | ✅ | ❌ | ✅ | optional |
| `Reducer/Expander` | ✅ | ✅ | ✅ | **required** |
| `TJunction` | ✅ | ❌ | ✅ | **required** |
| `YJunction` | ✅ | ❌ | ✅ | optional |
| `SplinePipe` | ✅ | ❌ | ✅ | **required** |

"Uses `net.mesh()`" — required when the connector builds volumes with `addVolume()` rather than OCC `extrude()`. When in doubt, always use `net.mesh()`.

---

## Common patterns

### Simple straight pipe

```python
pipe = PipeSpec(nang=6).core("fluid", radius=0.05, nrad=4)
with Model("pipe") as m:
    net = Network(pipe, direction=[0,1,0], up=[0,0,1])
    net.add(Straight(1.0, n_layers=10))
    net.write("pipe.msh")
```

### 90° elbow between two straight runs

```python
with Model("elbow") as m:
    net = Network(pipe, direction=[0,1,0], up=[0,0,1])
    net.add(Straight(0.3, n_layers=4))
    net.add(Elbow(90))
    net.add(Straight(0.3, n_layers=4))
    net.write("elbow.msh")
```

### T-junction with branch

```python
with Model("t_junction") as m:
    net = Network(pipe, direction=[0,1,0], up=[0,0,1])
    net.add(Straight(0.2, n_layers=3))
    n_main, n_branch = net.add(TJunction(
        approach_length=0.15, branch_length=0.15,
        departure_length=0.15, branch_r=0.03,
    ))
    net.add(n_main,   Straight(0.3, n_layers=4))
    net.add(n_branch, Straight(0.2, n_layers=3))
    net.write("t_junction.msh")
```

### Reducer hairpin

```python
large = PipeSpec(nang=6).core("fluid", radius=0.05, nrad=4)
small = PipeSpec(nang=6).core("fluid", radius=0.03, nrad=3)

with Model("hairpin") as m:
    net = Network(large, direction=[1,0,0], up=[0,0,1])
    net.add(Straight(0.3, n_layers=4))
    net.add(Reducer(outlet=small, length=0.1, n_layers=3))
    net.add(Elbow(180, schedule="long"))   # U-turn
    net.add(Expander(outlet=large, length=0.1, n_layers=3))
    net.add(Straight(0.3, n_layers=4))
    net.write("hairpin.msh")
```

### Curved pipe (SplinePipe)

```python
with Model("curved") as m:
    net = Network(pipe, direction=[0,1,0], up=[0,0,1])
    net.add(Straight(0.1, n_layers=2))
    net.add(SplinePipe(
        waypoints  = [[0,0.1,0], [0.05,0.3,0], [0.1,0.5,0], [0.1,0.7,0]],
        n_stations = 8,
        n_layers   = 1,
    ))
    net.add(Straight(0.1, n_layers=2))
    net.write("curved.msh")
```
