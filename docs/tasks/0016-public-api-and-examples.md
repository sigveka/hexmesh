# 0016 — Public API, examples and docs on the assembly

- **Status:** ready
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

## Questions for design

## Outcome

_Not done._
