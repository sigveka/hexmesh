# 0094 — Structured errors: a code, a location, the value and the limit

- **Status:** done
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

## Agent notes

**Steps refined.**
- `AssemblyError` and the new `AssemblyTypeError` live in the leaf
  `hexmesh/assembly/errors.py`, because `fittings` and the junctions
  raise them and `assembler` imports `fittings`.  `assembler` re-exports
  both, so `from hexmesh.assembly.assembler import AssemblyError` still
  works.
- `SpecError` and `SpecTypeError` are in `hexmesh/errors.py`: `core` is
  the bottom capability, so it has no package-level leaf of its own.
- I added `ReaderError(HexmeshError)` for `io.readers` (PCF units,
  bathymetry formats) and for the files `io.writers` reads back (`.msh`
  recipe block, OpenFOAM `boundary`, role manifest).  The readers can't
  raise `AssemblyError`: `io.writers` must not import `assembly`.  I
  also added `StudyTypeError(StudyError, TypeError)` for the
  post-processing result check.
- `HexmeshError.wrap(err, message, *, code, **where)`: the assembler
  re-raises a fitting's error with a location prefix.  `wrap` keeps the
  inner error's `code`, `value`, `limit` and `hint`, and merges its
  `where` with the location.  A plain `ValueError` gets the outer code
  (`fitting_invalid`, `section_not_supported`, …).  Used by `Assembly`
  (`add`, `validate`, `fill`), the network builder (one piece of
  `build_pieces`, junctions, bends), `Transition` and `duct_tap`.
- Fields survive pickling (`__reduce__`), so a study worker process's
  error arrives whole.
- Unregistered codes fail at construction (`KeyError`), as well as in
  the architecture test.
- A class that codes itself in `__init__` (`PreflightFailed`,
  `LayoutNotSupported`) is raised without `code=`.  The architecture rule
  reads the code from its `__init__`.
- Builder provenance: `build._source(x)` turns a part's `Provenance`
  into `{file, format, record, record_id, line, guid}`, dropping empty
  fields.  The PCF reader records no line numbers, so PCF errors carry
  no `line`.
- Codes shared across fittings for the same rule: `size_not_positive`,
  `value_not_positive`, `count_below_minimum`, `angle_out_of_range`,
  `option_invalid`, `counts_mismatch`, `rot_mismatch`,
  `fitting_not_resolved`, `n_layers_unresolved`,
  `outlet_frame_mismatch`, `predicted_sj_below_minimum`,
  `run_length_too_short`, `branch_length_too_short`, `switch_too_short`,
  `cell_budget_exceeded`, `cores_exceeded`.
- `limit` holds a `hexmesh.assembly.limits` constant's name where one is
  the bound; otherwise a number, a range dict or the allowed values.

**Internal checks left uncoded (plain `ValueError` / `TypeError`).**
I decided by asking whether public input can reach the check before a
coded check rejects it:

| site | check | why internal |
|------|-------|--------------|
| `assembly/sweep.py` `Path.__post_init__` (5) | one count per slab, ≥ 1 axial layer, prism/blend slabs one layer | `Path` is built by fittings from resolved counts |
| `assembly/sweep.py` `_fill_slab` (2) | the face has the layers the slab fills; it joins matching layers | stack changes are checked first (`stack_change_*`, `layer_termination_*`) |
| `assembly/wye.py` `to_wall` | a ray leaves the wye | the geometry is the wye's own |
| `assembly/projection.py` `nearest` | the wall projection finds a point for every node | likewise |
| `assembly/corners.py` `connect_patch` | a one-patch face has no layers outside its core | H shells are routed before this |
| `assembly/equipment.py` `head_height` | the radius is inside the drum | callers pass footprints already checked (`nozzle_footprint_outside`) |
| `assembly/signature.py` `signature`, `strategies_for` (TypeError) | each layer type has a signature; each fitting declares strategies | hexmesh's own classes (DESIGN A4) |
| `core/cross_section.py` `__post_init__` (2) | 4 or 8 outer points; curve count matches | built by `sections` |
| `core/shape.py` `outline`, `core_wall_span`; `sections/oh.py` `outline` | an outline exists for the shape; the layout has a core ring | hexmesh's own shape classes |
| `sections/h.py` `build_h_rect` (TypeError) | the H face is a rectangle | `PipeSpec` rejects H on other shapes (`h_layout_needs_rectangle`) |
| `sections/oh_gmsh.py` `build_oh_circle8`, `build_annulus` | even nang; positive dR | `PipeSpec` checks `nang_not_divisible`, `size_not_positive` first |
| `quality_hex.py` `_aggregate` | the aggregation mode | private; modes come from hexmesh |
| `interchange/build.py` `_elbow_params` (3) | the bend's corner point | its only caller wraps it as `bend_geometry_invalid` |
| `io/writers/msh_comments.py` `block` | no `$Comments` line ends the block | the recipe is JSON-escaped first |
| `study/openfoam.py` `read_patch_values` | a solver's patch value is a list | OpenFOAM's output, not the user's |

