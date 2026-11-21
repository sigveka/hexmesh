# 0188 — Hints from validation: what to watch, where users look

- **Status:** in progress (first pass done 2026-11-21; finished after
  0050, 0186 and 0187 report)
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

**First pass (2026-11-21, coding session).**  Only lessons with evidence
in a committed RESULTS.md, task file or RESEARCH.

| lesson | evidence | who meets it | where it went |
|---|---|---|---|
| `refined(k)` splits the wall cell: with wall functions y⁺ falls as 1/k and the model changes per level; fix `first_cell` and refine the rest | 0050: bend precursor y⁺ 23 / 11.6 / 7.8 at k 1-3, f vs McKeon +0.6 / +6.1 / +9.0 %; fixed at 1.95 mm: y⁺ 23.2 / 23.3, f +0.55 / +0.77 %. junction_loss: RESEARCH §7.2 correction, task 0186 | mesh user, OpenFOAM user, agent | GUIDE (with a level builder), `refined()` and `first_cell` docstrings, `lessons` in turbulent_bend and junction_loss |
| OpenFOAM's `fixedValue` wall gradient is first order next to sloped or kinked walls at any refinement | code_saturne MMS (0181): tee 1.96 / 1.97 vs OpenFOAM 1.28 / 1.03, reducer 1.72 / 1.85 vs 0.93 / 0.95; 1.85-2.0 on every non-wye fitting; RESEARCH §7.14 | OpenFOAM user, agent | GUIDE, `lessons` in mms |
| a wye's split region isn't refined (`n_split` capped at 6) | mms and code_saturne MMS: wye orders 0.27-0.51 at 2→4 in both codes; task 0056 | mesh user, agent | GUIDE (pointing at `refined`'s docstring, which already says it), `lessons` in mms |
| with Spalding and SST, a first-cell centre at y⁺ 8-12 reads f 6-9 % high; keep it at y⁺ ≳ 20 | 0050 precursors: y⁺ 7.8 / 11.6 / 12.0 / 23.2 → f +9.0 / +6.1 / +5.9 / +0.55 % (Q4; design session's wording) | mesh user, OpenFOAM user, agent | GUIDE, `lessons` in turbulent_bend |
| `potentialFoam` can blow up in thin wall cells | 0050: U up to 2.7e4 m/s on the fixed-wall k = 2 bend; simpleFoam floating-point exception at step 1, with and without -writep; from rest it runs | OpenFOAM user | GUIDE, `lessons` in turbulent_bend |
| a decomposed precursor floors Uy/Uz above `residualControl` | 0050: 2-5e-7 on 4 processes against 1e-7; one process converges in 3 245 steps | OpenFOAM user | GUIDE, `lessons` in turbulent_bend |
| steady RANS plateaus on the bend with a thick fixed wall cell | 0050 Q3: level 2 at y⁺ 50, K 0.227-0.271 by start; the y⁺ 25 test running | OpenFOAM user, agent | not yet: waits for Q3's test and, if needed, the transient run |

- `lessons` is an optional field in `case.json` (schema: id
  `^[a-z0-9_]+$`, text, a repo-relative link); `validation.tools.summary`
  copies it per case, `[]` where a case has none.  The stale test
  already covers it.
- Docstrings: wording only.
- No runtime warning proposed yet: `refined` on a spec with `first_cell`
  can't tell from the stored grading that the user wants wall functions;
  revisit with step 5.

## Questions for design

## Outcome
