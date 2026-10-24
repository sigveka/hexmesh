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
| [0003](0003-drum-body-and-shell-nozzles.md) | Meshing drum bodies and shell nozzles | proposed |
| [0004](0004-retire-legacy-api.md) | Retire the legacy API | accepted |

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

## Verified vs. assumed

Which claims are measured or checked, and which are reasoning or
unverified.
```
