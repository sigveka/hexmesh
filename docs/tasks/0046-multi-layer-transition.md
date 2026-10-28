# 0046 — Multi-layer `Transition`: every outline blends along the axis

- **Status:** done
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

- **Stations** (`Transition.station(spec, u)`): the core is a
  `BlendShape` of the end cores, as in task 0029; each shell is a
  `BlendShape` that also carries its ring's corners at both ends
  (`PipeSpec.corners()`).  Its sides blend the end rings' sides
  (`side(p0, p1, s)` between those corners), and `corners_from` returns
  the blended corners, so the corner lines blend too.  `build_ring` draws
  a station's sides as splines through 24 samples, as `build_oh_blend`
  does for the core.
- **Rules**: same layers is left to the class-0 check (it already names
  the layer and field); counts are checked per layer, naming it.  "Use
  Reducer" now means circles in every layer at both ends.
- **Nesting** (`Transition._check_nested`): `check_outlines` on each
  station and at 33 uniform fractions (the slabs are ruled, so a crossing
  between stations shows between them).  `BlendShape.extent` is the
  support function of 256 samples per side, cached.  At 64 per side the
  polygon under-read arcs by up to a fifth of `OUTLINE_MIN_GAP` and gave
  false rejections near the ends.  `extent` takes an array of angles
  (vectorised check): about 3 ms per station.

## Questions for design

_None._

## Outcome

**Files.**  `assembly/fittings.py` (`Transition`: rules, `station`,
`_check_nested`; `Reducer` docstring), `core/shape.py` (`BlendShape`
ring stations; `corners_from`; vectorised `extent`), `faces/annulus.py`
(spline sides), `assembly/interface.py` (vectorised `check_outlines`);
`API.md`, `README.md`.

**Tests.**  Kit: `transition-2layer-circle-rect` (circle + circle shell →
2:1 rectangle + rectangle shell), `transition-square-shell-circle`
(circle + square shell → circle + circle shell),
`transition-3layer-circle-2to1` (graded).  `tests/test_transition.py`
`TestMultiLayer` (6): cell count, station blends, station ends exact,
counts, shell-only change, crossing rejected before GMSH.  Rule tests
updated for the new messages; the single-layer-only rejection replaced by
a layer-mismatch test.  Full suite: 1744 passed, 5 skipped.

**Single-layer unchanged.**  All 46 pre-existing kit cases (the four
single-layer transitions included) meshed at the 0045 commit (7f87387)
and here: identical node coordinates (max |Δx| = 0).

**Quality** (all-hex, meshed = predicted):

| case | hexes | min SICN | min SJ |
|---|---|---|---|
| transition-circle-2to1 (single layer, reference) | 512 | 0.223 | 0.679 |
| transition-2layer-circle-rect | 768 | 0.119 | 0.679 |
| transition-square-shell-circle | 896 | 0.290 | 0.710 |
| transition-3layer-circle-2to1 | 1280 | 0.233 | 0.703 |

**Surprise: blending keeps nested layers nested.**  Over 2815 random
two-layer end pairs (circles and rectangles, gaps down to 0.3 %), no
station crossed.  Over 400 random 2–3-layer pairs at 256 samples per
side, the smallest interior gap was 0.996 of the smaller end gap.  Traced
along the length, the gap is smallest at the ends and grows toward the
middle.  So the station check is a safety net, not a limit users
meet, and the crossing test substitutes a crossing station
(monkeypatch).  `docs/RESEARCH.md` may want the observation; no proof
was attempted.

**Proposed follow-ups.**  None.
