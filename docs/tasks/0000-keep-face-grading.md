# 0000 — Keep face-builder grading through meshing (bug fix)

- **Status:** done
- **Decision:** [0001 — Complete A5/A7 in the assembly prototype](../decisions/0001-complete-assembly-prototype.md)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

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

## Agent notes

- Step 1 used a frozen `CurveMesh(tag, nodes, kind, coef)` dataclass
  (`assembly/sweep.py`) instead of a bare tuple.  It is the record task 0001
  extends, so 0001 step 1 is already done.
- Step 2 found a second bug.  With OCC, `gmsh.model.getBoundary` returns
  a curve's endpoints in **ascending tag order**, not start → end.
  `connectors.fittings._curve_endpoints` assumes the first one is the
  start, so it reports the curve reversed whenever the start point has the
  higher tag.  OCC accepts curve loops built from such wrongly signed
  curves, and uniform meshing doesn't care about direction, so nothing
  showed until grading.  Then the core radials came out at `1/mprg` while
  the shells happened to be right.
  The assembly path now uses `corners.curve_endpoints`, which takes the
  endpoint at the lower parametrisation bound.  `canonical_geom` and
  `BlockLayout` use it too.  I left the legacy helper unchanged: it has 16
  call sites in `hexmesh/connectors/`, which is out of scope.
- `BlockLayout` edges carry an optional `grading`, oriented a → b.
  `realise()` inverts the coefficient when the bound curve runs b → a.
  `face_vertices` grades port and station faces like the sweep.

## Questions for design

_None._

## Outcome

Commit `d8c7b83`.

- **Files:** `assembly/sweep.py` (`CurveMesh`, `UNIFORM`, `face_grading`;
  station grading in `sweep_fill`), `assembly/assembler.py`
  (`curve_constraints`; `mesh()` passes kind and coef),
  `assembly/corners.py` (`curve_endpoints`), `assembly/blocks.py` (edge
  grading), `tests/test_grading.py` (new), `tests/test_corners.py`
  (`TestCurveEndpoints`).
- **Tests:** full suite 456 passed, 10 failed (the known
  `TestYJunctionQuality` failures), 4 xfailed.  The Task 0 commit on its own:
  113 passed across the grading, corners, assembly, blocks, tee and
  conformance tests.
- **Measured:**
  - Core and shell radial cell ratios equal `mprg` (1.3, 0.8 and 1.25) to
    rtol 1e-6, from the inner end.
  - Internal bend stations are graded: 4 radials × 5 faces.
  - The `mbmp` bump is symmetric and non-uniform.
  - `BlockStraight` matches the sweep node for node with grading.
  - A graded tee meshes with quality ok.
- **Surprise:** the `getBoundary` ordering bug above.
- **Proposed follow-up:** a legacy-scope task to replace
  `connectors.fittings._curve_endpoints` with `corners.curve_endpoints`
  and check whether any legacy connector meshes reversed today.  It needs
  a design decision, because legacy code is out of scope.
