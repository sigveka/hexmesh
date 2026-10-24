# 0007 — Test that topology is unchanged across geometry variants

- **Status:** ready
- **Decision:** [0001 — Complete A5/A7 in the assembly prototype](../decisions/0001-complete-assembly-prototype.md)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

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

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
