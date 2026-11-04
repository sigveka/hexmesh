# 0085 — The O-H ↔ H switch, and `Transition` to an H rectangle

- **Status:** done
- **Decision:** [0036 — Cartesian (H) rectangular section](../decisions/0036-cartesian-rectangular-section.md) (items 5–6, rollout step 2); [0011](../decisions/0011-port-face-signatures-and-switch-strategies.md) (class 1, pillow / unpillow); DESIGN A4, §7.1
- **Depends on:** 0084.  Reuses task 0069's pillowed-dome construction
  (decision 0033 B).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  A rectangular O-H face is an H face with `nrad` ring layers
pillowed in (RESEARCH §7.11).  Going between them means ending those
ring sheets inside one fitting.  Circle ↔ rectangle transitions need it
once the H face is the default, and so do the duct junctions (0086).

**Where.**  New switch builder (in `assembly/`, using `sections`); the
`Switch` fitting; `Transition` in `assembly/fittings.py` (or its own
module, per decision 0037 item 5); tests; RESEARCH input via *Outcome*.

**Do.**
1. **Prototype both constructions** for a straight switch piece, O-H
   rect (`nang_w`, `nang_h`, `nrad`) ↔ H rect (`nang_w`, `nang_h`):
   - **turned out:** each ring sheet flares and ends on the wall along a
     loop, as the duct tap's dome (task 0069);
   - **capped:** each ring sheet closes with a cup across the duct, open
     toward the O-H side (core, four side, one cap and four corner-wedge
     blocks per sheet).
   - Measure each, predicted and meshed: min scaled Jacobian, max
     non-orthogonality, max skewness, and how the switch length must
     scale.  Use a/b = 1, 2, 4 and `nrad` = 1, 3, 6, with the ring
     graded as in typical specs.
