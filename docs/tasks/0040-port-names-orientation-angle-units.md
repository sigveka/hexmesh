# 0040 — Named ports, absolute orientation (`toward=`, junction roll), `rot` in degrees

- **Status:** done
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

- **Resolution hook.**  Fittings have `resolve(inlet, spec)` (default on
  `Sweep`: no change); `Assembly.add()` and `close()` call it and store
  the result.  `toward` is a dataclass field with
  `metadata={"input": True}`: `fitting_to_dict` skips input fields that
  are `None`, so saved files hold only `roll`.  `check()` rejects an
  unresolved `toward` (a fitting used outside an assembly).
- **Bends.**  `toward_roll(frame, toward)` (`interface.py`):
  `roll = atan2(p·right, p·up)` of the component `p` across the inlet;
  `rotate(up, normal, roll)` then points along `p`.  `toward` with a
  negative `angle` is rejected (it would turn away).
- **Junction roll.**  `Tee` and `Wye` declare their block layout in the
  inlet frame rolled by `roll` (`interface.rolled`).  The port faces the
  layout binds were built in the unrolled frames, so `bind_face` gained a
  `shift` (corner *k* of the layout binds corner `(k + shift) % n` of the
  face), and `blocks.corner_shift` computes it from the two frames.
  - `Tee`: the main outlet keeps the inlet's `up` (shifted like the
    inlet); the branch frame is unchanged in form (`up` = main axis).
  - `Wye`: outlets keep the rolled `up` (a daughter is not perpendicular
    to the unrolled `up` at roll 90).
  - Checked that the meshing test catches a wrong shift: with the shift
    disabled, all 12 non-zero-roll cases fail.
- **Junction `toward`.**  `Tee`: the branch direction.  `Wye`: the
  direction the `right` daughter turns toward (the rolled `right`), so
  `toward` reads like a bend's.  Snapped to the nearest multiple of the
  period; the miss is measured about the inlet axis.
- **Port names.**  `port_names` on `Sweep` (`("outlet",)`), `Tee`, `Wye`.
  A names list of the wrong length is now an error (it was silently
  truncated); no caller relied on that.
- **Radians warning** is issued in `add()`/`close()`, not at
  construction: `Elbow` and `MiterBend` build internal `Bend`s, which
  would warn again.  It fires for a saved file's small bend on load too.
- **Limits** live in `hexmesh/assembly/limits.py`:
  `RADIANS_WARNING_BELOW`, `TOWARD_MIN_ANGLE`, `JUNCTION_TOWARD_TOL`
  (all degrees).  Existing limits (`MAX_MITER_CUT`, `MAX_CHORD_TURN`, the
  wye's `ANGLE_RANGE`) stay where they are.
- **`rot`.**  `PipeSpec.rot` is degrees; `PipeSpec.rot_rad` feeds the face
  builders (`interface.build_face`, `half_extent`,
  `corners.corner0_angle`).  The face builders themselves keep radians.
  `intent.upgrade` converts every spec dict in a version-1 file
  (inlet, drum nozzles, `Reducer`/`Transition` outlets, `stack_changes`).

## Questions for design

_None._

## Outcome

- **Done** 2026-10-27.
- **Files:**
  - new `hexmesh/assembly/limits.py`;
  - `assembler.py` (`add`/`close` resolve, `_port_names`, warning),
    `fittings.py` (`_Toward`, `toward` on `Bend`/`Elbow`/`MiterBend`),
    `sweep.py` (`resolve`, `port_names`), `tee.py`, `wye.py` (`roll`,
    `toward`, `port_names`, rolled layout), `blocks.py` (`corner_shift`,
    `bind_face(shift=)`), `interface.py` (`toward_roll`, `rolled`,
    `junction_roll`, `junction_toward`, `rot_rad` users), `corners.py`,
    `intent.py` (version 2, `upgrade`), `core/spec.py` (`rot` degrees);
  - tests: new `tests/test_orientation.py` (42); `test_rect_duct.py`,
    `test_corners.py` (rot in degrees), `test_miter.py` (expects the
    warning for its deliberate 5° miter);
  - `API.md`, `README.md`; `examples/networks/pipe_network.py` (sideways
    tees by `toward`, no extra elbows; 13 992 → 11 496 cells, min SICN
    0.189 unchanged) and its gallery entry.
- **Accept:**
  - names: list and dict give identical `to_dict()` (Tee, Wye, Straight);
    a wrong key lists `main, branch`;
  - `toward`: 25 random inlet frames and directions each for `Bend`,
    `Elbow`, `MiterBend`: outlet normal in the (normal, toward) plane to
    1e-9, on the toward side;
  - junction roll: Tee and Wye at 0/90/180/270°, after a straight and
    after a 30°-rolled bend (16 cases): validate, port pairs class 0,
    hex only, meshed = predicted, no coincident hex nodes, quality ok.
    Roll 45° on a circle is rejected naming 90°;
  - `rot`: a version-1 description with `rot = π/4` loads as 45° and
    meshes to the same nodes as `rot = 45` (to 1e-12, in the test).
    Against the code before this task (git worktree of `6c27306`,
    `rot = π/4` vs. now `rot = 45`, a circle + shell and a 2:1 duct
    through a straight and a bend): node coordinates identical (max
    difference 0.0);
  - warning for `Bend(angle=1.57)` (and `Elbow`, `MiterBend`), none for
    15°.
- **Tests:** full suite 1314 passed, 5 skipped, 0 failed (1272 before,
  +42).  `-m openfoam` output tests: 6 passed.
- **Surprises:** none in meshing: rolled junctions were conformal on the
  first run.
- **Follow-ups (proposed):** `pipe_rack` and `cooling_channels` would
  read better with `toward=` (`pipe_rack` is rewritten in 0041).
