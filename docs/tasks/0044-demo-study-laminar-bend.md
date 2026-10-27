# 0044 — Demonstration study: laminar 90° bend, loss chart and aligned dataset

- **Status:** ready (after 0043)
- **Decision:** [0025 — Study runner](../decisions/0025-study-runner.md)
- **Depends on:** 0042, 0043.  Uses the laminar pipeline of task 0020.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  One study that shows the use cases end to end: a design chart
from a parameter sweep, a convergence check, and a node-aligned dataset.
It is laminar because only laminar cases are validated (decision 0012).

**Where.**  New `studies/laminar_bend/`: `study.json`, `template.py`
(`build(params)`), the case template directory, `post.py`, `README.md`,
`RESULTS.md`.  Link it from `docs/GALLERY.md`'s validation section (or
a new "Studies" section in `docs/gallery/build.py`, if simple).

**Do.**
1. **Network:** straight (development length) → 90° `Bend` → straight
   (recovery length), single-layer pipe, wall-graded core; counts fixed
   across the sweep so all variants share one topology key.
2. **Sweep:** bend radius ratio R/D ∈ {1, 1.5, 2, 3, 5} × Reynolds number
   ∈ {50, 200, 500} (Re enters the case template, not the mesh).  15
   variants, one topology.
3. **Post-processing:** Δp between stations upstream and downstream of
   the bend, minus the straight-pipe Δp of the same length (Poiseuille),
   giving the bend loss coefficient K; also the secondary-flow strength
   at the bend outlet (max in-plane velocity / mean axial velocity).
4. **Convergence:** for the extreme corners of the sweep (R/D 1 and 5 at
   Re 500), three levels with `refined(k)`, Richardson and GCI as in
   decision 0015 (amended).
5. **Comparison:** look up a laminar curved-pipe correlation or data set
   for K or for the friction ratio (e.g. Dean-number correlations; check
   the source and its validity range, and record it in RESEARCH with the
   citation).  Report agreement; don't tune.
6. **Outputs:** a chart (K vs R/D per Re) as PNG, the manifest, and the
   aligned `.npz` with the velocity field per variant (cell centres or
   nodes; say which).
7. `README.md` for a human reader: what the study shows, how to run it
   (`python3 -m hexmesh.study run studies/laminar_bend/study.json --jobs N`),
   total wall time, and what's needed for a turbulent version.

**Accept.**
- 15 variants preflight, mesh, case and run without manual steps; one
  topology key.
- GCI for K at the two corners reported; K's fine-level uncertainty
  stated in RESULTS.
- Comparison with the published source reported (agreement or the
  difference and a reason).
- Total wall time and cores used recorded (idle machine).
- The study is not in the default test run.

**Out of scope.**  Turbulent flow; tees (a later study once a
turbulent case is validated).

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
