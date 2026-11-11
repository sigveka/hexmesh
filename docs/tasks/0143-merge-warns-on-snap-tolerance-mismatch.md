# 0143 — `merge` warns when the two models' snap tolerances differ

- **Status:** ready
- **Decision:** none new: a follow-up to task 0138's design (the
  design session's own rule; the user, 2026-11-11: "write the task").
  Decision 0018 (vascular networks) is the constraint it protects.
- **Depends on:** 0138 (done).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0138 gave each network model its own snap tolerance and
made `merge` keep the larger of the two, so a PCF file's weld gaps still
snap (`interchange/operations.py`, `merge`).  The design session wrote
that rule, and it has a hole: merge a small-bore model (1 mm vessels,
`snap_tolerance` 1e-5 m) with a PCF model (0.11″, 2.79 mm), and the
merged model applies 2.79 mm to the small model's ends too.  Distinct
ends closer than that are then joined **without an error**, which is
exactly what 0138 set out to prevent (GUIDE, "How ends are connected:
the snap tolerance", *Why it is per reader*).  Nobody merges such models
today; decision 0018 heads there.

**The rule** (keep it simple): `merge` still keeps the larger value, and
**warns whenever the two differ**, naming both values and sources and
how to choose one.  Equal tolerances (two PCF files read with the
default) give no warning.

**Where.**  `hexmesh/interchange/operations.py` (`merge`);
`hexmesh/errors.py` if warning codes are registered there; the error
and warning catalogue in `API.md` (and the manifest, if it lists warning
codes: `tests/test_agent_manifest.py`); the GUIDE section above;
`tests/test_snap_tolerance.py`; CHANGELOG.

**Do.**
1. **The warning:** a `HexmeshWarning` with a new code
   `snap_tolerance_mismatch`.  Message: both values in mm and their
   sources, which one is kept, and that ends of the model with the
   smaller one may now join.  `value`: the kept tolerance; `limit`: the
   other.  `hint`: set `model.snap_tolerance` on the result, or pass
   `tol=` to the build.
2. **The report:** `out.report["merge"]` records both tolerances, their
   sources, and the one kept.
3. **Docs:** the GUIDE's *Why it is per reader* paragraph: "Merging two
   models keeps the larger of the two, so a PCF file's weld gaps still
   snap" gains the warning and what to do.  `API.md`: `merge` and the
   catalogue entry.
4. **Tests:**
   - a 1e-5 m model merged with a default PCF-read model warns
     (`snap_tolerance_mismatch`), either way round, and keeps 0.11″;
   - two default models merge silently;
   - setting `snap_tolerance` on the result is then used by the build
     (the report's `tol_source`);
   - replay of the merge log warns again (or doesn't: say which, and
     why that is right).

**Accept.**
- The tests above pass; meshes unchanged (no example merges models);
  the reader, interchange, agent and doc tests pass.

**Out of scope.**  Choosing the tolerance automatically from the
geometry (smallest bore or pipe length); per-part tolerances.  Both
would be design questions.

## Agent notes

## Questions for design

## Outcome
