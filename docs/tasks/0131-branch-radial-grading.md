# 0131 — A tee branch with its own radial grading (and the Reducer pattern documented)

- **Status:** ready
- **Decision:** [0028 — Multi-layer junctions](../decisions/0028-multi-layer-junctions.md) (amendment 2026-11-10); [0016](../decisions/0016-class-1-granularity-and-grading-changes.md) (grading-only changes in sweeps)
- **Depends on:** none (task 0027, done, gives the per-station grading).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  A tee's branch copies the main's `nrad` and `mprg`
(`hexmesh/assembly/tee.py`, `branch_spec`), so its wall cell scales with
r/R.  A `first_cell` (y+) target set on the main is missed on every
branch: at r/R 0.5 the branch's wall cell is about half the main's.
Decision 0028's amendment: the branch port may carry its own core grading.

**Where.**  `hexmesh/assembly/tee.py`, the sweep machinery task 0027
used (`fittings._with_radii`, `_mprgs`), `API.md`, `docs/GUIDE.md`,
`CHANGELOG.md`, the agent schema (a new field), `tests/`.

**Do.**
1. **Document today's pattern (any time, first).**
   - GUIDE: "a branch with its own wall cell": a grading-only `Reducer`
     straight after the branch (same radius, the branch spec with its own
     `first_cell`), with a short example.  Check it builds; if a
     same-radius `Reducer` is rejected, say so under *Agent notes* and
     document the smallest working form instead.
   - GUIDE's fittings table says `Reducer`: "Only radii may change".
     Task 0027 made grading-only changes legal: correct the line.
2. **The field.**  `Tee(…, branch_first_cell=None, branch_mprg=None)`
   (names may be refined; at most one of the two): the branch port's core
   grading.  Interpolated per station along the branch run, from the
   main's grading at the turning station to the given one at the port,
   as `Reducer` interpolates (task 0027).  Counts and shells unchanged.
   - Circular branches on O-H mains first.  Duct taps and H mains: reject
     with a coded error unless it falls out for free; say which under
     *Agent notes*.
   - `refined(k)`: as for a spec's `first_cell` (API.md): the resolved
     `mprg` nests.
   - The branch port's spec (`asm[...]`, `ports`) carries the new grading,
     so the next fitting matches it.
3. **Measure:** min SJ and non-orthogonality of the tee, against today's,
   for r/R 0.3, 0.5, 0.8 and a branch `first_cell` of 0.5×, 1× and 2× the
   main's wall cell, at `n_branch` 3 and 6.  If the branch run's
   interpolation worsens the tee beyond decision 0016's 10 % target,
   report the case and the `n_branch` that recovers it; propose a hint
   (e.g. a minimum `n_branch`) under *Questions for design*, don't set a
   limit.
4. **Tests:** the branch port's wall cell equals `branch_first_cell` (to
   1e-9 relative); omitting the field gives today's mesh byte-identically;
   a following `Straight` with the branch spec connects; the field
   round-trips through `to_dict`/`from_dict` and the JSON schema.

**Accept.**
- Steps 1–4; meshes without the field byte-identical; full suite: no new
  failures.

**Out of scope.**  Different `nrad`/`nang` in a branch (decision 0003);
the wye; shell grading.

## Agent notes

## Questions for design

## Outcome
