# hexmesh

Composable structured all-hex mesh generator for CFD pipe networks, built on [GMSH](https://gmsh.info/).

Describe a pipe network as a Python chain of connectors — straight runs, elbows, reducers, T-junctions, spline curves — and get a fully structured hexahedral mesh ready for OpenFOAM or any other finite-volume solver.

```
Straight → Elbow → Straight → TJunction → Straight
                                    └───→  Straight
```

All cells are hexahedral. No tetrahedra, no pyramids, no hanging nodes.

---

## Why structured hex?

- **Accuracy** — aligned cells reduce numerical diffusion compared to tet meshes
- **Efficiency** — roughly 5–10× fewer cells for the same resolution along the pipe axis
- **OpenFOAM compatibility** — all boundary conditions and wall functions work on pure hex

---

## Installation

```bash
pip install gmsh numpy scipy
pip install -e .           # from the repo root
```

Python ≥ 3.10 required. GMSH ≥ 4.10 recommended.

---

## Quick start

```python
from hexmesh import Model, Network
from hexmesh.core import PipeSpec
from hexmesh.connectors import Straight, Elbow

# 1. Define the cross-section: fluid core + pipe wall
pipe = (
    PipeSpec(nang=6)
    .core("fluid",     radius=0.05, nrad=4)
    .shell("pipe_wall", dR=0.01,   nrad=2)
)

# 2. Build the network inside a Model context
with Model("my_pipe") as m:
    net = Network(pipe, direction=[0, 1, 0], up=[0, 0, 1])

    net.add(Straight(length=0.3, n_layers=4))
    net.add(Elbow(angle=90))                   # long-radius 90° elbow, ASME default
    net.add(Straight(length=0.3, n_layers=4))

    net.write("my_pipe.msh")   # mesh + write in one call
```

The mesh file contains labelled Physical groups:

| Group | Type | Description |
|---|---|---|
| `fluid` | Volume | Fluid region |
| `pipe_wall` | Volume | Pipe wall material |
| `fluid_inlet` | Surface | System inlet face |
| `fluid_outlet` | Surface | System outlet face |
| `fluid_wall` | Surface | Outer fluid boundary (= fluid/wall interface) |
| `pipe_wall_wall` | Surface | External pipe surface |
| `fluid_to_pipe_wall` | Surface | Conformal interface between materials |

---

## Cross-section specification

Everything starts with a `PipeSpec` — a builder that stacks concentric layers:

```python
# Bare pipe (fluid only)
pipe = PipeSpec(nang=6).core("fluid", radius=0.05, nrad=4)

# Two-layer: fluid + pipe wall
pipe = (
    PipeSpec(nang=6)
    .core("fluid",      radius=0.05, nrad=4)
    .shell("pipe_wall", dR=0.01,     nrad=2)
)

# Three-layer: fluid + wall + insulation
pipe = (
    PipeSpec(nang=6)
    .core("fluid",       radius=0.05, nrad=4)
    .shell("pipe_wall",  dR=0.01,     nrad=2)
    .shell("insulation", dR=0.02,     nrad=3)
)

# Rectangular duct
duct = (
    PipeSpec(nang_w=6, nang_h=4)
    .core("air", half_w=0.2, half_h=0.1, nrad=4)
)
```

**Key parameters:**

| Parameter | Meaning |
|---|---|
| `nang` | Angular mesh divisions per 90° arc (more → finer azimuthal resolution) |
| `nrad` | Radial divisions across each layer (more → finer radial resolution) |
| `radius` | Outer radius of the circular core [m] |
| `dR` | Radial thickness of a shell layer [m] |

---

## Connector reference

### `Straight(length, n_layers)`
Linear extrusion along the current pipe axis.

```python
Straight(length=0.5, n_layers=6)
```

### `Elbow(angle, schedule="long", n_layers=8, roll=0.0)`
ASME standard short- or long-radius elbow. Radius is derived automatically from the pipe diameter.

```python
Elbow(90)                         # long-radius 90° (R = 1.5D)
Elbow(45, schedule="short")       # short-radius 45° (R = 1D)
Elbow(90, roll=90)                # same but bending upward instead of sideways
```

| `schedule` | Centreline radius | ASME standard |
|---|---|---|
| `"long"` (default) | R = 1.5 × D | B16.9 long radius |
| `"short"` | R = 1.0 × D | B16.9 short radius |

### `Bend(angle, n_layers, radius=None, radius_factor=None, roll=0.0)`
General smooth bend — use when the radius is not a standard SR/LR elbow.

```python
Bend(radius=0.15, angle=90, n_layers=8)        # absolute radius
Bend(radius_factor=3.0, angle=45, n_layers=6)  # 3D pipe bend
```

### `MiterBend(angle, roll=0.0, n_layers=1)`
Abrupt flat-cut direction change. Angles > 30° are automatically subdivided.

```python
MiterBend(angle=90)             # single 90° miter
MiterBend(angle=30, roll=90)    # 30° cut, bending upward
```

### `Reducer(outlet, length, n_layers)` / `Expander(outlet, length, n_layers)`
Taper from one pipe diameter to another. Both pipes must have the same `nang`.

```python
small = PipeSpec(nang=6).core("fluid", radius=0.03, nrad=3)
Reducer(outlet=small, length=0.1, n_layers=4)
```

### `TJunction(approach_length, branch_length, departure_length=0.0, branch_r=None, roll=0.0, n_layers=2)`
Perpendicular side-tap branch.

```python
# Returns (main_node, branch_node)
n_main, n_branch = net.add(TJunction(
    approach_length  = 0.2,    # inlet run to T-point (≥ branch_r)
    branch_length    = 0.15,   # T-point to branch outlet
    departure_length = 0.2,    # T-point to main outlet (0 = exit at T-point)
    branch_r         = 0.03,   # branch outer radius (< main R)
))
net.add(n_main,   Straight(0.4, n_layers=4))
net.add(n_branch, Straight(0.2, n_layers=3))
```

### `YJunction(length, half_angle=45, roll=0.0, n_layers=2)`
Symmetric Y-split: both legs deflect by `±half_angle`.

```python
# Returns (branch_1_node, branch_2_node)
n1, n2 = net.add(n_in, YJunction(length=0.15, half_angle=45))
```

### `SplinePipe(waypoints, n_stations=20, n_layers=1)`
Pipe following a cubic spline through 3D waypoints. Uses parallel-transport frames to eliminate roll.

```python
net.add(SplinePipe(
    waypoints  = [[0, 0, 0], [0.1, 0.3, 0.05], [0.2, 0.6, 0]],
    n_stations = 12,
    n_layers   = 1,
))
```

> **Note:** `SplinePipe` uses manually-built volumes (not OCC extrusion), so meshing requires `net.write()` or `net.mesh()` — **not** `m.mesh()`. See [Meshing](#meshing) below.

---

## Meshing

Two methods are available:

```python
# Preferred — applies all deferred transfinite constraints correctly
net.write("output.msh")        # mesh + write
net.mesh(dim=3)                # mesh only (then use m.write() separately)

# m.mesh() works for Straight/Bend/Elbow only — NOT for Reducer/SplinePipe/TJunction
m.mesh(dim=3)                  # only use if no manually-built volumes in network
```

`net.write()` / `net.mesh()` re-apply transfinite mesh constraints after the final GMSH synchronize — a required step for connectors that build volumes with `addVolume()` rather than `extrude()`.

---

## Junctions: DAG topology

Junctions return multiple outlet nodes. Subsequent connectors are attached to a specific node:

```python
net = Network(pipe, direction=[0, 1, 0], up=[0, 0, 1])
n_in = net.add(Straight(0.4, n_layers=4))

n_main, n_branch = net.add(n_in, TJunction(
    approach_length=0.2, branch_length=0.15, departure_length=0.2, branch_r=0.03
))

net.add(n_main,   Straight(0.4, n_layers=4))   # continue main run
net.add(n_branch, Straight(0.2, n_layers=3))   # branch leg
```

Physical groups are computed from the full DAG: `fluid_inlet` is the upstream face; `fluid_outlet` surfaces are all downstream outlets.

---

## Examples

Runnable examples in `hexmesh/examples/`:

| File | Demonstrates |
|---|---|
| `smooth_bend.py` | `Straight` + `Bend` |
| `miter_bend.py` | `MiterBend`, single and 3-cut |
| `insulated_pipe.py` | Multi-layer `PipeSpec` |
| `reducer_network.py` | `Reducer`, `Expander`, `Bend` hairpin |
| `simple_network.py` | `MiterBend` + `Bend` in sequence |
| `pipe_network.py` | Multi-branch network with DAG routing |
| `y_junction.py` | `YJunction` |
| `t_junction.py` | `TJunction` with `branch_r` |
| `spline_pipe.py` | `SplinePipe` S-bend and 3D curve |
| `stub_block_demo.py` | `TJunction` stub block internals |

Run any example from the repo root:

```bash
python -m hexmesh.examples.smooth_bend
```

---

## Mesh resolution guide

Cell count is controlled by three independent parameters:

| Parameter | Controls | Set on |
|---|---|---|
| `nang` | Angular resolution (cells around the pipe circumference) | `PipeSpec` |
| `nrad` | Radial resolution (cells across each material layer) | `.core()` / `.shell()` |
| `n_layers` | Axial resolution (cells along the pipe axis per connector) | Each connector |

All three are independent — you can refine one direction without changing the others.

Typical starting values for a single-layer pipe:

```python
PipeSpec(nang=6).core("fluid", radius=0.05, nrad=4)
Straight(length=0.4, n_layers=6)
```

This gives a 5-patch OH cross-section with 6×4 = 24 cells around the annulus and 6 axial layers — roughly 120 hex cells per `Straight(0.4)`.

---

## Cross-section topology (OH grid)

hexmesh uses a **5-patch O-H (butterfly) topology** for circular cross-sections:

```
      N
   NW / \ NE
  ───/───\───
 W | c_sq | E    ← centre square patch
  ───\───/───
   SW \ / SE
      S
```

One centre square patch + 4 outer arc quadrants (90° each). This avoids the singular pole point at the pipe centre that a purely O-grid would have, and produces well-conditioned hex cells at all radii.

---

## Physical groups naming convention

For a material layer named `"fluid"`:

| Physical group | Content |
|---|---|
| `fluid` | All fluid volumes |
| `fluid_inlet` | Inlet face(s) of the system |
| `fluid_outlet` | Outlet face(s) of the system |
| `fluid_wall` | Outer lateral boundary (wall or fluid/wall interface) |
| `fluid_to_pipe_wall` | Conformal interface to next layer (`pipe_wall`) |
