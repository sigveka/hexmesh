# 0063 — General branches, stage 4: shoe taps on ducts (`angle` on a rectangular main)

- **Status:** done
- **Decision:** [0031 — General branch junctions](../decisions/0031-general-branch-junctions.md) (stage 4); duct tees from [0027](../decisions/0027-duct-tees.md)
- **Depends on:** 0057 (rectangular tap), 0058 (round tap), 0060
  (`angle`).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  HVAC branch takeoffs are often "shoe" taps: the branch leaves
the main duct at an angle (typically 45°), for lower loss than a
straight tap.

**Where.**  `hexmesh/assembly/tee.py`, kit, `API.md`, the branched HVAC
example (0059) if it reads better with one.

**Do.**
1. `Tee(angle=…)` on a rectangular main, with a rectangular or round
   branch, on either face (0057/0058's `face`).  The hole on the flat
   face is the branch section cut at the angle: a stretched rectangle,
   or an ellipse for a round branch.  The corners stay on the branch's
   O-H corners.
2. Walls: planes are exact OCC surfaces; a round branch's cylinder by
   node projection, as in 0058.
3. Room checks, the predicted-quality tiers, the `run_length` hint.
4. **Measure:** predicted corner SJ over α ∈ {30, 45, 60, 90}° × branch
   ratio ∈ {0.3, 0.6} × rectangular / round branch.

**Accept.**
- `angle=90` matches 0057/0058's meshes (to 1e-12).
- Kit cases (45° rectangular shoe, 45° round shoe on a 2:1 duct):
  all-hex, meshed = predicted, class-0 ports, walls exact, quality ok.
- The quality table.
- Full suite: no new failures.

**Out of scope.**  Offset duct taps; splitter vanes (internals).

## Agent notes

- **Order.**  The user chose 0063 next (2026-11-09), ahead of design's
  0118; the design session was told.
- **Where the axis runs.**  Through the main's axis point o, as a pipe
  lateral's (0060), so the hole's centre on the face is b·cot α
  downstream of o.  Question 2 below.
- **The layout.**  Inside the main it is the perpendicular layout on the
  stretched hole (x scaled by 1/sin α about the hole's centre); only the
  branch run W → E leans, its edges along d.  A full-width tap's
  core-top corners are centred on the axis at z = ih, so its turn blocks
  lean with it.  Centred on the hole instead, the downstream turn block
  folds at exactly 45° (predicted SJ 0.0; 0.29 with the shift).
- **Step 2 refined: no projection.**  The round shoe's hole is an exact
  ellipse (`ArcAbout(stretch=…)`, the miter's `conic_arc`).  OCC's
  Stretch filling from it to the port's circle arc is the exact cylinder
  (2e-15 R; `docs/integrations/gmsh.md`).  So every shoe wall is exact
  with no node projection, as the perpendicular taps.
- **Moves for the architecture rules.**  `lean` moved from `tee.py` to
  `interface.py` (tee ↔ duct_tap cycle); `add_conic_arc` moved from
  `sections/_gmsh_helpers.py` to `_occ.conic_arc` (a private module
  crossing a package), keeping the old name in `sections`.

## Questions for design

1. **No minimum angle; the tiers decide.**  As for laterals (0060), no
   angle limit is added: every case down to 30° meshes, and the
   existing SJ and non-orthogonality tiers warn below about 45° (naming
   a larger angle).  Full-width shoes fall fastest (0.13 at 30°, reach
   0.3).  Confirm.
2. **Axis through the junction point.**  A shoe's hole sits b·cot α
   downstream of the point where its axis meets the main's (b·cot 45° =
   b; 1.7 b at 30°).  That matches pipe laterals and PCF's branch point.
   An HVAC user may expect to place the hole itself.  Keep, or add a way
   to place by the hole?
3. **Branch-run edge at 30°.**  Every pillowed shoe at 30° reads 0.224:
   the branch run's corner at the hole's upstream edge, angle α between
   the face and the branch wall.  A first run layer normal to the face
   would lift it.  Worth a follow-up, or are 30° shoes rare enough?

## Design answers (2026-11-09, the user: "yes")

Recorded in decision 0031's amendment (77138b3).
1. Confirmed: no minimum angle.  The tiers warn or reject and name a
   larger angle, as for laterals.
2. Keep the axis through the junction point; no hole-based placement
   before the 0.8 API review (a placement option can come in 1.x if
   users ask).  The GUIDE's shoe-tap text gives the offset, b·cot α
   downstream, with a worked example (added in this task).
3. The 30° branch-run edge (0.224) is a noted follow-up, not before 1.0.

## Outcome

**Files.**
- `hexmesh/assembly/duct_tap.py`: `angle` on `DuctTap` and
  `FullWidthTap` (`_lean`, the stretched hole, the leaning branch
  frame, the full-width core-top shift); `TapTemplate`: the range check,
  `shoe`, the room checks at the acute end with hints, the default
  `run_length`, and angle-aware tier hints (`nonorth_hint`).
  `angle_on_duct_tap` is retired.
- `hexmesh/assembly/blocks.py`: `ArcAbout(stretch=…)`, its points, and
  the ruled-cylinder test for stretched arcs.
- `hexmesh/_occ.py`: `conic_arc` (moved from
  `sections/_gmsh_helpers.add_conic_arc`, kept as an alias there).
- `hexmesh/assembly/interface.py`: `lean` (moved from `tee.py`).
- `docs/GUIDE.md`: shoe taps, the hole's offset with a worked example.
- `hexmesh/errors.py`, `API.md` (the shoe section, the code row),
  `CHANGELOG.md`, `docs/integrations/gmsh.md`.
- `validation/tools/duct_shoe.py` and `.json`.

**Tests.**
- Kit: 4 new cases, 24 checks, all passing: `tee-duct-rect-2-wide-shoe45`
  and `tee-duct-round-2-wide-shoe45` (the acceptance cases), plus
  `tee-duct-full-2-wide-shoe60` (oblique frame) and
  `tee-duct-h-rect-2-wide-shoe45` (H main).  All-hex, meshed =
  predicted, class-0 ports.  Walls exact: the kit's duct-tap wall check
  now measures the branch about its leaning axis; 9e-16 to 4e-15 on every
  shoe tried, including narrow faces and H mains.
- `tests/test_duct_tap.py`: 14 new tests: the hole is the cut section,
  the round hole an exact ellipse, the default `run_length`, five room
  checks whose hint values pass, the angle range, angle-aware hints, and
  JSON round trip and refinement.
- `tests/test_tee.py`: the old `angle_on_duct_tap` test is removed.
- Full suite: 3997 passed, 15 skipped, none failed.

**`angle=90` is bit-identical** to HEAD: all 16 kit duct-tap cases
(rectangular, round, full-width; both faces; O-H and H mains) give a node
difference of 0.0.

**Quality table** (`validation/tools/duct_shoe.json`): predicted min
corner SJ, with the meshed one in brackets where it differs; 2:1 duct,
wide face, 4 cells per side, nrad 3.  The ratio is the branch's reach
across the face over its half-width.  A full-width tap's ratio is its
length along the main.  "w" marks a warning.

| branch | ratio | 90° | 60° | 45° | 30° |
|---|---|---|---|---|---|
| rect | 0.3 | 0.417 | 0.404 | 0.401 | 0.224 w |
| rect | 0.6 | 0.373 | 0.352 | 0.343 | 0.224 w |
| round | 0.3 | 0.432 | 0.426 | 0.408 | 0.224 w |
| round | 0.6 | 0.404 | 0.405 | 0.408 | 0.224 (0.131) w |
| full | 0.3 | 0.403 | 0.316 | 0.219 w | 0.134 w |
| full | 0.6 | 0.577 | 0.409 | 0.289 w | 0.163 w |

All 24 mesh.  Predicted non-orthogonality: 55–64° at 45° and above,
67–76° at 30° (warning tier 70°).  The round r/a 0.6 shoe at 30° is the
known round-tap overestimate (task 0069); `mesh()`'s meshed check warns.

**Surprises.**
- The task expected node projection for the round branch; exact
  surfaces work (above).
- `DuctTap.layout` reuses `k` as a loop index, so the first draft's
  stretch became 3 at 90°.  The bit-identity check caught it.

**Proposed follow-ups.**
- Question 3's normal first layer, if design wants 30° shoes better.
