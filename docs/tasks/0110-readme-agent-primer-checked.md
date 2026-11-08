# 0110 — The README's agent primer: its numbers checked

- **Status:** ready
- **Decision:** [0040 — Agents for users](../decisions/0040-user-agents-network-design-and-resolution.md); follow-up of task 0078
- **Depends on:** 0078, 0107 (done).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The README's "With an agent" section (design, `6712f95`) quotes
numbers from real runs on 0.4.0: the hero network (`insulated_network`)
at 18 012 cells, and `advise` for water at 0.01 m/s, `fine`, budget
200 000, giving 641 680 → 536 432 (axial aspect 6 → 12) → 72 048 cells
at `medium`, `nang` 12, `nrad` 6.  They are written by hand, so nothing
catches them going stale.  Since 0107 the light commands need no gmsh
and run in about 0.3 s, so a test can recompute them cheaply.

(0078's *Outcome* said the section was empty.  It isn't; it was committed
in `6712f95`.)

**Where.**  `tests/test_readme.py`; `README.md` only if a number is
wrong.

**Do.**
1. **A test** that builds `hexmesh.examples.sections.insulated_network`,
   runs `estimate`, and runs `advise` with the primer's inputs, through
   the CLI functions (no GMSH), and checks every number the section
   quotes: the cell counts, the budget steps, the density and the
   accuracy it fell back to.
2. **The numbers in the README** are matched by text (a regex per
   number, or a small marked block), not regenerated: the section is
   prose.  On a mismatch the test names the number and the value it
   now gets.
3. Check the plain-English description in the primer still matches the
   example (bore, layer thicknesses, lengths, angle).  Report any
   difference under *Questions for design* rather than editing the prose.

**Accept.**
- The test passes, and a planted wrong number fails it with a message
  that names it.
- It runs in under 5 s and without gmsh.
- Full suite: no new failures.
