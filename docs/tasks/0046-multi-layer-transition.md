# 0046 — Multi-layer `Transition`: every outline blends along the axis

- **Status:** ready (after 0045)
- **Decision:** [0026 — Layer outlines: shells of any shape](../decisions/0026-layer-outlines.md)
- **Depends on:** 0045.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `Transition` (task 0029) joins a circle and a rectangle, single
layer only.  With layer outlines, an insulated round pipe can become an
insulated rectangular duct, or a round conductor in a round sleeve a
rectangular one, with every layer changing shape along the run.

**Where.**  `hexmesh/assembly/fittings.py` (`Transition`), `sweep.py`,
`hexmesh/core/shape.py` (`BlendShape`), the ring builder from 0045,
kit, `API.md`.

**Do.**
1. `Transition(outlet, length, n_layers, axial_grading=1.0)` accepts
   multi-layer specs.  The two ends must have the same layers (names,
   order, `nrad`, grading) and equal counts per side; each layer's
   outline may change shape and size.  Reject anything else naming the
   layer and the field.
2. Each station blends every outline separately (a `BlendShape` per
   layer, the node blend of task 0029), so all layers change together
   and the rings stay nested.  Check containment at every station, not
   only the ends; reject naming the station and layer.
3. `Reducer` stays the fitting for size-only changes; `Transition` for
   shape changes (state the rule in both docstrings).

**Accept.**
- Kit cases: circle + circle shell → rectangle + rectangle shell; circle
  + square shell → circle + circle shell; a three-layer stack circle →
  2:1 rectangle.  Each validates, meshes all-hex, meshed = predicted,
  interfaces conformal at both ends, quality ok (report min SICN and
  scaled Jacobian).
- A transition whose layers would cross at some station is rejected
  before GMSH.
- Single-layer transitions unchanged (node coordinates to 1e-12).
- Full suite: no new failures.

**Out of scope.**  Unequal counts; changing the layer stack (that is
`stack_changes`).

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
