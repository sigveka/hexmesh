# 0062 — General branches, stage 3: `Straight(twist=…)`, and `toward=` at any roll

- **Status:** done
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

- **Walls exact without projection (step 2 refined).**  A twisted
  `Straight` places a station at every axial layer (`Path(twisted=True)`,
  one layer per slab, as a `Bend`), each rolled by twist × its axial
  fraction.  Every node is then on an exact station face: the wall nodes
  are on the station circles or rectangles, and the side faces carry no
  nodes.  So no projector is needed; the kit's exactness check measures
  it, and for a duct measures each node in its station's frame.  The
  radial faces are filled (not planar), as for a `Transition`.
- **Two quantities, not one (step 3).**  `validation/tools/straight_twist.py`
  predicts each case from the section's quads at three rolled stations
  (`section_quality.twist_quality`, pure numpy) and meshes it: equal to
  1e-9 in every meshed case.
  - SJ and non-orthogonality depend on the wall shear γ = atan(R Δθ / Δz)
    alone: Δθ 5°/Δz 0.25 R, 10°/0.5 R and 20°/R all give 0.757.  `nrad`
    changes nothing.  γ is the twist per length, so **n_layers can't
    change it**: only a longer run or a smaller twist can.
  - The face warp follows Δθ (5° → 5–7.5°, 20° → 20–45°, more for short
    layers).  More layers lower it.
  - Δθ = 45° (half a circle's period) is ambiguous for the corners
    (`frame_offset`): every such case fails.
- So I implemented two tiers.
  - The roll per layer: `STRAIGHT_TWIST_WARN` 15° and `STRAIGHT_TWIST_MAX`
    30° (the face warp, and a margin to the 45° ambiguity), with the
    `n_layers` hint; `n_layers=None` resolves to the warning tier.
  - The shear, through the existing predicted SJ / non-orthogonality
    tiers, where the section alone passes them, with a length-or-twist
    hint.  For a circle these are about 170° per outer radius of length
    (warn, γ ≈ 71°) and 350°/R (error, γ ≈ 81°).
  See *Questions for design*.
- **`toward=` (step 4).**  `Assembly.add` runs `_twist_for_toward` before
  resolving a junction (`Tee`, `Wye`: a `toward_offset` class attribute,
  0° and 90°).  The rest of the wanted roll, within ±P/2, goes to the
  `Straight` whose outlet is the junction's inlet: it must have been
  added (not closed or prepended), be untwisted, and the interface must
  be open.  Its outlet frame is rolled.  A rest within
  `JUNCTION_TOWARD_TOL` still snaps as before.  A straight with too few
  layers keeps its own code and `n_layers` hint.
- **PCF (step 5).**  The builder's junction pre-check now calls the same
  `_twist_for_toward` first, so a set-on or tee at an odd roll twists its
  host's upstream piece.  No rejection test existed for odd rolls (the
  builder's root re-roll handles the first junction).
## Questions for design

1. **Confirm the two-part limit.**  The step asked for one limit on the
   twist per layer.  The measurements give two quantities.
   - The **roll per layer** sets the face warp, and more layers lower it.
     Implemented: `STRAIGHT_TWIST_WARN` 15° and `STRAIGHT_TWIST_MAX` 30°,
     with the `n_layers` hint.  Evidence: OpenFOAM v2406 `checkMesh
     -allGeometry` passes every case up to 30° (face flatness min 0.91 at
     30° and Δz 0.25 R, against its 0.8 flag; 0.989 at 15°), and 45° is
     the corners' ambiguity.  30° matches `MAX_CHORD_TURN`.  The warning
     tier at 15° is a judgement (flatness ≥ 0.99), not a measured harm.
   - The **wall shear** is the twist per length, so more layers don't
     change it.  It is implemented through the existing predicted SJ and
     non-orthogonality tiers (no new constant), with a length-or-twist
     hint.  For a circle that is about 170°/R_out to warn and 350°/R_out to
     raise.
2. **DESIGN §6 wording (proposed).**  "A twisted `Straight` places a
   station at every axial layer, rolled linearly with axial distance;
   every node lies on an exact station face, so its walls are exact
   without projection."
3. **`toward=` takes the rest from the preceding straight only if it is
   untwisted.**  A straight the user twisted keeps its twist, and the
   junction is rejected, naming the twist needed.  Adding to an existing
   twist would also work.  Is "explicit twist is the user's" the
   intended reading of step 4?

**Design answers (2026-11-09, the user: "yes"):** all three confirmed,
in decision 0031's amendment of 2026-11-09.
1. The two-part limit stands as implemented.
2. The wording is applied to DESIGN §6 through that amendment.
3. Yes: an explicit twist is the user's.

## Outcome

**Files.**
- `hexmesh/assembly/fittings.py`: `Straight.twist`, the twisted path,
  `layer_twist`, `layers_for`, `layers_ok`, and `validate` with the
  roll and shear tiers.
- `hexmesh/assembly/sweep.py`: `Path.twisted`, so radial faces are
  filled.
- `hexmesh/assembly/section_quality.py`: `twist_quality` and `face_warp`.
- `hexmesh/assembly/limits.py`: `STRAIGHT_TWIST_WARN` and
  `STRAIGHT_TWIST_MAX`.
- `hexmesh/assembly/assembler.py`: `_twist_for_toward`.
- `tee.py`, `wye.py`: `toward_offset`.
- `hexmesh/interchange/build.py`: the junction pre-check twists first.
- `hexmesh/errors.py`, `API.md`: `twist_per_layer_above_maximum`.
- `validation/tools/straight_twist.py` and `.json`.
- `hexmesh/agent/support.json`: regenerated; the Straight repr gains
  `twist=0.0`.
- Docs: `API.md` (Straight, Tee orientation, limits, the PCF row),
  `docs/integrations/pcf.md`, `docs/integrations/openfoam.md` (checkMesh
  on twisted hexes) and `CHANGELOG.md`.

**Tests.**
- Kit, 4 new cases, all passing: `straight-twist-90` (90° over 8
  layers), `straight-twist-2shell` (three layers, −60°),
  `duct-twist-180` (2:1, 180° over 12 layers) and `hduct-twist-90`.
  The duct's wall check now measures each node in its own station's
  frame.
- `tests/test_twist.py`: 20 tests, among them the acceptance case.  A
  tee with `toward=` 37° off `up` twists the straight by 37°, and its
  branch axis matches to 1e-9.  Also `refined(2)` keeps `twist` and
  doubles `n_layers`.
- `tests/test_pcf_junctions.py`: 1 new test (a set-on at 37°).
- Full suite: 3925 passed, 15 skipped, 2 failed, both mine and both
  fixed.  `test_every_error_is_coded` needs a literal `code=` on the
  shear raise.  `test_junction_toward_snaps_and_rejects` expects the
  miss unsigned, at 3 digits.  Their files (with the twist, PCF and
  manifest tests) then passed: 179.

**`twist=0` is bit-identical** to HEAD: five cases (plain; graded with
stack changes; both duct layouts; a tee after a straight) give a node
difference of 0.0.

**Quality table** (nang 8, nrad 3; nrad 2 and 5 give the same values
to 3 decimals).  Meshed = predicted to 1e-9 in every one of the 28
meshed cases, for SJ, non-orthogonality and warp.

| roll/layer ° | Δz / R | wall shear ° | min SJ | max non-orth ° | max face warp ° | verdict |
|---|---|---|---|---|---|---|
| 5 | 0.25 | 19.2 | 0.757 | 28.7 | 7.5 | ok |
| 10 | 0.25 | 34.9 | 0.713 | 33.1 | 17.7 | ok |
| 15 | 0.25 | 46.3 | 0.655 | 44.3 | 30.5 | ok |
| 20 | 0.25 | 54.4 | 0.580 | 52.4 | 45.5 | warns (roll) |
| 30 | 0.25 | 64.5 | 0.431 | 62.8 | 77.4 | warns (roll) |
| 40 | 0.25 | 70.3 | 0.341 | 68.9 | 105.3 | rejected (roll) |
| 5 | 1 | 5.0 | 0.772 | 28.1 | 5.2 | ok |
| 15 | 1 | 14.7 | 0.764 | 28.5 | 16.5 | ok |
| 30 | 1 | 27.6 | 0.738 | 29.4 | 36.3 | warns (roll) |
| 40 | 1 | 34.9 | 0.715 | 32.6 | 51.4 | rejected (roll) |

The untwisted section is SJ 0.773 and non-orthogonality 28.1°.

**Surprises.**
- No projector was needed: one station per layer puts every node on an
  exact face.
- The SJ and non-orthogonality don't depend on the layer count at all.
- `hexmesh/agent/validation.json` was stale since task 0109 (99 → 123
  MMS levels).  It was fixed in 0809f5a.

**Proposed follow-ups.**
- If design wants twist to add to a user's existing twist (question 3),
  it is a two-line change in `_twist_for_toward`.
