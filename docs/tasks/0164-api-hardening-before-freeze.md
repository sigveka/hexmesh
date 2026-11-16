# 0164 — Keyword-only arguments, copy-on-write specs, named outlets

- **Status:** ready
- **Decision:** [0053](../decisions/0053-api-hardening-before-freeze.md)
- **Depends on:** 0150 (the inventory and its test), 0163.
- **Blocks:** the 0.8.0 tag (task 0150's release prep is redone after
  this).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Three things about how the public API is called become
permanent at 1.0 and are cheap to change now (decision 0053's context).
No users yet: break directly, with CHANGELOG *Breaking* lines; no
deprecation shims.

**Do.**
1. **Measure first:** count the call sites that break under each point
   (positional calls past the new limit, in `hexmesh/`, `tests/`,
   `docs/`, `validation/`, the examples and README/API/GUIDE code
   blocks; `PipeSpec` uses that rely on mutation; unpacking of `add`).
   Record the counts in *Agent notes*.
2. **Copy-on-write `PipeSpec`** (decision rule 2): failing test first
   (the snippet in the decision), then `core()`, `shell()` and any other
   public mutating method return a new spec.  Fix the call sites that
   relied on mutation (`spec.shell(...)` without keeping the result).
3. **Keyword-only arguments** (rule 1): apply the defaults; list every
   exception you make in a table (callable, positional arguments kept,
   why).  Add an architecture test over `docs/api-1.0.json`: no public
   callable has more than two positional arguments besides `self`, apart
   from the table's exceptions, named in the test.
4. **Named outlets** (rule 3): a named tuple type per multi-outlet
   fitting, exported with it (or one generic type with fitting-specific
   field names: your choice, say which).  Tests: unpacking works as
   before; the fields name the right ports; `describe` and the agent's
   output are unchanged.
5. **README *Stability*:** rule 4's paragraph on limits.
6. **Rewrite the docs and examples** to keyword calls; examples stay
   byte-identical (the meshes, not the files' text).
7. **Regenerate** `docs/api-1.0.json`, the CHANGELOG (the 0.8.0 entry's
   *Breaking* section), then redo 0150's release prep on top.

**Accept.**
- The new architecture test and the tests of steps 2 and 4 pass.
- The exception table, under *Agent notes*.
- All examples byte-identical; full suite green; CI green on `next`.
- The 0.8.0 tag still waits for the user's OK (RELEASING.md).

**Out of scope.**  Renaming the jargon arguments (`mbmp`, `mprg`, `lc`,
`nang`, `nrad`); the deferred 1.x items in the decision's
*Consequences*.

## Agent notes

## Questions for design

## Outcome
