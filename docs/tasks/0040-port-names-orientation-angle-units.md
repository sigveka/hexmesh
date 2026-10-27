# 0040 — Named ports, absolute orientation (`toward=`, junction roll), `rot` in degrees

- **Status:** ready (after 0039)
- **Decision:** [0024 — API ergonomics](../decisions/0024-api-ergonomics.md)
- **Depends on:** 0039 (same `add()` code).  Coordinate with 0037 (PCF
  junctions use the Tee roll).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Outlet names depend on port order; `roll` is relative to a
frame that changes after every fitting; junction branches can only point
along the incoming `up`; `rot` is the one angle in radians.  Details and
choices: decision 0024.

**Where.**  `hexmesh/assembly/assembler.py` (`add`), `fittings.py`,
`tee.py`, `wye.py`, `intent.py` (format version, registry),
`hexmesh/core/spec.py` (`rot`), `signature.py` (period), `API.md`,
`README.md`, examples, tests.

**Do.**
1. **Port names.**  `port_names` on `Tee` (`("main", "branch")`) and
   `Wye` (`("left", "right")`).  `add(…, names=…)` accepts a list or a
   dict keyed by port name; unknown keys raise, listing the valid ones.
   Docstrings and `API.md` list each fitting's ports; `add`'s docstring
   states the tail rule.
2. **`toward=`** on `Bend`, `Elbow`, `MiterBend`: an absolute direction,
   resolved to `roll` in `add()` from the inlet frame (component
   perpendicular to the normal; reject if that component is below a
   tolerance, naming the angle to the normal).  Store only `roll` in the
   fitting and JSON.  Passing both `roll` and `toward` is an error.
3. **Junction roll.**  `roll` on `Tee` and `Wye`, restricted to
   multiples of the inlet section's symmetry period (`spec.period`,
   decision 0010); anything else is rejected naming the period.
   `toward=` on both picks the nearest allowed roll and rejects a
   direction more than a tolerance (e.g. 1°) off it, naming the
   deviation.  **Check conformity by meshing:** a Tee and a Wye at every
   allowed roll after a straight and after a rolled bend, meshed =
   predicted, all-hex, port signatures class 0.
4. **`rot` in degrees.**  `PipeSpec(rot=…)` in degrees; saved format
   version 2; `from_dict` converts version 1 (radians).  Search every
   caller (`tee.py`, `fittings.py`, `interface.py`, tests).
5. **Radians warning.**  A bend-like angle below 2π° (`Bend`, `Elbow`,
   `MiterBend`) gives a `UserWarning`.  Put the threshold and the
   tolerances above in one place a schema can read (decision 0019,
   constraint 6).
6. Rewrite `pipe_network` (and others where it reads better) with
   `toward=` and a sideways tee instead of the extra elbows; regenerate
   the gallery for changed examples.

**Accept.**
- Names: dict and list forms give identical `to_dict()`; a wrong key
  raises listing `main`, `branch`.
- `toward`: for random inlet frames and directions, the resolved bend
  turns its outlet normal into the plane of (normal, toward), on the
  `toward` side (test to 1e-9).
- Junction roll: step 3's meshing checks pass; a roll of 45° on a circle
  is rejected naming 90°.
- `rot`: a version-1 file with `rot` = π/4 loads as 45° and meshes
  identically (node coordinates to 1e-12) to before.
- Warning raised for `Bend(angle=1.57)`, not for 15°.
- Full suite: no new failures; examples meshed = predicted.

**Out of scope.**  Arbitrary branch orientation (needs a twist fitting,
decision 0024); structured error codes (decision 0019).

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
