# 0010 — Equipment nozzles as network boundaries

- **Status:** done
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

- **Module:** `hexmesh/assembly/equipment.py`, holding `Drum`, `Nozzle`,
  `OnShell`, `OnHead` and `EquipmentError`, all exported from
  `hexmesh`.  Locations are two small dataclasses, not a string tag, so
  each one carries exactly its own parameters.
- **Conventions** (module docstring and API.md):
  - angles are in degrees, right-handed about `axis` from `up`, so the
    radial direction is `cos·up + sin·(axis × up)`;
  - `up` is orthogonalised against `axis`, as in `Frame.from_vectors`;
  - the first head lies beyond `position`, along `-axis`.
- **Heads:**
  - 2:1 ellipsoidal: `h = (R/2)·sqrt(1 − ρ²/R²)`;
  - hemispherical: `h = sqrt(R² − ρ²)`;
  - torispherical: crown sphere centred at
    `z0 = −sqrt((L − r)² − (R − r)²)`, and a knuckle torus centred at
    radius `R − r`.  The junction is at `ρj = (R − r)·L/(L − r)`;
    continuity and tangency there are tested.  `crown_radius` and
    `knuckle_radius` have **no defaults** (decision 0002: proportions
    depend on the design code), and `0 < r < R < L` is enforced.
- **Validation** (`Drum.validate`):
  - **shell:** `projection > R`, per the task (RESEARCH §3.1).
  - **head:** `projection > h(max(0, c − r))`.  `h` falls with ρ, so the
    highest footprint point is at its innermost radius; this is exact
    for the whole footprint, and tested with an off-centre nozzle that
    clears its centre height but not its inner edge.  The footprint must
    also satisfy `c + r ≤` the crown limit (`R`, or `ρj` for a
    torispherical head).
  - **size:** nozzle outer radius `< R`.
  - **Added (not in the task):** a shell footprint must stay between the
    tangent lines (`axial ± r` within `0 … length`).  Past a tangent line
    the shell intersection no longer holds.
  - **Overlap:** two head nozzles on the same head overlap when their
    disc centres are closer than `r1 + r2` (exact).  For two shell
    nozzles, footprint membership is `(s − s0)² + (R sin(θ − θ0))² < r²`
    on the near side, and the footprints overlap when any of 720 boundary
    points of one lies inside the other.  Tests cover axial, angular,
    across-0° and coincident cases.  Shell and head footprints cannot
    meet, since each is confined to its own region.  The check is strict
    overlap only: no reinforcement clearance.
- **Assembly:**
  - `Assembly.from_nozzle(drum, name, lc=None)` validates the drum, uses
    the nozzle's spec and exact frame, and names the inlet
    `"{drum.name}_{name}"`, so the patch is `fluid_D101_N1`.
  - `prepend` raises at a nozzle inlet, and `extend_open_ends` skips the
    upstream side, since pipe can't go inside the drum.
- **Ending at a nozzle is not implemented** (step 5); see Questions.
- **Serialisation** (0006): the inlet records
  `nozzle: {drum: Drum.to_dict(), name}`, and `from_dict` replays
  `from_nozzle`, so the drum is the authority for the pose.  Moving the
  drum in the file moves the network (tested).

## Questions for design

1. **Ending a network at a nozzle.**  `close(source, target, fitting)`
   requires *target* to be the inlet of an existing fitting
   (`target.edges[0].ports[0] is target`), and both ends to be open
   interfaces of the graph.  An equipment nozzle is neither: it has no
   fitting.  Also, a nozzle frame's normal points away from the drum,
   while a closing fitting's target normal must point along the flow,
   into the drum.  So `close()` cannot end a pipe at a nozzle without
   changing the rule.  I did not change it and implemented
   start-at-nozzle only, per the task.  Options for design:
   - (a) register a nozzle as a fitting-less open interface with the
     inward normal, and let `close()` accept such "terminal" targets;
   - (b) an `Assembly.end_at(source, drum, nozzle, fitting)` that builds
     the closing edge itself;
   - (c) a network may only start at equipment, and the user reverses
     the flow direction.
2. **DESIGN §5 wording** (decision 0002 asks for it once this task is
   done).  Proposed: "*Equipment* (first: `Drum`) is an Intent-layer
   node that owns open interfaces (its nozzles) but no fill and no
   geometry.  Nozzle poses follow from the equipment's dimensions;
   patch names are `{equipment}_{nozzle}`.  A network may start at a
   nozzle (`Assembly.from_nozzle`)."
3. **Nozzle clearance.**  Validation rejects strict footprint overlap
   only.  Should there be a minimum clearance, for reinforcement pads or
   a CFD region around the junction?

## Outcome

- **Files:**
  - new `hexmesh/assembly/equipment.py`;
  - `assembly/assembler.py`: `from_nozzle`, and the nozzle guard in
    `prepend` / `extend_open_ends`;
  - `assembly/intent.py`: the nozzle inlet;
  - exports in `assembly/__init__.py` and `hexmesh/__init__.py`;
  - new `tests/test_equipment.py` (39 tests);
  - docs: `API.md`, `README.md`.
- **Accept:**
  - frames for a horizontal and a vertical drum (shell, oblique, both
    heads, centred and off-centre) match hand values to 1e-12;
  - every shell face is at `projection` from the axis for six angles;
  - a face inside the shell, an oversized nozzle and overlapping nozzles
    each raise, naming the nozzle;
  - a network started at `D101/N1` meshes all-hex, with inlet patch
    `fluid_D101_N1`, the predicted cell count and positive SICN;
  - the conformance kit is unchanged.
- **Not done:** ending at a nozzle (Q1).
- **Tests:** 527 passed, 0 failed.
