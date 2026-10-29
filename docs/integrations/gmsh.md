# gmsh (with OpenCASCADE)

## Role

**Backend.**  Pipeline steps 4–7 (DESIGN §5): build interface faces once,
fill fittings, write physical groups, and generate the transfinite hex
mesh.  Steps 1–3 must never call gmsh (DESIGN P3/P4).

## Versions

| gmsh | OCC | Source | Status |
|---|---|---|---|
| 4.12.1 | 7.6.3 | apt (`python3-gmsh`, `libgmsh4.12t64`, `gmsh-doc`), installed 2026-03-28 | **Tested**: the assembly suite runs here |
| 4.15.2 | bundled | PyPI wheel, scratch venv | Tried only for the legacy Y-junction (see quirks) |

To support a new version, the conformance kit
(`tests/test_fitting_conformance.py`) and the assembly tests must pass
unchanged.  Record the result here.

The gmsh version is **not pinned** in packaging.  Consider pinning it,
because OCC behaviour differs between versions (see quirks).

## Features used

Only the assembly path (`hexmesh/assembly/`, `hexmesh/faces/`) exists; the
legacy connectors were deleted in task 0017 (decision 0004).

- **Geometry (`gmsh.model.occ`):**
  - points and curves: `addPoint`, `addLine`, `addCircleArc`,
    `addEllipseArc`, `addSpline`, `addBSpline`;
  - surfaces: `addCurveLoop`, `addPlaneSurface`, `addSurfaceFilling`,
    `addBSplineFilling`;
  - volumes: `addSurfaceLoop`, `addVolume`;
  - housekeeping: `remove`, `synchronize`.
- **Topology queries (`gmsh.model`):** `getBoundary`, `getAdjacencies`,
  `getEntities`, `getType`, `getParametrizationBounds`, `getValue`.
- **Meshing (`gmsh.model.mesh`):** `setTransfiniteCurve` (with
  `meshType`/`coef` since task 0000), `setTransfiniteSurface`,
  `setTransfiniteVolume`, `setRecombine`, `generate`, `getElements`,
  `getElementQualities`.
- **Groups and output:** `addPhysicalGroup`, `setPhysicalName`,
  `gmsh.write`.

Deliberately **not** used, because DESIGN P2 forbids it: `occ.fragment`,
`removeDuplicateNodes`, bounding-box entity queries.

## Known quirks

### OCC `getBoundary` returns curve end points in tag order — *verified*
For a curve, `gmsh.model.getBoundary([(1, c)], oriented=False)` lists its
two end points in **ascending tag order**, not start → end.  Read the
start from the curve's own parametrisation instead: the end point at the
lower parameter bound.  Implemented in `corners.curve_endpoints`
(`hexmesh/assembly/corners.py`).  Found during task 0000.  Matters for
orienting progressions (tasks 0000–0002).

### Re-applying transfinite curves overrides earlier gradings — *verified*
`setTransfiniteCurve(tag, n)` without `meshType`/`coef` resets the curve
to uniform.  Face builders set radial progressions, and `Assembly.mesh()`
used to re-apply every curve as `(tag, n)`, which silently dropped
`mprg`.  Measured: last/first radial cell ratio 1.000 for `mprg = 1.3`.
Fixed in task 0000: one record per curve, and conflicting records raise.

### Construction points become stray mesh nodes — *verified*
Face builders leave helper points (arc centres) that bound nothing.  Left
in the model, they become isolated mesh nodes.  `Assembly.fill` removes
every 0-D entity with no adjacencies after filling (`assembler.py`).

### `occ.fragment()` is OCC-version-dependent — *verified*, legacy only
- 4.12.1 / OCC 7.6.3: fragment on the legacy Y-junction fails with "Could
  not fix wire in surface N", whether `healShapes` is on or off.
- 4.15.2: fragment succeeds but renumbers entities, so bbox-based tag
  recovery goes stale.  The mesh comes out as tets and prisms, with zero
  hexes.

Cause of the 10 `TestYJunctionQuality` failures, which were removed with
the legacy code in task 0017 (last legacy commit: tag `legacy-final`).  It is the reason
behind DESIGN P2, and the wye is being rebuilt as a block layout instead.

### Filled OCC surfaces deviate from true geometry — *verified*
About 3 % of the radius on a 30° bend slab, and about 21 % on a 90° slab
(DESIGN §6).  Hence "exactness lives in curves and nodes": every node sits
on an exact curve, and filled surfaces only carry faces between them.

**Transfinite interior nodes land on the filled surface, not on the
interpolated cylinder.**  This applies to a straight slab with several
axial layers.
- **Setup:** the side surface is `addSurfaceFilling` between two exact 90°
  arcs and two straight axial lines, exactly a quarter cylinder.
