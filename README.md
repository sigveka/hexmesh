# hexmesh

Structured all-hex meshes for CFD pipe networks, built on [GMSH](https://gmsh.info/).

Describe a network as a graph of fittings: straight runs, bends, elbows, miter
bends, reducers, spline pipes, tees and loop closures. hexmesh places and checks
it in pure Python, then builds a conformal hexahedral mesh for OpenFOAM or any
other finite-volume solver.

```
Straight → Bend → Straight → Tee → Straight
                              └──→ Elbow → Straight
```

All cells are hexahedra: no tetrahedra, no pyramids, no hanging nodes, and no
node merging. Neighbouring fittings share one face, so the mesh is conformal by
construction.

---

## Why structured hex?

- **Accuracy.** Cells aligned with the flow reduce numerical diffusion compared
  with tetrahedral meshes.
- **Efficiency.** For the same axial resolution you need roughly 5–10× fewer
  cells.
- **Solver compatibility.** Boundary conditions and wall functions work
  directly on pure-hex meshes.

---

## Installation

```bash
pip install gmsh numpy
pip install -e .              # from the repo root
pip install -e ".[io]"        # + scipy, for the bathymetry reader
```

Python ≥ 3.10. Developed and tested with GMSH 4.12.

---

## Quick start

```python
from hexmesh import Assembly, Bend, PipeSpec, Session, Straight

# 1. Cross-section: fluid core + pipe wall
pipe = (
    PipeSpec(nang=6)
    .core("fluid", radius=0.1, nrad=5)
    .shell("pipe_wall", dR=0.01, nrad=2)
)

# 2. Assembly: inlet at the origin, flowing along +x
with Session("elbow"):
    asm = Assembly(pipe, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.5, n_layers=10))
    asm.add(Bend(radius=0.3, angle=90, n_layers=12))
    asm.add(Straight(0.5, n_layers=10))

    asm.validate()                 # pure Python: raises before any geometry is built
    print(asm.cell_count())        # 6528, exact, before meshing
    asm.write("elbow.msh")         # build faces, fill, groups, mesh, write
    print(asm.check_quality())     # per-material minSICN report
```

To inspect a mesh, run `gmsh elbow.msh`. Use Tools → Clipping to see inside,
and Tools → Visibility to show individual patches.

---

## How it works

hexmesh follows a fixed pipeline. The full rules are in [DESIGN.md](DESIGN.md).

| Step | What | GMSH? |
|---|---|---|
| Intent | `add()` / `close()` record fittings and the interfaces between them | no |
| Place | each fitting computes its outlet frames from its inlet frame | no |
| Validate | port types, fitting geometry, cell budget | no |
| Faces | every interface face is built exactly once | yes |
| Fill | each fitting fills hex blocks between its existing port faces, in any order | yes |
| Groups | physical groups derived from the graph | yes |
| Mesh | transfinite meshing; nothing is merged | yes |

Accuracy comes from placing nodes on exact curves, not from OCC surfaces.
Bends, miter bends, reducers and spline pipes place one station per axial layer,
so every wall node lies on an exact station curve. Miter cuts are the exact
ellipse where the two pipes meet. There are two known exceptions:
- the interior wall nodes of a multi-layer `Straight` lie on a filled surface,
  up to 0.7 % of the radius off. This is an open follow-up
  ([task 0012](docs/tasks/0012-miter-bend-and-elbow.md#outcome));
- the tee's wall nodes are 2–5 % off, a deviation listed in DESIGN.md §9.

---

## Fittings

| Fitting | Use |
|---|---|
| `Straight(length, n_layers, axial_grading=1)` | Straight run |
| `Bend(radius, angle, n_layers, roll=0, axial_grading=1)` | Circular-arc bend. `roll` (degrees) turns the bend plane about the pipe axis; 0 bends toward `up` |
| `Elbow(angle=90, schedule="long", n_layers=8, roll=0, axial_grading=1)` | Butt-weld elbow: a `Bend` with radius 1.5 D (`"long"`) or 1 D (`"short"`), D = outer diameter |
| `MiterBend(radius, angle, n_cuts=1, n_layers=2, roll=0)` | Segmented bend of straight pieces. Same ports as `Bend(radius, angle)`; each cut turns ≤ 90° |
| `Reducer(outlet, length, n_layers, axial_grading=1)` | Concentric cone to another radius (reducer or expander). Only radii may change |
| `SplinePipe(points, n_layers, end_tangent=None, axial_grading=1)` | Pipe along a cubic spline; `points[0]` is the inlet position |
| `Tee(run_length, branch_length, branch_radius, n_run=3, n_branch=3, n_turn=2)` | Perpendicular side-branch tee, block layout; returns `(main, branch)` |
| `Closure(n_layers, tension=1.0, axial_grading=1)` | Smooth run between two existing interfaces, used with `close()` for loops |

### Building a network

```python
asm = Assembly(pipe, direction=[1, 0, 0], up=[0, 0, 1])

# add(fitting) continues from the tail
asm.add(Straight(0.4, n_layers=8))

# multi-outlet fittings return one interface per outlet
main, branch = asm.add(Tee(run_length=0.2, branch_length=0.25, branch_radius=0.06))

# add(interface, fitting) branches from any interface and returns its outlet
bend = asm.add(main, Bend(radius=0.3, angle=90, n_layers=12, roll=90))

# names= names the outlet; open ends become patches such as "fluid_main_end"
asm.add(bend, Straight(0.3, n_layers=6), names=["main_end"])
asm.add(branch, Straight(0.3, n_layers=6), names=["branch_end"])

# close(source, target, fitting) joins two open interfaces, e.g. a loop:
# asm.close(asm.interfaces[-1], asm.inlet, Closure(n_layers=24))
```

Validation runs before anything is built. It rejects, with a message naming the
fitting:
- mismatched cross-sections at an interface;
- bends tighter than the pipe;
- miter cuts outside 1–90°;
- reducers that change more than radii;
- closures that would kink;
- an assembly over `validate(max_cells=...)`.

---

## Cross-section specification

```python
from hexmesh import PipeSpec

# Bare pipe (fluid only)
PipeSpec(nang=6).core("fluid", radius=0.05, nrad=4)

# Fluid + pipe wall
PipeSpec(nang=6).core("fluid", radius=0.05, nrad=4).shell("pipe_wall", dR=0.005, nrad=2)

# Fluid + wall + insulation, refined toward the wall
(PipeSpec(nang=6)
 .core("fluid", radius=0.05, nrad=4)
 .shell("steel", dR=0.005, nrad=2)
 .shell("insulation", dR=0.03, nrad=4, mprg=1.2))
```

- `nang` sets the cells along each 90° arc of the cross-section. It is shared by
  every layer.
- `nrad` sets the cells across each layer.
- `mprg` is the radial progression. Values above 1 refine toward the inner side
  of the layer.
- `PipeSpec(mbmp=...)` sets an angular bump.
- `first_cell=` sets the radial height of the cell at a layer's outer wall,
  in place of `mprg`:

  ```python
  PipeSpec(nang=6).core("fluid", radius=0.05, nrad=12, first_cell=2e-4)
  ```

  This is a geometric height, not y⁺, which also depends on the flow.
  In a shell the height is exact all the way round. In the core it is the
  largest wall cell: it is reached at mid-arc, where the core is thickest,
  and the cells at the four corners are about 0.81× it.

Each layer becomes its own physical volume, and neighbouring layers meet at
conformal material interfaces, which is what conjugate heat transfer needs.
Every layer is built from a 5-patch O-H cross-section:

```
      N
   NW / \ NE
  ───/───\───
 W | c_sq | E    ← centre square patch
  ───\───/───
   SW \ / SE
      S
```

The centre square avoids the singular pole a pure O-grid would have.

---

## Resolution and cell count

| Parameter | Controls | Set on |
|---|---|---|
| `nang` | cells per 90° arc (around the pipe) | `PipeSpec` |
| `nrad` | cells across each layer | `.core()` / `.shell()` |
| `n_layers` | cells along the axis, per fitting | each fitting |

The mesh is structured, so its size is known exactly before meshing. A
cross-section has `nang² + 4·nang·Σnrad` cells, multiplied by each fitting's
axial layers:

```python
asm.validate(max_cells=2_000_000)   # raises AssemblyError over budget
asm.cell_count()                    # total, without GMSH
asm.cell_counts()                   # per fitting
```

**Axial grading.** `axial_grading` is the ratio of consecutive axial cell
lengths along a fitting, inlet to outlet. Above 1, cells are finest at the
inlet (for example after a tee); below 1, finest at the outlet. It doesn't
change the cell count. `MiterBend` and `Tee` are not graded yet.

```python
asm.add(Straight(1.0, n_layers=20, axial_grading=1.1))   # first cell at the inlet
asm.add(Bend(radius=0.3, angle=90, n_layers=12, axial_grading=0.9))
```

> **Refinement is cubic.** Doubling `nang`, every `nrad` and every `n_layers`
> doubles the nodes in each direction, which gives **8× the cells** in 3-D. If
> you come from unstructured meshing, expect this rather than a linear increase.

---

## Physical groups

For a layer named `"fluid"`:

| Physical group | Content |
|---|---|
| `fluid` | all fluid volumes |
| `fluid_inlet` | the inlet face (`Assembly(..., inlet_name=...)`) |
| `fluid_outlet` | the only other open end, when there is just one |
| `fluid_<name>` | an open end named with `add(..., names=[...])`; unnamed extra ends are `fluid_port<N>` |
| `fluid_to_pipe_wall` | conformal interface to the next layer |
| `pipe_wall_wall` | outer wall of the outermost layer |

Every boundary face belongs to exactly one group. A closed loop has no
inlet or outlet groups.

---

## Reading plant data

```python
from hexmesh.io.readers.pcf import read_pcf

net = read_pcf("line.pcf")                       # Isogen PCF, mm → m
asm = net.to_assembly(pipe)                      # or pipe=lambda bore: PipeSpec(...)
```

`to_assembly` maps the PCF components to fittings:
- pipes, flanges and valves become `Straight`;
- elbows become `Bend` in their own plane;
- concentric reducers become `Reducer`.

It checks every component against its PCF end points and raises
`AssemblyError` naming the component on any gap; nothing is snapped.

Pipeline routes from `hexmesh.io.readers.bathymetry.read_bathymetry` bend at
their vertices without fittings, so build them with
`to_assembly(pipe, kinks="spline")`.

---

## Examples

Each example writes `<name>.msh` to the current directory:

```bash
python3 -m hexmesh.examples.smooth_bend
```

| Example | Shows |
|---|---|
| `smooth_bend` | `Straight` + `Bend` |
| `miter_bend` | single 90° miter joint and a 3-cut segmented elbow |
| `insulated_pipe` | three material layers, long-radius `Elbow` |
| `reducer_network` | reducer, 180° hairpin, expander |
| `tee` | `Tee` with a bend on the main run; named outlets |
| `loop` | closed, non-planar loop with `Closure` |
| `spline_pipe` | 3-D spline |
| `pipe_network` | header with two tees, branches built from interfaces |

---

## Current limitations

- **Tee:** single-layer specs, perpendicular and centred branch, branch radius
  below the main radius.
- **No Y-junction (wye) yet.** The design is still open
  ([docs/RESEARCH.md](docs/RESEARCH.md) §4).
- **Circular sections only.** Rectangular ducts and circle-to-square
  transitions are planned (decision 0009).
- **Layer changes:** insulation can't start or stop inside a fitting yet
  (decision 0006).

Design decisions and planned work: [docs/decisions/](docs/decisions/) and
[docs/tasks/](docs/tasks/).
