# 0081 — Architecture tests, and the cross-package leaks

- **Status:** done
- **Decision:** [0037 — Capability boundaries](../decisions/0037-capability-boundaries.md) (items 3, 6 and the assembler part of item 6's "smaller"); DESIGN §3.1
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).  This task
works outside `hexmesh/assembly/`: in `tests/`, `hexmesh/interchange/`
and `hexmesh/assembly/` as listed.

**Why.**  DESIGN §3.1 sets a dependency order for the packages and three
rules, and says a test enforces them.  The survey (RESEARCH §12, hexmesh
`8b0dc98`) found:
- private names imported across packages: `interchange/build.py:321`
  imports `assembly.wye._IN_MARGIN`; `build.py:631` and `:1161` import
  `assembly.fittings._with_radii`;
- two module cycles, hidden by function-level imports:
  `assembly.assembler` ↔ `assembly.intent`, and `interchange.build` ↔
  `interchange.model`;
- the assembler naming fitting types: `assembler.py:417`
  (`isinstance(fitting, (Bend, Elbow, MiterBend))` for the radians
  warning).

Without a test, these grow back.

**Where.**  New `tests/test_architecture.py`; `hexmesh/interchange/build.py`,
`hexmesh/assembly/{fittings,wye,assembler}.py`, `hexmesh/core/spec.py`.

**Do.**
1. **`tests/test_architecture.py`**: pure Python, AST only, no imports
   of hexmesh modules.  It must also count imports inside functions.
   - **Dependency order** (DESIGN §3.1): each package imports only from
     packages to its left.
     - Order: `core` → `sections` → `assembly` → `interchange` →
       `study`.
     - `faces` counts as `sections` until task 0082 moves it.
     - `io.writers` is a leaf, allowed from `assembly` and `study`.
     - `_occ`, `session`, `quality_hex` are shared leaves.
     - `hexmesh/__init__.py` and `examples` may import anything.
     - Allowlist, each entry with its task: `io.readers` → `interchange`
       until task 0066.
   - **No private name crosses a package** (`from x import _y` where x
     is in another package).  `_occ` is the declared exception (DESIGN
     §3.1).
   - **No module cycles**, with function-level imports counted.
     Baseline allowlist: the two cycles above, each with a comment
     naming the task that removes it.  Remove them here if it's simple
     (step 3).
   - **A cap on shape-specific sites** outside `core/shape.py`,
     `sections/` and `faces/`.  A site is one of:
     - `isinstance(…, CircleShape | RectShape | BlendShape)`;
     - an attribute read of `.radius`, `.half_w`, `.half_h`, `.nang_w`
       or `.nang_h` on a value from `core_shape`, `shape` or `branch`.

     Make the definition precise in the test, and print the sites when
     it fails.  The cap is today's count after steps 2–3.  RESEARCH §12
     measured 89 with a cruder grep, so expect a different number.
     Record it under *Agent notes*.
   - Each failure message names the rule (DESIGN §3.1) and the file
     and line.
2. **Leaks:**
   - `_with_radii` → a public `PipeSpec.with_radii(radii, …)` in
     `core/spec.py` (it's spec knowledge).  `fittings.py` and
     `interchange` both use it.
   - `_IN_MARGIN`: the knowledge is "how far behind the junction does
     a wye's inlet station sit".  Expose it from the wye as a public
     function, e.g. `wye.inlet_run(radius, angle)`, and use it in
     `build.py`.
3. **Cycles:** make `intent` not import `assembler`, or the reverse,
   and the same for `interchange.build` and `model`.  Pass what's
   needed as arguments, or move the shared piece to the lower module.
   If either takes more than a small change, leave it in the allowlist
   with a note.
4. **Assembler naming fittings:** move the radians warning into each
   angled fitting's `resolve` (or a shared helper the fittings call),
   so `assembler.py` no longer imports `Bend`, `Elbow`, `MiterBend`.
   `prepend`'s `Straight`-only rule may stay (it's about the graph);
   note it if you change it.

