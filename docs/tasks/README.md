# Tasks

One file per unit of work for the coding agent.  Every task traces back to
an **accepted** decision in [`../decisions/`](../decisions/) or to a rule in
[`DESIGN.md`](../../DESIGN.md).  The process is described in
[`../decisions/README.md`](../decisions/README.md#the-loop).

## Index

| Task | Title | Status | Decision |
|---|---|---|---|
| [0000](0000-keep-face-grading.md) | Keep face-builder grading through meshing (bug fix) | done | 0001 |
| [0001](0001-axial-grading.md) | Axial grading per fitting | done | 0001 |
| [0002](0002-first-cell-height.md) | Radial grading from first-cell height | done | 0001 |
| [0003](0003-cell-count.md) | Exact cell count before GMSH | done | 0001 |
| [0004](0004-quality-per-fitting.md) | Quality report per fitting, with hex metrics | done | 0001 |
| [0005](0005-openfoam-output.md) | OpenFOAM-compatible output | done | 0001 |
| [0006](0006-intent-serialization.md) | Save and load the network description (Intent layer) | done | 0001 |
| [0007](0007-topology-invariance-test.md) | Test that topology is unchanged across geometry variants | done | 0001 |
| [0008](0008-open-end-extensions.md) | Inlet and outlet extensions | done | 0001 |
| [0009](0009-per-fitting-wall-patches.md) | Per-fitting wall patches | done | 0001 |
| [0010](0010-equipment-nozzle-boundaries.md) | Equipment nozzles as network boundaries | done | 0002 |
| [0011](0011-assembly-independent-of-legacy.md) | Assembly independent of legacy code | done | 0004 |
| [0012](0012-miter-bend-and-elbow.md) | Miter bends and standard elbows | done | 0004 |
| [0013](0013-reducer-expander.md) | Reducer, expander and transition | done | 0004 |
| [0014](0014-spline-pipe.md) | Spline pipe | done | 0004 |
| [0015](0015-io-on-assembly.md) | PCF and bathymetry readers build an Assembly | done | 0004 |
| [0016](0016-public-api-and-examples.md) | Public API, examples and docs on the assembly | done | 0004 |
| [0017](0017-delete-legacy.md) | Delete the legacy code | done | 0004 |
| [0018](0018-layer-termination-in-sweep.md) | Layer termination in `Sweep` (insulation stops and starts) | done | 0006 |
| [0019](0019-port-face-signatures-and-classifier.md) | Port-face signatures and the topology-switch classifier | done | 0011 |
| [0020](0020-validation-poiseuille.md) | Validation: laminar Hagen–Poiseuille pipe, three refinement levels | done | 0012, 0015 |
| [0021](0021-pcf-reader-spec-conformance.md) | PCF reader: conform to the PCF reference guide (bug fixes) | done | 0004 |
| [0022](0022-rename-interface-groups.md) | Rename material-interface groups to `interface_<inner>_<outer>` | done | 0013 |
| [0023](0023-boundary-role-manifest-and-retyping.md) | Boundary-role manifest and OpenFOAM patch retyping | done | 0013 |
| [0024](0024-parallel-test-suite.md) | Parallel test suite (pytest-xdist) and registered markers | done | 0014 |
| [0025](0025-ruled-straight-slabs.md) | Ruled side surfaces for straight slabs, and a wall-exactness check | done | 0015 |
| [0026](0026-assembly-refined.md) | `Assembly.refined(k)`: uniform refinement for convergence studies | done | 0015 |
| [0027](0027-grading-change-across-sweeps.md) | Grading-only changes across a sweep (wall-resolved reducers) | done | 0016 |
| [0028](0028-rectangular-cores.md) | Rectangular cores in the assembly (single-layer ducts) | done | 0009, 0010 |
| [0029](0029-transition-circle-rectangle.md) | `Transition`: circle ↔ rectangle and rectangle ↔ rectangle sweeps | done | 0009 |
| [0030](0030-wye-prototype.md) | Wye prototype: symmetric Y-junction as a block layout | done | 0017 |
| [0031](0031-profiled-reducer.md) | Profiled `Reducer`: constrictions, venturis and nozzles | done | 0008 |
| [0032](0032-validation-stenosis.md) | Validation: smooth cosine constriction (Varghese et al.), Re = 500 | ready (after 0031, 0020) | 0008, 0012 |
| [0033](0033-validation-heated-rod.md) | Validation: solid rod with uniform heat generation | done | 0012, 0015 |
| [0034](0034-validation-layered-conduction.md) | Validation: conduction through a heated multi-layer cylinder (CHT, solids) | ready (after 0025, 0033) | 0012 |
| [0035](0035-validation-heated-pipe-cht.md) | Validation: heated multi-layer pipe with laminar flow (full CHT) | ready (after 0034) | 0012 |
| [0036](0036-linear-build-time.md) | Linear build time: fewer `synchronize` calls, and a build benchmark | done | 0020 |
| [0037](0037-pcf-branched-networks.md) | PCF reader: branched networks and junctions | done | 0023 |
| [0038](0038-pcf-insulation-and-equipment.md) | PCF reader: insulation and equipment connections | ready (after 0037) | 0023 |
| [0039](0039-interface-degree-and-session-guard.md) | Two validation bugs: overlapping fittings on one interface, GMSH calls outside a session | done | 0024 |
| [0040](0040-port-names-orientation-angle-units.md) | Named ports, absolute orientation (`toward=`, junction roll), `rot` in degrees | done | 0024 |
| [0041](0041-assembly-axial-cell.md) | `Assembly(axial_cell=…)`: `n_layers` from a target cell size | done | 0024 |

Decision 0004 (retire legacy) comes first: 0011 → 0012 / 0013 / 0014 →
0015 → 0016 → 0017.  0017 waits for all the others.  Then the rest of
decision 0001.

Suggested order for decision 0001: 0000 → 0003 → 0001 → 0002 → 0004 → 0007 → 0006 → 0005 →
0008 → 0009, then 0010 (after 0006, which it builds on).  0001, 0004 and
0006 have the highest value.  0000 is a bug fix that 0001 and 0002 build on.

0018 (decision 0006) can start now that 0013 is done; it touches the
same sweep spec handling.  Prefer **0019 before 0018**: 0019 adds the
port-pair classifier, and 0018 then declares class 1 for layer
termination instead of adding its own check.

**0025 first**: it changes node positions in every mesh with a
multi-layer `Straight`, and 0020's re-run depends on it.  0026 is
independent; do it before 0020's re-run if convenient.

The multi-layer tee (needed for CHT networks with junctions) is not
low-hanging fruit and has no task yet.  It needs a design decision first;
it fits best after 0004, when first-cell grading and per-fitting quality
can measure its wall layers.

## Ground rules

These apply to every task.

- Read `DESIGN.md` first.  Changes must follow it and must **not** add rows
  to its "Current deviations" table.
- Work only in `hexmesh/assembly/` (and `hexmesh/core/` where stated).
- Anything computable without GMSH must be computed without GMSH (DESIGN
  P3/P4): in `ports()`, `validate()` or `Assembly.validate()`, never in
  `fill()`.
- Every task adds tests.  New fittings or fill changes must still pass the
  conformance kit, `tests/test_fitting_conformance.py`.
- Run tests with `python3 -m pytest` (never `python`).  Gate: no new
  failures before and after each task.  The full suite has no known
  failures.
  - Since task 0024 (2026-10-25), this runs **in parallel** (`-n auto`,
    from `pyproject.toml`) and **skips OpenFOAM tests**.  Serial for
    debugging: `-n 0`.
    Expected time (8 cores, 2026-10-27): about 4 min in parallel,
    12 min serial.
  - OpenFOAM tests are opt-in: `python3 -m pytest -m openfoam`.  Run
    them too when a task touches OpenFOAM output (e.g. 0009, 0022, 0023).
  - Follow `CLAUDE.md`, "Both sessions, shared machine", before long
    runs.
- Keep each task a separate, reviewable change.  Match the surrounding code
  style: dataclasses, numpy, short docstrings that cite DESIGN rules.

### Not part of any task

Don't fold these into a task: wye work beyond task 0030's symmetric
prototype (decision 0017), tee generalisation (multi-layer, laterals, offset taps, exact tee
walls), `n_outer = 8` core filling, or anything in `docs/RESEARCH.md` §8.
They are design decisions, not low-hanging fruit.  (The tee side-corner
arc split is no longer needed: the block-layout tee places its saddle
corners on the branch diagonals, DESIGN §7.1.)

## Working a task (coding agent)

1. Pick a `ready` task whose dependencies are `done`.  Set its status to
   `in progress` here and in the task file.
2. You may refine **Do** and **Accept** with what you learn from the code.
   Record what you changed and why under **Agent notes**.
3. You may not change a decision record or edit `DESIGN.md`.  If the work
   needs a design choice, or shows that a decision is wrong:
   - write the question, with options and evidence, under **Questions for
     design**;
   - set the status to `blocked`;
   - stop, or move to another task.
   You may *propose* exact DESIGN.md wording there; the design session
   applies it.
4. When finished, fill in **Outcome**: what changed (files), test results
   (counts, and any known failures), measurements, surprises, and proposed
   follow-up tasks.  Set the status to `done`.

New tasks found while working go in **Outcome** as proposals.  The design
session turns them into task files.

## Task template

```markdown
# NNNN — Title

- **Status:** ready | in progress | blocked | done
- **Decision:** [NNNN — title](../decisions/NNNN-slug.md)  (or a DESIGN.md rule)
- **Depends on:** NNNN, … | —

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The problem, with evidence (file:line, measurements).

**Where.**  Files and functions involved.

**Do.**  Numbered steps.

**Accept.**  Tests or measurements that prove it is done.

**Out of scope.**  (optional)

## Agent notes

## Questions for design

## Outcome
```