- **What happens:** the interior wall nodes are placed on the OCC plate,
  which sags up to **1.08 % of R** (at ~30° from a corner).
- **Independent of refinement:** the same 0.98922 R minimum at `nang` 6
  and 24, and at 16 axial layers.  It is a surface-shape error, not a
  resolution error.
- **Exact alternatives:** `addBSplineFilling(loop, type="Stretch")` (the
  ruled `_ruled` that miter slabs use) puts every wall node on the
  cylinder to 4e-16 R, as does one station per axial layer.  Min SICN is
  unchanged in both cases.
- **Consequence (task 0020):** laminar pipe flow through `Straight` runs
  had a Δp error stuck at +2.6 %.  The sagged section's area accounts for
  it within 0.1 %.
- *Verified* 2026-10-26, gmsh 4.12.1.
- **Fixed (task 0025, 2026-10-26):** every straight slab now uses the
  ruled `addBSplineFilling(type="Stretch")` side surfaces.  Wall and
  interface nodes of every conformance-kit case lie on their analytic
  surface to ≤ 2.2e-15 R, where they were 4.0–6.9e-3 R off before.  Block
  layouts (`blocks.py`) use the same ruled filling for arc/line/arc/line
  faces, which also puts the tee's run-wall nodes on the cylinder.

### `Progression` nodes are ~1e-9 L off the closed form — *verified*
4.12.1.  `setTransfiniteCurve(c, n + 1, "Progression", q)` on a straight
line of length L puts node i at L(qⁱ − 1)/(qⁿ − 1) only to about
**1e-9 L** (1.2e-9 for n = 5, q = 1.3; 9.7e-10 for n = 10, q = √1.3; the
same for L = 1, 0.3, 0.1).  Uniform curves (q = 1) are exact to 1e-16.
Presumably the nodes come from numerically integrating the spacing law.
Consequence: a mesh and its `refined(k)` agree at the coarse nodes only to
~1e-9 L on graded curves, and transfinite interiors inherit it (task 0026;
`tests/test_refined.py` gates at 1e-8 R).  Measured 2026-10-26.

### Transfinite volumes need exactly 5 or 6 bounding surfaces — *verified*

- gmsh 4.12.1, 2026-10-27, task 0030.
- A hex whose top face is split into two surfaces, with explicit corners
  on both `setTransfiniteSurface` (for the 5-curve side faces) and
  `setTransfiniteVolume`, fails at `generate(3)` with "Transfinite
  algorithm only available for volumes bounded by 5 or 6 surfaces".
- Surfaces allow more than 4 boundary curves when the corners are given;
  volumes do not allow more than 6 faces.  A block face cannot be shared
  half-and-half by two neighbouring blocks.  Every block face must be a
  whole face of exactly one neighbour, so a split between two blocks has
  to run through the whole layout.
- Reproducer: `split_face.py` in the task 0030 notes.

### Filling choices for long curved block faces — *verified*

- gmsh 4.12.1 / OCC 7.6.3, 2026-10-27, task 0030 (wye).  The faces are
  four-sided, bounded by splines, arcs and degree-1 B-splines, and span
  2–3 R.
- **Plate (`addSurfaceFilling`)** sags up to **0.66 R** inside the
  intended wall.  The fillings of mirror-image loops are not mirror
  images: surface nodes differ by up to 3 % of R, while curve nodes agree
  to 6e-15 R.
- **Plate with `pointTags`** (points pushed onto the wall) is fragile.
  OCC sometimes rebuilds a boundary edge as new curves with no end points,
  which breaks conformity ("curve N has 0 end points" in our corner
  lookup).  Denser constraint grids made it worse: inverted cells at
  5 × 5, "Curve loop is not closed" at 9 × 9.
- **`addBSplineFilling(type="Coons")`** fails with "GeomFill_BSplineCurves:
  invalid filling style".
- **`addBSplineFilling(type="Curved")`** and **`"Stretch"`** both work.
  Mirror-image loops give mirror-image surfaces (nodes agree to 1e-14 R).
  `Stretch` gave the better cells (min scaled Jacobian 0.43 vs 0.27–0.38
  at nang 6) and is what the wye uses.  Neither follows a curved wall
  closely: about ±20 % of R on the wye's patches.

### Wall surfaces through analytic points — *verified*

gmsh 4.12.1 / OCC 7.6.3, 2026-10-29, task 0051 (tee and wye wall faces).
The goal: a face bounded by the layout's existing curves whose interior
lies on an analytic wall.

