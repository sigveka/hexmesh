# 0059 — After 1.0: F, then C, then B in 1.x; the general section makes 2.0; D after it

- **Status:** accepted (2026-11-27, the user: the order).  Open items are
  listed at the end.
- **Date:** 2026-11-27
- **Tasks:** none yet.  Each theme is tasked only when its decisions are
  accepted.

## Context

Decision 0042 sets what 1.0 promises.  Breaking changes to the Python API,
the saved description, the CLI's JSON, the manifest or the error codes
come only in 2.0, and 1.x only adds.  The work after 1.0 is recorded as
*proposed* decisions and "after 1.0" notes, unordered.  The design
session grouped it into themes (2026-11-26):

| Theme | Records |
|---|---|
| **A. Reach** | PyPI; the docs site (0049, tasks 0137, 0172); network interchange (0032) |
| **B. More geometry** | forged tees (0045); branches on curved vessels (0048); drums, nozzles and density changes (0003, probe 0133); flow restrictions (0021) |
| **C. New domains** | idealised vascular networks (0018); pipe-in-pipe and multi-core sections (0035) |
| **D. Driving hexmesh** | the agent SDK (0019); the study and surrogate suite (0030) |
| **E. Validation depth** | the Taylor bubble (0079), the Vattenfall T-junction (0120), the KTH duct (0180); a second code inside validation; more export consumers (0057) |
| **F. Mesh quality** | the O-H core's convergence order (0022); the wyes' split region (RESEARCH §7.14); alternative backends (0007) |

The user (2026-11-27):
- "I want E as well as doc site before 1.0."
- "After 1.0 I think we start with F, then B, D finally C."
- On being told the 2.0 line: "push surrogate modelling until after
  2.0.  Let us [do] F -> C -> B -> 2.0 -> D".

**Where the 2.0 line falls** (the design session, from the records).
A new domain doesn't force 2.0.  What does is **the general section**:
a cross-section that isn't the 5-patch O-H face, with port signatures
that compare block graphs and counts instead of a fixed patch list.
The signature appears in saved descriptions, the manifest and the
interface checks, so generalising it is very likely breaking.  Three
records need it:
- 0035 stage B (multi-core sections) and stage C (routes, helical lay);
- 0018 item 7 (vascular contour sections);
- 0021 stage 3 (eccentric and segmental restrictions, contour sections).
Everything else in B, C and F can be additive.  0045 adds one field with
a default.  0003's note already requires density changes to arrive
additively.  A changed mesh isn't breaking (RELEASING §3).

## Options

- **A. Themes in the order of the theme letters.**  No reason behind it.
- **B. The design session's first sketch:** F → B → D → C, with C's
  section work as 2.0.
- **C. The user's order (chosen):** F → C → B → 2.0 → D.

## Decision

**Before 1.0:** E and the docs site join the exit criteria.  The scope is
open (below).  It's recorded as a note on 0042 once settled.

**After 1.0, in this order:**

1. **F, mesh quality (1.x).**  Settle 0022: does the order level off at
   k = 16, and does any case fail its gate because of the core?  Then the
   wyes' split region (a new decision: refine `n_split`, or a split
   family).  0007 (backends) stays proposed unless F shows a need.
2. **C's additive part (1.x):**
   - **vascular networks with circular sections** (0018): the
     centreline-and-radius importers and bifurcations;
   - **pipe-in-pipe** (0035 stage A).  It needs **0021 stage 1**,
     layer name vs material: a layer's fluid or solid role comes from its
     material, not its place in the stack.  That item is pulled forward
     from B into C.  Old descriptions migrate on load (0042), so it stays
     additive.
3. **B, more geometry (1.x):** 0045, 0048, then 0003 after its probe
   (task 0133) chooses an option, then 0021 stages 1 (if not done in C)
   and 2.
4. **2.0, the general section:**
   - one decision, designed once for all three users: 0035 B/C, 0018
     item 7 and 0021 stage 3;
   - its first release carries multi-core sections (the buried
     district-heating pair first, 0035's note), contour sections and
     asymmetric restrictions;
   - deprecations go first, in a 1.x minor release (0042 rule 2);
   - work in 1.x keeps 0035's constraints (don't hard-wire the O-H face
     in new interfaces), so 2.0 is a planned change, not a rewrite.
5. **D, after 2.0:** the agent SDK (0019), then the study and surrogate
   suite (0030).  Both are built on the schema and signatures that 2.0
   settles, so they aren't designed twice.

**Why this order** (the user's choice; the design session's reading):
- F first: it improves what 1.0 ships, and it's cheap.
- C's additive part before B: it opens new users, and the domains are
  further from today's code, so they show earlier what the general
  section must hold.
- B rounds out 1.x before the break.
- D last: an interface that agents and studies depend on should sit on
  the final model.

## Consequences

- **No DESIGN.md change.**  No tasks now.  Each step starts by accepting
  its proposed decisions.  Tasks follow one theme at a time.
- **Task 0133** (the density-change probe) stays `ready (after 1.0)`.
  Under this order it belongs to B, after C.  It's cheap, so it may run
  earlier if F leaves room.
- **Decision 0042** gets a note when the open items below are settled.
- **Future expansions:** this decision orders them.  It doesn't change
  their constraints:
  - 0018, 0021 and 0035 keep "don't hard-wire the O-H face", which is now
    the 2.0 boundary;
  - 0019 and 0030 move after 2.0;
  - every 1.x decision is still checked against all five.
- **Harder:** a long 1.x before the agent SDK, if the themes are
  large.  Users who want automation earlier have the CLI's JSON (0042's
  promise).

## Open items

1. ~~E's scope before 1.0.~~  **Settled (2026-11-28, the user: "Yes I
   want them before 1.0"):** all three cases with results, the
   Vattenfall LES by a volunteer (task 0202).  Note on 0042.
2. ~~The docs site before 1.0.~~  **Settled (the user: "Doc site will be
   updated"):** on the next Essens release.  Note on 0042.
3. **A (reach)** isn't placed: PyPI, 0032's network interchange.  The
   design session suggests it runs alongside every theme.
4. **Release cadence in 1.x:** a minor release per theme milestone is
   the suggestion.  Not decided.

## Verified vs. assumed

- **Verified (2026-11-27, from the records):**
  - 0042's promises;
  - 0045's one additive field;
  - 0003's note requiring additive density changes;
  - 0035's stage table and its constraints;
  - 0021's stages;
  - 0022's open question (k = 16).
- **Assumed:** that generalising the port signature is breaking.  It
  could perhaps be done additively, with a new signature kind beside the
  O-H one.  The 2.0 decision checks this first.  If it can be additive,
  the general section moves into 1.x and 2.0 has no driver yet.
