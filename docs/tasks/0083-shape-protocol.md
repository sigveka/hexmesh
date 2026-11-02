# 0083 — Shapes own their behaviour: the shape protocol

- **Status:** ready (after 0082)
- **Decision:** [0037 — Capability boundaries](../decisions/0037-capability-boundaries.md) (item 2); DESIGN §3.1 ("Shapes and section layouts own their behaviour")
- **Depends on:** 0082 (both touch `interface.py` and `spec.py`; 0082
  moves the layout dispatch first).

Ground rules for all tasks: [README](README.md#ground-rules).  This task
touches `core/`, `assembly/`, `interchange/` and `io/readers/`.

**Why.**  About 89 sites outside the shape and face code ask "which
shape is this?" and then compute the answer themselves (RESEARCH §12.2,
item 2).  The most are in `interchange/build.py` (25), `assembly/tee.py`
(15), `core/spec.py` (13), `assembly/wye.py` (8), `io/readers/pcf.py`
(6) and `assembly/interface.py` (6).  The free functions in
`interface.py` — `outer_radius`, `half_extent`, `hydraulic_diameter`,
`port_type` — switch on shape type.  Every new shape (contours,
decision 0018; eccentric cores, 0021) would edit all of them.  There
are three shapes already (`CircleShape`, `RectShape`, `BlendShape`), so
a protocol can be derived now, not guessed (DESIGN §6.1).

**Where.**  `core/shape.py` (the protocol and its three
implementations), then the callers: `core/spec.py`,
`assembly/interface.py`, `assembly/wye.py`, `assembly/fittings.py`,
`assembly/section_quality.py`, `assembly/intent.py`,
`interchange/build.py`, `io/readers/pcf.py`.

**Do.**
1. **List the questions.**  Go through every site the architecture
   test's shape cap counts, and group them by the question asked.
   Expected: outer extent (radius / half extent at an angle), hydraulic
   diameter, area, side counts, the outline at a corner parameter,
   serialisation, the symmetry period, and "is it round" for junction
   applicability.  Record the table (question → sites) in *Agent notes*.
2. **Define the protocol** in `core/shape.py` as a `typing.Protocol`
   with those questions as methods or properties.  Implement it on the
   three shapes.  No class hierarchy beyond what exists (DESIGN §6.1).
3. **Replace the switches** with protocol calls in `core/spec.py`,
   `assembly/interface.py` (its free functions become one-line
   delegations, or go), `wye.py`, `fittings.py`, `section_quality.py`,
   `intent.py`, `interchange/build.py` and `io/readers/pcf.py`.
4. **Junction applicability** is not a shape question.  "This tee
   supports circular mains only" belongs to the fitting.  Keep those
   checks in the fitting, phrased as the fitting's rule (a shape
   property such as `is_round` is fine; the type check isn't).
   `tee.py`'s duct branches go with the tee split (task 0060's design
   note), so leave `tee.py` to that task unless a change is mechanical.
5. **Lower the cap** in `tests/test_architecture.py` to the new count.
   Target: zero outside `tee.py` and the junction applicability checks.
   Report the count.

**Accept.**
- The protocol is implemented by all three shapes; a test checks each
  method against a known value per shape (circle, square, 2:1
  rectangle, a blend at u = 0.5).
- The shape-site cap is lowered; *Outcome* lists the remaining sites
  and why each stays.
- **No behaviour change:** task 0065's method (examples, conformance
  fixtures, interchange and reader fixtures).  `to_dict()`, cell
  counts, error messages and meshed node coordinates identical.
- Full suite: no new failures.

**Out of scope.**  New shapes; the tee split (0060); section layouts
(0082).

## Agent notes

## Questions for design

## Outcome
