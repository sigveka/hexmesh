# 0116 — The wye redesign, measured: can the hub take asymmetric and unequal daughters, and can the published topology be built?

- **Status:** ready (after 0103 and 0104, in 0.6's junction work)
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
