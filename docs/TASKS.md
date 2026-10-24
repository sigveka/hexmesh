# Tasks: low-hanging fruit in the assembly pipeline

Small, self-contained improvements to `hexmesh/assembly/`.  Each one
completes something `DESIGN.md` already promises, or unlocks a target use:
CHT pipe networks, junction-flow CFD, parametric and surrogate studies.

## Ground rules (apply to every task)

- Read `DESIGN.md` first.  Changes must follow it and must **not** add rows
  to its "Current deviations" table.
- Work only in `hexmesh/assembly/` (and `hexmesh/core/` where stated).  Do
  not touch the legacy connectors (`hexmesh/connectors/`, `network.py`)
  unless a task says so.
- Anything computable without GMSH must be computed without GMSH (DESIGN
  P3/P4): in `ports()`, `validate()` or `Assembly.validate()`, never in
  `fill()`.
- Every task adds tests.  New fittings or fill changes must still pass the
  conformance kit, `tests/test_fitting_conformance.py`.
- Run tests with `python3 -m pytest` (never `python`).  Gate: no new
  failures before and after each task.  The 10 `TestYJunctionQuality`
  failures in the legacy suite are known and out of scope: the legacy
  Y-junction's `occ.fragment()` breaks on both gmsh 4.12/OCC 7.6 and
  gmsh 4.15.
- Keep each task a separate, reviewable change.  Match the surrounding code
  style: dataclasses, numpy, short docstrings that cite DESIGN rules.

Suggested order: 0 → 3 → 1 → 2 → 4 → 7 → 6 → 5 → 8 → 9.  Tasks 1, 4 and 6
have the highest value.  Task 0 is a bug fix that tasks 1 and 2 build on.

The multi-layer tee (needed for CHT networks with junctions) is not
low-hanging fruit and is tracked separately; it fits best after task 4,
when first-cell grading and per-fitting quality can measure its wall
layers.

---

## 0. Keep face-builder grading through meshing (bug fix)

**Why.**  `PipeSpec`'s radial progression `mprg` is silently lost in the
assembly pipeline.  The face builders set progressions on radial curves,
but `Assembly.mesh()` re-applies every transfinite curve from
`FillResult.curves` as `(tag, n)` with no progression, overriding them.
Measured: a `Straight` with `mprg=1.3` meshes with uniform radial cells
(last/first cell length ratio 1.000).

**Do.**
1. Extend curve records to `(tag, n, kind, coef)` (this is task 1, step 1);
   `kind` is "Progression" or "Bump", `coef` a float, default uniform.
   Update `FillResult.merge`, `Assembly.mesh()` (pass
   `meshType`/`coef` to `setTransfiniteCurve`) and `BlockLayout.realise`.
2. Radial curves of interface and station faces carry the layer's `mprg`,
   oriented inner → outer by endpoint tags (`corners.canonical_geom`
   already signs `rc` inner → outer).  Angular arcs carry `mbmp` as
   "Bump".
3. A curve that appears twice must get one consistent record; conflicting
   records are an error, not "last wins".

**Accept.**
- Uniform specs mesh identically to before.
- New test: radial cell lengths of a meshed `Straight` grow by `mprg`
  from the inner end, for the core and for a shell layer.

---

---

## 1. Axial grading per fitting

**Why.**  DESIGN A5 says "`n_layers` and axial grading belong to the
individual fitting", but grading is not implemented.  Cells cannot be
concentrated near a tee or a bend exit.

**Where.**
- `FillResult.curves` is `list[tuple[int, int]]` (tag, n), in
  `hexmesh/assembly/sweep.py:31`.
- `_fill_slab` appends `(c, n_layers + 1)` at `sweep.py:145`.
- `Assembly.mesh()` calls `setTransfiniteCurve(tag, n)` with no
  progression at `hexmesh/assembly/assembler.py:306`.
- Arc curves come from `deferred["arc_curves"]` in `corners.connect_layer`.

