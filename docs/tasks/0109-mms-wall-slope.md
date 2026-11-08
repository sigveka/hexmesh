# 0109 — MMS: does the order track the wall slope?

- **Status:** ready (after 0108)
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md); follow-up of task 0074 (RESEARCH §7.14)
- **Depends on:** 0074, 0108.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  In 0074 the reducer, transition and tees converge at about
first order, and the least-squares gradient doesn't recover them.  What
they share is a wall-face non-orthogonality that refinement doesn't
shrink (reducer 21–24°, transition 12–14°, tee 9°), which OpenFOAM's
`fixedValue` snGrad doesn't correct.  Design has taken it as a scheme
property (RESEARCH §7.14), but not as verified to be the only cause.  If
it is, the order should rise as the wall slope falls.  If not, the
fittings' near-wall grid may need changing, which would be a decision.

**Where.**  `validation/mms/run.py` (a new series); `validation/mms/`
(`RESULTS.md`, `results.json`); RESEARCH numbers go in *Outcome* (design
moves them).

**Do.**
1. **A reducer slope series:** the cosine reducer at three or four
   constrictions, so the wall's maximum slope spans about 5° to the
   0074 case's (e.g. outlet radii 0.95, 0.9, 0.8 and 0074's R).  Same
   manufactured T, schemes and k levels (at least k 1, 2, 4) as 0074.
   Use `keep_orientation` as 0108 sets it.
2. **Measure** per constriction: the L2 order in the fitting (k 2→4,
   §7.12's rule), the median and maximum wall-face non-orthogonality,
   and the error's location (near the wall or in the interior).
3. **One control** that removes the boundary effect without changing the
   mesh: impose T through a boundary condition that corrects for
   non-orthogonality, if v2406 has one that fits (check
   `docs/integrations/openfoam.md` first; record what you find).  If
   none fits, say so and skip it.
4. **Plot** order against wall non-orthogonality (one PNG beside
   RESULTS.md).

**Accept.**
- The table and plot are in RESULTS.md; *Outcome* states plainly
  whether the order tracks the slope, and how closely.
- No gate: this is a measurement.  Its interpretation is for design.
- Meshes and case directories deleted after the run; results.json keeps
  the numbers.  Check `df -h .` before starting and note it here.

**Out of scope.**  Changing the reducer's or transition's grid.
