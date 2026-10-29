# 0031 — General branch junctions: laterals, offset taps and arbitrary roll

- **Status:** accepted (2026-10-29, by the user: "accept"), as
  recommended
- **Date:** 2026-10-29
- **Tasks:** 0060 (stage 1, `angle`), 0061 (stage 2, `offset`), 0062
  (stage 3, `twist`), 0063 (stage 4, duct shoe taps)

## Context

`Tee` is perpendicular and centred.  Since task 0040 its branch can
point in 90° steps about the run (`roll`, `toward=`), and since 0052 it
carries shells.  What real networks also need:
- **Laterals:** a branch at α < 90° to the run (45° laterals in plant
  piping; the Štigler lateral benchmark at 30°–90°, RESEARCH §7.2; HVAC
  "shoe" taps on ducts).
- **Offset (tangential) taps:** the branch axis doesn't pass through the
  main axis (PCF SKEYs TTSO/TORF and TOSO/TORF, `docs/integrations/pcf.md`;
  rejected by the reader today, decision 0023).
- **Arbitrary roll:** a branch pointing in any direction about the run,
  not only in 90° steps.  PCF set-on branches at odd angles are rejected
  today, and vascular bifurcations have arbitrary planes (decision 0018).

What already exists:
- **The exact intersection curve** for any α and offset h, checked
  numerically (RESEARCH §3.1):
  `P(φ) = h e_y + s(φ) d + r cos φ u + r sin φ e_y`, with
  `s(φ) = (√(R² − (h + r sin φ)²) − r cos φ cos α) / sin α`, valid for
  |h| + r < R and 0 < α ≤ 90°.  Tips move by arcsin(h/R) around the main
  axis, and become asymmetric along it when α ≠ 90° (RESEARCH §3.2).
- **The tee's block layout** (DESIGN §7.1): a continuous ring layer,
  turn faces bisecting the re-entrant corner, standard port faces.  Its
  saddle edges are already sampled splines of P(φ), so other α and h only
  change the points.
- **Exact walls for any tube union:** `projection.TubeUnion` (task 0051)
  takes tubes about arbitrary lines and rays, so a lateral's or offset
  tap's wall (and its shells at R + T, r + T) projects exactly (decision
  0029).
- **Predicted-quality limits** with two tiers and a hint (tasks 0047,
  0052).

## Options

### A. Generalise `Tee`: `angle` and `offset` fields
`Tee(…, angle=90, offset=0)`.  The layout keeps its topology; the saddle
points, the station positions (now asymmetric) and the turn faces follow
α and h.  One fitting for users and agents (decision 0019, constraint
4); every existing tee is the default case.

### B. A separate `Lateral` fitting
Clearer limits per class, but a second fitting with the same topology
and most of the same code.

### C. Arbitrary roll
1. **A twist fitting:** a straight whose cross-section rotates linearly
   by a given angle along its length (`Straight(twist=…)` or `Twist`).
   It used to be impossible (a twisted ruled surface isn't the cylinder,
   DESIGN §6).  With node projection (decision 0029) the wall nodes go
   onto the cylinder exactly, and the twist sets any roll before a
   junction.  The cost is cell skew, growing with twist per layer.
2. **Roll inside the junction:** the junction's inlet face rotated
   against its block layout.  Every junction becomes harder, and the
   twist still has to live somewhere.
3. **Absorb it in a neighbouring bend or closure** (as `Closure` already
   absorbs loop twist).  Works only where there is a bend.

### D. Shoe taps on ducts
A lateral on a rectangular main (with decision 0027): a planar
intersection, simpler than a pipe lateral.  It falls out of A once
0057/0058 exist.

## Decision (accepted as recommended)

**A + C1, staged; D after 0057/0058.**

