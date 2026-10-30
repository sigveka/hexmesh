# 0069 — Prototype: duct tap with a pillowed ring (hole on the wall)

- **Status:** done (prototype measured; the layout choice is Q1 for design)
- **Decision:** [0033 — Junction layout for duct taps](../decisions/0033-duct-tap-topology.md) (option B, accepted for prototyping)
- **Depends on:** —  (the duct sections of tasks 0028/0029; the tee's
  block-layout machinery and predicted-quality tiers from 0052)

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  A duct tap narrower than its face, and a round tap on a duct,
can't use the pipe tee's layout: the duct's creases would cross block
faces (task 0057, decision 0027's amendment).  The user chose to go
straight for a general layout.  This task prototypes it and measures
it; the layout is chosen on the numbers.

**The idea** (decision 0033, B).
- The hole is a patch of the main duct's own top-wall cells; its
  outline lies on mesh lines of the main's top face.
- The branch's O-grid ring layer continues into the main as a
  **pillow** sheet: a dome of cells under the hole patch whose boundary
  is a loop on the top wall around the hole.  The sheet ends on the wall
  (as pillowing does, RESEARCH §9.5, [`borden_and_benzley_etal_2000`]),
  not at a cap.
- The main's blocks are unchanged away from the dome, so the port faces
  stay the standard O-H face.
- The branch's own section joins the hole patch and the dome's rim.

**Where.**  A prototype first: `hexmesh/assembly/` (a new layout module,
e.g. `duct_tap.py`, on `BlockLayout`), behind `Tee` only once it
works.  Scripts and measurements in this session's scratchpad until
then.

**Do.**
1. **Rectangular tap inside the face** (q < a with a margin, p within the
   room), on a single-layer rectangular main, branch rectangular with
   the main's counts per side.  Work out:
   - which main cells the hole occupies (its outline on mesh lines);
   - the dome's extent (how many cells beyond the hole on the wall, how
     deep);
   - the blocks that realise it with `BlockLayout`.

   Write the layout down (a sketch in *Agent notes*) before coding.
2. **The sizing rule:** the hole's edges must fall on the main's mesh
   lines, so the tap size is tied to the main's counts.  State the rule,
   and what a user does when their tap size doesn't fit: the nearest
   valid size, or the counts that make it fit.  Give it as a hint.
3. **Round tap:** the same construction with a circular branch: the
   hole patch's outline approximates a circle on the wall (the branch's
   O-H corners at its diagonals), walls by node projection (decision
   0029) where needed.
