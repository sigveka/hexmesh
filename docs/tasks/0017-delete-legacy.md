# 0017 — Delete the legacy code

- **Status:** done
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
   - `faces/square.py` (single-patch square, incompatible with the OH
     layout), after checking with grep.  **Keep** `faces/oh_rect.py`,
     `faces/square_shell.py`, `RectShape` and `SquareShellSpec`: decision
     0009 needs them (amended 2026-10-24 by the design session);
   - the legacy tests: `test_connectors.py`, `test_t_block.py`,
     `test_spline_pipe.py`, and the legacy parts of `test_quality.py`.
   Keep `quality_hex.py`, which task 0004 uses.
3. **`PipeSpec`.**  Keep `SquareShellSpec` and the rectangular-core
   options (decision 0009).  Until 0009's tasks land, the assembly's
   `check_supported` rejection stays; don't remove them.
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

- **Tag.** `legacy-final` is `0280677` (task 0016), pushed to origin.
- **Also deleted, beyond the list** (each only served deleted code):
  - `core.shape.SquareShape`: the shape built by `faces/square.py`.
    `spec.py` mentioned it only in guards rejecting it as a shell base.
  - `core.region.RegionSet` and `io/writers/physical_groups.py`, with
    their exports (found in 0015).  `MaterialGraph` stays in
    `core/region.py`.
  - `tests/test_assembly_standalone.py`: it blocked the legacy modules to
    prove the assembly didn't import them, which can't happen now.
  - Every class in `tests/test_quality.py` used `Network`, so the whole
    file went, not just "the legacy parts".  The assembly has its own
    quality tests: `test_assembly.py::TestQuality`, the conformance kit,
    and the per-fitting tests.
- **Ported, not deleted.**
  - `tests/test_faces.py` tests the face builders, which stay.  It built
    its in-plane axes from `Cursor`; it now uses `Frame.from_vectors`,
    which has the same right/up convention (`right = normal × up`).
  - `tests/test_shapes.py` lost only its `Cursor` classes.
- **Comments.** Comments in `core/cross_section.py`,
  `faces/oh_circle.py` and `faces/annulus.py` that named connectors or
  legacy code were reworded.  The `CrossSection` fields they describe are
  all still used by `assembly/corners.py` and the fills.
- **Accept grep.** `grep -rn "connectors\|network\b\|Network(" hexmesh
  tests` matches only:
  - the plain word "network" in docstrings and example names
    (`pipe_network`), and `NetworkSpec` (PCF reader, current API);
  - one history note in `tests/test_spline.py` ("ports … the legacy
    `tests/test_spline_pipe.py`").
- **CLAUDE.md.**
  - The `n_outer` text is rewritten against `PipeSpec` / `Assembly`.
    It states that the assembly accepts only `n_outer = 4` and points to
    decision 0005.
  - The `refinement` text now states that the assembly has no such
    multiplier, keeps the 8× note, and points to `cell_count()`.
  - The design session's uncommitted "Both sessions" paragraph was left
    unstaged; the commit carries only this task's hunk.
- **Integrations.** Following the new "both sessions" rule, the four OCC
  quirks from task 0012 are recorded in `docs/integrations/gmsh.md`:
  - non-uniform `affineTransform` renumbering;
  - `addEllipseArc` rejecting symmetric arcs;
  - `getBoundingBox` padding;
  - plate filling between near-identical arcs.

  The note there on the 10 Y failures, and the one on legacy
  connectors, are updated.  The directory is the design session's and
  untracked, so I left it uncommitted.

## Questions for design

1. **DESIGN §9, per decision 0004** (for the design session to apply):
   - Delete these rows, whose code no longer exists:
     - "Fittings create their own outlet faces (producer-owns)";
     - "Relative (cursor-chained) placement; no graph";
     - "OCC `extrude` / `revolve` used for fills";
     - "`occ.fragment()` + bbox surface recovery";
     - "`removeDuplicateNodes()`";
     - "Geometry built inside `connect()`; no pre-GMSH validation";
     - "Topology detected from surface count";
     - "Corner correspondence … nearest-distance search" (it goes
       whole, with its "legacy connectors only" qualifier).
   - **Row "`nang` checked per connector, not resolved across the
     network" (A5, `fittings.py`, `spec.py`)** needs a decision, not just
     deletion.  Its `fittings.py` is the deleted legacy file, but
     `spec.py` stays.  In the assembly, `nang` can't change anywhere:
     every interface must match its neighbour's spec, and `Reducer`
     forbids density changes.  So it is uniform per connected network,
     but by restriction rather than resolution.  Does that satisfy A5,
     and can the row go?
   - Keep the `n_outer = 8` row and the two Tee rows.
2. **`refinement`.** CLAUDE.md used to describe
   `Network(spec, refinement=k)`, a global density multiplier.  The
   assembly has none; density is explicit per `PipeSpec` and per
   fitting.  Should the assembly get one, for example
   `Assembly.mesh(refinement=k)` scaling `nang`, `nrad` and `n_layers`
   at realisation time?  `cell_count()` would then take it too.  I have
   not invented it.
3. **Proposed new §9 row** (open since 0012): a multi-layer `Straight`
   fills its interior material-interface walls with OCC surfaces, so
   those wall nodes lie up to 0.69 % of R off the cylinder (§6
   exactness).  Bends, miters, reducers and splines don't have this
   problem.  Should it be recorded as a deviation, or should a task fix
   it (per-layer stations, as the sweeps do)?

## Outcome

- **Deleted:**
  - `hexmesh/connectors/` (9 files), `network.py`, `model.py`,
    `core/cursor.py`, `faces/square.py`,
    `io/writers/physical_groups.py`;
  - `SquareShape` and `RegionSet`;
  - the tests `test_connectors.py`, `test_t_block.py`,
    `test_spline_pipe.py`, `test_quality.py` and
    `test_assembly_standalone.py`.
- **Edited:**
  - `hexmesh/__init__.py` (lazy legacy exports removed);
  - `core/__init__.py`, `faces/__init__.py`, `io/__init__.py`,
    `io/writers/__init__.py`;
  - `core/shape.py`, `core/spec.py`, `core/region.py`;
  - comments in `core/cross_section.py`, `faces/oh_circle.py`,
    `faces/annulus.py`;
  - tests `test_faces.py` (ported to `Frame`) and `test_shapes.py`;
  - `CLAUDE.md` and `docs/tasks/README.md` (ground rules);
  - `docs/integrations/gmsh.md` (uncommitted; see notes).
- **Size:** `hexmesh/` went from 14,180 to 6,667 lines of Python.  The
  diff over `hexmesh/` and `tests/` is +31 / −10,410.
- **Tests:** 304 passed, 0 failed, 0 xfailed.  Before, it was 539 passed,
  10 failed and 4 xfailed; the failures and xfails were all in the
  deleted legacy tests.  The examples smoke test passes, all 8 examples.
- **Follow-ups:** the three Questions for design above.  None of them
  blocks this task: the task asks for the §9 changes to be handed over
  there.
