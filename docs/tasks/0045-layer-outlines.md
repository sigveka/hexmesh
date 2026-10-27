# 0045 — Layer outlines: circle and rectangle in either order, and rectangle in rectangle

- **Status:** ready
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

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
