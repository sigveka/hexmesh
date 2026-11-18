# 0177 — gmsh started by the caller before hexmesh has loaded it counts as a session

- **Status:** ready
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

## Questions for design

## Outcome
