# 0086 — H ports on duct junctions, and shells around an H core

- **Status:** in progress
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

**Order of work.**
1. 0060's split first: 0060 isn't done, and this task's *Depends on*
   says to do the split first in that case.
2. Then step 4, which the task says goes before step 1.
3. Then steps 1, 2, 3, 5 and 6.

Task 0094 (structured errors) shares `duct_tap.py` and `tee.py`, so it
goes between or after this task's commits, never mixed into one.

**Step 0, the split (0060's design note), done 2026-11-04.**
- The duct-tap front end leaves `Tee` for `duct_tap.TapTemplate`:
  resolve, check, ports, layout, quality, fill and `meshed_sj_check`.
  - `Tee._template(spec)` picks it on a non-round main, and `Tee`
    delegates.
  - `FULL_WIDTH_RUN` moves with it.
  - `thicknesses`, `branch_spec` and `tee_wall` stay public in `tee.py`.
- The template reads the branch and the main through the shape
  protocol: `corner(0)` for the half-extents (exact: the corner is ±1
  times them), `max_extent` for a round tap's radius, `is_round`, and
  `counts`.
- `SHAPE_SITES_CAP` goes from 15 to 7.  What's left is the pipe tee's
  radius reads in `tee.py`, which are round by definition.
- **No behaviour change** (task 0065's method).  21 test files that
  build tees were recorded before and after:
  - 334 of 334 distinct meshes are identical node for node;
  - 339 of 339 messages are identical;
  - 1262 tests passed.
- The one difference is on an error path that no test reaches.
  `check()` on a duct tee with no `branch` used to raise an
  `AttributeError`.  It now raises the named "needs branch=" message.

**Step 4, done 2026-11-04.**  The junction blocks ask `sections.oh`
for the inner square.
- New in `sections/oh.py`: `inner_radius(r)` (= OH_RATIO·r, the
  centre to an inner corner) and `inner_half_side(r)` (= OH_RATIO·r/√2).
  `oh.py`'s own copies of the expression use them too.
- The tee (`ci`, `si`), the wye (crotch corner F) and the round duct tap
  call them.  No `OH_RATIO` is left in `assembly/`.
- **Every existing junction mesh is unchanged, bit for bit.**  24 test
  files that build tees, wyes or duct taps were recorded before and
  after: 349 of 349 distinct meshes and 358 of 358 messages are
  identical, and 1320 tests passed.
- **Surprise:** the first try wrote the pipe tee's `ci` as
  `inner_half_side(r)`, which is OH_RATIO·r/√2 where the old code had
  OH_RATIO·(r/√2).  The values differ by 1 ulp (relative 1.3e-16).  At
  branch ratio 0.9 that grew to 6.9e-12 in the nodes (the kit's
  `tee-0.9` cases), which is over the 1e-12 acceptance.  `ci` is now
  `inner_radius(r/√2)`, the old order.
- `test_topology_invariance` shares meshes between its tests.  Its
  recording keys depend on xdist scheduling, so compare its meshes by
  content, not by key.

## Questions for design

**Q1 (2026-11-04, step 1 waits on it): what `nrad` and ring grading do
a duct junction's internal O-H blocks get when its ports are H?**
- An H port has no `nrad` (decision 0036 item 4).  But the junction
  keeps O-H blocks inside (item 5), and so do the switch legs
  embedded at its ports.  Those need an `nrad` and an `mprg`.
- A round tap on an H main has the same gap.  Its branch port is a
  circle, so O-H, and today it takes the main's `nrad` and `mprg`.
- 0085's `Transition` H end had the other end's `nrad`.  A junction
  whose ports are all H has nothing to borrow from.
- Options:
  - **(a) Derived, no new field (proposed).**  `nrad` is the number of
    H cells across one ring thickness t on the H face's smaller side:
    `max(1, round(n_s · (1 − OH_RATIO) / 2))`, with n_s that side's
    count.  That gives 1 at n_s = 4–6, 2 at 8, 3 at 12 and 5 at 24.
    The ring's `mprg` is set so its first cell is the H face's wall
    cell on that side (`progression_for_first_cell`), so near-wall
    resolution doesn't jump across the switch.  The internal spec is
    stored resolved in the fitting, like the duct-tap tunables.
  - **(b) A `Tee(nrad=…, mprg=…)` field, required when the main is H.**
    Explicit, but it's an O-H parameter on an H network, against
    "users don't place switches" (item 5).
  - **(c) (a) as the default, with (b) as an override.**
- (a) or (c) also covers the round branch on an H main.
- I'm working steps 4, 2, 3 and 5 meanwhile; step 1 waits.

**Answer (design, 2026-11-04; the user agreed): (c), with (a) counted on
the real nodes.  Step 1 goes ahead.**
1. **Derived default.**
   - nrad is the number of H cells lying within one ring thickness t of
     the wall on the smaller side.  Count it on the H face's actual node
     positions (graded by `wall_bump` if any); at least 1.
   - The ring's `mprg` comes from `progression_for_first_cell`, so its
     first cell is the H face's wall cell on that side.
   - Warn, with the values, if that `mprg` is outside the limits or the
     predicted ring quality drops below `PREDICTED_SJ_WARN`.
2. **Store resolved.**  The derived nrad and mprg go into the fitting's
   `to_dict`.  `refined(k)` treats them like a spec's (nrad × k,
   mprg^(1/k)), so a series nests; never re-derive per level.
3. **Override:** an optional `Tee(nrad=, mprg=)`.
   - Used only when the junction's own O-H blocks have no O-H port to
     inherit from (an H main), and it then replaces the derived values.
   - `validate()` checks it before GMSH: nrad ≥ 1, mprg > 0, and the
     ring's predicted quality.
   - Plain numbers, documented in API.md (decision 0040's advisor will
     set them).
4. **A round tap on an H main:** the branch port is O-H with its own
   spec.  The derived or overridden values apply only to the junction's
   own blocks and the embedded switch legs on the main side.
5. **Tests:**
   - a uniform and a graded H main: the derived nrad matches a hand
     count, the first cell matches to 1e-9, and `to_dict` and refined
     nest;
   - the override, and its rejection when invalid;
   - a round tap on an H main.

## Outcome
