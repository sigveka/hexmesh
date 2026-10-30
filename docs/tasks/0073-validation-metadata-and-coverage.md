# 0073 — Validation metadata (`case.json`), categories and a coverage matrix in the gallery

- **Status:** ready
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md) (amendment 2026-10-30: categories)
- **Depends on:** the gallery's validation section (`docs/gallery/build.py`).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Validation cases are listed flat today.  The user asked how
they're categorised; decision 0012 now defines a primary category (V1
exact, V2 high-fidelity simulation, V3 experiment, V4 correlation) and
tags (regime, physics, hexmesh features, toolchain).  A coverage matrix
shows what is validated and what isn't.

**Where.**  `validation/<case>/case.json` (new, every case),
`docs/gallery/build.py` (validation section), a schema
(`validation/case.schema.json`), `docs/tasks/README.md` (ground rule).

**Do.**
1. **Schema** (`validation/case.schema.json`), with `schemaVersion`:
   - `category`: V1–V4;
   - `references`: a list of {citation key, data source, role:
     primary or secondary};
   - `tags`: regime, physics, features from the fixed list in decision
     0012, toolchain;
   - `status`;
   - `gates`: a short list of quantity and limit;
   - `task`.
2. **Backfill** `case.json` for every existing case (poiseuille,
   heated_rod, layered_conduction, heated_pipe, stenosis), from their
   READMEs and RESULTS.  `status` comes from RESULTS' status line.
3. **Gallery:** the validation section groups cases by category (V1 →
   V4), each with its status, tags and links.  Add a **coverage matrix**:
   the hexmesh features down, the cases across, a mark where a case
   exercises a feature, coloured or annotated by status.  Planned cases
   (from `docs/tasks/*validation*`) appear as planned columns if they
   carry a category in their task file (add one line to each validation
   task: `- **Category:** Vn`).
4. **Ground rule** (tasks README): every new validation case ships a
   `case.json`; the gallery fails loudly on a missing or invalid one.

**Accept.**
- Every existing case has a valid `case.json`.
- The gallery page shows the four categories and the matrix.  The
  matrix's empty rows (e.g. `wye`, `duct-tap`) are visible, which is
  the point.
- Full suite unchanged (the gallery isn't part of it); the schema
  validation has a small test.

**Out of scope.**  Running any case; changing gates.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
