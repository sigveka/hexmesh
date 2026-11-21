# 0188 — Hints from validation: what to watch, where users look

- **Status:** ready (a first pass now; finished after 0050, 0186 and 0187
  report)
- **Decision:** [0058](../decisions/0058-diagnosis-ladder-and-user-hints.md)
  rule 3
- **Depends on:** none for the first pass.  0050, 0186, 0187 for the rest.
- **Blocks:** 1.0 (decision 0058 rule 4).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Validation keeps finding traps a user would fall into too.
Today the findings sit in task files and RESEARCH.  The user (2026-11-21)
wants them as hints in hexmesh before 1.0.

**Do.**
1. **Collect.**  One table under *Agent notes*: lesson, evidence (task,
   case, numbers), who meets it (mesh user, OpenFOAM user, agent), and
   where it goes.  At least these:
   - `refined(k)` splits the wall cell, so with wall functions y⁺ falls
     as 1/k and the model changes with the level (0050 Q2, RESEARCH
     §7.2 correction).  Fix `first_cell` and refine the rest; show how.
   - OpenFOAM's `fixedValue` wall gradient is first order next to
     sloped or kinked walls at any refinement (0109, 0181, RESEARCH
     §7.14).  A convergence study there shows about order 1, and it
     isn't the mesh.
   - The wyes' split region isn't refined by `refined(k)` (`n_split`).
     Their order stays low in both codes (RESEARCH §7.14).
   - Steady RANS in the bend plateaus with a thick fixed wall cell
     (0050 Q3).  Add the outcome when Q3's test reports.
   - `potentialFoam` as the initial field can blow up in thin wall
     cells (0050).
   - A decomposed precursor can floor its residuals above
     `residualControl` (0050).
   - Anything 0186 and 0187 add.
   Only lessons with evidence.  "Expect" beats "always".
2. **GUIDE:** a section "From our validation: what to watch".
   - One short paragraph per lesson: the symptom a user would see, the
     cause, and what to do, linking the case's RESULTS.md.
   - Put it after *Resolution and cell count*, and link to it from that
     section and from *Running studies*.
3. **Docstrings** at the trap: `refined()` (the wall cell), and
   `PipeSpec.core`'s `first_cell` (what `refined` does to it).  Wording
   only.  No behaviour change (decision 0053's freeze).
4. **Agents:** a `lessons` list per case in `hexmesh/agent/validation.json`.
   - Each lesson has a short id, one sentence, and the link.
   - It comes from a `lessons` field in each `case.json`, added to the
     schema as optional.
   - The generator and its stale test pick it up.
5. **The advisor:** no change now.  When 0050 and 0186 report, write
   under *Questions for design* whether `advise` could accept wall
   functions with the wall cell fixed, with the evidence.
6. **Runtime warnings:** none.  If one seems worth it (e.g. `refined`
   on a spec with `first_cell`), propose it under *Questions for design*.
7. CHANGELOG *Unreleased* (Docs): one line.

**Accept.**
- The table, the GUIDE section, the docstrings, and `lessons` in the
  agent file: each with its evidence link.
- Docs tests and the stale-file tests pass.
- After 0050, 0186 and 0187: their lessons added.

**Out of scope.**  Changing `refined(k)` or the advisor (design
questions, as above).

## Agent notes

## Questions for design

## Outcome