**Where `validate()` stops at the first error.**  `Assembly.validate()`
is two loops, interfaces then fittings (`assembler.py` from line 527).
Each check raises at once, so collecting would be easy.  Every raise in
the loops is an `AssemblyError` or `AssemblyError.wrap`.  Append those to a
list instead, and at the end raise the first (today's behaviour) or
return `{ok, errors: [e.to_dict() …]}`.  Two cases need care:
- a fitting's check that fails at `resolve` (inside `Assembly.add`)
  happens before `validate`;
- some later checks assume earlier ones passed (port types after
  `check`).  Those should skip a fitting that has already failed.
`PipeSpec` and the fitting constructors raise at the first problem
inside each method.  They would need the same change, one method at a
time.

## Questions for design

None.

## Outcome

**Files.**
- New: `hexmesh/errors.py` (the shared leaf: `HexmeshError`,
  `HexmeshWarning`, `SpecError`, `SpecTypeError`, `ReaderError`, `CODES`,
  `jsonable`); `hexmesh/assembly/errors.py` (`AssemblyError`,
  `AssemblyTypeError`); `tests/test_errors.py`.
- Coded: `core` (`spec`, `grading`, `shape`); `assembly` (`assembler`,
  `fittings`, `sweep`, `profile`, `duct_tap`, `tee`, `switch`, `wye`,
  `blocks`, `corners`, `equipment`, `intent`, `interface`,
  `section_quality`, `signature`); `interchange` (`build`, `model`);
  `io/readers` (`pcf`, `bathymetry`); `io/writers` (`msh_comments`,
  `openfoam_boundary`); `study` (`__init__`, `definition`, `manifest`,
  `openfoam`, `sampling`, `stages`).
- Exports: `hexmesh.HexmeshError`, `hexmesh.HexmeshWarning`, and
  `hexmesh.assembly.AssemblyTypeError`.
- `tests/test_architecture.py`: `hexmesh.errors` is a shared leaf.  New
  rule `code_violations`, with planted cases.
- `API.md` § Errors, with the table of codes.  `CHANGELOG.md`
  (Unreleased).

**Counts.**
- 275 codes in `CODES`.
- 405 coded error constructions: `assembly` 236, `interchange` 60,
  `core` 52, `study` 41, `io/readers` 8, `io/writers` 8.  This counts
  `raise X(…)`, `X.wrap(…)` and the two classes that code themselves.
- 13 coded warnings: `assembly` 6, `io/readers` 5, `io/writers` 1,
  `study` 1.
- 27 internal checks left uncoded (*Agent notes*).

**Messages unchanged** (the recorder plugin over the full suite, HEAD
3a4bc6a against the working tree):
- 390 recorded raises and warnings before.  After, 398: the 8 extra are
  `tests/test_errors.py`'s.
- Every text is identical.  The only differences are 3 messages that
  embed pytest's `tmp_path`, whose run number differs between runs.
- No raise or warning lost its `ValueError` or `TypeError` base.
- Type changes:

  | before | after | records |
  |--------|-------|---------|
  | `hexmesh.assembly.assembler.AssemblyError` | `hexmesh.assembly.errors.AssemblyError` (moved, re-exported) | 192 |
  | `ValueError` | `AssemblyError` | 52 |
  | `ValueError` | `SpecError` | 30 |
  | `ValueError` | `StudyError` | 7 |
  | `ValueError` | `ReaderError` | 1 |
  | `TypeError` | `SpecTypeError` (still a `TypeError`) | 7 |
  | `TypeError` | `AssemblyTypeError` (still a `TypeError`) | 4 |
  | `UserWarning` | `HexmeshWarning` (a `UserWarning`) | 20 |

- Former `TypeError`s, now also a `HexmeshError`.  Each keeps
  `TypeError` by multiple inheritance:
  - `SpecTypeError` (14 sites in `core/spec.py`):
    - `PipeSpec.core`: `shape=` with geometry keywords, or neither
      (`shape_args_conflict`, `shape_args_missing`), or a size without
      the spec's `nang` (`nang_missing`);
    - grading: `mprg=` with `first_cell=` (`grading_args_conflict`),
      `wall_bump=` on a non-H core, `first_cell=` on an unsupported core;
    - a shell without `nrad`, a shape that can't be serialised, a bundle
      pipe whose outer shell is not a rectangle;
  - `AssemblyTypeError` (7 sites):
    - `Assembly.add` from a non-`Interface` source;
    - `prepend` of a fitting other than a `Straight`;
    - a `Closure` added directly;
    - `Tee`'s missing or conflicting branch arguments;
    - a fitting `intent` can't serialise;
    - `NetworkModel.add_part`'s part type;
  - `StudyTypeError`: post-processing that returns a non-dict.

**Meshes unchanged.**  All 28 examples (`hexmesh.examples.ALL`) were
meshed at HEAD and on the working tree.  The SHA-256 of the `.msh`
`$Nodes` and `$Elements` sections and of the recipe (`to_dict`) are
identical for every one.

**Sample:** a builder error on a PCF file, with provenance.  The
elbow states `ANGLE 4600`, but its geometry gives 90°.

```json
{"type": "AssemblyError", "code": "stated_angle_disagrees",
 "message": "component 1 (ELBOW ELBOW_1 at [1. 0. 0.]): ANGLE 46° disagrees with the 90° from its END-POINTs and CENTRE-POINT",
 "where": {"part": "1",
           "source": {"file": ".../line.pcf", "format": "pcf",
                      "record": "ELBOW", "record_id": "1"}},
 "value": 46.0, "limit": 90.0, "hint": null}
```

**Tests.**  `tests/test_errors.py` has 22 tests:
- fields and message;
- refusal of an unregistered code;
- the former types kept;
- `to_dict` through `json` and through `pickle`;
- `jsonable`;
- `wrap`;
- one test per family (spec, assembly with `where` fitting/label,
  equipment, layout, study, reader, builder with provenance, warning);
- API.md lists every code.

`tests/test_architecture.py` has 10 planted cases for the code rule:
- no code;
- a code that is not a literal;
- an unregistered code;
- a `wrap` without a code;
- an uncoded warning;
- a self-coding class;
- a plain `ValueError`;
- a class used but never imported;
- unused registered codes.

Full suite: 3197 passed, 15 skipped (3163 at HEAD, plus 34 new).

**Surprises.**
- The recorder run caught 2 failures that no per-file check had: the
  `io/writers` modules raised `ReaderError` and `HexmeshWarning`
  without importing them.  An earlier chained command had stopped
  before adding the imports.  The architecture rule now also requires
  a coded class to be imported or defined in the module that uses it.
- `Straight(-1, 4)` and `Bend(radius < outer radius)` pass
  `Assembly.add`.  The fitting checks run in `validate()` (and `fill`),
  not at add.  That is today's behaviour, unchanged here.
- PCF provenance has no line numbers (`Provenance.line` is never set),
  so PCF errors locate by record and component index.

**Proposed follow-ups.**
- Have the PCF reader record each component's line in `Provenance.line`
  (small: `_iter_records` knows it).  `where["source"]["line"]` then
  points into the file.
- Let `validate()` collect errors (see *Agent notes*) when the CLI task
  of decision 0040 decides the `{ok, errors}` shape.
- Generate API.md's code table from `CODES` once task 0078's README
  generator exists.  It is written by hand today, and a test keeps it
  complete.
