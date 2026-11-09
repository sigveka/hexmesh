# 0111 — Hints for equipment and study errors; the layout errors reviewed

- **Status:** done
- **Decision:** [0040 — Agents for users](../decisions/0040-user-agents-network-design-and-resolution.md); follow-up of task 0106
- **Depends on:** 0106 (done).  Not needed before the launch.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0106 raised the share of coded errors with a hint from
13 % to 29 % in the modules it listed.  It found three places it didn't
list:
- `assembly/equipment.py`: 0 of 23 with a hint;
- `study/definition.py`: 0 of 18;
- `assembly/blocks.py`'s layout errors: 0 of 13, mostly invariants of
  the fittings' own layouts.

**Do.**
1. **Hints** in `equipment.py` and `study/definition.py`, on 0106's rule:
   a hint says what to change, with the number when there is one; no hint
   is better than a vague one.
2. **Review `blocks.py`'s 13** on 0106's split: a user-reachable error
   keeps its code and gains a hint; an invariant becomes `InternalError`.
   Put the table under *Agent notes*.
3. Report the hint share per module, before and after.

**Accept.**
- The table and the shares are in *Outcome*.
- Existing messages unchanged except where a hint is added or an error
  becomes `InternalError` (listed).
- The architecture rule still passes; full suite: no new failures.

## Agent notes

### `blocks.py`'s 13 (step 2)

`BlockLayout` isn't public (not in `API.md` or `__all__`).  Users reach
its errors only through a fitting, which wraps a `LayoutError` with
`AssemblyError.wrap` and keeps its code.  Two kinds of evidence decided
each one:
- **The tests.**  Every test of these errors builds a layout by hand
  (`tests/test_blocks.py`, `test_axial_grading.py`, `test_errors.py`).
  None reaches one through a fitting.
- **A sweep of the shipped fittings** through `Assembly.validate()`,
  about 2,500 configurations:
  - wyes: 30–120° in 5° steps, nang 4/8/12, no shell or 0.01/0.03 shells,
    short and long runs and branches;
  - tees and laterals: 30–150°, r/R 0.3–1.0, nang 4/8, shelled;
  - duct taps: H and O-H mains, both faces, round and rectangular
    branches, width ratios 0.1–1.0.

  Every rejection came from a fitting's own named check (`branch_length_too_short`,
  `predicted_sj_below_minimum`, `duct_tap_too_wide`, …).  No `block_*`
  code and no `port_roll_not_a_period` appeared.

"No" means hand-built layouts only: not reached through a fitting by any
test or by the sweep.

| code | what it guards | reachable? | now |
|---|---|---|---|
| `block_vertices_not_distinct` | a block's 8 vertex ids | no: the fittings name their vertices | `InternalError` |
| `block_division_conflict` | parallel edges' counts | no | `InternalError` |
| `block_grading_conflict` | parallel edges' gradings | no | `InternalError` |
| `block_division_missing` | an edge class with no count | no | `InternalError` |
| `block_layout_empty` | no blocks | no | `InternalError` |
| `block_vertex_unplaced` | a vertex without coordinates | no | `InternalError` |
| `block_face_shared` | a face in 3+ blocks | no | `InternalError` |
| `block_port_face_unused` | a port face no block uses | no | `InternalError` |
| `block_port_face_interior` | a port face inside the layout | no | `InternalError` |
| `block_port_faces_unbound` | `realise` before `bind_face` | no | `InternalError` |
| `block_h_core_in_ring` | `bind_face` with an H core inside a ring | no | `InternalError` |
| `port_roll_not_a_period` | `corner_shift` between frames | no: `junction_roll` rejects a bad `roll` first, coded `junction_roll_invalid` | `InternalError`: keeps `value`, drops `limit` (`InternalError` takes none) |
| `block_inverted` | a block inverted at a corner | **yes in principle**: geometry the fitting's own quality checks let through.  Not reached in the sweep. | `LayoutError`, coded, **no hint** |

`block_inverted` gets no hint: the remedy (a run length, a radius
ratio, an angle) depends on the fitting, and `blocks.py` doesn't know
which.  The fittings' own checks give those hints first.

The 12 codes leave `CODES` and `API.md`.  `test_architecture` fails on a
registered code nothing raises, so they can't stay registered.  They
were released in 0.5.0.  The CHANGELOG lists them as **retired**.  The
messages are unchanged, apart from `InternalError`'s report request
appended to each.

### Hints (step 1)

