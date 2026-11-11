# 0150 — The API review, then the freeze (0.8)

- **Status:** held (after 0147, 0148, 0149 and 0151)
- **Decision:** [0042](../decisions/0042-road-to-1-0.md) exit criterion 5
  ("the stable surface reviewed once, then frozen"), milestone 0.8 (the
  release candidate).
- **Depends on:**
  - 0147 (per-arc counts: a schema field to review);
  - 0148 (`io.readers` deprecated, to remove here);
  - 0149 (wheels);
  - 0151 (the shape-site cap to 0;
    [decision 0051](../decisions/0051-design-9-remaining-rows.md)).
  After these, DESIGN §9 holds only the `io.readers` row, which this
  task removes.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  1.0 promises that nothing breaks until 2.0: no removal or
rename in the Python API, the saved-description format, the CLI's JSON,
the manifest's format or the error codes.  Anything to rename or remove
must happen once, here, before the freeze.

**Do.**
1. **The inventory**, generated, not hand-written: every public name
   (`__all__` of each public package), every argument and default, the
   description schema, the CLI commands and their JSON `result`s, the
   manifest's format, the error and warning codes.  It becomes a
   committed file, say `docs/api-1.0.json`, that a test compares with
   the code from then on: a change to the frozen surface fails CI unless
   the file is updated on purpose.
2. **The review**, as a table under *Agent notes*: per item, keep,
   rename (with the old name deprecated), make internal, or remove.
   Criteria: one name per concept (DESIGN §3.1); names a user would
   guess; no internal type in a public signature; units in metres and
   degrees everywhere (decision 0047).  The design session reviews the
   table before any change.
3. **Known items** (decision 0042's 2026-11-11 note):
   - `interchange/build.py` calls `Assembly._twist_for_toward`, a
     private method, across packages: make it public or route it
     through `add(toward=…)`;
   - `validation/tools/wye_redesign.py` patches
     `hexmesh.assembly._checks.min_scaled_jacobians`;
   - the network document (decision 0032 stage 2): in the surface, or
     explicitly internal;
   - `hexmesh.io.readers`: removed (0148 deprecated it), and its
     DESIGN §9 row with it;
   - **branch shells** (decision 0051, option B, still open): ask the
     user whether to plan them for 1.x; if yes, reserve the `Tee`
     argument name (`branch_shells=` or better).
4. **Apply the table:** renames with deprecated aliases; removals of
   things deprecated for at least one release; each with a CHANGELOG
   line.
5. **README *Stability*:** rewritten for 1.x (decision 0042,
   *Consequences*), effective at 1.0.

**Accept.**
- The inventory file and its test.
- The review table, approved by the design session.
- Applied changes with deprecations.
- Full suite and CI green.
- 0.8.0 released by `docs/RELEASING.md`.

**Out of scope.**  New features.  After the freeze, 0.8 → 1.0 is fixes
only (the soak).

## Agent notes

## Questions for design

## Outcome