1. **Stage 1, `angle`:** laterals, α from a lower bound set by
   measurement (the acute crotch degrades as α falls; start the sweep at
   30°, after the Štigler range) up to 90°.  Prototype, measure
   (predicted corner SJ and non-orthogonality against α and r/R), then
   set the two-tier limit (decision 0017's approach).
2. **Stage 2, `offset`:** |h| + r < R with a margin from measurement;
   maps PCF tangential and offset set-on SKEYs (decision 0023).
3. **Stage 3, `twist`:** `Straight(twist=degrees)`, walls by node
   projection.  `toward=` on a junction then resolves an off-grid
   direction into a twist on the preceding straight plus a junction
   roll in 90° steps, or rejects with the twist it would need if there
   is no straight to carry it.  Limit: twist per axial layer, from
   measured skew.
4. **Stage 4, ducts:** shoe taps (angle on a rectangular main), after
   0057/0058.

Equal tees (r = R) go through the wye family (amendment below).
Crosses and multi-branch headers stay out: they are a different template
(RESEARCH §4.3; `livesu_and_muntoni_etal_2016` for higher valence).

### Amendment (2026-10-29, accepted by the user): equal tees through the wye family

**Why r = R fails in the tee layout.**  The saddle's side height,
√(R² − r² sin² φ) at φ = ±90°, falls to zero.  The two walls become
tangent at (0, ±R, 0), and the intersection degenerates into two
ellipses crossing there.  The tee's turn faces bisect a re-entrant
corner that vanishes at those points, and the side ring blocks are
squeezed to zero thickness.  Up to r/R = 0.95 the tee is good (min SICN
rising with r/R, DESIGN §7.1), so the failure is sharp, not gradual.

**Decision: one public `Tee`, two internal layouts chosen by r/R.**
- **r/R ≤ τ:** the tee layout, unchanged (exact walls, shells,
  predicted-quality limits).  τ is set by measurement, about 0.95 (the
  measured tables reach 0.95); the constant lives in `limits.py`.
- **r = R** (within a relative tolerance): an equal-tee layout from the
  **wye family**: a three-way junction of equal tubes, inlet and
  daughters at 0° and at the branch angle, with the canal-surface wall
  and `TubeUnion` projection (decision 0029).
- **τ < r/R < 1:** rejected before GMSH, naming the ratio and the hint
  ("an equal tee, or a branch radius ≤ τ·R").  Real fittings almost
  never land there: standard reducing tees top out near r/R ≈ 0.9 by
  outside diameter (14″×12″: 355.6/323.8 ≈ 0.91; most are 0.75–0.88).
- **The same split for laterals** (`angle` < 90°): reduced laterals in
  the tee family, equal laterals in the wye family.
- **Users and agents never choose a layout:** the JSON stores a `Tee`,
  the layout follows deterministically (decision 0019, constraints 4
  and 5), and each layout has its own predicted-quality tiers in one
  error format.

**Why not route every tee through the wye family:** robustness.  The
tee layout is proven and complete.  The wye family has open crease and
knee issues (task 0056), no shells yet (0053), and its redesign ahead
(decision 0029, item 5).  It takes only the case the tee can't do.

**Consequences.**
- The equal-tee layout is part of the **wye-layout redesign**, whose
  scope grows to *asymmetric daughters* (equal tees and equal laterals
  as instances).  An equal tee's saddle is a crease with two tangency
  points, so the redesign's crease rules apply.
- Insulated equal tees come after wye shells (0053) and the redesign;
  insulated reduced tees exist already (0052).
- The PCF reader keeps rejecting equal tees until then, with a message
  that says they're planned (decision 0023 note).
- The redesign also matters for validation: the Štigler T-junction
  benchmark (RESEARCH §7.2) is equal-diameter.

## Consequences

- `Tee` gains `angle`, `offset`; `Straight` gains `twist`; DESIGN §7.1
  gains the general saddle; RESEARCH §3.2's "side corners" note is
  obsolete (the block-layout tee puts its corners on the branch
  diagonals) and should be marked so.
- PCF (0023): laterals and offset set-ons map instead of being rejected;
  odd-angle branches resolve through a twist.
- **Effect on future expansions:**
  - **0018 (vascular):** arbitrary branch planes through `twist`; the
    tube-union projector already covers non-coplanar axes.  Vascular
    bifurcations are wyes, so the wye-layout redesign (decision 0029,
    item 5) is still needed for them.
  - **0019 (agent SDK):** one fitting with typed fields; limits in
    `limits.py`; errors with hints (the twist needed, the angle bound).
  - **0021 (flow restrictions):** none.
  - **0028 (multi-layer junctions):** shells at R + T and r + T follow
    the general saddle, with the same projector.
  - **0030 (suite):** none.

## Verified vs. assumed

- **Verified:** the intersection formula (RESEARCH §3.1, numerically);
  `TubeUnion` takes arbitrary lines and rays (task 0051); the tee's
  saddle edges are sampled splines (`tee.py`).
- **Assumed:**
  - that the tee's topology stays valid for α down to about 30° and
    for useful offsets (stage 1/2 prototypes measure);
  - that a twisted straight with projected walls keeps acceptable skew
    for useful twists.