4. **Full-width taps (q = a):** does the construction cover them (the
   dome's wall loop then meets the creases)?  If yes, say how; if no,
   say why.  This decides whether task 0057 returns.
5. **Measure** for each variant: predicted and meshed min corner SJ, max
   non-orthogonality, cell count against the main alone.  Over tap/face
   ratio 0.3 / 0.6 / 0.9, duct aspect 1 / 2 / 3, wide and narrow face,
   `nang` 4 and 8.  All-hex and conformal, with meshed = predicted.
6. **Report** under *Questions for design*: the layout, the sizing rule,
   the quality table, the full-width answer, and whether the collar
   (decision 0033, A) still needs prototyping.

**Accept** (for a prototype).
- A rectangular inside-the-face tap and a round tap mesh all-hex, with
  meshed = predicted, standard port faces and walls exact.  On a 2:1
  duct, wide face, ratio 0.6.
- The quality table and the sizing rule.
- The full-width question answered.
- Nothing merged into `Tee` yet (that is the follow-up task once design
  chooses).

**Out of scope.**  Shells; angled taps (decision 0031); merging into
`Tee`.

## Agent notes

**2026-10-30: step 1, the layout (written before coding).**

**Canonical frame.**
- x is the main axis; z points out of the tapped face (+U or −U for
  the wide face of a duct wider than tall, ±R for the narrow face).
- The duct's half-extents are a across (y) and b deep (z).
- The hole is |x| ≤ p, |y| ≤ q on the wall z = b.
- The main face's inner rectangle is (±iw, ±ih), with iw = a − t,
  ih = b − t and t = 0.4 min(a, b) (`build_oh_rect`).

**Main.**
- Port slabs A → Sa and Sd → B are standard: 5 blocks each, with Sa and
  Sd at x = ∓s and s = p + margin.
- Between the stations, the side rings S± and the bottom ring are
  unchanged, so every crease is a block edge.
- Only the top ring and the core between the stations are re-blocked,
  and their faces at the stations and towards S± stay single patches.
  The port faces stay the standard 5-patch O-H face.

**Top ring: an O-grid tube around a column K_r** (5 + 4 blocks).
- K_r runs from the hole (z = b) down to the core top (z = ih), with
  footprint (±p, ±q·iw/a) there.
- The 4 tube blocks join K_r's sides to the region's 4 faces: the two
  station patches and the two diagonal faces shared with S±.
- On the wall this is an O-grid: the hole patch plus 4 trapezoids
  between the hole outline and the junction's wall rectangle.  The
  trapezoids are planes; the creases are their outer edges.
- K_r carries the branch's O-H face, extruded down: a core column and 4
  ring columns.

**Core: the pillow (dome)** (5 + 6 blocks).
- K_c hangs from K_r's footprint into the core.  The core minus K_c is
  4 side blocks and 1 bottom block, so the core's faces at the stations,
  towards S± and towards the bottom ring stay single patches.
- Inside K_c, the branch's ring layer continues as a dome sheet around
  a dome core: 4 sides and a bottom, 6 blocks.

**Branch run:** the hole → port E, 5 blocks.

**Total:** 10 (slabs) + 3 (S±, bottom ring) + 9 (top ring) + 11 (core)
+ 5 (branch) = 38 blocks.

**Counts.**
- Opposite edges of a block share counts, so:
  - the hole's across edges carry the main's across count;
  - its along edges carry the junction section's axial count n_j;
  - K_r's depth carries the main's ring `nrad`;
  - K_c's depth carries the main's count across the core height;
  - the O-grid's radial count on the wall is free.
- So the branch has the main's counts per side, a class-0 port, with
  its frame turned so that its across count is the main's across count.
  n_j is the branch's count along x.

**Consequence for step 2: no sizing rule.**
- The tube's O-grid carries all of the main's across lines into the
  hole, so the hole's edges needn't fall on the straight duct's mesh
  lines, and any p, q inside the room fits.
- The decision's mesh-level picture (the hole as a subset of the main's
  wall cells) would need lines at y = ±q all along the run, which splits
  the port faces' top patch.
- The price: a tap of ratio 0.3 has the main's whole across count in
  30 % of the width, so its cells are 3× finer across than the main's,
  and the wall O-grid's trapezoids are skewed.  The prototype measures it.

**Round tap:** the same blocks.  The hole outline is the branch circle's
O-H outline (arcs on z = b, corners at the diagonals); K_r's sides are
cones; the branch walls are cylinders.  Class 0 needs a main with equal
counts per side.

**2026-10-30: steps 2–5, implementation and measurements.**
- **Module:** `hexmesh/assembly/duct_tap.py`, `DuctTap`: a stand-alone
  fitting on `BlockLayout`, not wired into `Tee`.
  - A single-layer rectangular main.
  - The tap is rectangular (`along`, `across`) or round (`radius`).
  - `face` "wide" / "narrow", `side` ±1.
  - Ports `main` and `branch`, both class 0.
  - `rect_face_vertices` is `face_vertices` for a rectangular face.
    (`face_vertices` places corners on a circle, so it is wrong for
    ducts: noted for the merge.)
- **The layout works first time for rectangular taps.**  Two fixes were
  needed for round taps, both found by meshing:
  - The stations must clear the hole's reach, r, not its O-H corner
    offset r/√2.
  - K_r's footprint at the core top must be a circle (arcs).  An arc at
    the wall over a chord at the core top gave a bulging filled face and
    a fold (SJ −0.24).
