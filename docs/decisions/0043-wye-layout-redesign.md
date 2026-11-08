# 0043 — The wye-layout redesign: equal tees, asymmetric and unequal daughters, creases

- **Status:** accepted, measure first (2026-11-08, by the user: "yes";
  decision 0042's critical path).  The layout (A, B or C) is chosen by an
  amendment after task 0116.
- **Date:** 2026-11-08
- **Tasks:** 0116 (the measurement)

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
