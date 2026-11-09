# 0118 — The oriented junction cube, measured: can a 7-hex cube with ports take equal tees and equal laterals?

- **Status:** done
- **Decision:** [0043 — The wye-layout redesign](../decisions/0043-wye-layout-redesign.md), amendment "the oriented junction cube before B3" (2026-11-09)
- **Depends on:** 0116 (done): its harness and probe.  A measurement:
  `Wye`'s public behaviour doesn't change.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0116 found today's hub can't take the equal tee (a flat
turn on the straight-through side) or the equal lateral (the hub's back
face stays square to the inlet and shears).  Bošnjak et al. 2024
(RESEARCH §4.3; `docs/papers/bosnjak_and_pepe_etal_2024.pdf`, Sect. 3.1,
Fig. 6–9) mesh vessel junctions with an oriented cube of seven hexes and
a port on each side a branch enters.  Every block is a 6-faced hex, so it
stays on today's gmsh transfinite path.  This task measures it before
the larger route B3 (task 0117).

**Where.**  Extend `hexmesh/assembly/_wye_probe.py` (private) or a
sibling private module; the harness `validation/tools/wye_redesign.py`;
results added to `validation/tools/wye_redesign.json` under their own
key, and in *Outcome*.

**Do.**
1. **The template** (the paper's scheme, adapted):
   - a centre hex about the junction point O, and one block on each of
     its six sides out to the wall;
   - on each side a branch enters, a **port**: that side's block
     subdivided so its outer face is the 5-patch O-H face of the
     branch's section (centre square on the core, four ring patches),
     joined to a plain `Straight` (class-0);
   - the sides with no branch: their block's outer face lies on the wall
     (projected, as today's junctions are);
   - shells (one, 0.1 R) as offset levels, as today's wye does.
2. **Orientation:** choose the cube's rotation about O so each branch
   meets its side as squarely as possible (the paper's heuristic: the
   largest smallest angle between a branch and its side's plane).
   Report the rotation found per case.  For the equal tee it should be
   the identity (inlet, run and branch on three sides).
3. **Cases** (0116's, so they compare): A1 equal tee (0°/90°), A2 equal
   lateral (0°/45°), A3 unequal (±30°, R/√2), and the 60° symmetric
   control.  `nang` 8, single layer and with the shell.
   - If a case needs the paper's small-angle step (branch blocks
     subdivided and joined nearer the junction, their Fig. 9), say so
     and measure it with and without.
4. **Measure, as 0116:** inverted cells; min corner SJ, predicted and
   meshed; min SICN; max NES; crease chord error, mitre / crotch / rest
   (% R); the projector's largest move; non-orthogonality, predicted and
   meshed, and where; ports class-0 (`check_port_pairs`).
   - For the equal tee also: whether the run/branch crease lies on block
     faces (design expects it in the cube's diagonal planes x = ±z) and
     how it crosses the ±y sides.
5. **Report against the gates** (decision 0043, fixed; unchanged):
   no inverted cells; min corner SJ ≥ 0.3 for no warning, ≥ 0.1 to build;
   crease chord ≤ 1 % R, or exact; ports class-0.  A miss is reported as
   a miss, with how far.  Non-orthogonality is reported, not gated.

**Accept.**
- The four cases measured, single layer and shelled, each against every
  gate, beside 0116's hub numbers.
- *Outcome* says which cases the cube passes and where the misses are.
  The choice is design's, by amendment.
- No change to `Wye`'s public behaviour: the full suite and the
  gallery's meshes unchanged (byte-identical).
- Meshes and scratch output deleted; numbers kept in the JSON.

**Out of scope.**  Implementing the chosen layout; per-arc counts;
crosses (the cube has six sides, so note whether a cross would fit, no
more); smoothing (decision 0029: no smoothing).

## Agent notes

- **Order.**  The user chose 0118 next (2026-11-09).
- **Step 1 adapted: the port joins its station in one step.**  In the
  paper a port is the side's block cut into a centre column and four
  ring blocks, with a mid square so each stays a hex (Fig. 8b, c), and
  blocks then join the port to the next cross-section.  Here that
  cross-section is the pipe's station, an O-H face, so a ported side's
  block sweeps straight from the centre hex's face and the side's four
  cube edges to the station.  That gives five hexes, with no mid square
  and no separate port face.  Cube corners lie on the wall along the
  cube's diagonals from O; the centre hex is the same corners scaled by
  `hub`.  Counts: cube and centre-hex edges `nang`, diagonals `nrad`, a
  port's axial edges `n_split`.  The code is
  `hexmesh/assembly/_cube_probe.py` (private; `CubeProbe` subclasses
  0116's `WyeProbe`).
- **Two shape parameters, tuned per case** by predicted SJ before
  meshing, as the duct tap tunes: `hub` (0.3–0.6) and `station`, the
  station's distance beyond the farthest obstacle (0.25–3 × the pipe's
  outer radius; a station must fit inside 0116's 4 R run).  `hub` barely
  matters; `station` dominates wherever a pipe meets its side off
  square.
- **Orientation** (step 2): the paper's heuristic maximises the smallest
  angle between a pipe and its side's plane.  It is searched over
  rotations (a grid, then Nelder–Mead), with the most square of tied
  orientations preferred.  Turns about `up` forced by hand (0°–45°) did
  no better on any case.
- **The small-angle step (Fig. 9) was not measured.**  It joins two
  branches nearer the junction when they are close.  Here the worst cells
  are in the inlet port's ring and its shell, and the fold sits in the
  centre hex, not between the daughters (below).  So it wouldn't address
  the measured failure.  Question 3 asks whether design still wants it.
- **Crosses** would fit: four in-plane pipes take ±e1 and ±e2 square, as
  the equal tee's three do.  Not built.
- `measure()` in the harness takes the block names for "where"; the
  folded path keeps the cube report.

## Questions for design

1. **The equal tee's crease.**  The cube passes every gate on A1 except
   the crease chord: 3.7 % R, 4.1 % with the shell.  It sits where the
   crease crosses the middle of the ±u sides (design's prediction),
   next to the cube corners on the branch side, and falls only at first
   order with `nang` (2.0 % at 16, 1.4 % at 24; about 33 for 1 %).
   Making it exact needs those sides split along the crease's V, which
   isn't a hex split of one block.  Take the cube for the equal tee with
   this miss, extend it, or go on to 0117?
2. **The equal lateral builds and warns.**  Min SJ is 0.134 meshed (0.223
   predicted), 0.136 with the shell, with no inverted cells.  The hub
   folded 28 cells here.  The worst is the inlet port's ring: the paper's
   orientation leaves every pipe 22.5° off square.  It needs stations 2 R
   past the cube (daughters at 4.45 R, inlet 3.15 R).
3. **The 60° cases don't build.**  The control and A3 fold 54–104 cells
   under wall projection (meshed SJ −0.995; projector moves 0.85–1.07 R).
   The best predicted SJ is 0.067 (0.115 with a 6 R run, still folding).
   The orientation found puts the left daughter square, and the inlet
   and right daughter 30° off.  The fold is attributed to the centre hex,
   the predicted worst to the inlet port's ring.  0116's hub builds both
   (0.156 and 0.133).  Should 0118 also measure the paper's small-angle
   step, or does decision 0043's choice follow from these numbers?

## Design answers (2026-11-09, the user: "yes")

1. No route has met the 1 % crease gate (hub or cube), so by decision
   0043's rule 0117 (B3) runs next.  Choosing the cube now would change
   the rule after the results.  If B3 fails, the rule falls to C, and the
   cube is that C: the cube for tees and laterals, the hub for symmetric
   wyes, with the crease error stated (the proposed follow-up below).  If
   B3 is feasible, design weighs the two.
2. Noted for the choice.
3. No, don't measure the small-angle step: the folds are in the centre
   hex and the inlet ring, not between the daughters, and the hub
   already builds symmetric wyes.

## Outcome

**Files.**
- `hexmesh/assembly/_cube_probe.py` (new, private): `CubeProbe`,
  `orient` (the paper's heuristic), and the layout.
- `validation/tools/wye_redesign.py`: the `K*` cases, `CUBE_BLOCKS`,
  `cube()` with the tuning grid, `cube_report`; `measure` takes block
  names.
- `validation/tools/wye_redesign.json`: eight `K*` rows (four cases,
  single and shelled), each with its `cube` report and gates.

**Results** at `nang` 8, beside 0116's hub (single layer; shelled in
brackets where it differs).  SJ is meshed (predicted).

| case | layout | min SJ | inverted | crease chord % R (mitre / crotch) | non-orth. ° | gates |
|---|---|---|---|---|---|---|
| A1 equal tee | cube | 0.577 (0.577) | 0 | 3.7 / 3.7 (4.1) | 45 | all but chord |
| | hub | 0.058 (0.197) | 0 (2) | 3.9 / 1.3 | 79 | fails SJ |
| A2 equal lateral 45° | cube | 0.134 (0.223) [0.136] | 0 | 2.2 / 2.9 | 71 | builds; warns; chord |
| | hub | folds | 28 (32) | 6.7 / 1.4 | 89 | fails |
| A3 unequal 60° | cube | folds, 0.067 predicted | 54 (78) | 5.5 / 5.3 | 89 | fails |
| | hub | 0.133 (0.256) [0.114] | 0 | 4.8 / 0.7 | 79 | builds; warns; chord |
| control 60° | cube | folds, 0.067 predicted | 56 (104) | 5.1 / 7.7 | 89 | fails |
| | hub | 0.156 (0.211) | 0 | 2.9 / 0.9 | 78 | builds; warns; chord |

Ports are class-0 in every case.  The cube's orientation, per case:
- **A1:** the identity; inlet, run and branch each square to a side.
- **A2:** turned 22.5° about `up`; each pipe at 67.5° to its side's
  plane.
- **60° and A3:** turned 30° about `up` (reported as 60°, composed with
  a cube symmetry).  The left daughter is square, the inlet and right
  daughter at 60°.

**Which cases the cube passes.**
- **A1:** every gate except the crease chord (3.7 % R).  It is the only
  layout that builds the equal tee without a warning.
- **A2:** builds with a warning, where the hub folds.
- **The 60° cases:** the cube fails where the hub builds.

**Surprises.**
- `Wye.layout`'s cache is keyed on the fitting's fields, so a monkeypatched
  orientation silently reused the first layout.  Experiments call
  `_layout` directly.
- Stations far from the cube matter more than the centre hex's size.

**Suite.**  The architecture and manifest tests pass (78).  `Wye`,
`blocks` and every public module are unchanged (the diff adds one
private module), so the gallery's meshes are unchanged by
construction.  The full suite: 3997 passed, 15 skipped (32 min).

**Proposed follow-up**, if design takes the cube for tees: a
per-junction choice, the cube for tees and laterals and the hub for
symmetric wyes, with the crease split of question 1.