**Do.**
1. Extend curve records to `(tag, n, kind, coef)`, with `kind` "Progression"
   or "Bump" and `coef` a float, defaulting to uniform.  Update
   `FillResult.merge` and `Assembly.mesh()`, which passes
   `meshType`/`coef` to `setTransfiniteCurve`.
2. Add an optional grading parameter to `Sweep` fittings (`Straight`,
   `Bend`, `Closure`), e.g. `axial_grading: float = 1.0` (progression) or
   `axial_bump`.  Apply it **only to axial curves**, never to curves owned
   by an interface face (rule A2).
   - `Straight` has one slab with `n_layers` divisions: grade its axial
     curves.
   - `Bend` and `Closure` have **one layer per slab** (so wall nodes stay
     exact, DESIGN §6).  A curve progression on them does nothing; grade
     them by spacing their `Path` stations non-uniformly instead.  This is
     a `Path` property, so it belongs in `Sweep`, not in each fitting.
   - Block layouts (`Tee`): parallel edges in one division class must share
     the grading *direction*.  `BlockLayout._division_classes` must track
     orientation (union-find with parity) and reject a class whose edges
     disagree.
3. Progression direction must follow the flow (inlet → outlet), whatever
   order GMSH gives the curve's endpoints.  Resolve it by endpoint tags
   (DESIGN §6.1: never by distance).

**Accept.**
- With grading 1.0 the mesh is identical to before; the existing tests are
  unchanged.
- New test: a `Straight` with progression `r` has axial cell lengths in
  ratio `r` (read node coordinates along one axial line).  The first cell
  is at the inlet end.  Same for a `Bend` (station spacing).
- The conformance kit passes with graded fittings added to `CASES`.

---

## 2. Radial grading from first-cell height

**Why.**  `PipeSpec` takes a radial progression `mprg`, but CFD users
specify a first-cell height at the wall.

**Where.**  `hexmesh/core/spec.py` (`core()`/`shell()` take `nrad`, `mprg`).
Depends on task 0: before it, `mprg` has no effect in the assembly
pipeline.

**Do.**
1. Add a pure function such as
   `progression_for_first_cell(thickness, n_nodes, h_first) -> float`.  It
   solves `h1 * (q**(n-1) - 1) / (q - 1) = t` for `q` by bisection or
   Newton, returning 1.0 when `h1 == t/(n-1)`.  Raise a `ValueError` when no
   `q > 0` exists.
2. Add an optional `first_cell=` kwarg next to `mprg` on the core and shell
   builders.  It is mutually exclusive with `mprg`, and the resulting `q`
   is stored in `mprg`.
