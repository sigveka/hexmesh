# 0107 — The light commands load neither gmsh nor scipy

- **Status:** ready (after 0106)
- **Decision:** [0040 — Agents for users](../decisions/0040-user-agents-network-design-and-resolution.md), amendment 2026-11-07 ("the light commands need no gmsh")
- **Depends on:** 0106 (its error codes and the architecture rule's
  form).  Third of the public-readiness tasks (0105, 0106, 0107, 0078).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `import hexmesh.agent` takes 0.52 s (`python3 -X importtime`,
2026-11-07, the coding session).  gmsh takes 0.13 s of that, and
`scipy.interpolate` 0.14 s (`scipy.optimize` 0.07 s within it), for one
`CubicSpline` in `assembly/blocks.py:497` (`_edge_points`).  Only `build`
and `Assembly.mesh()` use gmsh, yet eight modules import it at the top:
`session`, `_occ`, `assembly/assembler`, `blocks`, `corners`, `sweep`,
`sections/oh_gmsh`, `sections/_gmsh_helpers` (about 86 call sites).
Every validate, estimate or apply call in an agent's loop pays for it,
and those commands fail where gmsh can't load (decision 0039: Windows,
agents' sandboxes).

**Where.**  The eight modules; a new small gmsh loader module;
`assembly/blocks.py`; `hexmesh/errors.py`; `tests/test_architecture.py`;
`API.md`; `CHANGELOG.md`.

**Do.**
1. **scipy:** import inside `_edge_points`.  Check no other light-path
   module imports scipy at the top; move any that do.
2. **gmsh:** one small module whose `gmsh` loads the real module on first
   attribute access.  The eight modules import `gmsh` from it, and the
   `gmsh.model…` call sites stay unchanged.  `Session` loads it eagerly,
   so meshing behaves as today.
3. **`gmsh_unavailable`:** when loading fails, raise a coded error with
   the original import error (as `value` or in the message), a hint with
   the fix (`pip install gmsh`; on Linux the system libraries the CI
   workflow installs), and the commands that work without gmsh.
   Register the code; the CLI reports it in the usual envelope.
4. **The guard,** in `test_architecture`: in a fresh interpreter
   (subprocess), `import hexmesh.agent` and running `validate` and
   `estimate` on a small description leave `gmsh` and `scipy` out of
   `sys.modules`.  A planted top-level `import gmsh` in a light module
   makes it fail.
5. **Measure** `python3 -X importtime` again, and the CLI's time for
   `validate` and `estimate` before and after.

**Accept.**
- The guard passes and fails on the planted case.
- With gmsh made unimportable (e.g. a `sys.modules["gmsh"] = None`
  subprocess), schema, manifest, validate, estimate, describe, preview,
  advise and apply work, and `build` fails with `gmsh_unavailable` and its hint.
- The manifest's `needs_gmsh` agrees with the guard for every command
  (a test).
- Import and CLI timings, before and after, in *Outcome*.
- Full suite: no new failures; meshes byte-identical on the gallery
  examples (the loader changes nothing when gmsh loads).

**Out of scope.**  Deferring numpy (needed almost everywhere), and
hexmesh's own import time (about 0.1 s).
