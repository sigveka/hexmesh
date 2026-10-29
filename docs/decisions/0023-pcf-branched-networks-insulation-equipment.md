# 0023 — PCF input: branched networks, junctions, insulation and equipment

- **Status:** accepted
- **Date:** 2026-10-27 (accepted by the user: "So a PCF reader is
  sufficient for hexmesh?" → "yes" to writing the task)
- **Tasks:** 0037 (branches and junctions), 0038 (insulation and
  equipment)

## Context

PCF is hexmesh's plant-piping input; ISOGEN's older IDF is not needed
(most plant systems export PCF; no public IDF specification).  Task 0021
made the reader conform to the PCF reference guide for single runs.
Three gaps remain (`docs/integrations/pcf.md`, rows 6–8):

- **#6** one greedy chain: several pipelines and branches per file are
  mis-ordered;
- **#7** `TEE`, `TEE-SET-ON`, `OLET`, `CROSS`, `Y-PIECE-FABRICATED`
  are skipped, although the assembly now has `Tee` (task 0010) and
  `Wye` (task 0030);
- **#8** insulation, equipment and nozzles are ignored, although
  decisions 0002 and 0006 provide for them.

Facts that shape the design (pcf.md, from the guide):
- `TEE` has two run `END-POINT`s, a `CENTRE-POINT` and `BRANCH1-POINT`.
  `TEE-SET-ON` / `OLET` have **no end points**: they sit on a pipe that
  the PCF does not split.  SKEYs mark tangential and offset variants.
- Bore is nominal; insulation is a pipeline attribute
  (`INSULATION-THICKNESS`) switched per component and per end point.
- Equipment nozzles have a position, size and a compass `DIRECTION`;
  pipelines attach by `END-CONNECTION-EQUIPMENT`.

Limits of the fittings it maps to:
- `Tee`: single-layer spec, perpendicular centred branch, branch radius
  **strictly below** the main radius (so no equal tees).
- `Wye`: single-layer, symmetric, coplanar, equal daughters, 30°–120°.
- Every fitting is placed **from its inlet port** (`ports(inlet)`); a
  junction cannot be entered from a branch.

## Options

### Junction placement when the PCF is entered from a branch
- **A. Choose the root.**  Pick the network's inlet so that every
  junction is entered through its inlet (run end of a tee, stem of a
  wye).  Possible for many trees, impossible for some (two tees joined
  branch to branch).
- **B. Enter a fitting by any port.**  A general Assembly feature
  (`add(…, via="branch")`); touches every multi-port fitting and the
  port signatures.
- **Chosen: A now**, with an error naming the junction when no root
  works.  B is recorded below as a follow-up for design, not tasked.

### Unsupported variants
Equal tees, offset/tangential/angled set-ons, crosses, asymmetric Y
pieces: **reject with an error naming the PCF component and the limit**
(never substitute a different geometry).  An option to replace an
unsupported component by an open end pair is out of scope.

### Insulation
- **Off by default** (`insulation=False`): the spec callable decides the
  layers, as today.
- With `insulation=True`: the reader appends an `insulation` shell of
  the pipeline's `INSULATION-THICKNESS` to each spec, and turns it off
  and on with `stack_changes` (decision 0006) **inside straight
  components** where the PCF switches it.  Where a switch falls at a
  junction or another fitting that can't take it, the reader raises an
  error naming the component.  Junctions are single-layer today, so an
  insulated line with a tee fails with that error (expected).

### Equipment
A pipeline end with `END-CONNECTION-EQUIPMENT` becomes an open end named
`<equipment>_<nozzle>` (the rule of decision 0002, as `from_nozzle`
does), and is **marked as an equipment end**: `extend_open_ends` never
extends it.  The mark is an interface field saved in the JSON.  No
equipment geometry is built (decision 0002: nozzles are boundaries).

## Decision

1. The reader builds a **graph**: components joined at shared end points
   (within the existing tolerance) and by `END-CONNECTION-PIPELINE`,
   across all pipelines in a file.  Several files can be read into one
   network (`read_pcf([...])`).
2. **Root:** `to_assembly(..., inlet=...)` accepts an end point or an
   end name; by default the reader picks one by option A, deterministically
   (same file → same root).  Loops (cycles in the graph) are rejected
   for now, naming one component on the cycle (`Assembly.close` could
   join them later).
3. **Junction mapping:** `TEE` → `Tee`; `TEE-SET-ON`, `TEE-STUB`,
   `OLET` (perpendicular, centred SKEYs only) → the host pipe split at
   `CENTRE-POINT` into straight + `Tee` + straight;
   `Y-PIECE-FABRICATED` → `Wye` when within its limits.  Everything else
   → error, as above.
4. **Names:** fittings are labelled from the PCF (`<type>_<n>` in file
   order, or a component's own reference when present); open ends from
   the pipeline reference and the equipment connection.  Labels are
   unique and stable.
5. Insulation and equipment as above.

## Consequences

- `docs/integrations/pcf.md` rows 6–8 change to fixed or "rejected by
  design" as the tasks land.
- What stays out: equal tees, angled and offset branches, crosses, loops,
  insulated junctions.  Each is an error with a reason, so a user knows
  what to change.
- **Follow-up for design (not tasked):** entering a fitting by any port
  (option B); equal tees (RESEARCH §3: the intersection curve
  degenerates).
- **Effect on future expansions:**
  - 0019 (agent SDK): errors name the PCF component, field and limit
    (constraint 3); labels and end names are stable (constraint 4); the
    equipment mark is saved in the JSON (constraint 2); the root choice
    is deterministic (constraint 5).
  - 0018 (vascular): option B would also serve confluences (flow merging
    into a vessel); a vascular reader would reuse the graph-to-assembly
    traversal, so keep it independent of PCF records.
  - 0021 (flow restrictions): PCF instruments and orifice flanges stay
    `Straight` today; keeping the PCF component type in the label lets
    a later stage map them to restriction fittings.

**Note (2026-10-29, decision 0031's amendment):**
- **Equal tees** become `Tee`s with r = R, built by the wye-family
  layout once the wye-layout redesign lands.  Until then the reader's
  rejection should say they're planned, not unsupported (task 0064).
- **Odd ratios:** a PCF tee with τ < r/R < 1 is rejected with the hint
  from 0031.
- **Laterals and offset set-ons** map through 0031's stages 1–2.

## Verified vs. assumed

- **Verified:** the PCF facts (guide, via `docs/integrations/pcf.md`);
  the `Tee`/`Wye` limits and inlet-port placement (code, 2026-10-27).
- **Assumed:** that option A finds a root for most real plant files (no
  real exported PCF has been tested yet, pcf.md); whether the guide
  defines a flow-direction attribute that could pick the root (task 0037
  checks).
