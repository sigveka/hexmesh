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
| [0004](0004-quality-per-fitting.md) | Quality report per fitting, with hex metrics | ready | 0001 |
| [0005](0005-openfoam-output.md) | OpenFOAM-compatible output | ready | 0001 |
| [0006](0006-intent-serialization.md) | Save and load the network description (Intent layer) | ready | 0001 |
| [0007](0007-topology-invariance-test.md) | Test that topology is unchanged across geometry variants | ready | 0001 |
| [0008](0008-open-end-extensions.md) | Inlet and outlet extensions | ready | 0001 |
| [0009](0009-per-fitting-wall-patches.md) | Per-fitting wall patches | ready | 0001 |
| [0010](0010-equipment-nozzle-boundaries.md) | Equipment nozzles as network boundaries | ready | 0002 |
| [0011](0011-assembly-independent-of-legacy.md) | Assembly independent of legacy code | done | 0004 |
| [0012](0012-miter-bend-and-elbow.md) | Miter bends and standard elbows | done | 0004 |
| [0013](0013-reducer-expander.md) | Reducer, expander and transition | done | 0004 |
| [0014](0014-spline-pipe.md) | Spline pipe | done | 0004 |
| [0015](0015-io-on-assembly.md) | PCF and bathymetry readers build an Assembly | done | 0004 |
| [0016](0016-public-api-and-examples.md) | Public API, examples and docs on the assembly | done | 0004 |
| [0017](0017-delete-legacy.md) | Delete the legacy code | done | 0004 |
| [0018](0018-layer-termination-in-sweep.md) | Layer termination in `Sweep` (insulation stops and starts) | ready | 0006 |

Decision 0004 (retire legacy) comes first: 0011 → 0012 / 0013 / 0014 →
0015 → 0016 → 0017.  0017 waits for all the others.  Then the rest of
decision 0001.

Suggested order for decision 0001: 0000 → 0003 → 0001 → 0002 → 0004 → 0007 → 0006 → 0005 →
0008 → 0009, then 0010 (after 0006, which it builds on).  0001, 0004 and
0006 have the highest value.  0000 is a bug fix that 0001 and 0002 build on.

0018 (decision 0006) can start once 0013 is done; it touches the same
sweep spec handling.

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
- Keep each task a separate, reviewable change.  Match the surrounding code
  style: dataclasses, numpy, short docstrings that cite DESIGN rules.

### Not part of any task

Don't fold these into a task: Y-junction/Stage 6 work, tee generalisation (multi-layer, laterals, offset taps, exact tee
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
