# 0148 — Deprecate `hexmesh.io.readers` (removed in 0.8)

- **Status:** ready
- **Decision:** [0042](../decisions/0042-road-to-1-0.md) exit criterion 1
  ("readers out of `io`: the deprecated `io.readers` path removed before
  1.0; removing it after would be breaking"), and promise 2 (deprecation
  before removal).  DESIGN §9 row "Readers sit in `io`".  Decision 0037
  item 4.
- **Depends on:** none.  Ship in 0.7, so the removal in 0.8 follows at
  least one release with the warning.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0066 moved the readers to `hexmesh.interchange.importers`.
`hexmesh.io.readers` still re-exports them, with **no warning**
(`hexmesh/io/readers/__init__.py`).  As things stand, it would be part
of the 1.0 surface.

**Do.**
1. **Importing `hexmesh.io.readers`** (the package or a name from it)
   emits a `DeprecationWarning`: "use `hexmesh.interchange.read_pcf` /
   `read_bathymetry`; `hexmesh.io.readers` is removed in 0.8".  Once per
   import.
2. **Nothing inside hexmesh imports it:**
   - the tests that do (`tests/test_agent_describe.py` …) move to the
     new path;
   - one test checks that the old path still works and warns;
   - `test_architecture`'s re-export check stays until the removal.
3. **Docs and examples:** no `io.readers` left in README, GUIDE, API,
   the examples or the agent manifest, except one API line ("deprecated,
   removed in 0.8").
4. **CHANGELOG:** a **Deprecated** entry with what to change.
5. **The removal** is the API review's (task 0150) or 0.8's: record it
   there.  The DESIGN §9 row goes when the path is gone.

**Accept.**
- The warning is tested.
- No internal use of the old path.
- Full suite: no new failures (`-W error::DeprecationWarning` finds no
  hexmesh-internal use).

**Out of scope.**  The removal itself (0.8).

## Agent notes

## Questions for design

## Outcome
