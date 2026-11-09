# 0118 — The oriented junction cube, measured: can a 7-hex cube with ports take equal tees and equal laterals?

- **Status:** ready (before 0117)
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
