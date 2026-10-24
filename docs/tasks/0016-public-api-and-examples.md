# 0016 — Public API, examples and docs on the assembly

- **Status:** done
- **Decision:** [0004 — Retire the legacy API](../decisions/0004-retire-legacy-api.md)
- **Depends on:** 0012, 0013, 0014, 0015

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `hexmesh/__init__.py`, `README.md`, `API.md` and
`hexmesh/examples/` document only the legacy `Network` API.  The
assembly has no runnable example.

**Do.**
1. **Package root.**
   - `hexmesh/__init__.py` exports the assembly API: `Assembly`,
     `AssemblyError`, the fittings, `PipeSpec`, `CircleShape` and
     `QualityReport`.
   - Its quick-start docstring uses that API.
   - Version 0.3.0, in both `__init__.py` and `pyproject.toml`.
2. **Session helper.**  Keep a small `Model`-style context manager:
   initialize, add the model, `show()`, finalize.  It must not call
   `removeDuplicateNodes()`.  Put it in `hexmesh/session.py` or a
   rewritten `hexmesh/model.py`.
3. **Examples**, rewritten on the assembly; each writes its `.msh` to
   the current directory:
   - `smooth_bend`;
   - `miter_bend`;
   - `insulated_pipe` (multi-layer);
   - `reducer_network`;
   - `tee` (straight, then tee, then a bend on the main run);
   - `loop` (`Closure`);
   - `spline_pipe`;
   - `pipe_network` (several branches, using the graph).

   Delete the examples whose feature is gone: `y_junction`,
   `stub_block_demo`, `wall_zones`, `t_junction` (replaced by `tee`) and
   `unit_cube`, if it isn't a pipe example.
4. **Docs.**  Rewrite `README.md` and `API.md` for the assembly API.  Keep
   the "refinement ×2 ⇒ 8× cells" note, and show `cell_count()`.
5. Every example is run by a test, in a temporary directory, that checks
   predicted cells == meshed cells and `check_quality().ok`.

**Accept.**
- `python3 -m hexmesh.examples.<name>` works for every example and
  writes a `.msh` file.
- The examples smoke test passes.
- README and API.md contain no `Network`, `connectors` or `Model(`
  legacy usage.

## Agent notes

- **Package root.** `Model`, `Network` and `Node` stay reachable through a
  lazy module `__getattr__` until 0017, so legacy tests keep working.
  Importing `hexmesh` no longer loads `network.py` or `connectors/`.
- **Session.** It lives in `hexmesh/session.py`, with the class named
  `Session` so it doesn't clash with the legacy `Model` before 0017
  deletes it. It only initializes, adds the model, offers `show()`, and
  finalizes. It sets no mesh options and merges no nodes; meshing belongs
  to `Assembly.mesh()`.
- **Examples.**
  - The shared runner `examples/_run.py` validates, counts, writes, and
    prints the cell count, min SICN and physical groups. Each example
    exposes `build()` and `main(output)`, which the smoke test calls.
  - Also deleted: `simple_network.py`, which the task's list missed. It
    was a legacy `Network` duplicate of `smooth_bend`.
  - `unit_cube` was not a pipe example (a `SquareShape` duct), so it is
    deleted as the task allows. Rectangular sections return with
    decision 0009.
- **Loop example.** A loop whose closure gap is too short fails
  validation: the Hermite curve bends tighter than the pipe. The example
  uses 0.6 m runs with a 20° roll on the middle bend, which is non-planar
  and still valid. Validation caught my first attempt before GMSH, which
  is the behaviour the design asks for.
- **Accept check.** `grep -n "Network\|connectors\|Model(" README.md
  API.md` matches only `NetworkSpec`, the PCF reader's result class,
  which is current API.

## Questions for design

## Outcome

- **Files:**
  - new `hexmesh/session.py`, `hexmesh/examples/__init__.py`,
    `hexmesh/examples/_run.py`, `hexmesh/examples/tee.py`,
    `hexmesh/examples/loop.py`, `tests/test_examples.py`;
  - rewritten `hexmesh/__init__.py`, `README.md`, `API.md` and the
    examples `smooth_bend`, `miter_bend`, `insulated_pipe`,
    `reducer_network`, `spline_pipe`, `pipe_network`;
  - deleted the examples `y_junction`, `stub_block_demo`, `wall_zones`,
    `t_junction`, `unit_cube`, `simple_network`;
  - `pyproject.toml` and `__version__` set to 0.3.0.
- **Examples** (predicted cells = meshed cells in every one):

  | Example | Cells | min SICN |
  |---|---|---|
  | smooth_bend | 6528 | 0.239 |
  | miter_bend | 9792 | 0.110 |
  | insulated_pipe | 10800 | 0.144 |
  | reducer_network | 11832 | 0.221 |
  | tee | 7464 | 0.189 |
  | loop | 14688 | 0.140 |
  | spline_pipe | 9360 | 0.146 |
  | pipe_network | 13992 | 0.189 |

- **Docs.** The README quick-start and network snippets were run as
  written; they produce 6528 cells and the patch names the group table
  lists.
- **Tests:** 539 passed, 10 failed (the known `TestYJunctionQuality`
  failures), 4 xfailed.
