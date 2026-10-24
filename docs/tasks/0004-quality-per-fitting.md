# 0004 — Quality report per fitting, with hex metrics

- **Status:** ready
- **Decision:** [0001 — Complete A5/A7 in the assembly prototype](../decisions/0001-complete-assembly-prototype.md)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

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

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
