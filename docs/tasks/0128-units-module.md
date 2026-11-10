# 0128 — `hexmesh.units`: length constants, and an audit of absolute tolerances

- **Status:** ready
- **Decision:** [0047 — Length units](../decisions/0047-length-units.md); [0018](../decisions/0018-future-vascular-networks.md) (constraint 8)
- **Depends on:** none.  If task 0121 (the aorta) hasn't landed, leave
  its file to the design session and do step 3 for it afterwards.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Decision 0047: users write `CM = 0.01` and `INCH = 0.0254`
in every script.  One module of plain constants, metres underneath.

**Where.**  `hexmesh/units.py` (new), `hexmesh/interchange/importers/pcf.py`,
`hexmesh/examples/applications/idealised_aorta.py`, `API.md`,
`docs/GUIDE.md`, `CHANGELOG.md`, `tests/`.

**Do.**
1. **The module:** `m`, `cm`, `mm`, `um`, `inch`, `ft` as floats (metres
   per unit), with a docstring showing `radius=13.25 * mm`.  Not
   re-exported from `hexmesh`.  Listed in API.md beside "lengths are in
   metres".
2. **One source:** the PCF reader's `INCH` (and any other unit constant
   found by `grep`) imports from `hexmesh.units`.  Meshes unchanged.
3. **Use it** where an example's numbers come in other units (the aorta;
   any example that writes `* 1e-3` or `/ 1000` for a source in mm).
   Meshes byte-identical.
4. **Audit absolute lengths** (decision 0018, constraint 8): list every
   tolerance or default in `limits.py` and the fittings that is an
   absolute length in metres rather than relative to a radius or a cell
   (e.g. a merge or snap tolerance, a minimum length).  For each: what it
   is, its value, and whether a 1 mm vessel (radius 0.5 mm) would trip it.
   Fix it only if the fix is a one-line change to a relative tolerance
   with no mesh change; list the rest under *Questions for design*.
5. **The docs disagree today:** `hexmesh/core/params.py` says the
   `length` unit is "the user's length unit: hexmesh never converts",
   while API.md says lengths are metres (the architecture review,
   2026-11-10).  After step 4's audit, make both say the same thing,
   matching what the audit finds (metres, or any one unit if hexmesh is
   scale-free); the agent schema's `x-unit` text follows.
6. **Test:** a scaled build: the README's first example and one junction
   example with every length × 1e-3 (millimetre scale) validate and mesh
   with the same cell count and the same min SJ (to 1e-9) as at full
   size.  If one doesn't, that's an audit finding.

**Accept.**
- `from hexmesh.units import mm` works; API.md and GUIDE say so.
- No unit constant defined twice in the library.
- The audit table in *Outcome*; the scaled-build test passes or its
  failure is a question for design.
- *Outcome* says plainly whether hexmesh is scale-free (every length × k
  gives the same mesh scaled by k, to rounding), and what would have to
  change if not: decision 0047's note weighs an output `scale=` on it.
- Meshes byte-identical; full suite: no new failures.

**Out of scope.**  Quantity types, a per-assembly unit (decision 0047
rejects both); JSON in other units.

## Agent notes

## Questions for design

## Outcome
