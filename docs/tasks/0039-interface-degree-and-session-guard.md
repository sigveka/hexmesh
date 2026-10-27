# 0039 — Two validation bugs: overlapping fittings on one interface, GMSH calls outside a session

- **Status:** ready
- **Decision:** [0024 — API ergonomics](../decisions/0024-api-ergonomics.md) (items 1 and 2: bugs found in the review)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**
1. `validate()` accepts a second fitting on an interface that already
   has one on the same side, so two pipes overlap:
   ```python
   a = Assembly(pipe); a.add(Straight(0.2, 2))
   a.add(a.inlet, Straight(0.2, 2)); a.validate()   # passes
   ```
2. Calling `write()` or `check_quality()` outside a `Session` floods
   stderr with ~70 lines of "Gmsh has not been initialized" and fails
   with `RuntimeError: curve 1 has 0 end points`.

**Where.**  `hexmesh/assembly/assembler.py` (`add`, `close`, `prepend`,
`validate`, the GMSH-side methods), `hexmesh/session.py`, tests.

**Do.**
1. **Interface degree.**  An interface is the outlet of at most one
   fitting and the inlet of at most one (so at most two fittings).
   Reject the violation **in `add()` / `close()` / `prepend()`**, when it
   happens, with `AssemblyError` naming the interface (index and name),
   the fitting already attached and the new one; `validate()` checks it
   too (for assemblies loaded from JSON).  Check whether any test or
   example relied on it (there should be none).
2. **Session guard.**  Every method that needs GMSH (`build`,
   `build_faces`, `fill`, `mesh`, `write`, `write_openfoam`,
   `check_quality`, `fitting_volumes`, …) first checks
   `gmsh.isInitialized()` and raises `AssemblyError`: "needs a GMSH
   session: use `with Session(...):`" before any GMSH call.  One helper,
   not repeated checks.
3. `check_quality()` and `group_roles()` before `mesh()` inside a
   session: a clear error ("call mesh() or write() first"), as
   `group_roles` already does.

**Accept.**
- The snippet above raises at the second `add`, naming the inlet and
  both fittings; a loaded JSON with the same fault fails `validate()`.
- `write()` outside a session raises the session error with **no GMSH
  output on stderr** (capture it in the test).
- Every example and kit case unchanged.  Full suite: no new failures.

**Out of scope.**  Starting a session implicitly.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
