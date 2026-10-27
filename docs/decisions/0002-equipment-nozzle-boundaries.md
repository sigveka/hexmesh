# 0002 — Equipment nozzles as network boundaries

- **Status:** accepted
- **Date:** 2026-10-24
- **Tasks:** 0010

## Context

Industrial pipe networks start and end at equipment: drums, tanks, vessels,
pumps.  Most piping CFD stops at the equipment nozzle, and plant data (PCF,
isometrics) gives equipment nozzles as the network's end points.  Today a
user must work out every nozzle's absolute pose by hand.

Meshing equipment *interiors* is a separate question (decision 0003).

## Options

### A. Equipment as Intent-layer nodes that only provide interface poses
An `Equipment` (first: `Drum`) is defined by its geometry and a list of
nozzles.  It computes each nozzle's interface frame (position, normal,
roll) in pure Python.  The network attaches pipes to those interfaces.
The equipment itself creates no geometry, and its nozzles are open
interfaces named after the nozzle.

### B. Leave it to the user
No new code, but plant-data readers need it anyway, and every user
re-derives shell and head geometry.

## Decision

Option A.  It adds no rules: equipment nozzles are ordinary open
interfaces (A1, A3, A7), and nothing new is built in GMSH.

## Consequences

- New Intent-layer concept: equipment nodes that own interfaces but no
  fill.  DESIGN §3 already allows nodes with absolute positions, so no
  rule changes are needed.  Document the concept in DESIGN §5 when task
  0010 is done.
- Patch names come from equipment and nozzle names, e.g. `D101_N3`.
- A network may begin at an equipment nozzle instead of a free inlet.
  `Assembly` must accept an existing interface as its start.
- Decision 0003 can later give `Drum` a mesh without changing this API.

## Verified vs. assumed

- Head geometry (2:1 ellipsoidal, hemispherical, torispherical) follows
  standard proportions.  Check the torispherical crown and knuckle radii
  against the code the user works to (e.g. ASME VIII or EN 13445)
  before relying on them.
- PCF nozzle data: **verified 2026-10-25** against the PCF Reference
  Guide §10 (`docs/integrations/pcf.md`).  `EQUIPMENT-REFERENCE` blocks
  list `NOZZLE` entries with `REFERENCE`, `CO-ORDS` (x y z, size,
  connection) and `DIRECTION`.  `DIRECTION` is a compass/elevation word
  (`EAST`, `UP`, …), not a vector, so oblique nozzles need another
  source.  Pipelines attach via `END-CONNECTION-EQUIPMENT` /
  `CONNECTION-REFERENCE`.
