# 0045 — Layer outlines: circle and rectangle in either order, and rectangle in rectangle

- **Status:** done
- **Decision:** [0026 — Layer outlines: shells of any shape](../decisions/0026-layer-outlines.md)
- **Depends on:** —  (0046 and 0047 build on it)

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Shells are circular only, and the assembly rejects any shell
around a rectangle.  Wanted: a rectangle around a circle, a circle around
a rectangle, and a rectangle around a rectangle, through every sweep
fitting.

**Where.**
- `hexmesh/core/spec.py`: `shell(…, outer=…)`, remove `square_shell`
  and `SquareShellSpec`; `to_dict`/`from_dict`.
- `hexmesh/core/shape.py`: `outline`, extents; the outline protocol.
- `hexmesh/faces/annulus.py`: generalise `build_annulus` to any two
  outlines (or a new `faces/ring.py`); remove `faces/square_shell.py`.
- `hexmesh/assembly/interface.py`: `build_face`, `check_supported`,
  `outer_radius`, `half_extent`.
- `hexmesh/assembly/fittings.py`, `sweep.py`: bend-radius checks,
  `Reducer` rules; `signature.py` (check only).
- Conformance kit, `API.md`, `README.md`.

**Do.**
1. **Spec.**  `shell(name, dR=None, outer=None, nrad, mprg=None, *,
   first_cell=None)`: exactly one of `dR` and `outer`.  `dR` grows the
   previous outline (rectangle: half_w + dR, half_h + dR).  Every outline
   in a stack has equal counts per side (`nang`, `nang_w`, `nang_h` all
   equal), checked with a message naming the layer.  Serialise `outer`
   in the spec dict; old files load unchanged.
2. **Outline protocol.**  One interface for circle and rectangle (points
   along a side, corner points, extent in a direction, max extent), used
   by the ring builder and the checks.  No new `isinstance` chains
   (decision 0026: a contour shape should be one more class).
3. **Ring builder.**  Four blocks between any inner and outer outline,
   reusing the inner layer's entities (the stacking protocol of
   `build_annulus`).
   - Circle inside: corner lines from the O-H corners (45°) to the outer
     corners.
   - Rectangle inside: corner lines from the inner corners outward
     along their diagonals.
   - Circle outside a rectangle: arcs split at those diagonal
     directions.
   - Respect `rot` and `stretch` (miter cut faces) like `build_annulus`.
4. **Validation.**  Containment with a minimum gap (each outline strictly
   inside the next, at every angle), naming the layer; outlines centred
   is a rule in `validate()`, not an assumption in the data model.
5. **Fittings.**  Lift the rectangle-core shell rejection in
   `check_supported`.  Bend radius and spline/closure checks against the
   outermost outline (half-extent in the bend plane; half-diagonal where
   the plane varies).  `Reducer`: outline sizes may change, shapes and
   counts may not.  `Tee`, `Wye`, `Elbow` keep their rules (they reject
   these specs with a message naming the limit).  `stack_changes`: whole
   outer layers, any outline.
6. **Grading.**  `first_cell` on a shape-changing shell: solved at the
   longest radial of the ring (state where, as for the O-H core).
7. **Signatures.**  Confirm a circle-in-square ring classifies as class 0
   against a circle-in-circle ring with equal counts; record the result.
8. **Kit cases:** circle core + square shell; circle core + 2:1
   rectangle shell; 2:1 rectangle core + circle shell; rectangle core +
   rectangle shell + rectangle shell (`dR`); circle + rectangle +
   circle; each through a straight and an easy-way and a hard-way bend;
   one with `stack_changes` ending the outer layer.
9. Remove `square_shell`, `SquareShellSpec`, `faces/square_shell.py`
   and their tests, or port the tests to `outer=`.

**Accept.**
- Every kit case: validates, meshes all-hex, meshed = predicted,
  conformal interfaces (`interface_*` groups present and matched), quality
  check ok; min SICN and min scaled Jacobian reported per case.
