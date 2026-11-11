# 0047 — Length units: plain constants in `hexmesh.units`, metres underneath

- **Status:** accepted (2026-11-10, the user: "seems like built-in units
  could be an idea?", then "yes" to design's proposal)
- **Date:** 2026-11-10
- **Tasks:** 0128

## Context

hexmesh's lengths are metres everywhere (API.md, first lines), and its
angles degrees.  Users' sources aren't: clinical papers give cm and mm,
plant data mm and inches.  The idealised aorta (task 0121) defined
`CM = 0.01` and multiplied every cited value; the PCF reader keeps its
own `INCH = 0.0254` (`hexmesh/interchange/importers/pcf.py`).  Every user
writes these constants again.  Decision 0018's constraint 8 (units and
scale) asks that nothing assume pipe-sized metres.

## Options

### A. Leave it to users
No change; every script defines its own constants.

### B. Plain constants (chosen)
`hexmesh.units`: floats, metres per unit.  `radius=13.25 * mm`.  Nothing
else changes: every argument stays a float in metres.

### C. Quantities (pint or an own unit type)
Arguments carry their unit and are converted.  It reaches every
signature, the JSON schema, the agent layer and error messages, and adds
a dependency or a type to maintain, to save a multiplication.

### D. A per-assembly scale (`Assembly(..., length_unit="mm")`)
Every length of that assembly in the given unit.  A second meaning for
every number, which saved descriptions, limits and error messages would
all have to carry.

## Decision (accepted: B)

- **`hexmesh.units`** with `m = 1.0`, `cm = 0.01`, `mm = 0.001`,
  `um = 1e-6`, `inch = 0.0254`, `ft = 0.3048`.  Imported as a module or
  by name (`from hexmesh.units import mm`); not re-exported at the top
  level, so `mm` doesn't land in `from hexmesh import *`.
- **Metres stay the only internal unit**: every argument, the saved
  description, the JSON schema, the CLI and the agent layer.  The
  constants are a convenience for writing the numbers.
- **One source:** the PCF reader's `INCH` (and any other constant like
  it) uses `hexmesh.units`.
- **Docs:** GUIDE and API.md say where units are introduced: "lengths in
  metres; `hexmesh.units` has `mm`, `cm`, `inch`, …".  The examples with
  non-metre sources (the aorta) use them.

## Consequences

- **API:** one new module, additive (decision 0042: a 0.x or 1.x
  addition).
- **Task 0128:** the module, its use, and an audit of absolute-metre
  tolerances (decision 0018's constraint 8): listed, fixed only where
  trivial; the rest become questions.
- **Future expansions:**
  - **0018 (vascular):** helped (millimetre vessels read as written);
    the audit addresses constraint 8.
  - **0019/0040 (agents):** none; JSON stays metres, and the schema says
    so.
  - **0021, 0030, 0035:** none.

## Verified vs. assumed

- **Verified:** metres throughout (API.md); the PCF reader's own
  constants; the aorta's `CM`.
- **Assumed:** that no current tolerance breaks at millimetre scale
  (the audit checks).

## Note: a scale-free library, after task 0128 (2026-11-10)

Discussed, not decided (the user: "A scale-free library would be
elegant"; a global `HEXMESH_UNIT` was discussed and set aside: the same
script would mean different things depending on a setting outside it).
If task 0128's audit and scaled-build test show hexmesh is scale-free
(the same mesh, scaled, for every length × k), a user could build in any
unit and convert once at the output (e.g. `write_openfoam(..., scale=1e-3)`).
That would be an amendment here, after 0128, alongside or instead of
`hexmesh.units`.

## Note (2026-11-11): task 0139's measurements, for `scale=`

Task 0139 measured how close hexmesh is to scale-free.
- Every plate tolerance hexmesh sets is now relative to its face.
- The README tee builds down to 1:1000, with the same cells and minimum
  quality at every scale.
- Its nodes match the full-size mesh × the scale **exactly** (< 1e-15) at
  1:2 and 1:4.  At other scales they drift: 7.6e-7 of the size at 1:10,
  4.5e-6 at 1:20, and up to 0.6 % below about 1:30.  The causes are OCC's
  fixed tolerance and the plate's chaos at rounding level.

So an output `scale=` (build at a reference size, scale once when
writing) would give exact small meshes, which building small doesn't.
Not decided.  It adds an argument to every writer, so the API review
(task 0150) takes it up, or reserves the name.

