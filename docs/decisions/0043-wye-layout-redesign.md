# 0043 — The wye-layout redesign: equal tees, asymmetric and unequal daughters, creases

- **Status:** accepted, measure first (2026-11-08, by the user: "yes";
  decision 0042's critical path).  The layout (A, B or C) is chosen by an
  amendment after task 0116.
- **Date:** 2026-11-08
- **Tasks:** 0116 (the measurement); 0117 (the B3 experiment, amendment 2026-11-09); 0118 (the cube, measured); 0122 (the cube behind `Tee`, amendment 2026-11-10); 0124 (B3 opt-in for `Wye`, held)

## Context

Decision 0042 makes **equal tees and equal laterals** a 1.0 exit
criterion, through the wye family (decision 0031's amendment).  The
redesign that delivers them has been named three times but never
designed:
- **decision 0029, item 5** (2026-10-29): creases on block edges, after
  task 0056 measured two creases above 1 % R at `nang` 8: the mitre
  crease where the inlet cylinder meets each daughter (2.3 % at 60°,
  first order in `nang`), and the crotch of wyes under about 50°
  (1.7–3.1 %);
- **decision 0031's amendment** (2026-10-29): asymmetric daughters, so
  that an equal tee is daughters at 0° and 90°, and an equal lateral is
  daughters at 0° and α;
- **the user** (2026-10-30): unequal daughter radii (r_d < R), for real
  bifurcations, the Zhao & Lieber benchmark (r_d = R/√2, RESEARCH §7.9)
  and Murray's law (R/2^{1/3}).

**Today's wye** (`hexmesh/assembly/wye.py`, decisions 0017 and 0029,
tasks 0030, 0051, 0053, 0056):
- symmetric: both daughters at ±angle/2, both with the inlet's spec,
  coplanar, angle 30°–120°;
- a **hub** topology: hub H continues the inlet core, each daughter's
  core leaves a side face of H, and a ring layer offsets the wall.  The
  radial edges at H's back corners carry five blocks: the extraordinary
  vertices;
- the wall is the canal surface about the skeleton, reached by node
  projection (`TubeUnion`, smoothed normal), exact to 1e-15 R at the
  nodes.  The creases lie *inside* faces, so a chord error remains;
- shells exist (task 0053): at least 40°, total thickness at most
  R·min(0.65 tan(θ/2), 0.55).

**Why the published topology wasn't used** (task 0030, Q2, verified in
gmsh): Decroocq's separation half-planes and Marcinnó's butterfly fold
each branch's core along its midline.  A block ending on two faces
shared with different neighbours has 7 faces, and **gmsh transfinite
volumes take only 5 or 6.**  So the split would have to run back to the
port, where the core is one surface.  That's why the hub was built.

**What the redesign must deliver:**
1. equal tees (0°/90°) and equal laterals (0°/α);
2. per-daughter radius (r_d ≤ R) and per-daughter angle;
3. crease chord errors under 1 % R at `nang` 8 (decision 0029's
   threshold), or exact;
4. shells (insulated junctions), as today's wye has;
5. ports that are standard 4-corner O-H interfaces, class-0 against a
   plain `Straight` (DESIGN §7: junction internals are private).

## Options

### A. Generalise the hub layout
Keep today's topology and give it per-daughter angles and radii.  The
creases stay inside faces, handled by the projector.
- **For:** proven code path (projection, shells, axial counts, quality
  prediction, tests); ports unchanged.
- **Against:**
  - the creases' chord errors stay first order at the mitre;
  - an equal tee has a straight-through daughter, which may make the
    hub's turn on that side degenerate (not measured);
  - unequal radii move the hub's side faces off the daughters' cores.

### B. The published topology: creases on block edges
Separation half-planes (Decroocq) with Hermite and ellipse geometry
(Marcinnó), every crease an edge between blocks, so exact.
- **For:**
  - the creases become exact;
  - unequal radii are native (the split point X sits at a barycentre that
    favours the smaller vessel);
  - it is the published route to min SJ about 0.49 with no smoothing;
  - it generalises to n-furcations.
- **Against: the 5/6-face limit.**  Each branch's core must be split
  along its midline all the way to the port.  Three ways to meet it,
  none verified:
  - **B1, sub-partitioned ports:** the port face is cut along its
    0°/90°/180°/270° grid lines.  That's decision 0005's `n_outer = 8`
    sub-partition (task 0088): the same nodes, more patches.  But an
    interface is one set of shared entities, so a neighbour `Straight`
    would need the same partition.  Either every junction port becomes
    `n_outer = 8`, with a switch or a convention for its neighbours, or
    the sub-partition has to be invisible at the interface.  This touches
    DESIGN §7's "standard ports";
  - **B2, compound surfaces:** gmsh can mesh several surfaces as one
    (`Mesh.Compound…`), which might let a 7-face block count as 6.  Its
    behaviour with transfinite volumes is unknown here;
  - **B3, write the nodes:** place the junction's nodes directly, as
    Decroocq does, outside gmsh's transfinite meshing.  It is a new
    realisation path (decision 0007, alternative backends, is proposed).
