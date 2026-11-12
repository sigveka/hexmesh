# 0143 — `merge` warns when the two models' snap tolerances differ

- **Status:** done
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

- **Which model may now join:** the message names the source of the
  model with the smaller tolerance ("ends of the vessels model closer
  than that, which stayed apart at 0.01 mm, may now be joined").  It
  points at the caller of `NetworkModel.merge` (`stacklevel` 4).
- **Replay warns again (step 4), and that is right.**  The log's merge
  entry is replayed through the same `merge`, which keeps the larger
  tolerance again.  A value set on the result by hand
  (`m.snap_tolerance = …`) is an attribute, not a logged operation, so
  `replay` doesn't restore it; the repeated warning is what tells the
  user to set it again.  (Logging a "set the tolerance" operation would
  make replay keep it; not asked for, so not done.)
- `test_merge_takes_the_larger` (task 0138) merged different
  tolerances; it now asserts the warning.
- `API.md`'s catalogue: `size_not_positive` gains `ReaderError` (raised
  by `read_pcf`'s check since task 0138; missed then).

## Questions for design

## Outcome

Done 2026-11-12.

- `hexmesh/interchange/operations.py`: `merge` calls `_snap_mismatch`,
  which records `report["merge"]["snap_tolerance"]` (`a`, `b`, `kept`:
  value and source each) and, if the two differ, warns
  `snap_tolerance_mismatch` (`value` the kept, `limit` the other,
  `where` `{"field": "snap_tolerance"}`, `hint`: set
  `model.snap_tolerance` or pass `tol=`).  `hexmesh/errors.py`: the code.
- Docs: GUIDE *Why it is per reader*; API.md (`merge`, the catalogue);
  CHANGELOG.
- Tests (`tests/test_snap_tolerance.py`, now 18): a 1e-5 m model and a
  PCF model, either way round, warn and keep 0.11", the report has
  both; two default PCF models merge silently (warnings as errors); a
  tolerance set on the result is what the build uses ("relative" or
  "reader vessels"); replay warns again.  Reader, interchange, agent,
  doc and architecture tests: 340 passed, 1 skipped.
- Meshes unchanged: no example, gallery entry or validation case
  merges models.

