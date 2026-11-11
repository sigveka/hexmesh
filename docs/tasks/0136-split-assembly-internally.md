# 0136 — Split `Assembly` into internal modules behind the same class

- **Status:** done
- **Decision:** DESIGN §3.1 (capabilities; no private name crosses a package); [0042](../decisions/0042-road-to-1-0.md) (before the 0.8 API review)
- **Depends on:** none in code.  **Sequence:** not alongside another
  task editing `assembler.py` (task 0130 adds a correction record there);
  agree the order in the shared tree.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The architecture review (2026-11-10): `Assembly`
(`hexmesh/assembly/assembler.py`) is 1 280 lines, 50 methods, and
imports 22 library modules, the most of any.  It holds six concerns:
building the graph (`add`, `close`, `prepend`, `extend_open_ends`,
`from_nozzle`), serialisation (`to_dict`/`from_dict`, `save`/`load`,
`from_msh`, `refined`), validation and counts (`validate`,
`cell_count(s)`, the toward/twist resolution), realisation (`build`,
`build_faces`, `fill`, projection), output (`write_physical_groups`,
`group_roles`, `patch_name`, `write`, `write_openfoam`) and quality
(`check_quality`, the correction record).  Each change touches the one
file; the 0.8 API review reads easier over smaller units.

