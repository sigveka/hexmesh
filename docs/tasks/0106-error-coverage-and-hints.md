# 0106 — Every user-facing error coded, and hints where they help

- **Status:** ready (after 0105)
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
