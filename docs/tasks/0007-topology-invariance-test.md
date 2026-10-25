# 0007 — Test that topology is unchanged across geometry variants

- **Status:** done
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

- **Canonical comparison.**  Nodes are seeded with the geometric entity
  they are classified on, `(dim, tag)`.  These are identical across
  variants, because the assembly creates entities in the same order for
  each.  The seeds are then refined by hex-edge neighbourhood
  (Weisfeiler–Lehman) on the union of both meshes.  If every class holds
  one node of each mesh, that is the bijection, and the meshes are
  isomorphic when it maps every hex (as a node set, per volume) onto a
  hex.  It converges in 2–3 rounds.  Two negative controls check it: a
  density change (bend 6 vs 7 layers), and one hex rewired to a
  neighbouring node.
- **All variants are topologically invariant:**
  - bend radius 2R/3R;
  - bend angle 45°/90°;
  - mirrored bend ±90°;
  - roll 0°/30°;
  - tee ratio 0.4/0.6;
  - straight L/2L;
  - reducer outlet radius and length.
- **Raw GMSH numbering was not stable (found, then fixed).**  Before this
  task, these pairs had identical per-entity node sets but different
  element connectivity:
  - bend 45/90 (in the downstream `Straight`), the mirror, the roll, and
    the tee: GMSH chose the transfinite starting corner of a surface or
    volume itself, from geometry;
  - the mirror: in addition, the hex vertex order was reversed.

  No curve was reversed: the "OCC stores an arc reversed" risk named in
  the task did not occur.
- **Fix.**  `Assembly.mesh` passes `cornerTags` from the new
  `corners.transfinite_surface_corners` / `transfinite_volume_corners`.
  These choose the smallest point tag, then walk to neighbours in tag
  order, so the choice is topology only.  With it, raw node tags,
  element tags and connectivity are identical for every pair except the
  mirror.  For the mirror, node and element tags and each hex's node set
  match, but the vertex order is reversed, as it must be to keep the
  volumes positive.  Node coordinates and min SICN of the smooth_bend,
  miter_bend, tee, pipe_network and reducer_network examples are
  unchanged to 1e-15 (numbering only).
- `test_raw_numbering` therefore asserts the stronger property, and
  `test_mirrored_variant_reverses_vertex_order_only` pins the
  exception.

## Questions for design

_None._

## Outcome

- **Files:**
  - new `tests/test_topology_invariance.py` (16 tests);
  - `assembly/corners.py` (`transfinite_surface_corners`,
    `transfinite_volume_corners`, `_point_graph`);
  - `assembly/assembler.py` (`mesh` passes the corners).
- **Result:**
  - topology is invariant for every variant in the task, plus the mirror,
    the roll and the reducer;
  - raw GMSH numbering is now identical too, except the mirrored
    variant's hex vertex order.

  For POD or ML datasets, node tag *i* is the same point of the topology
  across variants.
- **Follow-up:** a public `canonical_node_order()` (the comparator in
  this test) would help users who mix in mirrored variants.
- **Tests:** 402 passed, 0 failed.
