# 0130 — Record a bend's second-order arc placement; label second order experimental

- **Status:** ready
- **Decision:** [0046 — gmsh meshes; hexmesh corrects](../decisions/0046-gmsh-meshes-hexmesh-corrects.md) (amendment 2026-11-10: rule 5 covers every node hexmesh moves); [0034](../decisions/0034-secondary-solvers.md) (note 2026-11-10: experimental until 0077)
- **Depends on:** 0123 (done: the correction record).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0123's record says "none" for a bend at `order=2`,
though `_revolve_high_order` moves its high-order nodes between stations
onto the arcs, wall and interior (0123's *Agent notes*).  Decision 0046's
amendment: every node hexmesh moves is recorded.  Separately, the user
asked that second order be labelled experimental until task 0077 has
verified it.

**Where.**  `hexmesh/assembly/assembler.py` (the correction record and
`_revolve_high_order`), `API.md`, `README.md`, `docs/GUIDE.md`,
`CHANGELOG.md`, the agent manifest text if it lists correction kinds,
`tests/`.

**Do.**
1. **Record the arc placement** as a third entry beside
   `wall_projection` and `second_order_wall_nodes`, named for what it
   does (e.g. `second_order_arc_nodes`), with the same fields (`nodes`,
   `largest_move`, `largest_move_radii`, `largest_move_edges`) and the
   same `CORRECTION_MIN_MOVE` threshold.  Its "local edge length" is the
   moved node's element's shortest edge, as for the other second-order
   entry.  Every fitting carries the entry ("none" for most).
   - If a node is moved by both the arc placement and the wall
     projection, say which entry counts it (once each, or in one) and why,
     under *Agent notes*.
2. **Sweep for others:** list every other place hexmesh writes a node
   coordinate gmsh produced (`setNode`, `setNodes`, or the like).  Record
   each, or say under *Agent notes* why it isn't a move of gmsh's
   node (e.g. it only writes back the same value).
3. **Schema:** if the manifest's correction record gains a key, its
   version follows decision 0040's rules, as in 0123.
4. **Label second order experimental** (decision 0034's note):
   `mesh(order=2)` and `write(…, order=2)` in API.md, the README's
   second-order line, GUIDE, and a CHANGELOG line: "experimental until
   the FEniCSx verification (task 0077)".  Docs only: no runtime warning.
   Task 0077's outcome removes the label (add that to 0077's *Agent
   notes*, as a pointer; don't change its steps).
5. **Tests:** a bend at `order=2` reports `nodes > 0` for the new entry,
   and its largest move equals the largest displacement of the bend's
   high-order nodes (measured independently: mesh once without the
   placement, or compare with the straight-edge midpoints); a straight
   reports "none".

**Accept.**
- A bend at order 2 no longer says "none"; the sweep's list is in
  *Agent notes*.
- The docs say "experimental" for second order, in the places above.
- Meshes byte-identical; full suite: no new failures.

**Out of scope.**  Changing the arc placement itself; any runtime
warning for order 2.

## Agent notes

## Questions for design

## Outcome