- **`addBSplineSurface(…, wireTags=[loop], wire3D=True)`** (and
  `addTrimmedSurface`) is exact, but **not conformal**.
  - The surface interpolated a projected 17 × 17 grid.  Interior nodes
    were within 1e-7 R of a cylinder on an isolated patch, against 3e-3
    for Stretch filling.
  - OCC projects the wire onto the surface and bounds the face by **new
    curves**: in the tee, surface 117 had curves 157–160, not the
    layout's.  Its neighbours don't share them, they get no transfinite
    constraint, and the volume fails ("Incompatible surface 117 in
    transfinite volume 7").
  - With the patch ending exactly on the wire: "Could not fix wire in
    surface N" or "Could not create wire".
- **Plate with `pointTags`** (Coons grid between the edges, interior 7 × 7
  points projected onto the wall, `tol3d` 1e-6 × face size,
  `maxDegree` 8, `maxSegments` 9) keeps the loop's curves.
  - **Tee:** reliable.  Wall nodes within 3.0e-4 R (r/R 0.5) and
    1.3e-4 R (r/R 0.9) at `nang` 4 and 8, including the oblique kit
    case, against 2.6–3.2 % before.  Cell quality unchanged; build +0.3 s
    per tee.  `BlockLayout._wall_surface`, used by `Tee`.
  - **Wye:** erratic, as in task 0030.  The best setting left 1–3 % of R
    on the hub's top and bottom and 5–9 % on the crotch face, which
    contains the crease.  Mirror-image faces differed: 0.0006 R vs
    0.46 R.  Other settings: 13 × 13 points, `numIter` 6, and
    `numPointsOnCurves` 40 failed to build; `degree` 2 and `anisotropic`
    didn't help.  Not used for the wye: its nodes are projected instead
    (next section).

### Moving surface nodes before volume meshing — *verified*

gmsh 4.12.1, 2026-10-29, task 0051 (decision 0029).  `Assembly.mesh()`
runs `generate(2)`, moves junction wall nodes onto the analytic wall with
`mesh.setNode`, then `generate(3)`.

- **Transfinite volumes use the moved positions.**  After `generate(3)`
  every projected wye and tee wall node is on the analytic wall to
  1e-15 R, and the volume interior follows (no folded cells at `nang` 4–32).
- **The OCC surfaces stay as built**: Stretch fillings (wye) or plates
  (tee), 3e-4 to 16 % of R off the wall.  Anything that reads the geometry
  (`getValue`, `getClosestPoint`, CAD export) sees those, not the mesh.
- **`setNode(tag, xyz, [])` keeps the old parametric coordinates**, which
  no longer match the node.  `getNode` returned the same (u, v) before
  and after the move on a cylinder face; passing new (u, v) is the only
  way to change them.  Anything that re-evaluates nodes from (u, v) on the
  OCC surface (mesh optimisation, `Mesh.SecondOrder` with curved
  elements) would undo or distort the projection.
- **`generate(3)` renumbers the surface nodes** in the assembly
  (`Mesh.Renumber` is 1 by default): of 3161 nodes after projection, 48
  kept both tag and position (60° wye kit model, `nang` 8).  A single
  OCC cylinder kept all its tags.  Match nodes across volume meshing by
  position (`Assembly._check_projection` does).

### Non-uniform `affineTransform` renumbers points and curves — *verified*
4.12.1 / OCC 7.6.3.  `occ.affineTransform` with a non-uniform scale keeps
the surface tags but gives the transformed surface's points and curves
new tags.  Tag-based corner identity (DESIGN §6.1) then breaks.  Found in
task 0012 (stretched miter cut faces).  The fix: build stretched faces
directly, through the `stretch=` argument of the face builders
(`faces/_gmsh_helpers.add_conic_arc`).

### `addEllipseArc` rejects arcs symmetric about the major axis — *verified*
4.12.1 / OCC 7.6.3.  `occ.addEllipseArc(start, centre, major, end)` fails
when the end points are mirror images about the major axis, which is
exactly the case for a stretched O-H arc.  Found in task 0012.  Stretched
arcs are built instead as exact rational quadratic B-splines: the
circle-arc NURBS with stretched control points, middle weight
√((1 + cos Δ)/2) (`add_conic_arc`).

### `occ.getBoundingBox` pads by the OCC tolerance — *verified*
4.12.1 / OCC 7.6.3.  For a point, the box corners are about 1e-7 off its
coordinates.  Reading a coordinate from either corner put points 3e-8 off
the exact ellipse.  The box centre is exact (error 1e-17), and it works
before `synchronize`.  It is used only to read the coordinates of a
point whose tag is already known (`add_conic_arc`), never to find
entities.  Found in task 0012.

### Plate filling fails between nearly identical arcs — *verified*
4.12.1 / OCC 7.6.3.  `occ.addSurfaceFilling` on a 4-sided loop whose two
long sides are B-spline arcs less than about 0.2° apart produces an
invalid surface.  The volume then has a hole and meshing fails.
`occ.addBSplineFilling(loop, type="Stretch")` works on the same loop;
`type="Coons"` fails.  It shows up between the tilted stations of a miter
segment.  Prism slabs use Stretch filling (`sweep._ruled`), with a
regression test in `tests/test_miter.py`.  Found in task 0012.

### `removePhysicalGroups([])` removes every group — *verified*
`gmsh.model.removePhysicalGroups(dimTags)` with an **empty** list removes
all physical groups; the docstring says so ("If `dimTags' is empty, remove
all groups").  Without groups, `gmsh.write` saves every element (points,
lines, quads, hexes) with physical tag 0, and `gmshToFoam` puts the whole
boundary in one `patch0`.  Guard the call with `if dimTags:`.  gmsh
4.12.1, 2026-10-25.  Hit by `Assembly.write_openfoam` on single-material
meshes, which have no interface groups to drop; found and fixed in task
0009, with a regression test in `tests/test_openfoam_output.py`.

### `occ.synchronize` costs time proportional to the model — *verified*
4.12.1 / OCC 7.6.3.  Each call rebuilds the GMSH model from the whole OCC
model.  On a serpentine of straights and 180° bends, 1928 calls took
304 s at 1050 volumes (0.16 s per call), and the build grew as
volumes^1.73.  With 4 calls per assembly the same network builds in
19.8 s (task 0036, 2026-10-27; `benchmarks/build_time.py`).

### `occ.remove` costs time proportional to the model, per point — *verified*
4.12.1 / OCC 7.6.3, task 0036, 2026-10-27.  About 3.9 ms per removed
point at 2100 volumes, whether removed one call at a time or all in one
call (one call removing 2900 points: 19.7 s), before or after a
synchronize.  Removed tags are not reused: the next `addPoint` gets a new
tag.  hexmesh therefore makes fewer construction points (a sweep shares
one arc centre per corner height) and removes them in one call.

### What works before `synchronize` — *verified*
4.12.1 / OCC 7.6.3, task 0036, 2026-10-27.
- **OCC calls work on unsynchronized OCC entities:** `addCurveLoop`,
  `addPlaneSurface`, `addSurfaceFilling`, `addBSplineFilling`,
  `addSurfaceLoop`, `addVolume`, `remove`, and `occ.getBoundingBox` (its
  centre is a point's exact coordinates).  A whole assembly is built
  with none in between; the meshes are identical node for node (66 kit
  cases and examples).
- **`gmsh.model` queries and mesh constraints need one:** `getBoundary`,
  `getValue`, `getParametrizationBounds`, `getType`, `setTransfinite*`,
  `setRecombine`.  hexmesh records curve end points and kinds when it
  creates curves (`hexmesh/_occ.py`), so it never queries during a build.
- **Constraints survive a later synchronize:** a transfinite curve keeps
  its node count after a synchronize that adds unrelated entities.  (The
  old comment in `corners.py` said it may be reset; not reproduced.  Not
  tested: an entity that OCC itself modifies, e.g. by a boolean.)
- **OCC keeps a curve's start where hexmesh put it:** for `addLine(a, b)`,
  `addCircleArc(a, c, b)`, `addSpline([a, …, b])` and
  `addBSpline([a, …, b])` the start (lower parameter bound) is `a`, and
  `getType` gives `Line`, `Circle`, `BSpline`, `BSpline`.  Checked on
  every curve of every kit case (`tests/test_build_sync.py`).

### Default MSH output version is 4.1
gmsh 4.x writes MSH 4.1 unless `Mesh.MshFileVersion` is set.  For
OpenFOAM this turned out **not** to matter: v1912 `gmshToFoam` reads 4.1
and 2.2 with identical results (task 0005).  `Assembly.write_openfoam`
writes 2.2 anyway, which every OpenFOAM line reads, and restores the
option afterwards.  `Assembly.write` keeps gmsh's default.
(Corrected 2026-10-25; this entry earlier said "nothing in hexmesh sets
it" and implied 4.1 was a problem.)

## Open questions

- ~~Does `gmsh.write` keep physical names and element orientation the way
  `gmshToFoam` expects?~~  **Settled in task 0005:** physical volumes
  become cellZones and boundary groups become patches by name;
  orientation needs no `-keepOrientation`.  Internal groups are the
  exception (see [openfoam.md](openfoam.md), Known quirks).
- Can the transfinite cut lines of an `n_outer = 8` sub-partition
  reproduce the 4-corner face's nodes exactly?  Decision 0005,
  pre-acceptance check.
- Behaviour of the assembly path on 4.15.x is untested.  Only the legacy
  wye was tried.
