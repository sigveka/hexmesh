# 0106 — Every user-facing error coded, and hints where they help

- **Status:** done (2026-11-07)
- **Decision:** [0040 — Agents for users](../decisions/0040-user-agents-network-design-and-resolution.md) (foundation A, task 0094: structured errors)
- **Depends on:** 0094, 0102 (done).  Second of the public-readiness
  tasks (0105, 0106, 0078).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The repository is public, and its pitch to agents is "every
error carries a code, the location, the value, the limit and a hint".
Measured by the design session on 2026-11-07 (a scan of `raise` calls
in `hexmesh/`):
- 308 registered codes; 427 raises pass `code=`.
- **57 of those 427 pass a `hint=`** (about 13 %).
- **50 raises are bare built-in errors**: `ValueError` 23,
  `RuntimeError` 8, `TypeError` 7, `AssertionError` 5, `KeyError` 3,
  `NotImplementedError` 3, `AttributeError` 1.  Most are in
  `assembly/sweep.py` (7), `core/spec.py` (5), `interchange/build.py`
  (4) and `core/cross_section.py` (3).  Some are internal invariants;
  some are reached by users (e.g. `check_supported`'s
  `NotImplementedError` in `assembly/interface.py`).
- Task 0102's probe found three bad rejections:
  1. a `Switch` on a circular section raises an uncoded
     `AttributeError` ("'CircleShape' object has no attribute
     'nang_w'");
  2. a duct tap on a shelled rectangle fails with the Switch's
     `switch_changes_shells`, naming a fitting the user didn't write;
  3. a `Tee` with `n_outer = 8` fails with `block_vertices_not_distinct`
     before the section check (`section_not_supported`).

**Where.**  The raising modules; `hexmesh/errors.py`;
`tests/test_architecture.py`; `tests/test_errors.py`; `API.md`;
`CHANGELOG.md`; the manifest's support data (`hexmesh/agent/support.json`).

**Do.**
1. **Classify the 50 bare raises**, in a table under *Agent notes*:
   user-reachable (bad input, an unsupported combination, a missing
   tool) or an internal invariant (a bug if it fires).
   - **User-reachable:** a `HexmeshError` subclass with a registered
     code, `where`, `value` and `limit` where they apply.  Keep the
     built-in class in the hierarchy (as `SpecTypeError` does), so
     callers' `except ValueError` still works.
   - **Internal invariants:** `assert`, or an `InternalError` with code
     `internal_invariant`, whose message asks for a bug report.  Not a
     user error.
2. **The probe's three:**
   - a `Switch` on a circle: a coded rejection (e.g. `switch_needs_rect`);
   - the duct tap on a shelled rectangle: its own code and message,
     naming the tap and what it can't do;
   - every fitting runs the section check (`check_supported`) before
     building blocks, so an unsupported section gets
     `section_not_supported` first.
3. **An architecture rule:** no bare `raise ValueError / TypeError /
   RuntimeError / KeyError / NotImplementedError / AttributeError` in
   `hexmesh/` outside a short, reviewed allow-list (with a reason per
   entry).  A planted case shows it fails.  The rule's count only goes
   down.
4. **Hints.**  Add a `hint` to the codes users and agents meet most:
   - spec and section errors (`core/spec.py`, `core/shape.py`);
   - `validate()`'s quality and fit errors (what to change: a radius, a
     count, an angle, a length);
   - PCF and network errors (`interchange/`);
   - the CLI's input errors.

   A hint says what to change, with the number when there is one (e.g.
   "use r/R ≥ 0.875 at 35°, or a larger angle").  No hint is better than
   a vague one.  Report the share of coded raises with a hint, before
   and after, per module.
5. **The manifest:** regenerate the support data if any rejection's code
   changes (`python3 -m hexmesh.agent._probe`).

**Accept.**
- No bare built-in raise outside the allow-list; the architecture test
  enforces it.
- The probe's three give their own codes; the support data shows them.
- Every error a user can trigger in the listed modules has a code; the
  hint share is reported per module.
