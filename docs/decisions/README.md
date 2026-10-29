# Design decisions

One record per design decision: what was decided, why, and what was
rejected.  Records are written in design sessions, and they are the only way
`DESIGN.md` changes.

| Document | Holds | Changed by |
|---|---|---|
| [`DESIGN.md`](../../DESIGN.md) | Rules | Design session, only through an accepted decision |
| [`RESEARCH.md`](../RESEARCH.md) | Evidence: sources, formulas, measurements | Design session |
| `decisions/NNNN-*.md` | Why: options, choice, consequences | Design session |
| [`tasks/NNNN-*.md`](../tasks/) | What: work, acceptance, findings | Design session writes; coding agent refines and reports |

## Index

| Decision | Title | Status |
|---|---|---|
| [0001](0001-complete-assembly-prototype.md) | Complete A5/A7 in the assembly prototype | accepted |
| [0002](0002-equipment-nozzle-boundaries.md) | Equipment nozzles as network boundaries | accepted |
| [0003](0003-drum-body-and-shell-nozzles.md) | Drum bodies, shell nozzles and density changes | proposed |
| [0004](0004-retire-legacy-api.md) | Retire the legacy API | accepted |
| [0005](0005-n-outer-as-sub-partition.md) | `n_outer = 8` as a sub-partition of the 4-corner grid | proposed |
| [0006](0006-layer-stack-changes-in-sweeps.md) | Layer-stack changes inside sweep fittings | accepted |
| [0007](0007-alternative-realisation-backends.md) | Alternative realisation backends (Cubit rejected) | proposed |
| [0008](0008-profiled-sweep.md) | Profiled sweep: a varying-radius fitting | accepted |
| [0009](0009-rectangular-sections-and-transitions.md) | Rectangular sections and circle ↔ rectangle transitions | accepted |
| [0010](0010-section-symmetry-period.md) | Corner identity by index and the section symmetry period P | accepted |
| [0011](0011-port-face-signatures-and-switch-strategies.md) | Port-face signatures and topology-switch strategies | accepted |
| [0012](0012-openfoam-validation-cases.md) | OpenFOAM verification and validation cases | accepted |
| [0013](0013-openfoam-group-names-and-boundary-roles.md) | OpenFOAM output: group names and boundary roles | accepted |
| [0014](0014-test-infrastructure.md) | Test infrastructure: parallel runs and shared-machine rules | accepted |
| [0015](0015-exact-straight-slabs-and-convergence-studies.md) | Exact walls in straight slabs, and how convergence is judged | accepted |
| [0016](0016-class-1-granularity-and-grading-changes.md) | Class-1 granularity, and grading changes across a sweep | accepted |
| [0017](0017-wye-junction-prototype.md) | Y-junction (wye): prototype first, quality limit after measurement | accepted |
| [0018](0018-future-vascular-networks.md) | Future expansion: idealised vascular networks | proposed (future) |
| [0019](0019-future-agent-sdk.md) | Future expansion: an agent SDK (hexmesh driven by AI tool calls) | proposed (future) |
| [0020](0020-build-time-scaling-and-parallelism.md) | Build time grows linearly with the model; parallelism only across jobs | accepted |
| [0021](0021-future-flow-restrictions.md) | Future expansion: flow restrictions (orifices, nozzles, venturis, and beyond) | proposed (future) |
| [0022](0022-oh-core-convergence-order.md) | Convergence order of the O-H section, and a self-similar core square | proposed |
| [0023](0023-pcf-branched-networks-insulation-equipment.md) | PCF input: branched networks, junctions, insulation and equipment | accepted |
| [0024](0024-api-ergonomics.md) | API ergonomics: port names, absolute orientation, angle units, axial cell size | accepted |
| [0025](0025-study-runner.md) | Study runner: many variants from one template, in parallel jobs | accepted |
| [0026](0026-layer-outlines.md) | Layer outlines: shells of any shape | accepted |
| [0027](0027-duct-tees.md) | Tees in rectangular ducts | accepted |
| [0028](0028-multi-layer-junctions.md) | Multi-layer junctions: insulation and pipe walls through tees and wyes | accepted |
| [0029](0029-wall-exactness-by-node-projection.md) | Wall exactness by node projection where no exact OCC surface fits | accepted |
| [0030](0030-future-simulation-suite.md) | Future expansion: hexmesh as one generator in a multi-domain study and surrogate suite | proposed (future) |
| [0031](0031-general-branch-junctions.md) | General branch junctions: laterals, offset taps and arbitrary roll | accepted |
| [0032](0032-network-interchange.md) | Network interchange: importers, a network model, a network document, one builder | proposed (work in progress) |

## Future expansions

Directions the user wants kept open, recorded as `proposed` decisions
with no tasks.  Each lists constraints that new decisions are checked
against (template, *Consequences*).

| Decision | Expansion |
|---|---|
| [0018](0018-future-vascular-networks.md) | Idealised vascular networks (centrelines + radius, bifurcations, VMTK input) |
| [0019](0019-future-agent-sdk.md) | Agent SDK: tool interface over the network JSON (schema, structured errors, preview, build jobs) |
| [0021](0021-future-flow-restrictions.md) | Flow restrictions, staged: profiles (stage 0) → orifice plates → bevels and rounded entries → eccentric, segmental, cone meters → non-swept devices |
| [0030](0030-future-simulation-suite.md) | A multi-domain study and surrogate suite with hexmesh as one generator (layers: generators, solver adapters, study engine, datasets, surrogates, V&V; versioned contracts) |

On hold, not yet recorded (discussed 2026-10-26): drum heads and closed
vessels (a `Head` fitting as half a cubed-sphere O-grid; spheres as two
heads), split from decision 0003 option A.

## The loop

1. **Design session.**  Discuss.  When a question is settled, write or
   update a decision record and the tasks that follow from it.  An
   unsettled question stays a `proposed` decision, or an entry in DESIGN
   §10 "Open decisions"; it gets no tasks.
2. **Coding session.**  The coding agent works `ready` tasks (see
   [`tasks/README.md`](../tasks/README.md#working-a-task-coding-agent)).  It
   may refine a task's steps, but not decisions or `DESIGN.md`.  Design
   questions and proposed DESIGN wording go in the task's **Questions for
   design**, and the task becomes `blocked`.
3. **Next design session.**  Start by reading every task that is `blocked`
   or newly `done`.  Move measurements into `RESEARCH.md`, answer
   questions, update or supersede decisions, and apply accepted DESIGN
   wording.

A task without a link to an accepted decision or a DESIGN rule is not
ready.

## Statuses

- `proposed`: under discussion; no tasks may depend on it.
- `accepted`: in force; tasks may be written from it.
- `rejected`: kept for the reasoning; say why.
- `superseded by NNNN`: replaced; kept for history.

## Template

```markdown
# NNNN — Title

- **Status:** proposed | accepted | rejected | superseded by NNNN
- **Date:** YYYY-MM-DD
- **Tasks:** NNNN, … | none

## Context

The problem and constraints.  Link DESIGN.md and RESEARCH.md sections.

## Options

### A. …
Trade-offs.

### B. …
Trade-offs.

## Decision

What was chosen and why.  For `proposed`: the recommendation and what
must be settled first.

## Consequences

DESIGN.md changes (exact sections), new tasks, what becomes harder.
Effect on future expansions (see "Future expansions"): none, or which
constraint is affected and how.

## Verified vs. assumed

Which claims are measured or checked, and which are reasoning or
unverified.
```