- Every wye measurement starts over.

### C. A separate equal-tee layout
Keep today's wye for symmetric splits and add a dedicated layout for
r = R tees.
- **For:** smallest change for the 1.0 criterion.
- **Against:** a third junction layout to maintain; it fixes neither the
  creases nor unequal radii, which then need a later redesign anyway.

## Decision (accepted: measure first)

**Measure first, then choose: one measurement task with gates fixed
now**, as decision 0017 did for the first wye.  The task answers, without
changing `Wye`:
1. **A's reach:** prototype the hub with per-daughter angles and radii;
   build the equal tee (0°/90°), an equal lateral (0°/45°) and an
   unequal symmetric wye (60°, r_d = R/√2).
2. **B's feasibility:** for each of B1–B3, a minimal gmsh experiment.
   B2: a compound face on a transfinite volume.  B1: whether a
   sub-partitioned port can share entities with an unpartitioned
   `Straight` (and if not, what a junction-port convention would need).
   B3: only scoped, not built.

**Gates, fixed before the runs** (on predicted and meshed quality, at
`nang` 8, single layer and with one shell):
- no inverted cells;
- min corner scaled Jacobian ≥ `PREDICTED_SJ_WARN` (0.3) without a
  warning, ≥ the 0.1 floor to build at all;
- the crease chord error ≤ 1 % R at `nang` 8, or exact;
- ports class-0 against a plain `Straight`.

**The choice after the measurement:**
- If A passes the gates for all three cases, **A** (least change, ports
  unchanged), with the creases' chord error stated per case.
- If A fails the equal tee but a B route is feasible, **B** with that
  route, and its port consequence decided by its own amendment.
- **C** only if neither A nor B can deliver equal tees within 0.6's
  scope.

**The API** is settled with the choice, before 0.8's freeze.  Its
direction now: `Wye` gains per-daughter angles and radii, and
`Tee(branch_radius = main radius)` keeps routing to the equal-tee layout
internally (users never choose a layout, decision 0031).

## Consequences

- **A measurement task** (gates above), first in 0.6's junction work.
- **Task 0088** (`n_outer = 8` sub-partition) may move into 0.6 if B1 is
  the route.
- **DESIGN §7:** gains §7.2 "Wye" (promised by decision 0017) from the
  chosen layout; §7's port rule is amended only if B1 needs it.
- **Validation:** the MMS wye series (task 0074) reruns on the new
  layout, and the Štigler T-junction benchmark (RESEARCH §7.2) becomes
  possible.
- **Future expansions:**
  - **0018 (vascular):** helped by unequal radii and asymmetric
    daughters.  B also generalises to n-furcations.
  - **0035 (pipe-in-pipe, multi-core):** none (no junctions in its
    scope).
  - **0021 (flow restrictions), 0030 (suite):** none.
  - **0040 (agents):** the API change goes through the schema and the
    manifest's support matrix.

## Verified vs. assumed

- **Verified:** the 5/6-face limit (task 0030, Q2, a gmsh reproducer);
  today's wye's creases and limits (tasks 0051, 0053, 0056; RESEARCH
  §4.3b); Marcinnó's reported quality (RESEARCH §4.2, from the paper).
- **Assumed, to be measured:**
  - that the hub degenerates for a straight-through daughter;
  - that B2's compound surfaces work with transfinite volumes;
  - that a sub-partitioned port can't share entities with an
    unpartitioned neighbour (B1);
  - that the gates are reachable at all for an equal tee (Marcinnó's
    0.49 is for a symmetric bifurcation).

## Amendment: the route after task 0116 (2026-11-09; the user: "yes")

**Measured** (task 0116; `validation/tools/wye_redesign.json`), at
`nang` 8, single layer and with one shell (0.1 R):

