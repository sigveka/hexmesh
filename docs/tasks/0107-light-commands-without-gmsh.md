# 0107 — The light commands load neither gmsh nor scipy

- **Status:** done (2026-11-07)
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

## Agent notes

- **The loader** is `hexmesh/_gmsh.py`.  `gmsh` there is a slot-less
  proxy whose `__getattr__` returns the real module's attribute, so a
  test's `monkeypatch.setattr(gmsh.model.occ, …)` on the real module
  still reaches every call site.  `load()` imports the real module once.
  `Session.__enter__` calls it before `gmsh.initialize()`, so a missing
  gmsh fails there, not in the middle of a build.
- **A ninth eager use:** `sections/_gmsh_helpers.py` bound
  `geo = gmsh.model.occ` and `mesh = gmsh.model.mesh` at module level, and
  that read loads the module.  Its 15 uses now spell out
  `gmsh.model.occ.` / `gmsh.model.mesh.`.  The other local `import gmsh`
  lines (`quality_hex`, `study/stages`, `study/manifest`) were already
  inside functions.  `examples/_run.py` imports gmsh at the top, but no
  light command imports the examples.
- **scipy:** `blocks.py` was its only top-level importer;
  `CubicSpline` is now imported inside `_edge_points`, in the spline
  branch.
- **`_gmsh` is a shared leaf** in `tests/test_architecture.py` (`LEAVES`,
  `PRIVATE_OK`), next to `_occ`.
- **`load()` catches `ImportError` and `OSError`.**  The `OSError` case is
  for gmsh's own `ctypes` load of `libgmsh` failing on a missing system
  library.  I haven't reproduced that here: the tests block the import
  with `sys.modules["gmsh"] = None`, which raises `ImportError`.
- **The guard** (`tests/test_architecture.py`, end) runs every command in
  one fresh interpreter, in `COMMANDS` order, through `cli.main`.  It
  records the heavy top-level modules in `sys.modules` after each.
  - `test_the_light_commands_load_neither_gmsh_nor_scipy`: gmsh is
    importable; `build` is skipped.
  - `test_planted_top_level_gmsh_import`: `import gmsh` is executed in
    `hexmesh.agent._commands`' namespace, as a top-level import there
    would be.
  - `test_without_gmsh_only_build_fails_and_the_manifest_says_so`: gmsh is
    blocked; the outcome of each command must match its manifest
    `needs_gmsh`.

  The three run in about 4 s.

## Questions for design

_None._  One proposed wording, not blocking: DESIGN §3.1 names `_occ`,
`errors` and `version` as the shared leaves.  It could add "`_gmsh` (gmsh
loaded on first use, task 0107)".

## Outcome

- **Files:**
  - new: `hexmesh/_gmsh.py`;
  - `hexmesh/errors.py` (`GmshUnavailable`, `gmsh_unavailable`);
  - `session.py`, `_occ.py`;
  - `assembly/assembler.py`, `blocks.py` (also scipy), `corners.py`,
    `sweep.py`;
  - `sections/oh_gmsh.py`, `sections/_gmsh_helpers.py`;
  - `tests/test_architecture.py`, `API.md`, `CHANGELOG.md`.
- **Behaviour without gmsh** (`sys.modules["gmsh"] = None`): schema,
  manifest, validate, estimate, describe, preview, advise and apply give
  `ok: true`.  `build` gives exit 1 and `gmsh_unavailable`, with the hint
  "pip install gmsh; on Linux gmsh also needs libglu1-mesa, libxrender1,
  libxcursor1, libxft2 and libxinerama1 (as in
  .github/workflows/tests.yml)".
- **Import time** (`python3 -X importtime`, cumulative):
  `hexmesh.agent` 517 ms → 267 ms.  gmsh (121 ms) and `scipy.interpolate`
  (142 ms) are no longer loaded; numpy (159 ms) remains.
- **CLI wall time** (median of 7, on the 4-fitting network in the guard):

  | | before | after |
  |---|---|---|
  | `python3 -c "import hexmesh.agent"` | 0.600 s | 0.308 s |
  | `python3 -c "import hexmesh"` | 0.576 s | 0.295 s |
  | `hexmesh validate` | 0.638 s | 0.367 s |
  | `hexmesh estimate` | 0.612 s | 0.318 s |
  | `hexmesh describe` | 0.643 s | 0.358 s |
  | `hexmesh schema` | 0.605 s | 0.317 s |
  | `hexmesh manifest` | 0.599 s | 0.311 s |

- **Meshes:** all 28 gallery examples were written with HEAD (a
  worktree) and with this change: 28/28 byte-identical.
- **Build time:** the whole gallery took 121.6 s and 121.1 s before,
  121.1 s and 122.4 s after.  The proxy costs nothing measurable.
- **Tests:** full suite 3678 passed, 15 skipped, 0 failed (19 min 41 s; it took 30 min 13 s for 0106, but under different machine load, so not a measurement of this change).  3 more tests than the 0106 run (3672 passed + 3 failed): the guard tests.
