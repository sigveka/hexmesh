# 0006 — Layer-stack changes inside sweep fittings

- **Status:** accepted
- **Date:** 2026-10-24 (accepted 2026-10-24)
- **Tasks:** 0018

## Context

In real piping, insulation and cladding stop and start: at flanges,
valves, supports and inspection points.  Wall thickness also changes.
DESIGN A4 already says layer-stack changes happen *inside* a fitting,
never across an interface, but no fitting implements one.

RESEARCH §9.1: removing an outer layer doesn't touch the twist planes of
the remaining layers.  The inner layers' mesh carries through unchanged;
only the removed layer ends.  So this is a cheap topology change, unlike
a node-count change (§9.3–9.4).

`sweep.Path` already supports a spec per station (`Path.spec_at`, used by
the planned Reducer).  `_fill_slab` pairs layers of the two faces
positionally.

## Options

### A. Layer termination inside `Sweep`
At a station where the spec loses one or more **outer** layers, the
station face is built with the full stack.  The slab before it fills all
layers.  The slab after it fills only the remaining layers.  The removed
layers' annuli on that station face become walls.  The downstream
side-surfaces of the new outermost layer become walls too, instead of
material interfaces.  The same applies in reverse when a layer starts.

Constraints, checked in `validate()`:
- only outermost layers may start or end;
- the remaining layers must have identical names, radii, `nrad` and
  grading on both sides;
- otherwise use a Reducer, which is a separate fitting.

### B. A dedicated `LayerChange` fitting
Same geometry, but as its own short fitting between two interfaces with
different stacks.  Clearer in the graph, but it adds a fitting where a
station property would do.

### C. Leave it to the user
Model insulation everywhere, or nowhere.  Wrong for CHT at uninsulated
flanges and valves, which are where heat losses concentrate.

## Decision

**Option A**, accepted 2026-10-24.  It is small, follows A4, and reuses
`Path.spec_at`.  Expose it to users as a sweep parameter (e.g.
`Straight(length, spec_out=...)` or a station list), and decide the exact
API in the task.

## Consequences

- **A7 physical groups:** end annuli go into a named group such as
  `{layer}_end`, optionally per fitting once task 0009 is done.  Each
  surface still belongs to exactly one group.
- **Conformance kit:** add a case with insulation ending and restarting
  inside one sweep.
- **Task 0018:** "Layer termination in `Sweep`".
  - match layers by name, not position, in `_fill_slab`;
  - build end walls;
  - validate the constraints above;
  - test that element count = inner-layer cells along the whole run +
    outer-layer cells only where present, and that each surface is in one
    group.
- **DESIGN.md:** §4 A4 and the §6.1 sweep table name outer-layer
  termination as a sweep capability (applied with this acceptance).
- Interacts with task 0003 (cell count).  The prediction must account for
  slabs with fewer layers.

## Verified vs. assumed

- Verified: `Path.spec_at` exists (`hexmesh/assembly/sweep.py`), and
  `_fill_slab` zips layers positionally.
- Assumed: removed layers' annuli are separate OCC surfaces on the
  station face, which they are when each layer is built as its own
  cross-section.  Check against `build_face`.
