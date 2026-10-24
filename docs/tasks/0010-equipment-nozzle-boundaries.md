# 0010 — Equipment nozzles as network boundaries

- **Status:** ready
- **Decision:** [0002 — Equipment nozzles as network boundaries](../decisions/0002-equipment-nozzle-boundaries.md)
- **Depends on:** — (integrate with 0006 serialization if that is done first)

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Networks start and end at equipment nozzles.  Users should
declare a drum and its nozzles once and get correct interface poses,
instead of working out each nozzle's absolute position, normal and roll by
hand.  This is pure Intent-layer work: no GMSH geometry for the drum.

**Where.**  New `hexmesh/assembly/equipment.py`.  `Assembly` in
`hexmesh/assembly/assembler.py` (start from or attach to a given
interface).  `Frame` in `hexmesh/assembly/interface.py`.

**Do.**
1. `Drum` dataclass (pure Python, numpy):
   - `diameter` (inside), `length` (tangent to tangent), `position` (centre
     of the first tangent plane), `axis` (unit vector; vertical and
     horizontal drums are just different axes), `up` (reference direction
     for angular positions).
   - `head`: `"ellipsoidal_2_1"` (depth D/4), `"hemispherical"` (depth D/2)
     or `"torispherical"` (crown radius and knuckle radius as parameters).
     Document the source of any default proportions, and **do not invent
     code-specific defaults**.  If unsure, require the parameters.
2. `Nozzle` dataclass: `name`, `spec` (PipeSpec), and a location:
   - **shell, radial:** axial distance from the first tangent plane,
     angle about the axis from `up`, `projection` = distance from the
     drum axis to the nozzle face;
   - **head, parallel to the axis:** which head, radial offset `c` and
     angle, `projection` = distance from the tangent plane to the nozzle
     face.
   Normal or hillside head nozzles are out of scope.
3. `Drum.frame(nozzle_name) -> Frame` for the **nozzle face**:
   - position at the face centre;
   - normal pointing away from the drum (the direction a pipe leaves in);
   - `up` defined by a documented convention: drum axis for shell
     nozzles, the head's radial direction for head nozzles (drum `up` for
     a centred nozzle).
4. `Drum.validate()` (no GMSH), raising errors that name the drum and
   nozzle:
   - the nozzle face lies outside the shell or head surface over the whole
     nozzle footprint.  For radial shell nozzles the intersection curve
     (RESEARCH §3.1) reaches at most R along the nozzle axis, so require
     `projection > R`.  For head
     nozzles use the head surface, e.g. for 2:1 ellipsoidal
     `z(φ) = b·sqrt(1 − |c + r·e(φ)|²/a²)`;
   - nozzle outer radius < drum radius; head nozzles stay inside the head
     (and inside the crown region for torispherical heads);
   - nozzle footprints don't overlap.
5. Connect to `Assembly`:
   - a network can **start** at a nozzle: `Assembly(spec, ...)` already
     takes a pose.  Add a convenience such as
     `Assembly.from_nozzle(drum, name)` with `inlet_name = f"{drum.name}_{name}"`;
   - a network can **end** at a nozzle.  This needs the nozzle registered
     as an existing open interface and joined with `Assembly.close()`.
     Check whether `close()`'s flow-direction rule (source = downstream
     end, target = upstream end) allows a pipe to *end* at an equipment
     interface.  If it does not, **don't change the rule**: record the
     question under *Questions for design* and implement start-at-nozzle
     only.
6. Patch names: `"{drum.name}_{nozzle.name}"` through the existing
   interface naming (A7).

**Accept.**
- Unit tests, no GMSH: frames for a horizontal and a vertical drum with
  known geometry (positions, normals, `up` vectors to 1e-12); every shell
  nozzle face centre is at distance `projection` from the axis.
- Validation tests: a nozzle face inside the shell, an oversized nozzle and
  overlapping nozzles each raise, naming the nozzle.
- One realisation test: a network starting at a drum nozzle meshes, and its
  inlet patch is named `D101_N1` (or similar).
- Conformance kit unchanged.

**Out of scope.**  Meshing the drum (decision 0003, proposed); normal or
hillside head nozzles; reading PCF.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
