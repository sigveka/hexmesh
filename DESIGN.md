# hexmesh — Design

This document states the design philosophy of hexmesh: what the tool is,
the rules every part of it follows, and how pipe fittings are assembled
into a network.  Where current code deviates from these rules, the
deviation is listed in [Current deviations](#current-deviations) and is
considered technical debt, not precedent.

The mathematics behind individual fittings (frames, bend and miter
geometry, cylinder intersections, junction block topologies) and the
supporting literature are in [`docs/RESEARCH.md`](docs/RESEARCH.md).

---

## 1. Purpose and scope

hexmesh generates **structured, all-hex, conformal** meshes of pipe
networks for CFD (primarily OpenFOAM), including multi-material
cross-sections (fluid, pipe wall, insulation) for conjugate heat transfer.

**In scope**

- Circular and rectangular pipes with concentric material layers
- Standard fittings: straights, bends, elbows, miters, reducers,
  transitions, spline routes, tees, wyes, laterals, crosses
- Tree and looped networks with multiple inlets and outlets
- Networks defined in code or from piping data (graph, PCF, …)

**Out of scope**

- Arbitrary CAD geometry
- Tetrahedral or hex-dominant fallback meshing
- Repairing non-conformal geometry after the fact

If a geometry cannot be meshed under these rules, hexmesh rejects it with
an error that names the offending fitting or interface.

---

## 2. Core principles

1. **All-hex, structured, conformal.** Every cell is a hexahedron; every
   shared face has exactly one node set on both sides.
2. **Conformal by construction, never by repair.** No `occ.fragment()`,
   no `removeDuplicateNodes()`, no spatial (bbox) entity recovery.  If a
   fitting needs any of these, its block template is wrong.
3. **Topology first, geometry second, GMSH last.** Block structure is
   decided and validated before any point is placed; GMSH is only called
   once the whole network is known to be consistent.
4. **Fail before meshing.** Every check that can be made without GMSH is
   made without GMSH.
5. **Topology and density are separate.** Topology (`n_outer`, `rot`,
   layer stack) fixes where interfaces land.  Density (`nang`, `nrad`,
   `n_layers`, grading) only sets resolution and can be scaled freely.

---

## 3. Layers

| Layer | Answers | Contains | Calls GMSH |
|---|---|---|---|
| **Intent** | *What* is the network? | Graph of nodes (absolute positions) and edges (fitting type + parameters + pipe spec) | No |
| **Topology** | *How* do blocks connect? | Interfaces with types and frames; fitting block templates with typed ports; resolved density | No |
| **Realisation** | *Where* are the points? | GMSH geometry, transfinite constraints, physical groups, mesh | Yes |

Each layer only consumes the one above it.  The turtle-style `Network.add()`
API is a front end to the Intent layer: it records nodes and edges, it
does not build geometry.

---

## 4. Assembly rules

Assembly is defined by one question: **who creates shared faces?**
The answer in hexmesh is: **the assembler does, once, before any fitting
is built.**

### Rule A1 — Interfaces are first-class

Every boundary between two fittings, and every open network end, is an
**interface**.  Interfaces are created by the assembler.  A fitting never
creates its own port faces.

### Rule A2 — Fittings are fills

A fitting is a **fill between N existing port faces**.  It creates only its
internal entities (points, curves, surfaces, volumes) and must not create,
modify or duplicate any entity belonging to an interface.

### Rule A3 — Every interface has its own frame

An interface has an absolute pose: position, normal, and roll (an `up`
vector).  The roll fixes where structural corners lie.  Any twist needed
between two frames is the responsibility of the fitting between them,
never of the assembler.

### Rule A4 — Ports are typed

An interface type consists of:

- boundary kind (circular / rectangular / square shell)
- layer stack (material names and order)
- `n_outer` and `rot`
- `nang` (or `nang_w`, `nang_h`) and per-layer `nrad`

Every port that touches an interface must match its type exactly.  Type
changes (diameter, layer stack, boundary kind) happen *inside* a fitting
(Reducer, Transition), never across an interface.

### Rule A5 — Density is solved globally; axial resolution is local

`nang` and `nrad` must agree across every connected interface and are
resolved over the whole network before realisation.  `n_layers` and axial
grading belong to the individual fitting.  `Network.refinement` scales
all of them uniformly.

### Rule A6 — Build order is irrelevant

Once interfaces exist, fittings may be filled in any order and must
produce an identical mesh.  Any order dependence indicates a violation of
A1 or A2.

### Rule A7 — Boundaries come from the graph

Physical groups are derived from the graph, not from geometric search:

- volumes — by material layer (optionally also by fitting)
- open interfaces (ports with no neighbour) — one patch per node, named
  after the node
- outer walls and material interfaces — from the fittings' declared
  wall and interface surfaces

---

## 5. The assembly pipeline

```
1. Intent      build graph (nodes, edges, specs)           net.add(...) / readers
2. Place       compute every interface pose                 absolute coordinates
3. Validate    port types, density, fit, clearance         errors name fitting/interface
4. Faces       build each interface face in GMSH, once
5. Fill        build each fitting between its port faces   any order
6. Groups      physical groups from the graph
7. Mesh        transfinite meshing + quality report
```

Steps 1–3 never touch GMSH.  A network that passes step 3 must mesh.

---

## 6. The fitting contract

Every fitting type provides:

| Member | Layer | Purpose |
|---|---|---|
| `ports(...)` | Topology | Given the incoming interface (or graph context), return the pose and type of every port |
| `validate(ports)` | Topology | Check that the fitting can be built between these ports (length, radius, angle, clearance); raise naming the fitting |
| `template` | Topology | The fixed block topology of the fitting for a given `n_outer` |
| `fill(port_faces)` | Realisation | Build internal entities between existing port faces; return volumes, walls and material interfaces |

The block template of a fitting is fixed for a given fitting type and
`n_outer`; only geometry is parameterised.  New fitting variants
(equal-diameter tee, lateral, cross) are new templates, not special cases
inside existing ones.

The fill primitive is a transfinite volume built between existing faces
(see `fittings._connect_layer`).  OCC `extrude` / `revolve` create their
own outlet face and therefore cannot be used to fill toward an existing
interface.

**Exactness lives in curves and nodes, not in OCC surfaces.**  OCC filled
surfaces deviate from the true geometry (≈3 % of radius on a 30° bend
slab, ≈21 % on a 90° slab), and exact trimmed surfaces of revolution are
unreliable in OCC.  A fitting therefore guarantees geometric accuracy by
placing every mesh node on an exact curve: station faces plus exact axial
curves (lines, circular arcs), with one axial layer per slab where the
axis is curved.  Filled side surfaces then only carry element faces
between exact nodes.  Interior nodes follow from transfinite
interpolation of those exact boundaries
([RESEARCH §5](docs/RESEARCH.md#5-filling-blocks-between-fixed-boundaries)).

The prototype in `hexmesh/assembly/` implements this pipeline for
`Straight`, `Bend` and `Closure` (`tests/test_assembly.py`).

### 6.1 Shared fitting infrastructure

Fittings are thin: they describe *what* to build, and a small set of
shared builders does the building.  Four pieces, each with one rule.

**Sweeps — every single-path fitting is a sweep.**
A fitting with one inlet and one outlet is defined only by its *path* —
station frames, and the spec at each station — and the kind of axial
curve joining stations (line, arc about an axis).  One shared builder
creates the internal station faces and fills the slabs between them.

| Fitting | Path | Axial curve | Spec along path |
|---|---|---|---|
| Straight | two frames | line | constant |
| Bend | frames rotated about the bend axis | arc | constant |
| Closure | Hermite centreline, Bishop frames, distributed twist | line | constant |
| Reducer / Expander | two frames | line | interpolated |
| Spline pipe | spline centreline, Bishop frames | line | constant |

Path geometry for each row (frames, torus bend, reducers) is in
[RESEARCH §1–2](docs/RESEARCH.md#1-frames-along-a-centreline).  Miter
bends are absent from the table: their oblique joint plane does not fit
the sweep model as it stands
([RESEARCH §2.3](docs/RESEARCH.md#23-miter-bend-miterbend)).

A new single-path fitting supplies a path and, where needed, its own
`validate` checks; it must not write its own fill.  `Sweep.validate`
checks every slab before GMSH: centreline bend radius above the pipe
outer radius, corner correspondence defined, and — where axial edges are
straight chords — a normal turn of at most 30° per slab.

**Corner identity — corners are named by the frame, never found by distance.**
Corner *k* of a face lies at angle `π/4 + rot + k · 2π / n_outer` from
`frame.right`.  The correspondence between two faces is the index offset
given by their frames alone (modulo the `2π / n_outer` symmetry), computed
in pure numpy so it is checked in validation and reused unchanged in
`fill`; curve directions are resolved by endpoint tags.  Nearest-distance matching is forbidden: it
fails for faces that are far apart or at large angles to each other, such
as a junction branch.

**Blocks — every multi-port fitting is a layout of hex blocks.**
A junction is built from hex blocks (8 corners, 12 edges with a curve
kind, 6 faces), some of whose faces are interface faces.  Blocks get
shared corners, edges and faces from a registry keyed by *topological
identity* (owning block and local index), never by coordinates.  This
keeps a junction conformal by construction (P2) without `fragment()` or
node merging.  Tee, wye, lateral and cross are block layouts on top of
this builder, not separate geometry code.  The closed-form tee/lateral
intersection curve and published bifurcation block layouts are in
[RESEARCH §3–4](docs/RESEARCH.md#3-tee-and-lateral-the-intersection-curve).

**Conformance — every fitting passes one shared test kit.**
A parametrised suite checks the design rules for any fitting:

- `ports` and `validate` run without GMSH (P3, P4)
- `fill` leaves port faces untouched (A1, A2)
- no coincident hex nodes; every interior interface is shared by
  exactly two fittings (P2)
- every permutation of the fill order gives the same mesh (A6)
- each surface belongs to exactly one physical group (A7)

A fitting is not finished until it passes the kit.

**Not built on speculation.**  The infrastructure is a protocol plus
shared builders, not a class hierarchy or a plugin registry.  Generic
N-port junction topology is derived from at least two working junctions
(tee and wye), not designed ahead of them.  Published n-way constructions
exist ([RESEARCH §4.4](docs/RESEARCH.md#44-what-this-means-for-stage-6-y-junction-redesign))
but are held back by this rule.

---

## 7. Junctions

A junction is an ordinary fitting with three or more ports.  Its internal
blocks (stub, saddle, T-zone) are private to it.  Neighbouring fittings see
only its port faces.

Junction port frames must place structural corners where the junction
template needs them.  This is why `n_outer = 8` is the target topology:
it puts corners at 0°/90°/180°/270° so tee tips and wye split planes fall
on structural corners rather than arc midpoints.  The literature suggests
`n_outer = 4` with a π/4 interface roll may also suffice; see
[RESEARCH §4.4](docs/RESEARCH.md#44-what-this-means-for-stage-6-y-junction-redesign).
Tee side corners land at ±arcsin(r/R) for any `n_outer`
([RESEARCH §3.2](docs/RESEARCH.md#32-consequences-for-block-topology)).

### 7.1 Tee: continuous ring layer

The tee (`hexmesh/assembly/tee.py`, `n_outer = 4`, `rot = 0`) does not
place the branch on the main pipe's wall.  Instead the O-grid ring layer
stays continuous around the junction, as an offset of the whole tee wall:

- the main approach and departure top-ring blocks turn the corner into
  the branch's −x and +x ring blocks;
- the junction's two side-ring blocks turn into the branch's ±y ring
  blocks;
- one core block at the T-point links the main cores to the branch core.

Each turn face runs from a saddle arc to the branch core and bisects the
270° re-entrant corner, so every block stays a proper hex.  The saddle
corners are the branch OH's diagonal corners, at ±r/√2 along both the
main axis and the transverse direction.  They become the corners of the
junction's internal stations, so every arc keeps `nang` divisions and no
sub-arc rule is needed.  All three ports keep the standard OH pattern.

Tried and rejected: hole-on-wall layouts, where the branch's 5 patches
sit on the main pipe's wall and the main blocks below are split to
match.  The branch's ring sheet must then either end at a closed "cap"
or "plate" block with five faces on one smooth surface (degenerate
cells), or run through to the main inlet and outlet faces, which would
change their topology.

Measured on the prototype (single layer, nang = 4): all-hex, no bad
cells for r/R from 0.3 to 0.95, minimum SICN rising from 0.16 to 0.38
with r/R.

---

## 8. Loops

A loop is closed by a fitting whose ports are *both* existing interfaces.
Under A1/A2 this needs no special assembly logic.  The closing fitting
must:

- absorb any roll mismatch between the two frames (A3), and
- reject closures it cannot fill within quality limits (A3, principle 4).

Implementation (`Assembly.close(source, target, fitting)`):

- Any fitting can close a loop if its `validate()` accepts the two given
  frames — a `Straight` or `Bend` that fits exactly, or a `Closure` for an
  arbitrary gap.
- Flow direction is enforced: *source* must be a downstream end and
  *target* an upstream end.  Joining two outlets head-on needs a
  different fitting and is not supported.
- `Closure` follows a cubic Hermite centreline tangent to both interface
  normals, with parallel-transported (Bishop) frames.  In a non-planar
  loop the transported frame returns rotated (holonomy); this residual
  roll is distributed linearly by arc length.  Frame theory and a
  higher-order transport (double reflection) are in
  [RESEARCH §1](docs/RESEARCH.md#1-frames-along-a-centreline).
- Roll only matters modulo the cross-section symmetry `2π / n_outer`
  (90° for `n_outer = 4`), so the absorbed twist never exceeds
  `π / n_outer`.
- Validation computes the minimum centreline bend radius before any GMSH
  call and rejects paths tighter than the pipe outer radius.

---

## 9. Current deviations

The present code predates these rules.  Known deviations:

| Deviation | Rule | Where |
|---|---|---|
| Fittings create their own outlet faces (producer-owns) | A1, A2 | all connectors via `connect(inlet, cursor)` |
| Relative (cursor-chained) placement; no graph | §3, A3 | `Network.add()` |
| OCC `extrude` / `revolve` used for fills | A2 | `straight.py`, `bend.py` |
| `occ.fragment()` + bbox surface recovery | P2 | `y_block.py`, `junction.py` |
| `removeDuplicateNodes()` | P2 | `model.py`, `network.py` |
| Geometry built inside `connect()`; no pre-GMSH validation | P3, P4 | all connectors |
| Topology detected from surface count | A4 | `straight.py`, `bend.py`, `fittings.py` |
| `nang` checked per connector, not resolved across the network | A5 | `fittings.py`, `spec.py` |
| Corner correspondence between two faces found by nearest-distance search, not from interface frames | A3, §6.1 | `fittings._connect_layer` — legacy connectors only; `hexmesh/assembly` uses `corners.frame_offset` |
| `n_outer = 8` core cannot be filled: its 8-sided centre patch does not bound a transfinite hex block (needs splitting into 4 blocks) | §7 | `faces/oh_circle.build_oh_circle8`; rejected in validation by `hexmesh/assembly` |
| Tee wall faces (junction and run slabs) are OCC-filled surfaces, so interior wall nodes lie 2–5 % of R off the true cylinders | §6 exactness | `hexmesh/assembly/tee.py` |
| Tee prototype limited to single-layer specs, `rot = 0`, perpendicular centred branch | §7.1 | `hexmesh/assembly/tee.py` |

New code must not add to this table.

---

## 10. Open decisions

- **Library or tool?** A scripting library for engineers, or a tool that
  takes plant data and returns a mesh.  Determines how much investment
  goes into readers and automatic sizing.
- **`n_outer` per network or per interface?** One value per network is
  simplest; mixed values require transition templates.  Evidence on
  whether junctions need `n_outer = 8`:
  [RESEARCH §4.4](docs/RESEARCH.md#44-what-this-means-for-stage-6-y-junction-redesign).
- **Reject or degrade?** When quality limits cannot be met, should
  validation fail, or warn and continue?  Published structured
  bifurcations reach min scaled Jacobian ≈ 0.49
  ([RESEARCH §4.2](docs/RESEARCH.md#42-hermite-curve-butterfly-marcinno_and_hinz_etal_2025)).
  Metric definitions and a flow-validation benchmark:
  [RESEARCH §7](docs/RESEARCH.md#7-validation-and-quality-metrics).
- **Loop twist.** User-supplied closing segment, or solver-distributed
  twist across the loop?
- **Interface placement at bends.** How tangent points are derived from
  piping data (trimming straight lengths against bend radii).
