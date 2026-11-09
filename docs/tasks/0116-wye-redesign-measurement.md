# 0116 — The wye redesign, measured: can the hub take asymmetric and unequal daughters, and can the published topology be built?

- **Status:** done (route chosen: decision 0043, amendment 2026-11-09)
- **Decision:** [0043 — The wye-layout redesign](../decisions/0043-wye-layout-redesign.md) (measure first); [0042 — The road to 1.0](../decisions/0042-road-to-1-0.md), criterion 2
- **Depends on:** 0112 (done).  A measurement: `Wye`'s public behaviour
  doesn't change in this task.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Equal tees and laterals are a 1.0 criterion, through the wye
family.  Decision 0043 compares three layouts:
- **A**, today's hub, generalised to a radius and an angle per daughter;
- **B**, the published separation-plane topology, with creases on block
  edges, blocked so far by gmsh's 5/6-face limit on transfinite volumes
  (task 0030, Q2);
- **C**, a separate equal-tee layout.

It chooses by measurement, on gates fixed before the runs (below).

**Where.**  Prototype code under `validation/tools/` or a scratch module
`hexmesh/assembly/_wye_probe.py` (not exported, not in `__all__`);
experiments' scripts under your scratchpad, or committed under
`docs/integrations/` evidence if they document gmsh behaviour; results
in *Outcome* and a committed JSON (`validation/tools/wye_redesign.json`).

