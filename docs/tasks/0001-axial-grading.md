# 0001 — Axial grading per fitting

- **Status:** ready
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

## Questions for design

_None._

## Outcome

_Not done._