**Accept.**
- `tests/test_architecture.py` passes, and fails on a planted violation
  of each rule (a temporary file in `tmp_path` or a parametrised
  synthetic module tree; don't commit planted violations).
- No `_`-prefixed name crosses a package, except `_occ`.
- **No behaviour change.**  Record `to_dict()` and the meshed node
  coordinates (1e-12) of every `hexmesh/examples` script and the
  interchange fixtures, before and after.  Use task 0065's method: a
  pytest plugin or script under your session's scratchpad.  All
  identical; warnings identical, including the radians warning's text
  and `stacklevel` (the user sees the caller's line).
- Full suite: no new failures; the test count goes up by the new tests.

**Out of scope.**  The section package (0082); the shape protocol (0083);
moving readers (0066); splitting large modules (decision 0037 item 5).

## Agent notes

- **Shape-site cap: 69**, counted by the AST definition in
  `shape_sites()`.  RESEARCH §12's grep found 89.  Steps 2–3 left the
  count unchanged.  By file: tee 17, spec 14, interface 9, wye 8,
  corners 6, section_quality 6, fittings 3, interchange.build 3,
  blocks 2, equipment 1.  `examples` are not counted: they are user
  code.
- **The `intent` ↔ `assembler` "cycle" is type-only.**
  - `intent` imports `Assembly` under `if TYPE_CHECKING:`, for
    annotations; it never runs.
  - So the cycle rule ignores `TYPE_CHECKING` imports.  The order and
    private-name rules still count them.
  - No code change, and no allowlist entry.
- **A third private crossing that the survey missed:**
  - `assembler` imported `add_physical_group` from the private module
    `faces._gmsh_helpers`.
  - `hexmesh.faces` now re-exports it publicly.  0082 moves it with
    `faces`.
- **Private modules count:** an import of a `_`-prefixed module from
  another package is a violation, like a `_`-prefixed name.  `_occ` is
  exempt.
- **`_with_radii` had no caller left in `fittings.py`;** only the builder
  used it.  It is now `PipeSpec.with_radii(radii, mprgs=None)`,
  documented in API.md.
- **`_IN_MARGIN`:**
  - The builder works with a measured half-angle in radians, so the
    public function is `wye.inlet_clearance(half)`, which returns
    tan(half) + margin in units of R.
  - The builder's run is `R * (inlet_clearance(half) + 0.5)`, the same
    operations in the same order as before.
  - `Wye.placement()` uses it too.  That changes `s / c` to `tan h`;
    measured node difference 0.
- **`interchange.build` ↔ `model`:**
  - The model now calls the builder through `model.BUILDERS`, which
    `build.py` fills when it is imported.  `hexmesh.interchange`
    always imports it.
  - This follows the module's existing `register_formatter` pattern.
    `NetworkModel.to_assembly` / `to_assemblies` are unchanged.
- **The radians warning** now lives in `_Toward.resolve`: Bend,
  MiterBend and Elbow are the only `_Toward` fittings.
  - Its `stacklevel` goes from 3 to 4 (one frame deeper), so it still
    points at the caller's `add()` / `close()` line.
  - `assembler.py` no longer imports `Bend`, `Elbow`, `MiterBend` or
    `RADIANS_WARNING_BELOW`.
  - `prepend`'s `Straight`-only rule is unchanged.

## Questions for design

## Outcome

Done 2026-11-02.

**Files.**
- New: `tests/test_architecture.py` (24 tests), AST only.
  - Rule checks: `order_violations`, `private_violations`, `cycles`,
    `shape_sites`.  Each failure names its DESIGN §3.1 rule and the file
    and line.
  - Planted-violation tests run the same checks on synthetic trees in
    `tmp_path`: 4 for order, 3 for private names, 2 for cycles
    (function-level, `TYPE_CHECKING`), 7 for shape sites, plus 2
    negative cases.
- Changed:
  - `hexmesh/core/spec.py`: `PipeSpec.with_radii`.
  - `hexmesh/assembly/fittings.py`: `_with_radii` removed; the radians
    warning moved into `_Toward.resolve`.
  - `hexmesh/assembly/wye.py`: `inlet_clearance`.
  - `hexmesh/assembly/assembler.py`: no fitting types besides
    `Straight`; `add_physical_group` from `hexmesh.faces`.
  - `hexmesh/faces/__init__.py`: re-exports `add_physical_group`.
  - `hexmesh/interchange/model.py`: `BUILDERS`.
  - `hexmesh/interchange/build.py`: registers the builder; uses the
    public names.
  - `API.md`: `with_radii`.
- Allowlists:
  - edges: `io.readers → interchange` (task 0066);
  - cycles: none;
  - shape-site cap: 69.

**No behaviour change, measured** (task 0065's method; recorders in the
session scratchpad).
- 28 examples: `to_dict()` identical, and the meshed node tags and
  coordinates identical (max difference 0).
- 93 interchange builder calls in the five reader test files: 52
  assemblies, 3 piece sets and 38 errors, all identical (results,
  error texts, warnings).  Their 38 distinct dicts were meshed from
  `to_dict()`: identical nodes, difference 0.
- Radians probe (Bend, MiterBend, Elbow, Bend with `toward`):
  identical text and category, reported at the caller's `add()` line.
- Warnings otherwise identical except `lineno` inside `assembler.py`
  (584 → 577) for the validation warnings that point at
  `assembler.py` itself, shifted by the 7 removed lines.

**Suite.**
- Before: 2165 passed, 15 skipped.
- After: 2189 passed, 15 skipped; +24 new, no new failures.

**Surprises.**
- The `intent` cycle was type-only (`TYPE_CHECKING`), not hidden by a
  function-level import.
- One `test_topology_invariance` tee case
  (`test_raw_numbering[tee-ratio-0.4-0.6]`) emits its predicted-SJ
  warning in some runs and not others.  This happens on unchanged code
  too, so the suite's warning total varies by one between runs (147 /
  148).

**Proposed follow-ups.**
- The shape-site list is 0083's work list: tee 17 and spec 14 are the
  largest.
- `core/spec.py` counts as outside `core/shape.py`.  If design wants
  spec's layout checks treated as shape-owned, the cap drops by 14.

