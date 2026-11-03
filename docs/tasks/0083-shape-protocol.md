# 0083 — Shapes own their behaviour: the shape protocol

- **Status:** done
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

- **Design refinement (design session, 2026-11-03, the user agreed;
  answer to 0082's Q1).**  The O-H formulas move from `core` to
  `sections` (decision 0037: sections own their layout).  DESIGN §3.1
  doesn't make layout geometry part of `core`.  Once the shape protocol
  exists, `core` asks the shape for shape geometry only.  Three places
  get their layout-dependent part from `sections`, through the protocol
  or a caller-supplied layout, not by importing it:
  - `spec.corners()`;
  - `first_cell`'s wall span;
  - `BlendShape`'s inner outline.

  The `core/shape.py` section "O-H face geometry" then moves to
  `sections/oh.py`.  Any of the three that can't be done without `core`
  importing `sections` goes under *Questions for design*.
- **Step 1, the questions** (the 59 sites the cap counted at 0082):

  | question | sites | answer |
  |---|---|---|
  | hydraulic diameter | `interface.hydraulic_diameter` (6) | `shape.hydraulic_diameter` |
  | side counts of the core | `spec.side_counts` (3) | `shape.side_count(k, n)` (existed) |
  | density parameters it sets | `spec._validate_shape_nang` (8), `fittings._counts` (1) | `shape.angular_counts` |
  | is it round (a fitting's or option's rule) | `spec.core(first_cell=)` (1), `section_quality.changes_shape` (2), `equipment` (1), `Transition` "use Reducer" (1), wye (2), tee `_check_circle` (2) | `shape.is_round` |
  | is it a `Transition` station | `interface.check_supported` (1), `section_quality` (1), `Transition.check` (1) | `shape.is_station` |
  | a description for messages | `section_quality._describe` (3) | `shape.label` |
  | flat sides (cells tile) | `BundleSpec` (1) | `side_curve == "line"` (existed) |
  | the round core's radius | `first_cell` (1), wye (6), `interchange/build` (3) | `max_extent` (existed) |
  | tee: branch and main dispatch, radii | `tee.py` (15) | left for the tee split (0060) |

  `pcf.py` and `intent.py` had no sites left by 0082 (the cruder grep of
  RESEARCH §12 counted them).  The area and the outline at a corner
  parameter weren't asked anywhere outside the shape code, so the
  protocol doesn't have them.
- **Step 2:** `Shape` is a `typing.Protocol` (`runtime_checkable`) in
  `core/shape.py`, replacing the `Union` alias of the same name.  Its
  members are `is_round`, `is_station`, `hydraulic_diameter`,
  `angular_counts`, `label`, and the existing `side_curve`,
  `max_extent`, `counts`, `corner`, `corners_from`, `side_count`,
  `extent` and `period`.  All three shapes implement it.  A blend's
  `hydraulic_diameter` comes from its sampled `boundary`.  Circles and
  rectangles also keep the ring and offset methods, which a blend
  doesn't have.  The module docstring says so.
- **Kept behaviour:**
  - `_validate_shape_nang` skips stations (`is_station`), as the old
    `isinstance` chain did implicitly.  Messages are unchanged, as
    `f"{type(shape).__name__}.{name}=…"`.
  - `spec.side_counts` uses `n_outer` on a round core and 4 otherwise,
    as before.

- **The design refinement, done as far as it goes without `core`
  importing `sections`:**
  - Moved to `sections/oh.py`:
    - `oh_ring_thickness` → `oh.ring_thickness`;
    - `oh_inner_corner` → `oh.inner_corner`;
    - `oh_inner_arc_centre` → `oh.inner_arc_centre`;
    - the inner outlines of circles and rectangles;
    - `BlendShape`'s inner blend, as `oh.outline(shape, k, s, inner)`.
  - `BlendShape.outline(k, s)` and `core.shape.outline(shape, k, s)`
    keep the outer curves only.  The callers use `oh.outline`:
    `section_quality`, the blend builder, `oh.core_corners` and
    `test_transition`.  `tee` and `duct_tap` call `oh.ring_thickness`.
  - Left in `core/shape.py`: `OH_RATIO` and `oh_core_wall_span`, for
    `first_cell` (Question 1).  `spec.corners()` is unchanged; it uses
    `shape.corner(k)` and `ring_corner` from the outline protocol
    (Question 2).
- **Remaining `OH_RATIO` uses** outside `core/shape.py` and `sections`:
  `tee.py:353–354`, `wye.py:386` and `duct_tap.py:242`, the junction
  blocks.  Task 0086 moves them (design answer to 0082's Q2).

## Questions for design

Neither blocks.

1. **`first_cell` needs the O-H wall span when the spec is built**, so
   `OH_RATIO` and `oh_core_wall_span` stay in `core`.
   `PipeSpec.core(first_cell=)` solves `_core_mprg` immediately, and
   `to_dict`, `port_type`, the signature and the layouts all read it.
   `core` has no layout to ask.  The ways out I see:
   - (a) The spec keeps `first_cell` and resolves the grading lazily,
     through a hook that `sections` registers on import.  That is
     implicit global state.
   - (b) When task 0084 adds `layout=` to the spec, the wall span
     becomes a question the *layout* answers.  `core` would still need
     the layout object, which lives in `sections`.
   - (c) Accept that the O-H ratio is a spec-level constant in `core`.

   I lean to (b), decided together with 0084.  It isn't something to
   build now.
2. **Are a shape's own corners shape geometry or layout?**
   `shape.corner(k)` puts a circle's corners at 45° + k·90°, which is
   the O-H face's choice.  `spec.corners()` chains rings from there,
   and `PipeSpec.shell()` uses it in `core` to check ring thickness
   (`longest_radial`).  The H layout (0084) has the same corners, so
   nothing conflicts yet.  A layout with other corners would need
   `spec.corners()` to come from `sections`.  That runs into the same
   problem as Question 1, because the check runs inside `shell()`.

## Outcome

- **Files.**
  - `core/shape.py`:
    - the `Shape` protocol (replacing the `Union` alias), with its
      members on the three shapes;
    - the O-H section reduced to `OH_RATIO` and `oh_core_wall_span`;
    - outer outlines only.
  - `sections/oh.py`: the moved formulas.
  - Callers: `core/spec.py`,
    `assembly/{interface,section_quality,fittings,equipment,wye,tee,duct_tap}.py`,
    `interchange/build.py`, `sections/oh_gmsh.py`.
  - Tests: new `tests/test_shape_protocol.py` (6 tests);
    `tests/test_architecture.py` (cap); `tests/test_transition.py`
    (imports `oh.outline`).
  - Also: `validation/{layered_conduction,rect_duct}/run.py` tolerance
    comments now cite the accepted limits (design request, 0093).
- **Shape sites: 59 → 15**, all in `tee.py`:
  - the duct-or-pipe main dispatch (`_is_duct`);
  - the `branch=CircleShape` shorthand and duct branches (`resolve`,
    `_resolve_duct`, `ports`, `layout`);
  - main radius reads (`thicknesses`, `resolve`, `layout`).

  All of them go with the tee split (0060).  `_check_circle`, the
  tee's applicability rule, now uses `is_round`.
- **Protocol test**: circle, square, 2:1 rectangle and a blend at
  u = 0.5 (two squares, so the expected values are closed-form).  Each
  checks every protocol member, plus a blended circle's sampled
  hydraulic diameter (within 1e-5).
- **No behaviour change** (task 0065's method, extended).  I recorded
  the whole suite before and after each of the two commits.  The
  recorder also stored the type and message of every exception a test
  expects through `pytest.raises` (332 of them), as well as every
  warning.
  - 1168 meshes, 439 distinct.  Nodes, tags, `to_dict` and cell counts
    are identical.
  - All 634 messages are identical once tmp paths are masked and sets
    sorted.  One remains: `test_port_not_tiled` reports a different
    port face from run to run.  That depends only on the hash seed:
    unchanged code gave five different faces across eight
    `PYTHONHASHSEED`s.
  - Recorder artefact: the module-scoped `snapshots` cache in
    `test_topology_invariance` is built by whichever test reaches it
    first on each xdist worker, so its meshes change keys between
    runs.  The comparison matches meshes by content.
- **Full suite:** 2326 passed, 15 skipped, 0 failed.
- **Line counts**, at 6546043 → now:
  - `core/shape.py` 471 → 531 (protocol +, O-H formulas −);
  - `sections/oh.py` 197 → 272;
  - `interface.py` 294 → 288; `spec.py` 667 → 670;
    `section_quality.py` 266 → 270; `fittings.py` 1025 → 1035;
    `interchange/build.py` 1310 → 1323 (one docstring).
- **Surprises.**
  - Two error messages put a `set` into the message, so their order
    changes with the hash seed: the `LayoutError` port-face and
    grading-conflict messages in `assembly/blocks.py`.  That's
    harmless, but it isn't reproducible.  Sorting them would make
    messages deterministic (proposed follow-up, small).
  - `pcf.py` and `intent.py` had no sites left by the time of this
    task.
- **Follow-ups (proposed).**
  - Deterministic `LayoutError` messages.
  - Questions 1 and 2, with 0084.
- **Disk:** the recordings (305 MB, in the scratchpad) were deleted
  after the comparison.  Nothing in the repo.