- Wall exactness (task 0025's check): nodes on flat sides lie on their
  planes, on arcs on their circles, to the check's tolerance.
- Containment, count and fitting rejections each raise naming the layer
  or fitting and the limit.
- `to_dict()` → `from_dict()` round trip for each new spec.
- Existing circular-shell meshes unchanged (node coordinates to 1e-12 on
  the existing kit cases).
- Full suite: no new failures.

**Out of scope.**  Changing outline shape along the axis (task 0046);
an aspect-ratio limit (task 0047, report the numbers here); unequal
counts per side; junctions with shells; tube bundles.

## Agent notes

- **Outline protocol** (`core/shape.py`): `CircleShape` and `RectShape`
  answer `corner`, `ring_corner(direction)`, `side(p0, p1, s)`,
  `side_curve`, `side_count`, `extent(angle)`, `max_extent`,
  `distance(u, v)`, `grown(dR)`, `scaled`, `lerp`, `counts`, `period`,
  `to_dict` (+ `shape_from_dict`).  Callers dispatch on `side_curve`
  ("arc"/"line") or call the protocol; no new `isinstance` chains.  A
  contour shape would be one more class with these members.
  `BlendShape` (Transition stations) has the subset a spec asks of it.
- **Spec**: `LayerSpec(name, dR, nrad, mprg, outer)` with exactly one of
  `dR`/`outer`; `PipeSpec.outlines`, `PipeSpec.corners()`.  `shell()`'s
  signature keeps `dR` second, so existing positional calls work.
  `square_shell`, `SquareShellSpec`, `faces/square_shell.py` and
  `build_square_shell` removed; a saved `"square_shell"` dict loads as the
  same ring (square `outer` with the stack's `nang`).  `BundleSpec` now
  requires the outermost outline to be a `RectShape` (it was untested and
  is still unused).
- **Ring**: `build_ring(inner, outer, …)` in `faces/annulus.py`, same
  entity creation order as the old `build_annulus`, which is now a
  wrapper (`inner.shape.grown(dR)`).  Corner lines leave the inner
  corners in the direction from the centre (`ring_corner`), so a
  rectangle core's corner lines run along its diagonals and a circle
  outside it is split there.  `rot` and `stretch` handled as before.
- **Containment** (`interface.check_outlines`, from `check_supported`):
  support functions compared over 720 angles plus every corner direction;
  `limits.OUTLINE_MIN_GAP = 1e-3` of the outer outline's max extent.
  Valid because the outlines are convex and concentric.
- **Reducer**: interpolates each layer as given (`dR` linearly, an
  `outer` outline by `lerp`), so circular reducers are unchanged; a
  rectangle's sides interpolate linearly, so its walls are planes and the
  exactness check holds.  Profiled reducers scale every size.
- **`refined(k)`** also scales the counts of `outer` outlines.
- **Drum nozzles**: every outline must be circular (was: the core).
- **Kit helper fix**: `_rect_dev` in the conformance kit rotated by
  `spec.rot` (degrees) as if radians.  Harmless (every kit duct has
  rot 0); the new `_outline_dev` uses `rot_rad`.

## Questions for design

_None._

## Outcome

**Files.**  `core/shape.py` (outline protocol, `ring_corners`,
`longest_radial`, `shape_from_dict`), `core/spec.py`, `faces/annulus.py`
(`build_ring`), `faces/__init__.py`, `faces/square_shell.py` (removed),
`assembly/interface.py` (`outer_radius`, `half_extent`, `build_face`,
`check_outlines`), `assembly/limits.py` (`OUTLINE_MIN_GAP`),
`assembly/fittings.py` (Reducer, Elbow rule), `assembly/sweep.py`
(termination compares outlines; clearance message), `assembly/intent.py`
(refinement), `assembly/equipment.py`; docs `API.md`, `README.md`.

**Tests.**  New `tests/test_layer_outlines.py` (24): spec, period,
extents, counts, `n_outer`, round trip, old `square_shell` dicts,
`BundleSpec`, `first_cell` spans, class 0, containment (3), fitting
rejections (Elbow, Tee, Wye, Transition, Reducer shape change),
termination, drum nozzles.  Conformance kit: 18 new cases (5 stacks ×
straight / easy / hard, plus rolled c-r-c bend, lagging stop/restart via
`stack_changes`, duct-stack reducer, miter); `wall_deviations` measures
every layer's outline (`_outline_dev`).  The kit cases also run through
`test_intent` round trips and `test_refined`.  Square-shell tests ported
to `build_ring` / `outer=`.  Full suite: 1693 passed, 5 skipped (was 1368 + 5).

**Signature (item 7).**  A circle-in-square and a circle-in-2:1-rectangle
ring have *the same* signature as a circle-in-circle ring with equal
counts (`LayerSig` kind `annulus`; combinatorial period 90° from the
counts), so class 0.  Roll handling uses the geometric `PipeSpec.period`,
now the largest over the outlines (180° for a 2:1 rectangle anywhere in
the stack).

**Existing meshes unchanged.**  All 46 pre-existing kit cases meshed in a
worktree at HEAD (2373ca6) and in this tree: node coordinates identical
(max |Δx| = 0).

**Quality** (straight 0.2 → fitting → straight 0.2; bends R = 0.5; core
r = 0.1 / 2:1 0.1 × 0.05; `nang` 4, core nrad 3):

| case | hexes = predicted | min SICN | min SJ |
|---|---|---|---|
| straight-2layer (reference) | 672 | 0.290 | 0.754 |
| duct-straight (reference) | 224 | 0.255 | 0.857 |
| circle-square straight / easy / hard | 784 / 1120 / 1120 | 0.290 / 0.207 / 0.207 | 0.710 / 0.677 / 0.677 |
| circle-2:1 straight / easy / hard | 784 / 1120 / 1120 | 0.155 / 0.120 / 0.138 | 0.533 / 0.532 / 0.507 |
| 2:1-circle straight / easy / hard | 784 / 1120 / 1120 | 0.166 / 0.121 / 0.110 | 0.338 / 0.333 / 0.323 |
| rect+rect+rect (dR) straight / easy / hard | 896 / 1280 / 1280 | 0.130 / 0.094 / 0.088 | 0.889 / 0.856 / 0.878 |
| c-r-c straight / easy / hard | 896 / 1280 / 1280 | 0.149 / 0.109 / 0.109 | 0.494 / 0.476 / 0.476 |
| c-r-c rolled bend (−60°, roll 45) | 1024 | 0.108 | 0.478 |
| lagging gap (stack_changes) | 1216 | 0.130 | 0.889 |
| duct-stack reducer | 896 | 0.130 | 0.829 |
| circle-2:1 miter | 1344 | 0.138 | 0.530 |

**Surprises / for task 0047.**
- The scaled Jacobian falls with skew, as decision 0026 expects: 0.71 for
  a circle in a square, 0.53 in a 2:1 rectangle (radius 0.1 in
  0.25 × 0.125), 0.34 for a 2:1 rectangle in a circle (radius 0.16;
  the casing's arcs split at the rectangle's diagonals, 53° / 127°).
  Task 0047's sweep should vary both the aspect ratio and the gap.
- Min SICN for the rectangle-in-rectangle stack (0.09) is below the
  single-layer duct's (0.24) while its SJ is the best of all: SICN
  penalises the thin, long cells of a 0.01 wall along a 0.2 side.
  Quality limits should say which metric they bound.

**Proposed follow-ups.**  None beyond 0046 and 0047.