2. **Choose.**
   - Prefer the one with the higher meshed min SJ.  If they are within
     0.05, prefer turned out (it reuses 0069's code).
   - If neither meets `limits.py`'s quality limits, stop: write the
     numbers under *Questions for design* and set `blocked`.
3. **`Switch(length=…, n_layers=…)`**: a sweep-like fitting between an
   O-H rectangular port and an H rectangular port with equal counts and
   the same shape.
   - It declares the class-1 strategy (decision 0011 item 3; DESIGN
     §6's `strategies`).  Either direction works.
   - `validate()` checks the counts and the length rule from step 1
     before GMSH.
   - It has an exact cell count.
4. **`Transition` with an H rectangular end**: circle O-H ↔ rect H, in
   either direction.  The transition stays a class-0 blend to an O-H
   rectangle, and the switch is embedded in its rectangular end slab(s)
   (DESIGN §7.1's paragraph on duct junctions; decision 0036 item 5).
   - The user passes only the two specs.
   - Multi-layer transitions (task 0046) keep working when the
     rectangular end is O-H.  With H plus shells, wait for 0086 and
     reject with a named error.
5. **Flow check** (OpenFOAM v2406, laminar, Re 100, the rect duct's
   setup): an O-H run → `Switch` → H run, fully developed.  Report:
   - the f·Re of each run, against the plain runs;
   - the pressure-loss defect over the switch, as a percentage of the
     developed Δp over the switch length;
   - the velocity field just downstream, compared with the series.

   This is a check, not a gate.  Report the numbers.

**Accept.**
- The chosen switch passes the conformance kit in both directions, and
  its signature pair classifies as class 1 and is accepted.
- An O-H ↔ H pair joined directly (no switch) is rejected before GMSH,
  naming class 1 and `Switch` as the fix.
- `Transition` circle ↔ rect H passes the kit, at a/b = 1 and 2.
- *Outcome*: the step 1 table, the choice and why, and the step 5
  numbers, written for RESEARCH §7.11.
- Every existing mesh unchanged (the default is still `"oh"`).
- Full suite: no new failures.

**Out of scope.**  Switches inside junctions (0086); the default flip
(0087); class-2 count changes at the switch (counts must match).

## Agent notes

**Steps 1–2 refined (design answer, 2026-11-04): capped only.**
Decision 0036 has an amendment under item 6, and RESEARCH §7.11 has the
argument.
- Step 1 prototypes the capped construction only.  Turned out is
  dropped, for the reason below.
- Step 2's choice is only whether capped meets `limits.py` over a/b
  1/2/4 and nrad 1/3/6, plus the length rule.  The tie-break toward
  turned out goes.
- If capped missed the limits, or needed an impractical length at
  nrad 6, the hybrid would be prototyped before stopping for design.
  The hybrid: inner sheets cross the outer one and end crosswise on the
  wall, and the outer one is capped.  Capped passes, so the hybrid isn't
  needed.

**Why turned out can't work.**  It can't end every ring sheet on the
wall.  The outermost ring sheet is dual to the
ring layer next to the wall, so its dual curve runs up the wall column of
cells.  It can leave that column only inward, never through the wall, so
it must close across the duct: that is a cap.  An inner sheet could turn
out only by crossing the sheets outside it, which is a hybrid that needs
nrad ≥ 2 and still caps the outermost sheet.  Task 0069's dome is a
different case, because its wall-ending sheets wrap around the tap's hole
column, and a straight duct has no hole.  The design session confirmed
the argument and generalised it.  On a flat wall where every edge has two
hexes, every wall hex on one side lies in one wall-normal sheet: the
O-H side's outer ring.  Leaving the wall needs an irregular wall edge,
with 3 hexes (60° wedges) or 1 (180°).

**Capped construction: 6 blocks, not the 10 per sheet the step listed.**
- Core: the O-H face's centre rectangle → level C at L − t, the same
  rectangle, where t = `oh.ring_thickness(half_w, half_h)`.
- Cap: a frustum C → the whole H face, nrad cells along the axis.
- Four side blocks: the ring patches → the wall from O to H, closed by
  the slants C → H.
- The three slants meet at 45° at each corner of C, like a cube O-grid's
  corner, so the corner min SJ is 1/√3 whatever the aspect ratio, nrad
  or length.
- All nrad ring sheets close in the one cap: the cap's axial cells are
  the sheets.  The corner-wedge blocks aren't needed.
- Cells: `nw·nh·(n + nrad) + 2(nw + nh)·nrad·n`.
- Parameter sweep: cap depth d = t and offset g = 0 were best.

**Step 1 table (capped).**
- Meshed in GMSH, with the metrics in numpy using OpenFOAM's formulas.
  Spot-checked against checkMesh (`scratchpad 0085/checkmesh.py`), they
  agree to all digits: non-orthogonality 51.0576, skewness 1.76483.
  Skewness is `faceSkewness` with boundary faces mirrored.
- Ring graded as `first_cell = 0.5 t / nrad` (as in the rect duct's
  specs); uniform H outlet; L = 3t, n_layers 3.
- Predicted min SJ is 0.577 in every row.

| a/b | nrad | switch cells | meshed min SJ | max non-orth | max skewness |
|---|---|---|---|---|---|
| 1 | 1 | 216 | 0.577 | 39.4° | 0.84 |
| 1 | 3 | 432 | 0.577 | 49.7° | 1.75 |
| 1 | 6 | 756 | 0.577 | 49.7° | 2.49 |
| 2 | 1 | 396 | 0.577 | 40.4° | 0.93 |
| 2 | 3 | 756 | 0.577 | 51.1° | 2.02 |
| 2 | 6 | 1296 | 0.577 | 51.1° | 2.50 |
| 4 | 1 | 756 | 0.577 | 42.5° | 0.97 |
| 4 | 3 | 1404 | 0.577 | 51.8° | 2.13 |
| 4 | 6 | 2376 | 0.577 | 51.8° | 2.49 |

**The slant angle sets the quality; the length rule follows from it**
(a/b 2, nrad 3, graded ring and H end; `scratchpad 0085/slant.py`).
- The slants C → H rise t (the ring thickness) over the cap depth d, at
  atan(t/d) from the axis.
- Min SJ depends on the slant alone.  It is the same at the shortest
  length L = d + 0.25t and at L = d + 2t:

| d / t | slant from the axis | meshed min SJ | max non-orth |
|---|---|---|---|
| 0.5 | 63.4° | 0.333 | 68.0° |
| 0.75 | 53.1° | 0.469 | 58.8° |
| 1 | 45° | **0.577** | 51.1° |
| 1.5 | 33.7° | 0.485 | 55.4–57.2° |
| 2 | 26.6° | 0.408 | 60.4–63.2° |
| 3 | 18.4° | 0.302 | 69.4–70.7° |

- So the cap is one ring thickness deep (45°, d = t), and the length
  rule is the cap plus a short core: L ≥ d + 0.25t = 1.25t.  A deeper
  cap would only lengthen the switch and lose quality.
- A shallower cap (d = 0.5t) shortens the switch to 0.75t, at min SJ
  0.333 and non-orth 68°.  That is near the warn limits (0.3 and 70°),
  so it isn't offered.

**Length scaling at d = t** (a/b 2, nrad 3):
- L/t of 1.25, 1.5, 2, 3 and 5 all give min SJ 0.577 and non-orth
  51.1–52.1°.
- Skewness goes 1.64 → 2.18 as L grows (the core's cells lengthen).
- Below L ≈ t the cap has no room, so the rule is `L ≥ 1.25 t`
  (`limits.SWITCH_MIN_LENGTH`).
- The length scales with the ring thickness, not with nrad or a/b.
- Graded rings raise skewness: the uniform ring at a/b 2, nrad 3 gives
  1.26 against 2.02 graded.

**Graded H outlet: put the grading change at C, not in the cap.**
- With the change in the cap: min SJ 0.39–0.49, non-orth 59–65°.
- With it in the core (C carries the H face's side grading): min SJ
  0.547–0.577, non-orth ≤ 54°.
- So C's edges carry the H grading, and the core block changes from the
  O-H face's uniform sides to it along the axis.

**`own_grading` (blocks.py).**
- gmsh transfinite volumes need equal node counts on opposite edges, but
  not equal grading.
- Without the flag, the H face's bump propagated through
  `_division_classes` to the O-H face's bound curves: "conflicting
  transfinite constraints".
- An edge marked `own_grading` keeps its grading and joins its class for
  the count only.
- The flag defaults to False, so existing layouts are unchanged.

**Direct O-H ↔ H join.** `signature.py`'s pillow branch now raises a
`ValueError`, naming class 1 and `Switch`, for every fitting that doesn't
declare `pillows`.  Before, it fired only when 1 was in the fitting's
strategies.  The assembly wraps the error as an `AssemblyError` in
`validate()`, before GMSH (test: a closed loop that switches once).

**Transition with an H end (step 4).**
- `Transition` declares classes {0, 1} and `pillows`.  Its class-1 use
  is the H end only: a layer that starts or ends still raises, with the
  classifier's wording.
- It splits into a class-0 blend to the O-H face of the H end's
  rectangle (the other end's nrad and mprg) plus a `Switch`.
- The switch takes m of the n_layers, the fewest that reach 1.25 t at
  equal shares of the length, with at least one layer left for the blend.
- `fill` builds the O-H station face between the two parts.
- Through the transition, min SJ 0.577 and non-orth 46.7° at a/b 1 and 2,
  both ways.

## Questions for design

## Outcome

Done 2026-11-04.  All acceptance items are met.  The flow check's loss
defect is negative (below).

**Choice (step 2): capped.**
- It meets `limits.py` everywhere on the grid: min SJ 0.577 against warn
  0.3, and non-orthogonality ≤ 54° against warn 70°.  The step 1 table
  and the slant-angle table are under *Agent notes*.
- The length rule is `L ≥ 1.25 t` (`limits.SWITCH_MIN_LENGTH`), so the
  switch is about one ring thickness long at any nrad.  At nrad 6 that
  is practical, so the hybrid wasn't needed.
- Turned out is impossible on a flat wall (decision 0036, amendment
  under item 6).

**Files.**
- New: `hexmesh/assembly/switch.py` (`Switch`) and `tests/test_switch.py`
  (34 tests).
- `hexmesh/assembly/fittings.py`: `Transition` with an H end (`_h_end`,
  `_split`, `_parts`; validate, cell_count, fill and path delegate).
- `hexmesh/assembly/blocks.py`: the `own_grading` edge flag, and
  `bind_face` for H faces.
- `hexmesh/assembly/signature.py`: the class-1 pillow message names
  `Switch` for every fitting that doesn't pillow.
- `hexmesh/assembly/limits.py`: `SWITCH_MIN_LENGTH`.
- Registration: `intent.py`, `assembly/__init__.py`, `hexmesh/__init__.py`.
- Tests:
  - `tests/test_fitting_conformance.py`: 6 switch cases and 4 H-end
    transition cases, plus the `Switch` branch of the wall check.
  - `tests/test_h_layout.py`: the pillow message; the obsolete
    `Transition` rejection case removed.
  - `tests/test_intent.py`: the registry.
- Docs: `API.md` (`Switch`, and the H end under `Transition`),
  `docs/GUIDE.md`, `docs/integrations/gmsh.md` (opposite edges may
  differ in grading) and `docs/integrations/openfoam.md` (a residual
  floor on a steady field).

**Acceptance.**
- **Kit, both directions:** O-H → H and H → O-H; a/b 1, 2 and 4; graded
  H ends; oblique.  The pair classifies as class 1 and is accepted.
- **A direct O-H ↔ H join is rejected by `validate()`**, before GMSH.
  The test is a closed loop with one switch: "That is switch class 1, a
  pillow … put a Switch between them".
- **`Transition` circle ↔ H rect** passes the kit at a/b 1 and 2, both
  ways, including a graded H end.
  - Through it: min SJ 0.577, non-orth 46.7°.
  - With shells it is rejected, naming 0086.
  - A layer that starts or ends is still rejected, naming the layer.
  - Multi-layer O-H transitions are unchanged.
- **Every existing mesh unchanged** (task 0065's method).
  - Full-suite recordings at 30df5be and in the working tree.
  - All 489 distinct meshes from before are in the after run, identical
    node for node.  The 31 new ones all come from switch and transition
    cases (`test_fitting_conformance`, `test_build_sync`, `test_intent`,
    `test_refined`, `test_switch`).
  - Messages: 649 before and 663 after.  Every difference is an intended
    rewording (the pillow message, `Transition`'s layer message, the
    removed 0085 rejection) or a new switch test's expected raise.
- **Full suite:** at 30df5be, 2627 passed, 15 skipped.  In the working
  tree, 2798 passed, 15 skipped, 2 failed.  Both failures were mine and
  are fixed:
  - the registry test now lists `Switch`;
  - a type check in `switch.py` took the DESIGN §3.1 shape-site count
    to 16 against a cap of 15.  It now asks the shape (`side_curve`).
  - After the fixes, `test_architecture`, `test_intent` and
    `test_switch` pass (191), and so do the switch and transition cases
    of the kit, `test_build_sync` and `test_refined` (315).
  - **Final full suite, at a869477:** 2800 passed, 15 skipped, 0 failed.

**Step 5: flow check** (OpenFOAM v2406, simpleFoam, laminar Re 100).
- **Setup:** the rect duct's setup at a/b 2, exact inlet; counts
  `nang_w` 24, `nang_h` 12, `nrad` 6 (the series' k = 2), axial cell D_h/4.
  - 10 D_h of O-H, then a `Switch` of 2t = 0.3 D_h (1 core layer), then
    14 D_h of H; 47 376 cells.
  - checkMesh OK: non-orth 53.0°, skewness 1.52.  Mass error 1e-11.
- **Convergence:** `residualControl` was never met, but the solution is
  steady.  Fields written every 2500 iterations up to 20 000 give the
  same numbers to every digit below, and the residuals are frozen
  (`openfoam.md`).
- **f·Re** (planes 3–7 D_h; downstream 6–10 D_h past the switch):

  | run | f·Re | the plain run on the same mesh | exact |
  |---|---|---|---|
  | O-H run | 62.627 | 62.627 (the series' `oh`, k = 2) | 62.192 |
  | H run | 61.122 | 61.082 (a plain H duct with these counts) | 62.192 |

  - The series' `h` row (61.696) has finer H counts (`nang_w + 2 nrad`
    per side), so it isn't this H run's comparison.
- **Loss defect over the switch:** −39.3% of the developed Δp over the
  switch length.
  - That is a loss coefficient K = −0.073 (on ½U²), or −0.12 D_h of
    duct.
  - The switch loses less than the developed flow would.  The absolute
    size is small: about the 2.4% gap between the two runs' gradients
    acting over 5 D_h.
  - It is probably the change from O-H's discrete profile to H's, not a
    physical recovery, but that was not separated.
- **Velocity downstream** (RMS / max error against the exact profile, as
  a share of u_c):

  | distance past the switch (D_h) | 0.5 | 1 | 2 | 3 | 6–12 | plain H run |
  |---|---|---|---|---|---|---|
  | RMS | 1.85% | 0.98% | 0.68% | 0.62% | 0.60% | 0.59% |
  | max | 2.89% | 2.04% | 1.35% | 1.16% | 1.10–1.12% | 1.07% |

  - Upstream, the O-H run gives RMS 0.29–0.38%, against 0.36% for the
    series' `oh` at k = 2.
  - So the profile recovers within about 3 D_h.
- **Outputs:** the cases were deleted; the numbers are here only.  Peak
  disk use was 74 MB per case, and the mesh recordings took 320 MB,
  also deleted.

**Surprises.**
- Min SJ depends only on the slant angle (*Agent notes*).
- gmsh accepts opposite transfinite edges with different gradings; only
  hexmesh's own edge classes forced one grading.
- The pillow rejection used to depend on whether a fitting declared
  class 1.  Now every non-pillowing fitting names `Switch`.

**Proposed follow-ups.**
- 0086: a switch inside shells, and H ports on duct junctions.
  `bind_face` already binds H faces, and its shell branch raises,
  naming 0086.
- RESEARCH §7.11: the slant-angle table and the flow numbers above.
- Possibly a committed validation case for the switch (the run takes
  about 30 min on 2 processes) if the loss defect matters for 0087's
  default flip.

