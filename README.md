# hexmesh

Structured all-hex meshes for CFD pipe networks, built on [GMSH](https://gmsh.info/).

Describe a network as a graph of fittings: straight runs, bends, elbows, miter
bends, reducers, duct transitions, spline pipes, tees, wyes and loop closures.
hexmesh places and checks it in pure Python, then builds a conformal
hexahedral mesh for OpenFOAM or any other finite-volume solver.

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

To find the fitting that holds the worst cell, group by fitting and use
a shape metric:

```python
report = asm.check_quality("scaled_jacobian", threshold=0.6, by="fitting")
print(report.worst_region.name)    # e.g. "#3 Tee"
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
- the tee's wall nodes are 2–5 % off, a deviation listed in DESIGN.md §9;
- the wye's junction wall nodes are up to about 20 % of the radius off, and
  its crotch is rounded (prototype, [task 0030](docs/tasks/0030-wye-prototype.md)).

---

## Fittings

| Fitting | Use |
|---|---|
| `Straight(length, n_layers, axial_grading=1, stack_changes=())` | Straight run. `stack_changes` ends or starts outer layers inside it (see *Insulation gaps*) |
| `Bend(radius, angle, n_layers, roll=0, axial_grading=1, stack_changes=(), toward=None)` | Circular-arc bend. `roll` (degrees) turns the bend plane about the pipe axis; 0 bends toward `up`. Or `toward=(x, y, z)`: the absolute direction to turn toward |
| `Elbow(angle=90, schedule="long", n_layers=8, roll=0, axial_grading=1, toward=None)` | Butt-weld elbow: a `Bend` with radius 1.5 D (`"long"`) or 1 D (`"short"`), D = outer diameter |
| `MiterBend(radius, angle, n_cuts=1, n_layers=2, roll=0, toward=None)` | Segmented bend of straight pieces. Same ports as `Bend(radius, angle)`; each cut turns ≤ 90° |
| `Reducer(outlet, length, n_layers, axial_grading=1)` | Concentric cone to another radius (reducer or expander). Only radii may change |
| `Transition(outlet, length, n_layers, axial_grading=1)` | Circle ↔ rectangle, or rectangle ↔ rectangle; equal counts per side |
| `SplinePipe(points, n_layers, end_tangent=None, axial_grading=1)` | Pipe along a cubic spline; `points[0]` is the inlet position |
| `Tee(run_length, branch_length, branch_radius, n_run=3, n_branch=3, n_turn=2, roll=0, toward=None)` | Perpendicular side-branch tee, block layout; returns `(main, branch)`. The branch points along `up`, rolled by a multiple of 90°, or `toward` a direction |
| `Wye(angle, run_length, branch_length, n_run=3, n_branch=3, n_split=3, roll=0, toward=None)` | Symmetric Y-junction, block layout; returns `(left, right)`. `roll` (a multiple of 90°) turns its plane |
| `Closure(n_layers, tension=1.0, axial_grading=1)` | Smooth run between two existing interfaces, used with `close()` for loops |

### Building a network

```python
asm = Assembly(pipe, direction=[1, 0, 0], up=[0, 0, 1])

# add(fitting) continues from the tail
asm.add(Straight(0.4, n_layers=8))

# multi-outlet fittings return one interface per outlet; toward= points
# the branch in an absolute direction (here sideways, +y)
main, branch = asm.add(Tee(run_length=0.2, branch_length=0.25, branch_radius=0.06,
                           toward=(0, 1, 0)))

# add(interface, fitting) branches from any interface and returns its outlet
bend = asm.add(main, Bend(radius=0.3, angle=90, n_layers=12, toward=(0, -1, 0)))

# names= names the outlets (a list, or a dict by port name: a tee has
# "main" and "branch"); open ends become patches such as "fluid_main_end"
asm.add(bend, Straight(0.3, n_layers=6), names=["main_end"])
asm.add(branch, Straight(0.3, n_layers=6), names={"outlet": "branch_end"})

# every angle is in degrees, including PipeSpec(rot=...)

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

### Rectangular ducts

```python
# 2:1 duct, 0.2 wide (along the frame's right) by 0.1 high (along up)
PipeSpec(nang_w=8, nang_h=4).core("air", half_w=0.1, half_h=0.05, nrad=3)
```

A duct uses the same O-H layout with straight sides: a centre rectangle and
a ring of uniform thickness, with `nang_w` cells along the width and
`nang_h` along the height. Ducts are single-layer for now, and run through
`Straight`, `Bend`, `MiterBend`, `SplinePipe` and `Closure`.
`Transition` joins a duct to a circular pipe, or to a duct of another size,
when the counts per side match: a circle's `nang` equals the duct's
`nang_w` and `nang_h`.

`up` decides which side is the height, and a bend's `roll` decides its
plane. `Bend(..., roll=0)` turns toward `up`, across the height: the
**easy way** for a wide, flat duct. `roll=90` turns across the width: the
**hard way**. Its radius is checked against the half-width instead of
the half-height. A 2:1 duct only matches itself turned by 180°, not 90°,
so loops close modulo 180°.

---

## Resolution and cell count

| Parameter | Controls | Set on |
|---|---|---|
| `nang` | cells per 90° arc (around the pipe) | `PipeSpec` |
| `nrad` | cells across each layer | `.core()` / `.shell()` |
| `n_layers` | cells along the axis, per fitting | each fitting, or from `Assembly(axial_cell=…)` |

The mesh is structured, so its size is known exactly before meshing. A
cross-section has `nang² + 4·nang·Σnrad` cells, multiplied by each fitting's
axial layers:

```python
asm.validate(max_cells=2_000_000)   # raises AssemblyError over budget
asm.cell_count()                    # total, without GMSH
asm.cell_counts()                   # per fitting
```

**Axial cell size.** Instead of `n_layers` on every fitting, give the
assembly a target axial cell length and leave `n_layers` out: each sweep
fitting gets `ceil(L / axial_cell)` layers, `L` its centreline length, or
more if it needs more to be valid (a spline's 30° turn per layer, a
profiled reducer's chord tolerance, a bend's < 180° per layer). The
resolved count is stored in the fitting and in the saved file. An
explicit `n_layers` always wins; `Elbow` and `MiterBend` have defaults
(8 and 2), so pass `n_layers=None` to them. `Tee` and `Wye` keep their own
counts.

```python
asm = Assembly(pipe, direction=[1, 0, 0], up=[0, 0, 1], axial_cell=0.05)
asm.add(Straight(0.5))                         # 10 layers
asm.add(Bend(radius=0.3, angle=90))            # 0.471 / 0.05 → 10 layers
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

**Convergence studies.** `asm.refined(k)` returns a copy at k× the
resolution in every direction: `nang`, every `nrad` and every axial count
× k, and every grading ratio replaced by its k-th root, so each coarse cell
splits into k cells of the same growth. It has **k³× the cells**, and the
original is unchanged.

```python
levels = [asm, asm.refined(2), asm.refined(4)]   # 1×, 8×, 64× the cells
```

A spec built with `first_cell=` keeps its resolved progression, so the
refined first cell is smaller.

---

## Physical groups

For a layer named `"fluid"`:

| Physical group | Content |
|---|---|
| `fluid` | all fluid volumes |
| `fluid_inlet` | the inlet face (`Assembly(..., inlet_name=...)`) |
| `fluid_outlet` | the only other open end, when there is just one |
| `fluid_<name>` | an open end named with `add(..., names=[...])`; unnamed extra ends are `fluid_port<N>` |
| `interface_fluid_pipe_wall` | conformal interface to the next layer (inner, then outer material) |
| `pipe_wall_wall` | outer wall, named after the layer that is outermost there |
| `insulation_end` | end faces of a layer that stops or starts inside a fitting |
| `pipe_wall_wall_<fitting>` | with `mesh(walls_by_fitting=True)`: the outer wall of one fitting, in place of `pipe_wall_wall` (likewise `insulation_end_<fitting>`). `<fitting>` is its `add(..., label=...)` or `<Type><index>` (`Bend3`) |

Every boundary face belongs to exactly one group. A closed loop has no
inlet or outlet groups.

### Insulation gaps

Outer layers can stop and start inside a `Straight` or `Bend`, e.g. at a
flange or a support.  `stack_changes` lists `(i, spec)` pairs: from axial
cell `i` on, the stack is `spec`.

```python
bare = PipeSpec(nang=4).core("fluid", radius=0.1, nrad=3).shell("pipe_wall", dR=0.01, nrad=2)
insulated = PipeSpec(nang=4).core("fluid", radius=0.1, nrad=3) \
    .shell("pipe_wall", dR=0.01, nrad=2).shell("insulation", dR=0.03, nrad=2)

asm = Assembly(insulated)
asm.add(Straight(1.0, n_layers=10, stack_changes=((3, bare), (7, insulated))))
```

Cells 3–6 are bare.  The rules:
- only outermost layers may stop or start;
- the remaining layers keep their names, radii, `nrad` and grading (to
  change those, use a `Reducer`);
- changes sit inside the fitting (`0 < i < n_layers`), never at a port.

The outlet port carries the last stack.  The cell count counts each layer
only where it is present.

### OpenFOAM

```python
asm.write_openfoam("pipe.msh")    # MSH 2.2 ASCII, for gmshToFoam
```

```bash
gmshToFoam pipe.msh
splitMeshRegions -cellZones -overwrite   # multi-material (CHT) only
```

Each material becomes a cellZone, and after the split a region with
`mappedWall` interfaces to its neighbours.  `write_openfoam` leaves the
`interface_*` groups out of the file by default, because the split
rebuilds every interface as a `mappedWall` pair itself;
`interfaces=True` keeps them as faceZones.

`gmshToFoam` writes every patch as type `patch`.  `write_openfoam` also
writes `pipe.roles.json`, the role of each group taken from the network
(wall, open end, interface, volume), and one call retypes the walls:

```python
from hexmesh.io.writers.openfoam_boundary import apply_boundary_roles_to_regions
apply_boundary_roles_to_regions("case", "pipe.roles.json")   # every region, or the unsplit mesh
```

Open ends stay `patch`, and the split's `mappedWall` interfaces are left
alone.  Verified with OpenFOAM v1912; details in
[docs/integrations/openfoam.md](docs/integrations/openfoam.md).

---

## Inlet and outlet runs

CFD boundary conditions want straight pipe before and after the region of
interest.  Add it in diameters, before building:

```python
asm.extend_open_ends(upstream=5, downstream=10)   # 5 D before, 10 D after each outlet
```

The diameter is that of each end's flow core (for a duct, the hydraulic
diameter 4A / P).  The patch names
(`fluid_inlet`, `fluid_outlet`, named ends) stay the same.

## Starting at a drum nozzle

Declare the drum and its nozzles once, and the nozzle poses follow:

```python
from hexmesh import Drum, Nozzle, OnShell, OnHead

drum = Drum("D101", diameter=2.0, length=6.0, axis=[1, 0, 0], up=[0, 0, 1],
            nozzles=[Nozzle("N1", pipe, OnShell(axial=1.5, angle=0, projection=1.4)),
                     Nozzle("N2", pipe, OnHead("second", offset=0.0, angle=0, projection=0.8))])
asm = Assembly.from_nozzle(drum, "N1")   # inlet patch fluid_D101_N1
asm.add(Straight(0.5, n_layers=10))
```

`drum.validate()` (run by `from_nozzle`) rejects nozzles whose face is
inside the shell or head, nozzles that are too large, and footprints that
overlap.  The drum itself is not meshed.

## Saving a network

An assembly can be saved as a JSON description of how it was built, and
loaded again, with no GMSH involved:

```python
asm.save("network.json")
asm = Assembly.load("network.json")   # same interfaces, same mesh
```

The file lists the inlet, then every fitting in order with its parameters.
Edit a parameter there and everything downstream moves with it, which
suits parametric studies.  Lengths are in your unit, unconverted.

## Reading plant data

```python
from hexmesh.io.readers.pcf import read_pcf

net = read_pcf("line.pcf")                       # Isogen PCF; units from its header
asm = net.to_assembly(pipe)                      # or pipe=lambda bore: PipeSpec(...)
```

The reader follows the PCF reference guide.  Units come from
`UNITS-CO-ORDS` and `UNITS-BORE`.  `bore` is the **nominal** size in
metres (4" → 0.1016 m), not an inside diameter.

`to_assembly` maps the PCF components to fittings:
- pipes, flanges, valves and caps become `Straight`;
- elbows and bends become `Bend`, from their corner point, checked against
  `ANGLE` and `BEND-RADIUS`;
- concentric reducers become `Reducer`;
- welds, couplings and gaskets up to 1/16" long are absorbed into the
  neighbouring straight runs instead of being meshed as slivers.

It checks every component against its PCF end points and raises
`AssemblyError` naming the component on any gap; nothing is snapped.  The
tolerance scales with the model (at least 0.11").

Pipeline routes from `hexmesh.io.readers.bathymetry.read_bathymetry` bend at
their vertices without fittings, so build them with
`to_assembly(pipe, kinks="spline")`.

---

## Examples

The examples are grouped by what they illustrate.  Each writes
`<name>.msh` to the current directory:

```bash
python3 -m hexmesh.examples.fittings.smooth_bend
```

**[docs/GALLERY.md](docs/GALLERY.md)** shows every example with images,
cell counts and quality metrics, and the validation cases.  Regenerate it
with `python3 docs/gallery/build.py` (needs `vtk`).

| Category | Examples | Shows |
|---|---|---|
| `fittings` | `smooth_bend`, `miter_bend`, `spline_pipe`, `reducer_network`, `tee`, `wye`, `loop` | one building block each: bends, reducer, junctions, `Closure` |
| `sections` | `insulated_pipe`, `insulated_route`, `graded_bend`, `rect_duct`, `duct_transition` | what runs through the pipe: layer stacks, wall and axial grading, rectangular ducts, `Transition` |
| `networks` | `pipe_network`, `pipe_rack`, `distribution_tree`, `bifurcation_tree`, `skewed_network` | composing fittings: routes, branches, trees, any orientation |
| `applications` | `drum_nozzle`, `hvac_supply`, `cooling_channels` | equipment nozzles, ventilation ducting, cooling channels |

---

## Current limitations

- **Tee:** single-layer specs, perpendicular and centred branch, branch radius
  below the main radius.
- **Wye (prototype):** single-layer specs, equal daughters with the inlet's
  spec, coplanar and symmetric, angle 30°–120°. Quality is measured, not
  yet bounded: min scaled Jacobian about 0.1 (decision 0017).
- **Rectangular ducts:** single-layer only (no duct wall or insulation
  shells yet); no tee or elbow for ducts. `Transition` needs equal
  counts per side and single-layer specs.
- **Layer changes:** insulation can't start or stop inside a fitting yet
  (decision 0006).

Design decisions and planned work: [docs/decisions/](docs/decisions/) and
[docs/tasks/](docs/tasks/).
