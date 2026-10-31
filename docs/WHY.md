# Why hexmesh?

For CFD engineers deciding whether hexmesh fits their pipe or duct
problem: what it does that other routes don't, the evidence, and when
to use something else.

## The problem

Pipe and duct networks look simple and mesh badly.

- **Straight runs and bends** are easy to sweep as hexes.
- **Junctions** are where it breaks down: tees, wyes, taps, transitions.
  - **Unstructured meshers** fill them with tetrahedra and pyramids, or
    with split hexes and polyhedra (snappyHexMesh, cfMesh).  The cells
    are badly aligned with the flow exactly where it separates and
    mixes.
  - **Hand-built block topologies** (blockMesh, ICEM CFD Hexa,
    Pointwise) give good hexes, but every junction is hours of manual
    blocking.  It is redone for each variant, which rules out parameter
    studies.
- **Conjugate heat transfer adds layers:** wall and insulation.  These
  must be conformal with the fluid, and stay conformal through every
  junction.  Most routes give up conformality there, or mesh the
  regions separately and map between them.

## What hexmesh does

You describe the network as fittings connected at named interfaces.
hexmesh then builds it as transfinite hex blocks:
- an **O-H cross-section**, with the same topology at every interface;
- each fitting filled between faces that already exist, so neighbours
  share faces and the mesh is **conformal by construction**, with no
  node merging (the rules: [DESIGN.md](../DESIGN.md)).

What that gives you:

| | |
|---|---|
| **All-hex in junctions** | Tees, wyes, laterals and duct taps have their own block layouts.  Walls, steel and insulation shells run through them. |
| **Exact walls** | Every wall node lies on the true surface: a torus for bends, the intersection ellipse at miters, an analytic projection at junctions.  Poiseuille Δp is within 0.03 % after extrapolation. |
| **Regions for CHT** | Fluid, steel and insulation are separate regions with conformal interfaces.  The OpenFOAM writer sets up patches, regions and `regionProperties`. |
| **A known cell count** | `Assembly.cell_count()` is exact before any geometry is built.  `validate(max_cells=…)` enforces a budget. |
| **Studies and surrogates** | Change a dimension and the node numbering stays: node *i* is the same point in every variant.  Fields map one-to-one, which reduced-order models and surrogates need.  `hexmesh.study` runs the sweep. |
| **Quality you can check** | Corner scaled Jacobian per fitting, a check before meshing (limits in `API.md`), and `checkMesh` in every validation case. |

## The evidence

- **The [gallery](GALLERY.md):** every example with its mesh, its quality
  numbers (min scaled Jacobian and where it is, SICN, aspect ratio) and
  its code.
- **Validation:** grid-convergence studies against exact solutions, DNS
  and (planned) experiments, with gates set before the runs.  Cases,
  categories and the coverage matrix:
  [GALLERY.md, Validation](GALLERY.md#validation).
- **Design records:** every design choice, the options rejected and the
  measurements behind it are in [decisions/](decisions/).  Fitting
  mathematics and sources: [RESEARCH.md](RESEARCH.md).

## When to use something else

hexmesh is for **networks of pipes and ducts**.  Use another tool for:
- **arbitrary CAD**: valve bodies, pump volutes, vessels with internals.
  Use snappyHexMesh, cfMesh or a commercial mesher;
- **junction types hexmesh doesn't have yet** (see the guide's
  [limitations](GUIDE.md#current-limitations)), unless you can wait;
- **adaptive refinement**: hexmesh meshes are structured, so refinement
  is global, by density parameters.  Doubling every density parameter
  gives 8× the cells;
- **very poor junction quality budgets**: the worst cells of a wye or a
  narrow duct tap have scaled Jacobians around 0.1–0.2.  That's fine for
  OpenFOAM (`checkMesh` passes), but check it against your solver.

## Coming

Planned work, with its design decisions:
- second-order export for spectral-element and high-order solvers;
- general branches (angled, offset);
- flow restrictions (orifice plates, meters);
- vascular networks.

The live list is [tasks/](tasks/README.md).
