# 0133 — Probe: two density changes meshed by gmsh (a +1-ring radial step, a ×2 nang slab)

- **Status:** ready (after 1.0: not a 1.0 item, decision 0042; the user
  may release it earlier)
- **Decision:** [0003](../decisions/0003-drum-body-and-shell-nozzles.md) (proposed; note 2026-11-10), [0046](../decisions/0046-gmsh-meshes-hexmesh-corrects.md) (gmsh creates every element), [0018](../decisions/0018-future-vascular-networks.md) (prerequisite 5)
- **Depends on:** none in code.  Read RESEARCH §9.3–9.5 first.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Decision 0003 can't choose between conformal transitions
(option A) and declared non-conformal breaks (option C) without numbers.
Two questions decide it: what quality an unsmoothed transition reaches
on hexmesh's structured O-H section, and whether gmsh can build one at a
practical cost.  Like task 0117, this is a probe in a scratch module: no
library change, no API.

**Where.**  A probe script in the task's scratch area (not in
`hexmesh/`); results in this file and RESEARCH §9 (design session).

**Do.**
1. **Radial +1 ring.**  One straight slab, O-H section, `nang` 8, `nrad`
   4 at the inlet and 5 at the outlet: the new O-ring sheet enters at the
   outlet and ends inside the slab on the wall (a pillow / cleave,
   RESEARCH §9.5).  Built as ordinary transfinite blocks if the layout
   allows; otherwise say why.  Measure min SJ, min SICN and
   non-orthogonality against a plain `Straight` at `nrad` 4 and 5, for a
   slab of 1, 2 and 4 axial cells, and at `nrad` 8 → 9.
2. **Angular ×2.**  One slab from `nang` 8 to 16 using the parallel-sheet
   template (RESEARCH §9.3, `harris_and_benzley_etal_2004`), each
   transition cell a one-cell transfinite block, so gmsh creates every
   element (decision 0046).  Measure the same quality numbers, plus the
   OCC volume count, build time and memory, at `nang` 8 → 16 and
   16 → 32.  Run alone (CLAUDE.md, shared machine).
3. **Optional, if 1 or 2 fails:** the same slab as a declared
   non-conformal joint (two `Straight`s, `nang` 8 and 16, AMI in
   OpenFOAM v2406): `checkMesh` and a laminar Poiseuille flow, the
   pressure-drop error at the joint against a single-density run.  Note
   the disk used; delete the case after.
4. **Report** in *Outcome*: a table per variant (quality, build cost),
   and which of decision 0003's options the numbers favour.  No limits,
   no API: that's design's next step.

**Accept.**
- Steps 1–2 measured (or a stated reason a variant can't be built in
  gmsh); the scratch code kept with the task, not in the library.

**Out of scope.**  A fitting, API, schema; smoothing (DESIGN A2);
written elements (decision 0046 makes them opt-in only).

## Agent notes

## Questions for design

## Outcome