| case | inverted | min SJ, meshed | crease chord, mitre / crotch (% R) | non-orth., meshed |
|---|---|---|---|---|
| control (today's 60° wye) | 0 | 0.156 | 2.9 / 0.85 | 77.8° |
| A1 equal tee (station moved to 1.1 R) | 0; 2 with the shell | 0.058; 0 with the shell | 3.9 / 1.3 | 79.4° |
| A2 equal lateral (0°/45°) | 28; 32 with the shell | −0.207 | 6.7 / 1.35 | 88.7° |
| A3 unequal (±30°, R/√2) | 0 | 0.133; 0.114 with the shell | 4.8 / 0.68 | 79.4° |

- **A misses the gates in every case, the control included** (SJ 0.3,
  chord 1 % R).  The equal tee doesn't build at today's station rule,
  and misses the 0.1 floor at a moved one.  The equal lateral folds:
  the hub's back face stays square to the inlet while its front faces
  follow the tilted daughters.  The failures are in the hub and the
  crotch ring, the part A keeps.
- **B2 is closed:** a 7-face transfinite volume fails at `generate(3)`
  with or without `setCompound`, on gmsh 4.12.1 and 4.15.2
  (`docs/integrations/gmsh.md`, reproducer in `evidence/`).
- **B1 is closed** without a P2 or §7 change: an uncut neighbour's face
  can't share entities with a cut port, and a switch block to it would
  have 7 faces.  Only a coherence step (`removeDuplicateNodes`) makes
  them conformal, which P2 forbids.
- **B3** (hexmesh writes the junction's nodes) is scoped, not built.
  P2 holds if the junction's port-face nodes are read from the ports'
  own transfinite meshes and never recomputed.
- **C** wasn't measured.  It would avoid A1's flat turn but not A2's
  sheared hub.

**Decided:**
1. **A is rejected,** by this decision's rule: it fails the equal tee,
   and it misses the gates on the control too.  A reworked hub (back
   face along the daughters' bisector, 0116's follow-up) isn't pursued:
   it would keep the crotch ring and the mitre chord.
2. **B1 and B2 are rejected** (above).
3. **B3 is the provisional route,** subject to one feasibility
   experiment with gates fixed now (task 0117):
   - **conformal by construction:** the written block's port-face nodes
     are the neighbours' own node tags; no `removeDuplicateNodes`, no
     node created twice;
   - **OpenFOAM:** `gmshToFoam` then `checkMesh` (v2406) pass, with no
     failed check, one connected region, and the physical groups as
     patches;
   - **no inverted cells,** by `would_invert` and the scaled Jacobian;
   - **reproducible:** the `.msh` byte-identical on a rerun;
   - **on gmsh 4.12 and 4.15.**
4. **If the experiment passes,** B3 is taken.  Its realisation-path
   consequences are decided by amendments before any implementation
   task: decision 0007 (option C, native realisation, scoped to
   junctions), DESIGN §5 (junction ports meshed first) and §6 (the fill
   primitive), and second order (decision 0034, task 0076).
5. **If it fails,** C, as this decision's rule says: an equal-tee
   layout for 0.6, with equal laterals and unequal radii reconsidered
   after it.

**Consequences:**
- **Milestone 0.6** grows: B3 is the largest item on decision 0042's
  path.  No estimate is made before the experiment.
- **Today's `Wye`** is unchanged until the route is built; its
  warning-only tiers (task 0104) stand.
- **`_wye_probe.py`** stays private until the route is chosen, then is
  removed or folded in.
- **Task 0104's follow-up** (port-face edges declared as lines) is held:
  under B3 hexmesh places those nodes itself.
- **Future expansions:** 0018 (vascular) is helped most by B3 (the
  published topology generalises to n-furcations); 0035 and 0021 none;
  0040 (agents): none until the API changes.

**Verified vs. assumed:** verified, A's four cases and B1/B2 (task
0116).  Assumed: that gmsh's discrete entities can be bounded by
meshed transfinite surfaces and written with them (task 0117 checks);
that B3's node placement can reach Marcinnó's quality (not measured
here).

## Amendment: the oriented junction cube before B3 (2026-11-09; the user: "yes wite the tasks")

**New evidence** (design's web research, RESEARCH §4.3):
- **Bošnjak et al. 2024** mesh vessel junctions with a "structured
  cube" of seven hexahedra, oriented so each branch meets a side as
  squarely as possible, with a port (the side's block subdivided to the
  branch's 5-block section) on each side a branch enters.  Every block
  is a 6-faced hex: the template fits gmsh's transfinite volumes.
- It is the hub with a free orientation, which is the follow-up task
  0116 proposed and the previous amendment set aside.  The equal tee is
  its natural case (no turn block, A1's failure).
- **gmsh documents that OpenCASCADE entities can't have discrete
  entities on their boundary** (tutorial x2).  hexmesh builds with OCC,
  so B3 carries a risk that 0116's scope didn't see.

**Decided:**
1. **The oriented cube is measured first** (task 0118), as a route-A
   variant on today's realisation path, against **this decision's gates,
   unchanged**, on A1, A2, A3 and the 60° control.
2. **The choice after 0118:** if the cube passes the gates on the equal
   tee and the equal lateral, it is taken, and B3 isn't pursued.  If it
   misses, task 0117 (B3) runs, then C if B3 fails, as before.
3. **Task 0117** stays ready but runs after 0118, and gains a first
   step: whether a discrete volume can reference OCC surfaces' node
   tags at all.

**Consequences:** no change to the gates, the API direction or the
future-expansion checks above.  0018 (vascular) is helped by either
route; the cube is the published vascular template too.

## Amendment: the route after task 0117 (2026-11-10; the user: "go with option 1, my thouhts are that gmsh should be responsible for meshing", "opt-in, … go ahead and write it")

**Measured** (task 0117): route B3 is feasible.  A discrete volume of
hexmesh-written hexes between OCC transfinite straights passes every
gate fixed in this decision's 2026-11-09 amendment: conformal by
construction (port tags reused, no node duplicated), `checkMesh` v2406
with one region and the groups as patches, no inverted cells, byte-
identical on reruns, on gmsh 4.12.1 and 4.15.2.  Tutorial x2's OCC
limit did not apply.  What 0117 didn't measure: a junction layout's
quality or crease error under B3.

**Decided:**
1. **B3 is not the default route,** on the user's principle (decision
   0046): gmsh creates every element of a default build.  This changes
   this decision's rule after a result, so the reason is recorded: it is
   a principle about which tool meshes, not the result, and it sets
   aside the route that *passed*.
2. **The rule falls to C:** a layout for equal tees and equal laterals,
   on gmsh's transfinite path.  **C is the oriented junction cube**
   (task 0118), behind `Tee(branch_radius = R)` at any supported angle
   (decision 0031: users never choose the layout).  **Symmetric wyes keep
   today's hub** (`Wye`, unchanged), which builds the 60° cases the cube
   folds.
3. **The crease gate is not moved; the cube misses it, stated.**  The
   equal tee's crease chord is 3.7 % R at `nang` 8 (4.1 % shelled),
   first order in `nang` (about `nang` 33 for 1 %).  It is stated in the
   GUIDE and in the fitting's docstring, per angle as measured.  Wall
   projection can't remove it: the error is cells straddling the crease,
   not nodes off the wall.  The route to the crease on tees is decision
   0045 (a rounded crotch: no crease), proposed.
4. **The lateral angles** the cube supports, and their tiers (warn,
   error), are set by measurement in the implementation task (0122),
   from 90° down: 0118 measured 90° (SJ 0.577) and 45° (0.134, warns).
5. **B3 survives as an opt-in for `Wye`** (decision 0046, rule 3):
   `Wye(…, written_nodes=True)`, task 0124, held until after 0122.  It is
   built only if its layout meets this decision's gates (unchanged) on a
   case where the hub misses them; the hint then names it for those
   cases.

**Consequences:**
- **Task 0122:** the cube behind `Tee`.  The error
  `equal_tee_unsupported` goes; the τ < r/R < 1 hint keeps "an equal
  tee".  `_cube_probe.py` is folded into the layout; `_wye_probe.py`
  stays private until 0124 settles.
- **DESIGN §7** gains §7.2 "Equal tee: the oriented cube" from 0122's
  proposed wording.  §7.2 "Wye" (promised by decision 0017) follows when
  the wye changes; it doesn't change now.
- **This decision's API direction** (per-daughter angles and radii on
  `Wye`) is deferred: the hub doesn't take them (task 0116), and the
  opt-in is the place to measure them (0124).  Unequal daughters are
  built as equal daughters followed by `Reducer`s meanwhile.
- **Milestone 0.6** shrinks: no native realisation path before 1.0.
  Decision 0007 is amended to match.
- **Task 0104's held follow-up** (port-face edges as lines) stays held.
- **Future expansions:** 0018 (vascular) gets tees at any ratio and
  equal laterals; odd-angle bifurcations wait for 0124.  0040 (agents):
  the `Tee` schema is unchanged except that r = R now builds.  0021,
  0030, 0035: none.

## Note: task 0122's result (2026-11-10)

- **Equal tees ship** through the cube (90°, centred): min meshed SJ
  0.511 at `nang` 8, 0.305 at 48; `checkMesh` v2406 passes, bare,
  shelled and insulated; crease 3.7 % R at 8, 0.7 % at 48.  DESIGN
  §7.2 written from 0122's wording.
- **Equal laterals are deferred** (`EQUAL_LATERAL_ANGLE_MIN` 90, the
  user's "yes" to design's answer): they build at `nang` 8 but degrade
  with refinement, and fail `checkMesh` skewness from 60° down.  Cause:
  the wall sides' flat faces sit up to 0.18 R inside the wall, and
  projection's fixed move crushes more of the thinner cells as `nang`
  rises.  Candidate fix (not a task): carry the projection's move into
  the blocks' interior nodes, a node-position correction under decision
  0046.
- **Second order** is rejected before meshing for the equal tee, as for
  the wye (72 of 4160 Hex27 inverted).
- **The slide with refinement is unexplained** (task 0126, closed):
  carrying the projection's move into the internal faces only made it
  worse, and the layout's geometric limit (SJ 0.665–0.707) is far above
  the meshed values.  No correction is planned; equal laterals and
  second order stay deferred.
