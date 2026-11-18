# 0177 — gmsh started by the caller before hexmesh has loaded it counts as a session

- **Status:** in progress
- **Decision:** none.  A bug fix in task 0167's session rules
  (`_require_session`: "a Session, gmsh the caller initialized, or a
  to_mesh() call running").
- **Depends on:** none.
- **Blocks:** the 0.8.0 tag.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Found by the design session on 2026-11-18, and confirmed by the
coding session.  In a fresh process:

```python
import gmsh, hexmesh._gmsh as g
gmsh.initialize()
print(g.caller_drives())    # False; True after g.load()
```

`caller_drives()` checks `_module is not None and _module.isInitialized()`,
and `_module` is set only by `_gmsh.load()`.  So a caller who starts
gmsh before hexmesh has loaded it gets `AssemblyError`
`no_gmsh_session` from `assembly.mesh()`.  That is a documented way to
mesh.  `tests/test_build_sync.py` run alone fails 178 tests this way, at
`aa04883` and every commit since.  CI passes only because earlier tests
in each worker call `load()`.

**Do.**
1. **The fix:** where `hexmesh/_gmsh.py` tests `_module` (`caller_drives`,
   `models`, `started`, and any other), use the gmsh the process has
   imported when `_module` is `None`: `sys.modules.get("gmsh")`.  A caller
   who imported gmsh is seen.  A process that never imported it still
   doesn't pay for the import, so `load()` stays lazy, and the commands
   without gmsh (task 0107) stay without it.  Look for the same pattern
   elsewhere (`grep -n "_module" hexmesh/`) and say what else changed.
2. **Tests:**
   - the repro above as a `subprocess` test with `sys.executable` and an
     absolute path, so test order can't hide it.  It checks
     `caller_drives()` and an actual `assembly.mesh()` of a small
     straight pipe after a bare `gmsh.initialize()`;
   - the same in a process that never imported gmsh:
     `caller_drives()` is `False`, and `gmsh` is not in `sys.modules`
     afterwards;
   - `tests/test_build_sync.py` run alone passes.
3. **Other order-dependent tests:** run each test module alone once
   (a loop over `tests/test_*.py`, `-p no:cacheprovider`, in parallel
   as the machine allows).  List the modules that fail alone but pass
   in the full suite, under *Agent notes*.  Fix those with this cause
   here.  Others get a line each as follow-ups, not fixes here.
4. CHANGELOG, in the 0.8.0 section (not yet tagged): *Fixed*, one line.

**Accept.**
- The subprocess tests pass on all CI jobs.
- `test_build_sync.py` alone passes.
- Step 3's list is recorded, even if empty.
- The full suite passes.

**Out of scope.**  Changes to the session rules themselves (tasks 0039
and 0167).  A CI job that runs
modules alone: propose one under *Agent notes* if step 3 finds more
than this case.

## Agent notes

- **Step 1** (2026-11-18): `_gmsh._imported()` returns `_module`, or,
  when it is `None` and `sys.modules` has `gmsh`, calls `load()` (the
  import is already done, so it costs nothing).  `caller_drives()` and
  `models()` use it.  The other `_module` uses (`_finish`, `model`,
  `release`, `remove_model`) run only after hexmesh has loaded gmsh
  itself, so they are unchanged.  `grep -n "_module" hexmesh/` finds
  nothing outside `_gmsh.py`.  The repro prints `True` with the fix.
- **Step 2:** two `subprocess` tests in `tests/test_to_mesh.py`, each a
  fresh `sys.executable` with the repository root on `sys.path`: a bare
  `gmsh.initialize()` then `assembly.mesh()` (the hex count equals
  `cell_count()`), and a process that never imported gmsh (`caller_drives()`
  False, `models()` empty, `gmsh` not in `sys.modules`).  Both pass.
  `tests/test_build_sync.py` alone: 180 passed (378 s, `-n 1`); 178
  failed before the fix.
- **Step 3, in progress** at this commit: each module alone, `-n 1`,
  one after another (beside an OpenFOAM run).  26 of 86 modules done, none
  failing.  The list follows in a later commit.  The slowest alone so
  far: `test_build_sync` 361 s, `test_agent_describe` 129 s,
  `test_assembly` 124 s, `test_agent_advise` 51 s.
- Committed before step 3 ends so that the fix goes into the 0.8.0
  push; the status stays in progress until the list is recorded.

## Questions for design

## Outcome