**Do.**
1. **A: the hub, generalised.**  A prototype layout with per-daughter
   angle θ_i (measured from the inlet axis, in the inlet's plane) and
   radius r_i ≤ R, from today's `Wye` code.  Build:
   - **case 1, the equal tee:** θ = (0°, 90°), r = (R, R);
   - **case 2, the equal lateral:** θ = (0°, 45°), r = (R, R);
   - **case 3, unequal symmetric:** θ = (±30°), r = (R/√2, R/√2);
   - **control:** today's 60° symmetric wye, r = R, must match today's
     predicted and meshed quality exactly (same code path).

   For each: predicted and meshed min corner SJ, min SICN, NES, where the
   worst cells are, the crease chord errors (mitre and crotch, as task
   0056 measured them), the projector's largest move, and whether the
   ports are class-0 against a plain `Straight` (`check_port_pairs`).
   Also each case's worst non-orthogonality, predicted (task 0104) and
   meshed, and where: reported, not a gate (design, 2026-11-09).
   At `nang` 8, single layer and with one shell (thickness 0.1 R).  If a
   case can't be built at all, say what degenerates and where.
2. **B: three feasibility experiments** (minimal gmsh scripts, no hexmesh
   layout):
   - **B2, compound surfaces:** a transfinite hex volume whose one side
     is two surfaces meshed as a compound (`Mesh.Compound…`, gmsh
     4.12 and 4.15).  Does `generate(3)` accept it, and is the volume
     mesh structured?  Record in `docs/integrations/gmsh.md` either way.
   - **B1, sub-partitioned ports:** can a port face cut along its
     0°/90°/180°/270° grid lines (task 0088's sub-partition) share its
     mesh with a neighbour `Straight` whose face isn't cut?  If not,
     say what a junction-port convention would need: the neighbour cut
     too, a switch, or a coherence step.
   - **B3, written nodes:** scope only.  What would placing a junction's
     nodes directly, outside transfinite meshing, mean for P2, the
     physical groups and the `.msh` writer?  A page, no code.
3. **Report against the gates,** one table per case and experiment.

**Gates (decision 0043, fixed before the runs).**  At `nang` 8, single
layer and with one shell, predicted and meshed:
- no inverted cells;
- min corner SJ ≥ 0.3 (`PREDICTED_SJ_WARN`) for no warning, ≥ 0.1 to
  build at all;
- crease chord error ≤ 1 % R, or exact;
- ports class-0 against a plain `Straight`.

Don't change a gate after seeing a result.  A case that misses is
reported as a miss, with how far.

**Accept.**
- A's three cases and the control are measured, each against every gate.
- B1 and B2 have a yes or no with a reproducer; B3 is scoped.
- *Outcome* names which of decision 0043's routes each result supports.
  The choice itself is design's, by amendment.
- No change to `Wye`'s public behaviour: the full suite and the gallery's
  meshes unchanged (byte-identical).
- Meshes and scratch output deleted; numbers kept in the JSON.

**Out of scope.**  Implementing the chosen layout; per-arc counts
(decision 0041 C); crosses.

## Agent notes

- **Setup.**  R 0.1, run 0.4, daughters 0.7 (as 0056), `nang` 8, `nrad`
  3, plain `Straight`s at every port.  The shell is `steel`, 0.1 R,
  `nrad` 2.  Counts are resolved (`n_split` capped at 6).
- **Route A prototype:** `hexmesh/assembly/_wye_probe.py`, `WyeProbe`,
  private and not exported.
  - It is a generalised copy of `Wye._layout`: θ per daughter, a
    daughters' radius ratio, and the crotch built about the daughters'
    bisector.
  - **Its control is bit-identical to `Wye(60)`:** vertices, edges,
    blocks and division classes, single layer and shelled.  So are the
    measured numbers.
  - Unequal daughters (r_left ≠ r_right) aren't built; no case needs
    them.
- **Harness:** `validation/tools/wye_redesign.py`; results in
  `validation/tools/wye_redesign.json`.
  - **Crease chord error:** as 0056, the largest distance from the tube
    union of the wall quads' centres and edge midpoints, in % of R.  A
    sample is on a crease when its second-nearest tube is within 0.1 R:
    the mitre (inlet and daughter) or the crotch (daughter and
    daughter).
  - The crotch value reproduces 0056's 60° figure at `nang` 8 (0.85 %).
  - The control's mitre is 2.9 %, against decision 0043's 2.3 % from
    0056.  0056 used `n_split` 17; it is now capped at 6.
  - **Folded cases:** `mesh()` stops at the wall-projection fold check.
    They are re-measured with only that check bypassed, in the harness,
    to count and locate the folds (`fold_check_bypassed`).
- **References, not gated:** today's symmetric 45° and 90° wyes, the
  included angles of A2 and A1.  They separate the effect of asymmetry
  from that of the angle.

## Outcome

**Route A: the hub, generalised.**  Columns: inverted cells; min corner
SJ, predicted / meshed; min SICN; max NES; crease chord error, mitre /
crotch / rest, % R; the projector's largest move, × R;
non-orthogonality, predicted / meshed, degrees; where the worst cells
are.

| case | inv. | SJ pred / mesh | SICN | NES | chord % R | move | non-orth | worst |
|---|---|---|---|---|---|---|---|---|
| control 60° | 0 | 0.211 / 0.156 | 0.144 | 0.88 | 2.87 / 0.85 / 1.78 | 0.18 | 77.2 / 77.8 | crotch ring |
| control 60°, shell | 0 | 0.211 / 0.156 | 0.130 | 0.88 | 3.07 / 0.89 / 0.90 | 0.18 | 77.2 / 77.8 | crotch ring |
| A1 equal tee (0°/90°) | – | – | – | – | – | – | – | can't build (below) |
| A1, station 1.1 R | 0 | 0.197 / **0.058** | 0.068 | 0.95 | 3.88 / 1.33 / 3.04 | 0.19 | 79.0 / 79.4 | crotch ring |
| A1, station 1.1 R, shell | **2** | 0.180 / **0.000** | 0.000 | 1.00 | 3.98 / 1.64 / 0.92 | 0.24 | 79.0 / 79.4 | a daughter's turn |
| A2 equal lateral (0°/45°) | **28** | 0.085 / **−0.207** | −0.350 | 0.99 | 6.72 / 1.35 / 4.00 | 0.38 | 89.3 / 88.7 | hub; crotch ring |
| A2, shell | **32** | 0.085 / **−0.207** | −0.350 | 0.99 | 7.23 / 1.29 / 3.57 | 0.38 | 89.6 / 88.7 | hub; crotch ring |
| A3 unequal (±30°, R/√2) | 0 | 0.256 / 0.133 | 0.130 | 0.89 | 4.82 / 0.68 / 1.71 | 0.13 | 79.1 / 79.4 | crotch ring |
| A3, shell | 0 | 0.256 / 0.114 | 0.115 | 0.89 | 4.90 / 0.61 / 1.63 | 0.13 | 79.1 / 79.4 | crotch ring |
| ref: today's 45° | 0 | 0.133 / 0.133 | 0.121 | 0.89 | 5.24 / 1.35 / 0.86 | 0.38 | 79.0 / 79.5 | crotch ring |
| ref: today's 90° | 0 | 0.361 / 0.164 | 0.170 | 0.86 | 3.88 / 0.75 / 2.63 | 0.13 | 76.4 / 76.9 | crotch ring |

**Against the gates** (single layer and shelled; "builds" is SJ ≥ 0.1):

| case | no inverted | SJ ≥ 0.3 | builds | chord ≤ 1 % R | ports class-0 |
|---|---|---|---|---|---|
| control 60° | pass | miss (0.156, 0.144 short) | pass | miss (mitre 2.9 / 3.1 %) | pass |
| A1 equal tee | can't build at the default station | – | – | – | – |
| A1, station 1.1 R | pass; **miss** with the shell (2) | miss (0.058) | **miss** (0.042 short; 0 with the shell) | miss (mitre 3.9–4.0 %, crotch 1.3–1.6 %) | pass |
| A2 equal lateral | **miss** (28 / 32) | miss | **miss** (−0.207) | miss (mitre 6.7–7.2 %, crotch 1.3 %) | pass |
| A3 unequal | pass | miss (0.133 / 0.114) | pass | miss (mitre 4.8–4.9 %); crotch passes (0.6–0.7 %) | pass |

"Ports class-0" holds by construction: the probe declares its ports with
`face_vertices`, the same as `Wye`, and each port's spec is a plain
`Straight`'s (`signature` class 0).  Every case that meshed was
conformal at its ports.

**What degenerates, and where:**
- **A1, the equal tee.**  The inlet station sits R·(tan θ_max + 0.1)
  behind O, and tan 90° is infinite (1.6e15 R).
  - The geometric clearance for equal radii is R·tan(θ/2), finite at
    90°.  With the station at 1.1 R the tee builds, but its crotch ring
    falls to SJ 0.058.
  - With a shell, two cells of a daughter's turn fold at the projection.
  - The straight-through daughter makes the hub's turn on that side
    flat, as decision 0043 feared.
- **A2, the equal lateral.**  It folds in the hub and in the crotch
  ring, predicted SJ 0.085.
  - Today's symmetric 45° wye builds (SJ 0.133) with the same crotch
    (same crotch chord, same projector move).  So the tilt is the cause,
    not the included angle.
  - The fold isn't the inlet station: at the symmetric wye's station
    distance (0.51 R) it still folds, 24 / 26 cells.
  - The hub's back face stays square to the inlet while its front faces
    follow the tilted daughters, so the hub shears.
- **A3, unequal radii.**  It builds, below the warning tier as today's
  wyes are.  Its mitre crease is the worst of the built cases (4.8 %):
  the union of an R inlet with r = R/√2 daughters has a step where each
  daughter leaves the inlet's sphere about O.  A smooth bifurcation
  would need a tapered wall (the projector takes only constant-radius
  tubes).
- **Every case** has its worst non-orthogonality (77–89°) and its worst
  SJ in the ring at the crotch.  That is the hub layout, shared by all
  A cases.

**Route B: feasibility.**

| experiment | answer | evidence |
|---|---|---|
| B2, compound surfaces | **No**, on gmsh 4.12.1 and 4.15.2.  A 7-face transfinite volume fails at `generate(3)` with or without `setCompound` on the split surfaces and curves.  The 6-face control meshes 64 structured hexes. | `docs/integrations/evidence/gmsh_compound_transfinite.py`; gmsh.md |
| B1, sub-partitioned ports | **No shared entities.**  `fragment` cuts the neighbour's face, and gmsh meshes it with tets and pyramids.  Distinct entities are non-conformal.  Distinct entities plus `removeDuplicateNodes` are conformal, but DESIGN §2 P2 forbids that step. | `docs/integrations/evidence/gmsh_subpartitioned_port.py`; gmsh.md |

**B1, what a junction-port convention would need.**  An uncut
neighbour's face can't be shared by construction.  Neither can a switch
block from a cut face to an uncut one: that block would have 7 faces,
the same limit.  What remains:
- (a) every neighbour of a junction port carries the same cut, all the
  way to the next interface that has it: `n_outer = 8` straights
  (decision 0005, task 0088) and an `n_outer` 8 → 4 change somewhere
  else;
- (b) a coherence step at junction ports only, which P2 forbids;
- (c) junction ports whose face isn't cut, the split stopping inside
  the junction: that is today's hub, route A.

**B3, written nodes (scope only, no code).**  The junction's nodes are
placed by hexmesh, as Decroocq does, and written as a discrete mesh, not
meshed by gmsh's transfinite algorithm.
- **P2 (conformal by construction):** kept, if the junction's
  port-face nodes are taken from the port's own transfinite mesh, read
  back from gmsh, and never recomputed.  The junction becomes a discrete
  entity bounded by the ports' surfaces.  That needs gmsh's discrete
  entities (`addDiscreteEntity`, `addNodes`, `addElements`), and the
  port surfaces meshed before the junction.  The pipeline order (DESIGN
  §5 steps 4–7) changes for junctions: their ports' surfaces mesh
  first.
- **P3/P4:** prediction is exact rather than modelled.  The node
  placement is hexmesh's own code, so predicted equals meshed by
  construction.  `BlockLayout.cells()` (task 0104) is a start.
- **Physical groups:** a discrete volume can carry a physical group as
  any volume does.  The wall's 2-D elements must be added as discrete
  surfaces too, so the wall and interface groups (A7) stay per surface.
- **The `.msh` writer and gmshToFoam:** discrete entities are written
  like any other.  The orientation test (`would_invert`, task 0108)
  applies unchanged.  Second order (task 0076) would need hexmesh's own
  mid-edge nodes, because gmsh's `setOrder(2)` on a discrete entity
  can't place them on the wall.
- **Cost:** a second realisation path for one family of fittings, in
  decision 0007's terms (alternative backends, proposed).
  `refined(k)`, `cell_count` and the conformance kit must cover it.
  It is the only route here that gives the published topology without a
  P2 or §7 change.

**Which routes the results support** (the choice is design's):
- **A, as it stands, doesn't reach the 1.0 cases.**  The equal tee
  builds only with a new station rule, and then misses the build gate
  (SJ 0.058).  The equal lateral folds.  Both fail in the hub, the part
  route A keeps.  Unequal symmetric daughters do build, at today's
  quality.  A needs at least a reworked hub for tilted daughters, which
  is more than "generalise".
- **B via B1 or B2 is closed** on gmsh 4.12 and 4.15 without a P2 or
  §7 change.  Of route B, B3 remains, at the cost of a second
  realisation path.
- **C** (a dedicated equal-tee layout) isn't measured here.  It would
  avoid A1's flat turn, but nothing here bears on A2's tilted hub.
- **Every route** also has the crotch ring's non-orthogonality to
  answer: 77–80° in every hub case that builds (task 0104's warning
  tier), 89° in the folded lateral.

**Files:**
- `hexmesh/assembly/_wye_probe.py` (private);
- `validation/tools/wye_redesign.py` and `.json`;
- `docs/integrations/evidence/gmsh_compound_transfinite.py` and
  `gmsh_subpartitioned_port.py`;
- `docs/integrations/gmsh.md`: B2 added to the 5/6-face entry; B1 is a
  new entry.

`Wye` is unchanged: `git diff` shows no edit under `hexmesh/` except the
new private module.

**Proposed follow-ups:**
- if A is kept, a hub whose back face turns with the daughters'
  bisector, then re-measure A1 and A2;
- if B3 is taken, a minimal discrete-entity experiment: one written
  hex block between two transfinite straights, through gmshToFoam;
- a tapered wall projector for unequal radii (A3's mitre).

**Full suite:** 3775 passed, 15 skipped, no failures.  The one extra
test over 0104's run is a per-module architecture check picking up
`_wye_probe.py`.  No mesh was kept; the 4.15.2 scratch venv is deleted.

**Design (2026-11-09, the user: "yes"):** decision 0043's amendment
rejects A, B1 and B2 and takes B3 provisionally, subject to task 0117's
experiment; C if it fails.  The follow-ups: the bisector hub isn't
pursued; the discrete-entity experiment is task 0117; the tapered
projector waits on the route.
