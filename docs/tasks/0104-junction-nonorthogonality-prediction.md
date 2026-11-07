# 0104 — Junctions predict non-orthogonality in `validate()`

- **Status:** ready (after 0060)
- **Decision:** [0031 — General branch junctions](../decisions/0031-general-branch-junctions.md), amendment 2026-11-07, item 5
- **Depends on:** 0060.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0060 measured 75–78° non-orthogonality in small-ratio
tees, 90° included, and nothing reports it before meshing.  `mesh()`
checks meshed non-orthogonality on the tiers `OUTLINE_NONORTH_WARN`
(70°) and `OUTLINE_NONORTH_MAX` (80°), and section outlines predict it
(`assembly/section_quality.py`).  Junctions predict only the scaled
Jacobian.  Task 0074 also met a duct tap the solver couldn't converge on,
at 64°, so the number matters to users before they wait for a mesh.

**Where.**  The junction fittings (`assembly/tee.py`, `duct_tap.py`,
the wye); `assembly/section_quality.py` or wherever the prediction is
shared; tests; `API.md`; `CHANGELOG.md`.

**Do.**
1. **Predict** the worst non-orthogonality of each junction's blocks
   from the same straight-edge block geometry that predicts the scaled
   Jacobian, without GMSH.  Reuse the outline prediction's definition
   (the angle between a face normal and the line joining the cell
   centres either side), so predicted and meshed values compare.
2. **Report** it in `validate()` on the existing tiers: a warning above
   `OUTLINE_NONORTH_WARN`, an error above `OUTLINE_NONORTH_MAX`.  The
   message names the fitting and the block (e.g. "the turn block at the
   acute crotch"), and the hint names what lowers it (a larger r/R, a
   larger angle).
   - If junction blocks need tiers of their own, propose them under
     *Questions for design*.  Don't add them.
3. **Measure the prediction against the mesh** on the conformance kit's
   junctions and on 0060's sweep (angle × r/R): predicted against meshed
   worst non-orthogonality.  Record the error.  If the prediction is
   optimistic anywhere, say where and by how much.
4. **Docs:** API.md and the GUIDE's quality section; CHANGELOG (new
   warnings can appear on existing networks: list which examples warn).

**Accept.**
- The examples: list every one whose `validate()` result changes.  An
  example that newly *errors* is a question for design before merging.
- The prediction against meshed table is in *Outcome*.
- Full suite: no new failures, apart from expected new warnings, listed.

**Out of scope.**  Changing junction layouts to lower the angle; that
follows from the measurements, by decision.