3. Document which wall the first cell is at (the outer wall of the layer)
   and how this relates to the existing `mprg` convention ("> 1 refines
   …", `spec.py:51`).  Check the existing direction before choosing a sign.

**Accept.**
- Unit tests: round trip (`q` → `h1` → `q`); uniform case; an impossible
  input raises.
- One realisation test: the measured first radial cell height of a meshed
  `Straight` matches `h_first` within 1 %.

**Note.**  This sets a first-cell height, not y+.  y+ depends on flow
velocity; don't add a y+ API.

---

## 3. Exact cell count before GMSH

**Why.**  The mesh is structured, so the cell count is known exactly from
topology and density.  Reporting it in validation enforces DESIGN P4, and it
makes "refinement ×2 ⇒ 8× cells" (CLAUDE.md) visible before meshing.

**Where.**  `Assembly.validate()` at `assembler.py:173`; fittings in
`assembly/fittings.py` and `assembly/tee.py`.

**Do.**
1. Add `cell_count(frames, spec) -> int` to the fitting protocol (frames,
   like `validate`, because block layouts need them): per-layer
   cross-section quads × axial layers for sweeps, the sum over blocks for
   `Tee`.  Derive cross-section quad counts from
   `n_outer`/`nang`/`nrad`; no GMSH.  For block layouts this is generic:
   `BlockLayout` already solves the division classes, so a block's cells
   are the product of its three class counts.
2. Add `Assembly.cell_count()` (the sum) and
   `Assembly.validate(max_cells=None)`, which raises `AssemblyError` naming
   the total and the largest fitting when the budget is exceeded.

**Accept.**
- For every case in the conformance kit, `cell_count()` before GMSH equals
  the number of 3-D elements after `mesh()`.  Add this as a kit test so
  every future fitting must implement it.

---

## 4. Quality report per fitting, with hex metrics

**Why.**  `Assembly.check_quality` (`assembler.py:329`) groups results by
**material** and uses only gmsh SICN.  DESIGN wants failures that name the
fitting.  `hexmesh/quality_hex.py` already has Verdict-style hex metrics,
but only the legacy `network.py:874` uses them.

**Do.**
1. Record volume tags **per fitting**: in `Assembly.fill`, keep each
   edge's `FillResult` (or its `volumes`) keyed by `edge.index` before
   merging.
2. Extend `check_quality(by="fitting" | "material")`.  The default stays
   "material", for backward compatibility.
3. Allow metrics from `quality_hex` as well as gmsh quality names.  Add
   **scaled Jacobian** (Knupp: minimum over the 8 corners of
   det(J)/(|e1||e2||e3|)) and **NES** (max of
   `(θmax−90)/90`, `(90−θmin)/90` over face angles); neither is in
   `quality_hex.py` yet (it has mean ratio, shape regularity and face
   metrics).  `BlockLayout.corner_jacobians()` already computes the
   scaled Jacobian per block corner before GMSH; reuse the formula.  These are the metrics used in `docs/RESEARCH.md` §4.2 and §7.1.
4. Report rows show the fitting index, type name and the worst value.

**Accept.**
- Unit tests for scaled Jacobian and NES: a unit cube gives 1 and 0; a
  sheared hex gives known values.
- An assembly with a `Tee` produces one report row per fitting, and the
  tee row is the worst.

---

## 5. OpenFOAM-compatible output

**Why.**  `Assembly.write()` (`assembler.py:315`) calls `gmsh.write(path)`
with no format options, and nothing in the repo sets
`Mesh.MshFileVersion`.

**Do.**
1. **Verify first:** check which MSH versions the target OpenFOAM's
   `gmshToFoam` reads (expected MSH 2.2 ASCII, but confirm).  Record the
   result in the docstring.
2. Add `Assembly.write(path, format=None)`, or a `write_openfoam(path)`
   helper, that sets `Mesh.MshFileVersion` (and `Mesh.Binary = 0`) for
   `.msh` output, restoring the previous option values afterwards.
3. Add `docs/OPENFOAM.md` with the CHT recipe: `gmshToFoam` →
   `splitMeshRegions -cellZones -overwrite` for multi-material meshes.
   Physical volumes are already per material.  Mark any step you could not
   run as unverified.

**Accept.**
- Test: the written `.msh` header has the expected version.  Parse the
  `$MeshFormat` line; OpenFOAM is not needed in CI.

---

## 6. Save and load the network description (Intent layer)

**Why.**  DESIGN §3 defines the Intent layer as a graph, but today it only
exists as a sequence of `Assembly.add()` calls.  A serialized form enables
parametric studies, plant-data readers (DESIGN §10) and reproducible test
cases.

**Where.**  `Assembly.add` (`assembler.py:93`), `Edge`, `Interface`; fitting
dataclasses in `assembly/fittings.py` and `assembly/tee.py`; `PipeSpec` in
`core/spec.py`.

**Do.**
1. Add `Assembly.to_dict()` and `Assembly.from_dict(d)` (plain
   JSON-serializable data):
   - inlet pose and spec
   - an ordered edge list: fitting type name, dataclass fields, source
     interface index, outlet names
   - loop closures (`close()` calls).
2. Use a small explicit registry mapping type names to classes; no
   plugins or entry points (DESIGN §6.1 "not built on speculation").
3. `PipeSpec` needs `to_dict()`/`from_dict()`; include layer names, radii,
   `nrad`, `mprg`, `n_outer`, `rot` and `nang`.
4. Units: document that lengths are in the user's unit and unconverted.

**Accept.**
- Round trip for every conformance-kit case:
  `from_dict(to_dict(a))` produces identical interface frames and an
  identical mesh (node count, element count, physical group names).
- The JSON file is human-readable (indented, sorted keys).

---

## 7. Test that topology is unchanged across geometry variants

**Why.**  Parametric and surrogate studies (POD, mesh morphing, ML
datasets) need **identical connectivity** when only geometry changes.
hexmesh should give this by construction, but nothing tests it.

**Do.**  Add a test module (or a kit test) that meshes pairs of variants at
fixed density and asserts identical element counts **and** identical
element→node connectivity after renumbering by topological order.
Variants:
- `Bend`: bend radius 2R vs 3R; angle 45° vs 90°
- `Tee`: branch radius ratio 0.4 vs 0.6
- `Straight`: length L vs 2L

If GMSH node numbering is not stable across variants, compare
connectivity through a canonical ordering, such as sorting by (fitting,
block, i, j, k) when available.  Known risk: OCC may store a circular arc
reversed depending on its geometry, which flips node order along that
curve without changing topology.  Otherwise report the gap rather than
weakening the test.

**Accept.**  The tests pass, or a clearly documented failure explains
which fitting breaks topology invariance and why.

---

## 8. Inlet and outlet extensions

**Why.**  CFD boundary conditions need straight run before and after the
region of interest, typically 5–10 D upstream and more downstream.

**Do.**  Add `Assembly.extend_open_ends(upstream=5.0, downstream=10.0,
n_layers=...)`, in diameters.  It must run before `build()`:
- downstream: `add(iface, Straight(length))` on each open outlet
- upstream: needs a new inlet *before* the current one.  This fits the
  graph without hacks: place a new inlet frame `L` back along the current
  inlet's normal, add an edge `[new, old]` with a `Straight` (whose
  `validate` already checks that placement), and make the new interface
  `Assembly.inlet`.  Add this as `Assembly.prepend(fitting)`, limited to
  fittings that can be placed backwards (`Straight`).