- **Tunables.**  Three tunables:
  - `margin`: the stations' distance beyond the hole, in units of t;
  - `dome`: K_c's depth, as a fraction of the core height;
  - `sheet`: the dome sheet's thickness.

  Their best values roughly double the min SJ in hard cases (3:1
  narrow, ratio 0.9: 0.066 → 0.164).  The best values change from case
  to case.  So `DuctTap.resolve` picks them in `add()` by maximising the
  predicted SJ over a 4 × 4 × 3 grid of pure layouts, as `Tee` resolves
  its run.  That costs 48 layouts per tap.
- **Step 5 grid:**
  - ratio 0.3 / 0.6 / 0.9 × aspect 1 / 2 / 3 × wide / narrow ×
    `nang` 4 / 8 × rectangular / round: 72 meshes;
  - main `nrad` 3, equal counts per side;
  - the tap's run is 3·w + 2·depth each side;
  - the scripts are in this session's scratchpad (`0069/`).
- **Result:**
  - All 72 are all-hex, with meshed = predicted cells.
  - Every wall node is on its plane or cylinder within 3e-16.
  - Meshed min SJ equals the predicted value, except for large round
    taps.  The worst of those: 3:1 wide, ratio 0.9, predicted 0.255,
    meshed 0.143 / 0.165 at `nang` 4 / 8; the arcs are curved where the
    estimate uses straight edges.
  - "Cells / plain" compares the tap's cells with a straight main and
    branch run with the same axial counts (`nang` 4).  On a square duct
    the narrow face is the wide face, so those rows are left out.

  | tap | face | aspect | ratio | meshed SJ `nang` 4 / 8 | max non-orth. 4 / 8 | cells / plain |
  |---|---|---|---|---|---|---|
  | rect | wide | 1:1 | 0.3 / 0.6 / 0.9 | 0.351 / 0.364 / 0.203 (same at 8) | 63–73 / 64–75 | 1.6–1.8 |
  | rect | wide | 2:1 | 0.3 / 0.6 / 0.9 | 0.417 / 0.373 / 0.417 | 59–62 / 62–65 | 1.6–1.9 |
  | rect | wide | 3:1 | 0.3 / 0.6 / 0.9 | 0.315 / 0.277 / 0.284 | 66–69 / 69–72 | 1.6–1.8 |
  | rect | narrow | 2:1 | 0.3 / 0.6 / 0.9 | 0.205 / 0.220 / 0.203 | 74–76 / 75–77 | 1.6–1.8 |
  | rect | narrow | 3:1 | 0.3 / 0.6 / 0.9 | 0.129 / 0.142 / 0.164 | 79–81 / 80–82 | 1.6–1.8 |
  | round | wide | 1:1 | 0.3 / 0.6 / 0.9 | 0.372 / 0.378 / 0.200 (0.196) | 56–74 / 60–75 | 1.6–2.0 |
  | round | wide | 2:1 | 0.3 / 0.6 / 0.9 | 0.432 / 0.404 / 0.360 (0.353) | 57–61 / 61–64 | 1.6–2.3 |
  | round | wide | 3:1 | 0.3 / 0.6 / 0.9 | 0.337 / 0.318 (0.334) / 0.143 (0.165) | 64–71 / 67–77 | 1.6–2.0 |
  | round | narrow | 2:1 | 0.3 / 0.6 / 0.9 | 0.199 / 0.229 / 0.200 (0.196) | 73–75 / 75–77 | 1.6–2.0 |
  | round | narrow | 3:1 | 0.3 / 0.6 / 0.9 | 0.125 / 0.145 / 0.153 | 79–81 / 80–82 | 1.6–2.0 |

  - **Hard cases:** the narrow face of a deep duct (the tap goes in
    along the duct's long side, the dome reaches into a deep, thin core)
    and the largest round taps.
  - **Non-orthogonality:** passes `OUTLINE_NONORTH_WARN` (70°) in most
    narrow-face cases, and reaches 81–82° on 3:1 narrow faces.
- **Step 4, full-width taps (q = a): not covered.**
  - The hole's corners land on the creases, so the ±y tube blocks have
    zero width.
  - K_r's footprint on the core top then reaches the core's ±y edges, so
    the core-minus-K_c side blocks share an edge with the core's faces:
    wedges, not hexes.
  - The pillow needs room on all four sides of the hole, in the wall and
    on the core top.  `test_full_width_tap_rejected` covers it (the
    prototype rejects it as "does not fit").
  - So 0057 returns for q = a.
- **Tests:** `tests/test_duct_tap.py`, 4 tests:
  - the accept case (2:1 duct, wide face, ratio 0.6), rectangular and
    round: all-hex, meshed = predicted, class-0 ports, quality ok, walls
    exact to 1e-12;
  - the pure layout valid on wide and narrow faces, both sides, 1:1 to
    3:1;
  - the full-width rejection.

## Questions for design

**Q1. Adopt B (the pillowed tap) as the duct-tap layout?**  Recommended,
on these numbers:
- **The layout** (*Agent notes*, step 1): 38 blocks.  The ports stay
  the standard O-H face, every crease is a block edge, and all walls are
  exact planes or cylinders, with no projection needed.  The same blocks
  serve rectangular and round taps.
- **The sizing rule: there isn't one.**
  - In block form, the tube's O-grid carries all of the main's across
    lines into the hole, so any tap inside the face fits.
  - The coupling that remains is the counts: the branch has the main's
    counts per side, a class-0 port, with its frame turned to match.  A
    round tap needs a main with equal counts per side.
  - The cost: a small tap is finer across than the main (3× at ratio
    0.3), and the tap section has 1.6–2.3× the cells of a plain main and
    branch run.
- **Quality:**
  - Every case is ≥ 0.125 min corner SJ.
  - Wide faces are ≥ 0.20, mostly 0.3–0.43.
  - Narrow faces of a 3:1 duct are 0.125–0.164, with non-orthogonality
    up to 82°.
  - With 0052's two tiers, narrow faces warn and nothing is rejected.
    Is a narrow-face tap on a 3:1 duct acceptable with a warning, or
    should it be rejected (e.g. by a non-orthogonality cap)?
- **Full-width taps: not covered** (*Agent notes*, step 4), so 0057
  returns as the complement for q = a.  The tap's across ratio needs an
  upper limit, below 1.  0.9 measures fine; the limit is where the ±y
  tube blocks get too thin, to be set when merging.
- **Collar (A):** not needed on these numbers.  B covers every inside-
  the-face case measured, with no sizing rule.
- **For the merge task:**
  - `Tee(branch=RectShape | CircleShape, face=…)` builds this layout on
    a rectangular main.
  - The tunables are resolved as here.
  - The predicted-SJ tiers apply, but round taps need the meshed check:
    the prediction overestimates them by up to 0.11.
  - `face_vertices` needs the rectangular case (`rect_face_vertices`).
  - The branch frame's orientation, which keeps counts per side, should
    be documented.

## Outcome

**Done (2026-10-30), as a prototype; the choice is Q1.**
- **Files:** `hexmesh/assembly/duct_tap.py` (new, not exported or
  wired into `Tee`), `tests/test_duct_tap.py` (4 tests).  Probe
  scripts and the 72-case results are in the session scratchpad.
- **Accept:**
  - Rectangular and round taps on a 2:1 duct, wide face, ratio 0.6:
    all-hex, meshed = predicted, standard ports, walls exact (SJ 0.373 /
    0.404).
  - The quality table, the sizing rule (none) and the full-width answer
    (not covered) are under *Agent notes*.
  - Nothing is merged into `Tee`.
- **Surprises:**
  - There's no sizing rule after all; the block-level O-grid removes it.
  - The tunables matter by up to 2.5×, so they're resolved per tap.
  - For round taps the predicted SJ can overestimate the meshed one by
    up to 0.11.
- **Follow-ups:**
  - the merge task;
  - 0057 for full-width taps;
  - an upper across-ratio limit;
  - a decision on the narrow-face (3:1) quality.
