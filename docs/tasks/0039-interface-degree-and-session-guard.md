# 0039 — Two validation bugs: overlapping fittings on one interface, GMSH calls outside a session

- **Status:** done
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

- **Degree check.**  `Assembly._check_degree(iface, role, fitting)` runs
  in `add()` (the source as inlet, before any interface is created, so a
  rejected `add` records nothing), `close()` (source as inlet, target as
  outlet) and `prepend()` (the old inlet as outlet).  In `close()` and
  `prepend()` the existing open-end checks already exclude the fault, so
  there the call is a safeguard only.  `validate()` checks every
  interface for more than one fitting per role.
- **Loaded JSON.**  `Assembly.from_dict` replays `add()`, so a saved
  description with the fault fails **at load**, at the offending `add`,
  rather than at `validate()`.  The `validate()` check is tested on an
  edge inserted without `add()`.  No test or example relied on the old
  behaviour.
- **Session guard.**  One module helper, `_require_session()`
  (`gmsh.isInitialized()`), called first in `build`, `build_faces`,
  `fill`, `write_openfoam` and `check_quality`.  The others (`mesh`,
  `write`, `write_physical_groups`, `volumes`, `fitting_volumes`) reach
  it through `build()` before any GMSH call.
- **Mesh first.**  `mesh()` sets `_meshed`; `check_quality()` raises "no
  mesh yet; call mesh() or write() first" without it.  Nothing outside
  the assembler calls `gmsh.model.mesh.generate`, so the flag is
  reliable.  `group_roles()` keeps its existing message.

## Questions for design

_None._

## Outcome

- **Done** 2026-10-27.
- **Files:**
  - `hexmesh/assembly/assembler.py`: `_require_session`,
    `Assembly._attached`, `Assembly._check_degree`, the degree loop in
    `validate()`, the `_meshed` flag;
  - `tests/test_assembly_guards.py` (new, 17 tests): degree at `add`
    (inlet and outlet; nothing recorded on rejection), loaded JSON,
    `validate()` on a hand-built overlap, `prepend` unaffected; ten
    GMSH-side methods outside a session raise with empty stderr and
    stdout (`capfd`); `check_quality` / `group_roles` before `mesh()`.
- **Accept:**
  - the snippet raises at the second `add`: "Interface(inlet, …)
    (interface #0) is already the inlet of fitting #0 Straight(…); it
    cannot also be the inlet of Straight(…)";
  - `write()` outside a session raises "needs a GMSH session: use
    `with Session(...):`", with nothing on stderr;
  - examples and conformance kit unchanged (in the suite).
- **Tests:** full suite 1272 passed, 5 skipped, 0 failed (1255 before,
  +17).  `-m openfoam` output tests (`test_openfoam_output.py`,
  `test_openfoam_boundary.py`, `test_wye.py`): 6 passed.
- **Surprises:** none.
- **Follow-ups:** none proposed.