Patch names of the extended ends must keep the original names.

**Accept.**  Outlet patch names are unchanged after extension, and the
total length is correct.

---

## 9. Per-fitting wall patches

**Why.**  All walls go into one `"{outer}_wall"` group (`assembler.py:292`).
Per-fitting wall patches give per-fitting wall shear, heat flux and
erosion results in post-processing.  DESIGN A7 already allows "optionally
also by fitting" for volumes.

**Do.**
1. `Assembly.write_physical_groups(walls_by_fitting=False)`.  When true,
   emit `"{outer}_wall_{fitting_name}"` per edge instead of one wall group,
   with each surface still in exactly one group (A7).
2. Fitting names: an optional `label` on `add()`, defaulting to
   `f"{type}{index}"`.  Not `name`: `add(..., names=...)` already names
   the outlet interfaces.

**Accept.**  The kit's "each surface belongs to exactly one physical group"
check passes with the option on.  The wall groups' union equals the
original wall group.

**Do not** add internal interface surfaces as physical groups in this
task.  How `gmshToFoam` treats internal physical surfaces is unverified.

---

## Out of scope for these tasks

Do not combine these tasks with: Y-junction/Stage 6 work, miter bends in
`Sweep`, tee generalisation (multi-layer, laterals, offset taps, exact
tee walls), `n_outer = 8` core filling, or anything in
`docs/RESEARCH.md` §8.  Those are design decisions, not low-hanging fruit.

(The tee side-corner arc split is no longer needed: the block-layout tee
places its saddle corners on the branch diagonals, DESIGN §7.1.)
