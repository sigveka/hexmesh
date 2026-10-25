# 0001 — Axial grading per fitting

- **Status:** done
- **Decision:** [0001 — Complete A5/A7 in the assembly prototype](../decisions/0001-complete-assembly-prototype.md)
- **Depends on:** 0000

Ground rules for all tasks: [README](README.md#ground-rules).

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

## Agent notes

- Step 1 was done in task 0000 (`CurveMesh` in `assembly/sweep.py`;
  `Assembly.mesh()` passes kind and coef).  The **Where** line numbers
  predate that change.
- For step 3, use `corners.curve_endpoints`, not
  `connectors.fittings._curve_endpoints`.  The legacy helper can report a
  curve reversed (see 0000 Agent notes).

- **Scope grew with tasks 0012–0014.**  Graded: `Straight`, `Bend`,
  `Elbow` (passed to its `Bend`), `Reducer`, `SplinePipe`, `Closure`.
  Not graded: `MiterBend` (its stations are tied to the cut planes; a
  grading would need a rule for where layers go per segment) and `Tee`
  (no axial parameter yet).  Both are listed as follow-ups.
- **One parameter, progression only.**  `axial_grading: float = 1.0`, the
  ratio of consecutive axial cell lengths inlet → outlet, GMSH's
  "Progression" law.  `station_fractions(n, r)` in `sweep.py` is that law
  for station placement, so a station-spaced sweep and a curve-graded
  `Straight` agree.  No `axial_bump`: GMSH's "Bump" formula is
  version-dependent, and station spacing would have to reproduce it
  exactly; I left it out rather than guess.
- **Where it lives.**  `Sweep.fractions(n)` (rule: a `Path` property, not
  per fitting) gives the station positions; each fitting's `path()` uses
  them.  `Path.axial_grading` carries the curve progression for
  multi-layer slabs (`Straight`).  `_transported_stations` takes
  `fractions` and grades its arc-length + turning measure.
- **Direction (step 3).**  `sweep._axial_mesh` reads the axial curve's
  start point with `corners.curve_endpoints` and checks it against the
  inlet face's point tags; tags only, no distances.
- **Block layouts (step 2).**  `BlockLayout._division_classes` is now a
  union-find with parity.  Each class carries one grading, oriented per
  edge; every edge of the class gets it, and declared gradings that
  disagree in kind, coefficient or direction raise `LayoutError`.  Edge
  orientation is the declared a → b, otherwise the first traversal in
  block order, which is the order `realise` creates undeclared edges in.
  On the tee with `mprg = 1.3` and `mbmp = 0.5`, min SICN is identical
  before and after (0.090 / 0.139 / 0.088): its classes were already
  consistent.
- **Validation before GMSH.**  `Sweep.check` rejects `axial_grading <= 0`.
  `SplinePipe._check_points` also checks it, because `ports()` runs at
  `add()`, before `validate`.

## Questions for design

_None._

## Outcome

- **Files:** `assembly/sweep.py` (`station_fractions`,
  `Path.axial_grading`, `_axial_mesh`, `Sweep.fractions`, grading check),
  `assembly/fittings.py` (`axial_grading` on six fittings,
  `_transported_stations(fractions=)`), `assembly/blocks.py` (oriented
  division classes), new `tests/test_axial_grading.py` (22 tests), five
  graded cases in `tests/test_fitting_conformance.py`, `README.md`,
  `API.md`.
- **Tests:** 341 passed, 0 failed.  Grading 1.0 meshes node-for-node as
  before (explicit test); meshed `Straight` (1 and 2 layers, along and
  against an axis) and `Bend` have cell-length ratios equal to the
  grading to 1e-5 (nodes are rounded to 1e-9), first cell at the inlet.
- **Measured** (fluid r = 0.1, nrad 5, wall dR 0.01, nrad 2; min SICN):

  | Grading | Straight(0.5, 10) | Bend(0.3, 90°, 12) |
  |---|---|---|
  | 1.0 | 0.251 | 0.239 |
  | 1.1 | 0.183 | 0.161 |
  | 1.3 | 0.115 | 0.092 |
  | 0.8 | 0.126 | 0.103 |

  SICN falls because the finest axial cells get short against the thin
  wall layer's radial size; it stays positive.  Task 0002 (first-cell
  height) and 0004 (per-fitting quality) are where to judge this.
- **Follow-ups:** grading for `MiterBend` (per-segment rule) and `Tee`
  (axial parameter on its runs and branch); an `axial_bump` once GMSH's
  bump law is pinned to a version in `docs/integrations/gmsh.md`.
