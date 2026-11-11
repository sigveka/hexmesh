# 0141 — Bug: a tee's fill fails when its direction is 1e-16 off an axis

- **Status:** done
- **Decision:** none (a bug).  Found by the design session's ring
  prototype for task 0140, 2026-11-11.
- **Depends on:** none.  Before task 0140: a ring of tees placed by
  trigonometry hits it.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  A ring of eight identical tees (task 0140's prototype: R 0.02,
steel 0.003, branch r 0.012, `roll=90`, `Bend`s of 45° between them)
validates, then fails to mesh at the sixth tee: `fill failed
(Exception: Could not build surface filling)`, on clean `HEAD` (5089f66)
as well as in the working tree.  The sixth tee's inlet points along
−x up to rounding.  One tee alone reproduces it, and only at one
floating-point value:

```python
import warnings
from hexmesh import Assembly, PipeSpec, Tee, Session
warnings.simplefilter("ignore")
spec = PipeSpec(nang=6).core("lox", radius=0.02, nrad=4).shell("steel", dR=0.003, nrad=2)
for dz in (0.0, -1.2246e-16, 1.2246e-16, -1e-12, -1e-9, -1e-6):
    with Session("t"):
        asm = Assembly(spec, direction=[-1, 0, dz], up=[0, -1, 0])
        asm.add(Tee(branch_length=0.05, branch_radius=0.012))
        try: asm.mesh(); r = "ok"
        except Exception: r = "FAIL"
    print(dz, r)
# 0.0 ok; -1.2246e-16 FAIL; +1.2246e-16 ok; -1e-12 ok; -1e-9 ok; -1e-6 ok
```

`-1.2246e-16` is `-sin(π)`, what `[cos a, 0, -sin a]` gives at 180°.
A failure at exactly one rounding-level value, and not at 0 or 1e-12,
suggests hexmesh's frame arithmetic (a sign test, an `atan2`, a roll or
corner choice that flips at ±0) rather than the geometry kernel's
tolerances, but that is unconfirmed.  Measured in the same session: an
8-direction sweep of one tee in the ring's plane fails only at 180°;
without the steel shell, at r/R 0.4, or at `nang` 8, the exact-axis
cases passed (not yet rerun at the failing value).

**Where.**  To be found: `hexmesh/assembly/tee.py` (junction layout,
`junction_toward`), `corners.py`, `blocks.py`, the frame code
(`interface.py`, `core/frame`-like helpers).  `tests/`.

**Do.**
1. **Find the cause.**  Compare the failing and passing (dz 0) cases
   step by step: the frames, the resolved roll, the corner order, the
   block layout and the points handed to `addSurfaceFilling`; find the
   first difference beyond rounding.  Record it under *Agent notes*.
2. **Fix it at the cause**, not by perturbing inputs: e.g. a robust
   sign or branch choice, or snapping a frame vector's rounding-level
   components where the frame is built (say which, and why that place).
   No mesh changes for directions that work today (the examples
   byte-identical).
3. **Tests:** the reproduction above (all six pass); one tee at each of
   the 8 ring directions `[cos a, 0, -sin a]`, a = 0°, 45° … 315°, meshed;
   and the same sweep for a `Wye` and a `Bend` (does the same choice
   exist there?), meshed or at least filled.
4. If the cause is in gmsh/OCC after all, record it in
   `docs/integrations/gmsh.md` with the minimal case, and work around it
   where hexmesh hands the geometry over.

**Accept.**
- The reproduction and the sweeps pass; meshes of today's examples
  byte-identical; full suite: no new failures.

**Out of scope.**  Task 0140's example itself.

## Agent notes

- **Step 1, the cause: OCC's plate filling, not hexmesh's frames**
  (2026-11-11).  The failing and passing (dz 0) cases have the same
  frames (up to the 1e-16 component), resolved roll, corner order and
  block layout: every `_surface` call up to the failing face takes the
  same branch.  The face that fails, `(B,1,0) (B,2,0) (Sd,2,0) (Sd,1,0)`
  (two lines, two splines; the 34th plate), is filled in both; its OCC
  curves agree to 1e-17.  OCC's plate refuses it at the default `tol3d`
  1e-4 and at every degree and point count tried, and copies of the four
  curves too; `tol3d` 1e-6 or 1e-3 and both B-spline fillings build.
  Written to BREP and read back (the text rounds the last bits) it
  builds at every tolerance, so there's no minimal file.  Recorded in
  `docs/integrations/gmsh.md`.
- **Step 4, the workaround where hexmesh hands the face over:**
  `blocks.BlockLayout._plate` builds the default plate first (every face
  that builds today is unchanged, so no mesh changes), and retries a
  refused one at `tol3d` relative to the face (`_PLATE_RETRY_TOLS`: 1e-6,
  the wall plates' `_WALL_TOL`, then 1e-3), gmsh's messages off for the
  attempts that may fail.  The reported tee: the first retry builds;
  the mesh is within 1.8e-4 R of the dz 0 tee's, worst minSICN 0.178 in
  both.
- **For task 0139**, same call: when the plate passes a relative `tol3d`
  from the start, the retry stays useful (the plate is chaotic at any
  tolerance: 1e-5 failed here where 1e-6 and 1e-3 built); its first
  retry value should then differ from 0139's chosen factor.
- `corners.py`'s default `side_surface` is also a plate, but every sweep
  passes `_ruled`; nothing in hexmesh uses the default today.

## Questions for design

## Outcome

Done 2026-11-11.

- **Cause:** OCC's plate filling (gmsh 4.12.1), chaotic at rounding
  level; not hexmesh's frame arithmetic (Agent notes; `gmsh.md`, "Plate
  filling is chaotic at rounding level").
- **Fix:** `hexmesh/assembly/blocks.py`: `BlockLayout._plate` and
  `_PLATE_RETRY_TOLS` (1e-6, 1e-3 of the face's extent), `_quiet`.  The
  default plate is tried first, so nothing that built before changes.
- **Tests:** `tests/test_rounding_directions.py`, 30: the six values of
  the reproduction, and a `Tee` (`roll=90`), a `Wye` and a `Bend` at each
  of the 8 ring directions, meshed.  Without the retry the reported
  value fails; with it all pass.  The `Wye` and `Bend` passed at every
  direction before the fix too (no plate was refused).
- **Checks:** the 31 examples byte-identical to `HEAD`; junction-related
  tests (blocks, tee, equal tee, duct tap, wye, switch, junction quality,
  PCF junctions, corrections, units, branch grading, the kit's tee /
  wye / lateral / switch cases): 767 passed, 1 xfailed.  **The full
  suite was not run**: twice stopped for low memory on the shared
  machine; the user chose the junction-related subset.
- **Measured:** the reported tee builds at the first retry (`tol3d`
  1.65e-8 m); its mesh is within 1.8e-4 R of the `[-1, 0, 0]` tee's,
  worst minSICN 0.178 in both.
- **For 0139:** keep the retry when the plate gets a relative `tol3d`
  (Agent notes).

