# 0062 — General branches, stage 3: `Straight(twist=…)`, and `toward=` at any roll

- **Status:** ready (after 0060; independent of 0061)
- **Decision:** [0031 — General branch junctions](../decisions/0031-general-branch-junctions.md) (stage 3); walls by [0029](../decisions/0029-wall-exactness-by-node-projection.md)
- **Depends on:** 0051's node projection; 0040's `toward=` / roll
  resolution.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Junctions roll only in 90° steps (the section's period), so a
branch can't point in an arbitrary direction.  PCF set-ons at odd angles
are rejected, and vascular branch planes are arbitrary.

**Where.**  `hexmesh/assembly/fittings.py` / `sweep.py` (`Straight`),
`projection.py` (a cylinder projector for a straight),
`assembler.py` (`resolve` / `toward=` on junctions), `limits.py`,
`refined_dict`, kit, `API.md`, DESIGN §6 (design applies the wording if
needed).

**Do.**
1. **`Straight(…, twist=0.0)`**, in degrees: the cross-section rotates
   linearly about the axis from inlet to outlet.  The outlet frame's
   `up` is the inlet's rotated by `twist`.  Any twist, both signs.
   Works with shells and rectangular sections (the period rules of
   decision 0010 apply to what joins next, not to the twist).
2. **Walls:** the side faces are twisted, not cylinders, so walls (and
   shell boundaries, and a rectangle's planes) are made exact by node
   projection (decision 0029; a `TubeUnion` of one tube for circles; a
   plane projector for rectangle sides).  The kit's exactness check
   covers it.
3. **Limit:** twist per axial layer.  Measure predicted corner SJ and
   non-orthogonality against twist per layer (5°–45°) and `nrad`,
   propose a two-tier limit, and give the `n_layers` hint (or resolve
   `n_layers=None` to satisfy it).
4. **`toward=` on a junction at any direction:** if the wanted roll
   isn't a multiple of the period, and the junction's inlet is a
   `Straight` added by the same user without an explicit `twist`, set
   that straight's `twist` to the remainder.  Otherwise reject, naming
   the twist needed and where to put it.  Store the resolved numbers
   (JSON explicit).
5. **PCF:** set-on branches at odd angles map through a twist on the
   host pipe's upstream piece; update the rejection tests.

**Accept.**
- `twist=0` meshes identically to today's `Straight` (to 1e-12).
- Kit cases: a twisted single-layer pipe (90° over 8 layers), a
  twisted two-shell pipe, a twisted 2:1 duct (180°): all-hex, meshed =
  predicted, walls exact on the final mesh, quality reported.
- A tee placed with `toward=` at 37° off the up direction resolves a
  twist on the preceding straight; its branch axis matches to 1e-9.
- `refined(k)` keeps `twist` (geometry) and scales `n_layers`.
- The quality table and the proposed limit.
- Full suite: no new failures.

**Out of scope.**  Twist inside bends or junctions; non-linear twist
laws.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
