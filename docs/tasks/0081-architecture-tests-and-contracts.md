# 0081 — Architecture tests, and the cross-package leaks

- **Status:** ready
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

## Questions for design

## Outcome