On 0106's rule.  Messages that already state the fix get no hint:
`size_not_positive`, `option_invalid`, `nozzle_unknown` (it lists the
names), `jobs`/`cores_per_job` must be ≥ 1, `format`, `template`'s two
forms, `study_not_json` (it quotes the parser's line and column), the
case stage that needs `"format": "openfoam"`.  Also none for
`drum_axis_zero` and `nozzle_projection_too_short`: their messages give
the number already.

**`equipment.py`** (14 hints):

| code | hint, e.g. |
|---|---|
| `drum_name_invalid`, `nozzle_name_invalid` | `e.g. name='V_1'`: the name with every other character made `_` |
| `drum_head_args_invalid` (radii on another head) | `drop crown_radius and knuckle_radius, or use head='torispherical'` |
| `drum_head_args_invalid` (radii missing) | `e.g. a Klöpper head (DIN 28011): crown_radius=1, knuckle_radius=0.1` (D, 0.1 D) |
| `drum_head_args_invalid` (order) | `knuckle_radius in (0, 0.5); crown_radius above 0.5`, only the violated parts |
| `drum_up_parallel` | `e.g. up=(1, 0, 0)`: the world axis least aligned with the drum axis |
| `nozzle_name_duplicate` | `rename one of each, e.g. N1_2` |
| `nozzle_not_circular` | ``give layer `s` dR= (a circle)``, or `radius=` for the core |
| `nozzle_too_large` | `a nozzle outer radius below 0.5, or a drum diameter above 1.2` |
| `nozzle_footprint_outside` (shell) | `axial between 0.05 and 1.95`, or the drum length the nozzle needs |
| `nozzle_footprint_outside` (head) | `offset at most 0.45`, or `a nozzle outer radius below 0.444444, or OnShell` |
| `nozzle_location_unknown` | `OnShell(axial=, angle=, projection=) or OnHead(head=, offset=, angle=, projection=)` |
| `nozzle_footprints_overlap` (shell) | `axial positions at least 0.1 apart (now 0.05), or their angles further apart`: an axial gap of r_a + r_b always clears |
| `nozzle_footprints_overlap` (head) | `nozzle axes at least 0.1 apart (now 0.0517638)` |

**`study/definition.py`** (8 hints):

| code | hint, e.g. |
|---|---|
| `study_function_invalid` | `e.g. 'mymod:build'`, from `mymod.build`; else `e.g. 'template:build'` |
| `study_function_not_found` (no module) | `put mymod.py in <the study file's folder>` |
| `study_function_not_found` (no function) | `define build(params) in mymod` |
| `study_placeholders_mismatch` (check, substitute) | `add angle to parameters; use $length in the template, or drop it from parameters` |
| `study_not_object` | a minimal study object |
| `study_key_unknown` (top level, budget, case/run) | `rename 'paramters' to 'parameters'`, through `difflib`; none without a close match |

`study_function_not_found` was built with `StudyError.wrap`, which takes
no hint.  Its error is now built directly, with the same message, code
and `where`.  An `ImportError` or `AttributeError` raised inside the
user's module gets no hint: the fix is in their code.

Each hint was triggered and read (a scratch script, not kept).

### Counting

Coded constructions: a call of an `…Error` or `…Warning` class, or of
`.wrap`, with `code=`, counted with an AST scan.  Hinted means it also
has `hint=`.  This counts every construction, not just `raise X(…)`,
so its totals differ slightly from 0106's.  "Before" is HEAD at the
start (edfb74e).

## Outcome

**Done** (2026-11-09).

**Hint share** (coded constructions with a hint; before = edfb74e):

| module | before | after |
|---|---|---|
| `assembly/equipment.py` | 0/23 | 14/23 |
| `study/definition.py` | 0/18 | 8/18 |
| `assembly/blocks.py` | 0/13 | 0/1 (12 became `InternalError`; `block_inverted` has no hint, see notes) |
| **all of `hexmesh/`** | **141/494 (28.5 %)** | **163/482 (33.8 %)** |

**Files.**
- `hexmesh/assembly/blocks.py`: 12 invariants → `InternalError`; `LayoutError`'s docstring.
- `hexmesh/assembly/equipment.py`: 14 hints; `_safe_name`.
- `hexmesh/study/definition.py`: 8 hints; `_did_you_mean`; `function()` builds its error directly (`wrap` takes no hint).
- `hexmesh/errors.py`, `API.md`: the 12 codes retired.
- Tests: `test_blocks.py`, `test_axial_grading.py` expect `InternalError`; `test_errors.py`: `test_layout_error` covers both kinds, plus `test_equipment_hints` (7), `test_study_key_hints` (3), `test_study_function_hints`.
- `CHANGELOG.md`.

**Messages changed:** none, except the 12 that are now `InternalError`. Each gains `InternalError`'s report request, and `port_roll_not_a_period` loses its `limit`.

**Tests:** full suite 3775 passed, 15 skipped (before the 11 new tests); the four touched files 138 passed, with the new tests in. The architecture rule passes.

**Surprises.**
- The retirement needed a decision of its own. `test_architecture` refuses a registered code nothing raises, so turning an error into `InternalError` removes its code. These codes shipped in 0.5.0, and `errors.py` says codes "never change once released". I read the task's "an invariant becomes `InternalError`" as covering this, and listed the 12 as retired in the CHANGELOG. **Design: confirm, or say whether retired codes should stay registered (e.g. a `RETIRED` set the rule accepts).**
- `block_layout_invalid` never reaches anyone. Tee, Wye, Switch and the duct tap wrap a `LayoutError` with `wrap(…, code="block_layout_invalid")`, but `wrap` keeps the inner error's code, which a `LayoutError` always has. A user sees `block_inverted` instead.

**Proposed follow-ups.**
- `block_layout_invalid`: retire it, or have the fittings' wrap use it with a fitting-specific hint for `block_inverted`.
- `study/sampling.py` (0/7) is the last unreviewed module that 0106 named.

**Design (2026-11-09, the user: "yes"):** `block_layout_invalid` stays
registered (removing a code is breaking, 0.5.0's *Stability*); raising
it with a fitting-specific hint is fine when next in that code.
`study/sampling.py` is reviewed in 0.8's API review (decision 0042).
