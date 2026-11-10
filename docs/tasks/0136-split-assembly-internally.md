# 0136 — Split `Assembly` into internal modules behind the same class

- **Status:** ready
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

## Questions for design

## Outcome
