# 0017 — Delete the legacy code

- **Status:** ready
- **Decision:** [0004 — Retire the legacy API](../decisions/0004-retire-legacy-api.md)
- **Depends on:** 0011, 0012, 0013, 0014, 0015, 0016

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Decision 0004: one API.  This is the last step of that decision.

**Do.**
1. Tag the commit before deletion `legacy-final`, and push the tag.
2. **Delete:**
   - `hexmesh/connectors/`, `hexmesh/network.py` and the legacy
     `hexmesh/model.py` (unless task 0016 rewrote it in place);
   - `core/cursor.py`, if nothing uses it any more;
   - face builders the assembly does not use (`faces/oh_rect.py`,
     `faces/square.py`, `faces/square_shell.py`), after checking with
     grep;
   - the legacy tests: `test_connectors.py`, `test_t_block.py`,
     `test_spline_pipe.py`, and the legacy parts of `test_quality.py`.
   Keep `quality_hex.py`, which task 0004 uses.
3. **`PipeSpec`.**  If `SquareShellSpec` and the square-core options can
   no longer be built, raise in `PipeSpec` (or keep the assembly's
   `check_supported` rejection).  Note in **Questions for design** whether
   they should be removed.
4. **`CLAUDE.md`.**
   - Remove the legacy sections: the staged `n_outer` plan, the
     Y-junction constraints, the Reducer constraints and the T-junction
     implementation.
   - Rewrite the `n_outer` topology and `refinement` text against
     `PipeSpec`/`Assembly`.  `refinement` doesn't exist in the assembly:
     add it to **Questions for design**, don't invent it.
5. **`DESIGN.md`.**  Don't edit it.  Put the exact §9 changes from
   decision 0004 under **Questions for design** for the design session.
6. **Tasks README.**  Drop the "legacy connectors" ground rule and the
   10 known Y failures from the gate.

**Accept.**
- `grep -rn "connectors\|network\b\|Network(" hexmesh tests` finds
  nothing outside history notes.
- The full suite passes with **no** failures (the known Y failures go
  with the legacy tests).
- All examples run (task 0016 test).

## Agent notes

## Questions for design

## Outcome

_Not done._
