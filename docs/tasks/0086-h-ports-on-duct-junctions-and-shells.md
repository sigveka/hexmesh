# 0086 — H ports on duct junctions, and shells around an H core

- **Status:** ready (after 0085)
- **Decision:** [0036 — Cartesian (H) rectangular section](../decisions/0036-cartesian-rectangular-section.md) (item 5, rollout step 3); [0026](../decisions/0026-layer-outlines.md) (layer outlines); DESIGN §7.1 ("Duct junctions and the H layout")
- **Depends on:** 0085 (the switch builder); 0060's split of the
  duct-tap front end out of `Tee`, if done by then.  Otherwise do that
  split first, as described in 0060's design note.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Before the default flips (0087), every rectangular fitting must
accept H ports.  Duct junctions keep their O-H blocks and embed the
switch in their legs, so users never place switches around them
(decision 0036 item 5).  Lagged ducts need shells around an H core.

**Where.**  `assembly/duct_tap.py` (and `tee.py`'s dispatch);
`sections/` (shells around `h`); `faces`/ring builders as moved by
0082; the conformance kit; the HVAC examples.

**Do.**
1. **Duct taps and duct tees on H mains and branches.**
   - When a duct junction's port is H, its leg next to that port
     includes the switch slab(s) from 0085.  The junction's internal
     blocks stay O-H.
   - The junction declares the class-1 strategy for those ports.
   - Cover round and rectangular branches, wide and narrow faces, and
     full-width taps.
   - The leg length grows by the switch's length rule; `validate()`
     reports it in the room checks.
2. **Shells around an H core** (lagged ducts, decision 0026):
   - The first shell's ring takes the H core's four corners as its
     inner corners.  The corner diagonals then lie in the shell (solid)
     and the fluid stays Cartesian (decision 0036, option B).
   - Support the outline combinations that rectangular O-H cores
     support today: rectangle in rectangle, rectangle in circle, and
     the kit's `_rect3` / `_in_rect` / `_rect_in_circle` cases.  Any
     other combination is rejected with a named error.
   - Measure the corner-cell quality of the first shell against the
     O-H equivalent.  Check it against the skewed-ring limit from task
     0047 (`limits.py`).
3. **`Transition` with shells and an H end**: lift 0085's rejection,
   once step 2 works.
4. **Junction blocks ask `sections.oh` for their inner square**
   (design answer to task 0082's Question 2, 2026-11-03).  The tee
   (`tee.py:340–341`), wye (`wye.py:374`) and duct tap
   (`duct_tap.py:229`) still compute `OH_RATIO · R` and the ring inset
   themselves.  Take the inner-square corners and the ring thickness
   from the layout instead, so the face and the junction blocks share
   one description (decision 0037).  Do this before step 1 adds H legs,
   so that work starts from the shared form.  Accept: no `OH_RATIO` in
   `assembly/`, and every existing junction mesh is unchanged (node
   coordinates to 1e-12, the 0065 method).
5. **The switch's loss defect, separated** (design, 2026-11-04, from
   task 0085's flow check; the user agreed).  0085 measured K = −0.073
   over a `Switch` (a/b 2, Re 100): the switch loses less than developed
   flow.  The likely cause is the change between the O-H and H
   discrete developed profiles, whose f·Re differ by 2.4 %.  Before
   switches go into every duct-junction leg, check that:
   - From the two plain runs' developed outlet planes (O-H and H, the
     counts of 0085's check), compute the momentum-flux coefficient
     β = ∫u² dA / (U² A) of each.  Also compute the kinetic-energy
     coefficient α = ∫u³ dA / (U³ A).
   - Predict the pressure-line shift from the momentum balance,
     Δp_shift = ρ U² (β_H − β_OH), and compare it with 0085's
     −0.12 D_h-equivalent defect.
   - Report both under *Outcome*.  If β accounts for the defect within
     about 20 %, say so: the switch itself adds no measurable loss.  If
     it doesn't, put the numbers under *Questions for design* before
     the junction flow work relies on switches.
   - Small: reuse 0085's setup, or a 2-D-equivalent short duct.  Delete
     the runs, keep the numbers.
6. **Examples:** build the HVAC examples (`hvac_supply`,
   `hvac_branched`) and `lagged_duct` with `layout="h"` explicitly, in
   a test (not in the examples yet; 0087 changes them).  Record cell
   counts and min SJ against the O-H versions.

**Accept.**
- The conformance kit passes for every duct-tap case in
  `tests/test_fitting_conformance.py` (`_duct_tap`), now with H ports,
  and for every layered duct spec with an H core.
- No fitting that takes rectangular ports rejects `layout="h"` any
  more.  List any exceptions under *Questions for design*.
- The H builds of the three examples mesh; *Outcome* has the cell-count
  and quality table against O-H.
- Every existing mesh unchanged (the default is still `"oh"`).
- Full suite: no new failures.

**Out of scope.**  Junction layouts native to the H face (a later
decision, only if these measure badly); the default flip (0087).

## Agent notes

## Questions for design

## Outcome