**Where.**  `hexmesh/assembly/assembler.py` and new private modules in
`hexmesh/assembly/`; `tests/test_architecture.py` only if a rule needs
a listed exception (it shouldn't).

**Do.**
1. **Plan first** (under *Agent notes*, before moving code): which
   methods go to which module, what state each needs, and how `Assembly`
   delegates.  Suggested split: `_graph.py`, `_serial.py`,
   `_realise.py`, `_output.py`, keeping validation and the public
   methods on `Assembly`.  Delegation by plain functions taking the
   assembly is preferred to mixins; say why if you choose otherwise.
2. **Public surface unchanged:** every public name, signature, default,
   docstring (API.md is generated from or checked against them) and
   attribute stays on `Assembly`.  `help(Assembly)` lists the same
   methods.
3. **Move, don't rewrite:** behaviour identical; the diff is moves plus
   delegation stubs.  New modules are private (`_` prefix) and imported
   only inside `assembly`.
4. **Check:** every example's mesh byte-identical; saved descriptions
   identical (`to_dict` of every example equal before and after); the
   architecture test passes with no new cycle or allowed edge; full
   suite.  Report the before/after sizes and import fan-out of
   `assembler.py` in *Outcome*.

**Accept.**
- `assembler.py` under ~500 lines; no new cycles; meshes and saved
  descriptions identical; full suite: no new failures.

**Out of scope.**  Regrouping `assembly` into subpackages; API changes
(the 0.8 review's job); other classes (`Tee`, `TapTemplate`, `Wye`).

## Agent notes

**Plan (step 1), 2026-11-11.**  Before: `assembler.py` 1 521 lines
(after 0130), `Assembly` 1 300 lines: 237 lines of public signatures and
docstrings, 512 of public bodies, 451 of private methods.

- **Delegation: plain functions taking the assembly** (`fn(asm, …)`),
  as the task prefers.  Every public method stays on `Assembly` with
  its signature, defaults and docstring, and its body becomes one
  `return _module.fn(self, …)`.  Moved bodies are the old ones with
  `self` renamed `asm`.  A call to another moved private method becomes
  a direct call of its function.  State stays where it is: every
  attribute is still set in `Assembly.__init__` and read or written as
  `asm._edges`, `asm._fitting_volumes`, …; no module holds state.
- **Modules** (all private, imported only by `assembler.py` and each
  other):
  - `_graph.py`: building the graph.  `Edge`, `add`, `close`, `prepend`,
    `extend_open_ends`, `_check_label`, `_twist_for_toward`, `_resolved`,
    `_port_names`, `_attached`, `_check_degree`, `_new_interface`, `_at`.
  - `_validate.py`: `validate` (102 lines; moved so that `assembler.py`
    gets under 500).
  - `_realise.py`: `build`, `build_faces`, `fill`, `_set_constraints`,
    `mesh`, `_project_walls`, `_second_order`, `_revolve_high_order`,
    and the helpers they use (`_require_session`, `curve_constraints`,
    `_located`, `_Parents`, `_element_parents`, `_rotation`,
    `_HEX_EDGES`, `_quad_edges`, `_surface_quads`, `_wall_edges`).
  - `_checks.py`: the checks after meshing and the record:
    `_check_projection`, `_check_second_order`, `_check_meshed_sj`,
    `_check_meshed_nonorth`, `_written_elements`,
    `_record_corrections`, `check_quality`, `_element_qualities`.
  - `_output.py`: `write_physical_groups`, `patch_name`, `write`,
    `_stamp`, `write_openfoam`.
  - **No `_serial.py`:** `to_dict`, `from_dict`, `from_msh`, `refined`,
    `save` and `load` are 3–9 lines each and already delegate to
    `intent`; a module for them would hold stubs for stubs.  They stay
    on `Assembly`, with `__init__`, `from_nozzle`, the properties,
    `cell_count(s)`, `group_roles`, `open_interfaces`, `volumes` and
    `fitting_volumes`.
- **Kept as private stubs on `Assembly`:** `_project_walls` and
  `_revolve_high_order`.  Tests patch them on the class
  (`test_projection.py`, `test_corrections.py`), so the moved `mesh` and
  `_second_order` call them through `asm`.  Other private methods go
  entirely.
- **Re-exports from `assembler`:** `Edge` (`tests/test_assembly_guards.py`)
  and `curve_constraints` (`tests/test_grading.py`), so no test changes.
  `validation/tools/wye_redesign.py` patches
  `assembler.min_scaled_jacobians`, so it is changed to patch
  `_checks`, where the call moves.
- **Warning locations:** a stub adds one frame between the user's call
  and a warning, so each `stacklevel` that counts through `Assembly`
  gains one: `validate`'s two (2 → 3), `_check_projection` and
  `_check_meshed_sj` (3 → 4), `_check_meshed_nonorth` (4 → 5), and the
  radians warning in `fittings._Toward.resolve` (4 → 5, comment
  updated).  Checked: each warning's file and line, before and after.
- **Checks (step 4):** every example's `.msh` (without `$Comments`) and
  `to_dict()` equal to HEAD's (worktree); `help(Assembly)` text equal;
  the architecture test; the full suite.

## Questions for design

## Outcome

**Done 2026-11-11**, as planned, with two more methods kept on the class
(below).

| module | lines | holds |
|---|---|---|
| `assembler.py` | 1 521 → **482** | `Assembly`: public signatures and docstrings, one-line delegations, `__init__`, serialisation, properties |
| `_graph.py` | 325 | `Edge`, `add`, `close`, `prepend`, `extend_open_ends` and their helpers |
| `_validate.py` | 126 | `validate` |
| `_realise.py` | 393 | `build`, `build_faces`, `fill`, `mesh`, projection, second order |
| `_checks.py` | 292 | the session guard, checks after meshing, the correction record, `check_quality` |
| `_output.py` | 137 | physical groups, patch names, `write`, `write_openfoam` |

- **Import fan-out of `assembler.py`:** 18 modules → 13, of which 5
  are the new private modules (8 library modules).  No new cycle or
  allowed edge (architecture test passes unchanged).
- **Kept on the class** besides the plan's two: `_new_interface`
  (`tests/test_assembly_guards.py` calls it) and `_twist_for_toward`
  (`hexmesh/interchange/build.py` calls it on the assembly).  Each is a
  stub with a comment saying why.
- **How:** a script did the move (scratchpad `split0136.py`, not
  committed): each method's source with `self` → `asm`, calls to moved
  private methods made direct, imports cut to what each module uses.
  No body was edited by hand.
- **Checks:** all 31 examples' `.msh` (without `$Comments`) and
  `to_dict()` equal to HEAD's (worktree); `help(Assembly)` text and all
  26 public signatures equal; warnings point at the same user line as
  before (the radians warning from `add`, `validate`'s, the projection
  move, the duct taps' meshed SJ and non-orthogonality); full suite
  4080 passed, 15 skipped, 1 xfailed (design's 0137 added one test).
- **Outside the package:** `fittings.py` (the radians warning's
  `stacklevel` 4 → 5 and its comment); `validation/tools/wye_redesign.py`
  patches `_checks.min_scaled_jacobians`.  No test changed.
- **Before the split:** `refined()`'s docstring no longer names density
  switches (commit 0df1fe1, design's request from task 0132).
- **Follow-up for the 0.8 review:** four docstrings or comments still
  point at moved private methods with `:meth:` (`_record_corrections`,
  `_second_order`, `_stamp`, `_project_walls`); left, since this task
  keeps docstrings unchanged.
