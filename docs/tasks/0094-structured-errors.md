# 0094 — Structured errors: a code, a location, the value and the limit

- **Status:** ready
- **Decision:** [0040 — Agents for users](../decisions/0040-user-agents-network-design-and-resolution.md) (foundation A); [0019](../decisions/0019-future-agent-sdk.md) item 1 and constraint 3
- **Depends on:** —.  It touches no geometry, so it can be picked up
  alongside the H-section track.  It edits many files that 0086 also
  edits (`duct_tap.py`, `tee.py`).  Do it between 0086's commits, or
  after them, not interleaved within one.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Every error hexmesh raises for bad input is a sentence today,
for example `fitting #1 Bend(radius=0.05, …): path bends with radius
0.05, tighter than the pipe outer radius 0.1`.  The sentence names the
fitting, but a program can only parse the text.  Decision 0040's
network designer and resolution advisor need to know:
- which rule failed (a stable code);
- where (part, label, interface, field);
- the value and the limit;
- a fix (a hint).

People benefit too: the hint, and a list of codes in API.md.

Counted 2026-11-04 (`a9e7128`):
- `raise AssemblyError`: 88, of which 52 are in `io/readers` and
  `interchange`;
- `raise EquipmentError`: 23;
- `raise LayoutError`: 16;
- `StudyError` is defined in `study/definition.py`;
- `raise ValueError`: 234, the most in `assembly/fittings.py` (38),
  `sweep.py` (24), `core/spec.py` (20), `duct_tap.py` (20), `wye.py` and
  `tee.py` (14 each);
- `raise TypeError`: 26;
- `warnings.warn`: 12.
- Tests: 100 `pytest.raises(AssemblyError…)` and 58
  `pytest.raises(ValueError…)`, many with `match=` on the text.

**Where.**  A new shared leaf `hexmesh/errors.py` (like
`hexmesh/version.py`: every package may import it, and it imports
nothing from hexmesh).  Every module that raises for user input;
`tests/test_architecture.py`; `API.md`.

**Do.**
1. **`hexmesh/errors.py`:**
   - `HexmeshError(ValueError)`, with keyword fields:
     - `code: str` (required);
     - `where: dict` (any of `fitting` index, `label`, `interface`,
       `field`, `part`, `source`: provenance such as file and line);
     - `value`, `limit` (a number, a range dict like
       `{"min_exclusive": 0.1}`, or the name of a `limits.py`
       constant);
     - `hint: str | None`.

     `str(err)` is the message exactly as today.  `err.to_dict()`
     returns all fields as JSON-safe data.
   - `HexmeshWarning(UserWarning)` with the same fields, for the 12
     `warnings.warn` sites.
   - `CODES: dict[str, str]`: every code, with a one-line description.
     Codes are `snake_case` and describe the rule, not the fitting, for
     example `bend_radius_below_outer_radius`, `counts_mismatch`,
     `switch_too_short`.  A code never changes once released; a new
     rule gets a new code.
2. **The existing classes become subclasses:** `AssemblyError`,
   `EquipmentError`, `LayoutError` and `StudyError` derive from
   `HexmeshError`.  They are still `ValueError`, so every existing
   `except` and `pytest.raises` keeps working.
3. **Code every error a user's input can cause.**
   - That is every raise reachable from a constructor, `PipeSpec`
     methods, `Assembly.add` / `close` / `validate` / `cell_count`,
     `from_dict` / `upgrade`, the readers, the builder and `study`.
   - Plain `ValueError` and `TypeError` raised for user input become
     the layer's `HexmeshError` subclass: add `SpecError` in `core`,
     and use `AssemblyError` in `assembly`.
   - Internal invariant checks, which are bugs if they fire, stay as
     they are.  List them in *Agent notes*, with how you decided
     (reachable from public input or not).
   - Fill `where`, `value`, `limit` and `hint` wherever the information
     is at hand.  Where a `limits.py` constant is the limit, pass its
     name.
   - Reader and builder errors put the network model's provenance in
     `where["source"]`.
4. **Warnings:** the 12 sites raise `HexmeshWarning` with codes.
   Existing `pytest.warns(UserWarning, …)` keeps working.
5. **Tests:**
   - An AST test in `tests/test_architecture.py`: every `raise` of a
     `HexmeshError` subclass, and every `warn` of a `HexmeshWarning`,
     passes a `code=` that is a string literal in `CODES`.  No code in
     `CODES` is unused.  The test plants one bad case, as the other
     architecture rules do.
   - A test that `to_dict()` round-trips through `json` for one error
     of each class.
   - Add at least one test per code family asserting `code` and `where`
     (not only `match=` on the text).
6. **API.md:** an "Errors" section with the fields, how to catch them,
   and the table of codes.  Generate the table from `CODES`, as task
   0078 does for the README sections, if that exists by then.
   Otherwise write it by hand, with a test that it lists every code.

**Accept.**
- Every message is unchanged.  Use the recorder method of tasks
  0083–0085: before and after, every expected exception's type and text
  are identical, except where a `ValueError` or `TypeError` became a
  `HexmeshError` subclass (list those).  Those are still `ValueError`.
- A former `TypeError` that becomes a `HexmeshError` is no longer a
  `TypeError`.  List each one in *Outcome*.  Keep it a `TypeError` too
  (multiple inheritance, `class SpecTypeError(SpecError, TypeError)`)
  if any test or caller catches `TypeError`.
- The architecture test passes, with its planted case.
- Every existing mesh is unchanged (`to_dict`, nodes and counts); this
  task changes no geometry.
- Full suite: no new failures.
- *Outcome*: the number of codes; the raises coded per package; the
  internal checks left uncoded; a sample `to_dict()` of a reader error
  with provenance.

**Out of scope.**
- Collecting several errors in one `validate()` call (`{ok, errors}`):
  decision 0040's CLI task decides that.  Note under *Agent notes*
  where `validate()` stops at the first error, if that would be easy to
  change.
- Rewording messages, and the schema and limits work (foundation B).