- Existing messages unchanged except where a code or hint is added
  (list them in *Outcome*).
- Full suite: no new failures.

**Out of scope.**  Rewording existing messages beyond adding the hint.

## Agent notes

### The 52 bare raises (step 1)

An AST scan of `raise` in `hexmesh/` found 52 bare built-in raises at the
start: design's 50, plus `FileNotFoundError` in `pcf.py` and one more
`NotImplementedError`.  A message that a test triggers is reachable by
definition.  For the rest the call path decided: is the value checked
earlier by the spec or the fitting?

| class | sites | treatment |
|---|---|---|
| **user-reachable** | `agent/_describe.py` `describe`, `agent/_preview.py` `preview`, `agent/advise.py` `advise` (TypeError) | `AssemblyTypeError`, `agent_input_type`, hint |
| | `assembly/interface.py` `check_supported` ×2, `assembly/section_quality.py` (NotImplementedError) | `AssemblyError`, `section_not_supported`, hint; the assembler catches `AssemblyError` and wraps it with the same message |
| | `assembly/signature.py` `strategies_for` (TypeError: a custom fitting without `strategies`) | `AssemblyTypeError`, `fitting_declares_no_strategies`, hint |
| | `core/spec.py` `core()` twice, `shell()` before `core()`, no core ×3 (RuntimeError; `test_shapes` expects RuntimeError) | `SpecUsageError(SpecError, RuntimeError)`: `spec_core_twice`, `spec_shell_before_core`, `spec_no_core`, hints |
| | `interchange/build.py` `_elbow_params` ×3 (ValueError, wrapped as `bend_geometry_invalid`) | `AssemblyError` `bend_geometry_invalid` at the source, with value, limit and hint |
| | `interchange/importers/pcf.py` missing file (FileNotFoundError) | `ReaderFileNotFound(ReaderError, FileNotFoundError)`, `pcf_file_not_found` |
| | `quality_hex.py` `_aggregate` mode (ValueError; a public `mode=`) | `HexmeshError`, `quality_mode_unknown` |
| | `study/openfoam.py` `foam` (RuntimeError: a failed command) | `FoamCommandFailed(StudyError, RuntimeError)`, `openfoam_command_failed`, hint naming the log and the runner |
| | `study/openfoam.py` `read_patch_values` uniform without `n` (ValueError) | `StudyError`, `openfoam_value_uniform`, hint |
| | `sections/oh_gmsh.py` `build_oh_circle8` odd nang, `build_shell` dR (ValueError; public builders, `test_faces` calls the first directly) | `SpecError`: `nang_not_divisible` with a hint, `size_not_positive` |
| **internal invariant** | `_occ.py` curve ends; `assembly/corners.py` ×2; `assembly/equipment.py` head radius; `assembly/projection.py` and `assembly/wye.py` wall projection; `assembly/signature.py` layer type; `assembly/sweep.py` `Path.__post_init__` ×5 and the slab pairing ×2; `core/cross_section.py` ×2; `core/shape.py` outline type, core ring; `sections/h.py`, `sections/oh.py`; `io/writers/msh_comments.py` (the `$Comments` guard: the lines are hexmesh's own, and the recipe is JSON with `$` escaped) | `InternalError` (`internal_invariant`), message unchanged plus the report request: 21 sites |
| **already an invariant** | `raise AssertionError` in `agent/advise.py`, `agent/cli.py`, `interchange/build.py` (`# pragma: no cover` unreachables) and the `limits.py` / `params.py` registries | unchanged: not in the rule's set |
| **allow-list** (5) | `interchange/__init__.py` `__getattr__` (AttributeError); `errors.py` `_Fields._set` (KeyError, the registry's own guard; `test_errors` expects it); `assembly/sweep.py` `Sweep.path` (an abstract method); `core/cross_section.py` `LayeredCrossSection.get` and `core/region.py` `MaterialGraph.interface_label` (KeyError: lookups by name, internal callers only) | `BARE_ALLOWED` in `tests/test_architecture.py`, with the reasons |

`InternalError` is `_Fields` + `RuntimeError`, not a `HexmeshError`: a
caller's `except HexmeshError` or `except ValueError` doesn't hide a bug.
Its message ends "(an internal check failed: this is a bug in hexmesh;
please report it, with the input that caused it, at
https://github.com/sigveka/hexmesh/issues)".  `code_violations` now also
counts a class that sets its code through `_set(code=…)` as self-coded.

### The probe's three (step 2)

1. **Switch on a circle.**  `resolve()` reads the inlet's `nang_w` in
   `outlet_spec`, before `check()` gets to `switch_needs_rectangle`.  The
   rectangle check is now `Switch._check_rectangle`, run first in
   `outlet_spec` and still in `check`, with a hint.
2. **Duct tap on a shelled rectangle.**  On an H main, `TapTemplate.check`
   handed off to `_check_h` before its shell check, so the internal Switch
   leg was the first to object.  The shell check now runs before the
   layout branch, so both layouts give `junction_shells_unsupported`
   ("Tee: duct taps are single-layer…"), now with a hint.
3. **Tee with n_outer = 8.**  `Assembly._resolved` runs `check_supported`
   before a fitting's `resolve()`, which for a Tee builds its layout (the
   shortest run).  Only fittings with a `resolve` are affected.
   `check_supported` costs 0.11 ms (three-layer spec, 100 calls).

The regenerated `support.json` gives `section_not_supported` for every
n_outer = 8 entry.  `Wye` had given `junction_needs_rot_0_n_outer_4`
there.

**A probe artefact, fixed:** the probe gave a `Switch` from an H inlet the
single-layer O-H outlet, so `rect_shells` showed `switch_changes_shells`.
It now copies the inlet's shells onto the outlet, and the matrix shows
`supported: true`.  The library was right; the matrix was wrong.

### The rule (step 3)

`test_no_bare_builtin_raise`: no `raise ValueError / TypeError /
RuntimeError / KeyError / NotImplementedError / AttributeError` in
`hexmesh/` outside `BARE_ALLOWED`.  A raise is keyed by (module,
enclosing qualified name, exception), so line moves don't matter.
- `test_bare_allow_list_still_needed`: every entry must still be raised,
  so the list only shrinks.
- `test_planted_bare_raise` (7 cases): a call and a bare name, module
  level, a method; `InternalError`, `AssertionError` and
  `FileNotFoundError` pass, and so does an allowed entry.

### Hints (step 4)

A hint is added only where it names a change, preferably with its
number:
- `nang_not_divisible`: "nang=4 or nang=6 (a multiple of 2)";
- `layer_name_invalid`: "e.g. 'my_fluid'";
- the fit checks: `run_length > 0.2273, or run_length=None to resolve
  it`, the Wye's angle range, the shell thickness or the wider angle that
  fits, the outlet's `rot` or `layout`, and the counts a layer must take;
- the CLI: the full command, e.g. `hexmesh build NETWORK --out mesh.msh`.

Messages that already state the fix ("must be positive, got -0.1", "known:
…") get none.  Nor does `switch_class_not_bridged`: `BRIDGES` names design
references ("a density switch (decision 0003)"), not something to type.

Coded raises with a hint, per module (before = HEAD at the start, with
0060 in):

| module | before (hinted/coded) | after |
|---|---|---|
| `agent/_describe.py` | 0/0 | 1/1 |
| `agent/_preview.py` | 0/0 | 1/1 |
| `agent/advise.py` | 2/3 | 3/4 |
| `agent/cli.py` | 0/8 | 6/8 |
| `assembly/duct_tap.py` | 6/29 | 7/29 |
| `assembly/fittings.py` | 13/40 | 19/40 |
| `assembly/interface.py` | 0/6 | 2/8 |
| `assembly/profile.py` | 2/11 | 3/11 |
| `assembly/section_quality.py` | 0/2 | 1/3 |
| `assembly/signature.py` | 1/3 | 2/4 |
| `assembly/sweep.py` | 5/17 | 7/17 |
| `assembly/switch.py` | 4/13 | 5/13 |
| `assembly/tee.py` | 8/19 | 14/19 |
| `assembly/wye.py` | 2/13 | 10/13 |
| `core/spec.py` | 2/36 | 20/41 |
| `interchange/build.py` | 1/36 | 11/39 |
| `interchange/graph.py` | 0/16 | 2/16 |
| `interchange/importers/pcf.py` | 0/3 | 1/4 |
| `interchange/insulation.py` | 0/6 | 1/6 |
| `interchange/operations.py` | 0/17 | 3/17 |
| `quality_hex.py` | 0/0 | 0/1 |
| `sections/oh_gmsh.py` | 0/0 | 1/2 |
| `study/openfoam.py` | 0/4 | 2/6 |
| **all of hexmesh/** | **58/443 (13.1 %)** | **134/464 (28.9 %)** |

Unchanged modules are left out.  Not in step 4's list, and so not
reviewed: `study/definition.py` (0/18), `assembly/equipment.py` (0/23),
`assembly/blocks.py` (0/13, layout errors), `study/sampling.py` (0/7).

## Questions for design

_None._

## Outcome

- **Files:**
  - `hexmesh/errors.py`: `InternalError`, `SpecUsageError`,
    `ReaderFileNotFound`, `ISSUES`, 10 new codes;
  - the 21 user-reachable sites and 21 invariants (the table above);
  - `assembly/assembler.py`: the section check before `resolve()`;
  - `assembly/switch.py`, `assembly/duct_tap.py`: the probe's rejections;
  - hints in 21 modules (the table above);
  - `agent/_probe.py`: the Switch outlet keeps the inlet's shells;
    `agent/support.json` regenerated;
  - `tests/test_architecture.py`: the rule, its allow-list, and 9 tests;
  - `tests/test_corners.py`, `tests/test_msh_recipe.py` (see below);
  - `API.md` (the classes, `InternalError` and 10 code rows),
    `CHANGELOG.md`.
- **Tests:** full suite 3672 passed, 15 skipped, 3 failed.  The three
  were sites I had first classed as internal that tests reach:
  - `build_oh_circle8`'s odd nang (`test_faces`);
  - the `$Comments` guard (`test_msh_recipe`, which plants a bad
    constant);
  - n_outer = 8 at `add()` (`test_corners`).

  I reclassed the two `oh_gmsh` builder checks as `SpecError`.
  `test_msh_recipe` now expects `InternalError` for the guard, and
  `test_corners` expects the n_outer = 8 rejection at `add()` with its
  code.  Those files, with the architecture, error and manifest tests:
  212 passed.
- **Messages changed beyond an added hint:**
  - every `InternalError` message gains the report request;
  - a `Switch` on a circle: `switch_needs_rectangle` ("Switch changes a
    rectangular duct's section; the inlet core is a circle") replaces
    the `AttributeError`;
  - a duct tap on a shelled H rectangle: `junction_shells_unsupported`
    replaces `switch_changes_shells`;
  - an unsupported section at a fitting with a `resolve` (Straight, Bend,
    Tee, Wye, …) is reported by `add()` as `fitting_invalid`'s wrapper,
    "`<fitting>` at `<interface>`: assembly prototype supports n_outer=4
    only…", keeping the code `section_not_supported`.  Before, it came
    from `validate()` as "`<interface>`: …", or for a Tee or Wye as a
    layout error.
- **Hint share:** 58/443 (13.1 %) → 134/464 (28.9 %).
- **Proposed follow-ups:**
  - hints for `assembly/equipment.py` (0/23) and `study/definition.py`
    (0/18), which step 4 didn't list;
  - `assembly/blocks.py`'s layout errors (0/13), which are mostly
    invariants of the fittings' own layouts.  A candidate for the same
    user-versus-internal review.
