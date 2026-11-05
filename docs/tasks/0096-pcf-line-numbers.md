# 0096 — PCF errors name the line: record `Provenance.line`

- **Status:** done
- **Decision:** [0040 — Agents for users](../decisions/0040-user-agents-network-design-and-resolution.md) (errors that point to the user's own input); [0032](../decisions/0032-network-interchange.md) (provenance); task 0094's proposed follow-up
- **Depends on:** 0094 (done).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  An error in an imported PCF network says which component
failed, through `where["source"]` (task 0094), but not where it is in
the file.  `interchange.model.Provenance` has a `line` field, which the
PCF importer never sets.  `io/readers/pcf.py:827` builds the
provenance with the record type and the component index only.  Users
and decision 0040's network designer need `plant.pcf:214`, the place to
look.

**Where.**  `io/readers/pcf.py`: the parser, `ComponentSpec`, and the
provenance at about line 827.  Connections and equipment blocks too
(about line 878 and line 892).  Tests in `tests/test_pcf*.py`.

**Do.**
1. While parsing, keep the 1-based line number where each record starts
   (the line of the record keyword, e.g. `ELBOW`).  Store it on
   `ComponentSpec` (a new `line: int | None` field), and on connection
   and equipment records.
   - Files merged by `read_pcf` (several files, `net.pipelines.update`)
     keep each record's own `source` and line.
2. Pass it into `Provenance(line=…)` for parts, ports and connections.
3. Where an error message describes a part from its provenance
   (`interchange.model.describe` and the formatter that
   `register_formatter` registers for PCF), add `file:line` when both
   are known.
   - **This changes message text,** which task 0094 kept fixed.  It's
     wanted here.  List every message that changes, before and after,
     in *Outcome*.
   - The tests' `match=` patterns may need updating; update them, and
     list them too.
4. `where["source"]` in the structured error carries `line`.
5. **Bathymetry:** if its route records have line or feature numbers, do
   the same; otherwise note it.

**Accept.**
- A test reads a small PCF with a deliberate error at a known line (a
  bend tighter than the pipe's outer radius, say).  The error's message
  and `where["source"]["line"]` name that line, and the file.
- A multi-file `read_pcf`: each record keeps its own file and line.
- Every mesh is unchanged (the 0065 method over the PCF examples and
  tests).  Message changes are only the added `file:line`.
- Full suite: no new failures.

**Out of scope.**  Column positions; other formats' line numbers
(future importers record them from the start).

## Agent notes

- `_iter_records` yields `(record_type, attrs, pipeline, line)`, where
  *line* is the 1-based line of the record keyword (comments and blank
  lines count).  `ComponentSpec.line` is new.
- Connection and equipment blocks keep their file and line in their
  attributes as `_source` and `_line`, beside the existing private
  `_point`.  So a multi-file `read_pcf` keeps each record's own file
  for `Terminal`s and declared connections too.  Before, those took
  the merged `net.source`, which is `"a.pcf, b.pcf"`.
- `interchange.model.Connection` gets a `provenance` field (default
  None).  The PCF reader sets it on declared `END-CONNECTION-PIPELINE`
  connections.
- Message form: `component 1 (ELBOW ELBOW_1 at [1. 0. 0.], plant.pcf:7)`,
  and `END-CONNECTION-EQUIPMENT V-102/N2 (plant.pcf:30)` for a terminal.
  The text uses the file name; `where["source"]["file"]` keeps the path
  as given.
- The two skip warnings (`pcf_component_unsupported`,
  `pcf_component_incomplete`) carry `line` in `where["source"]`.  Their
  text is unchanged.
- **The task's example error doesn't work:** a bend tighter than the
  pipe's outer radius doesn't reach the PCF line.  The *assembly* finds
  that error (`bend_radius_below_outer_radius`) in `validate()`, and it
  names the fitting (`fitting #1 Bend(…)`, `where` = fitting and label)
  with no PCF provenance.  The assembly never sees the source.  The
  acceptance test uses an error the *builder* finds at a known line (a
  stated `ANGLE` that disagrees with the geometry); see *Questions for
  design*.
- **Bathymetry:** the route is one `Polyline` through waypoints
  interpolated from the route file (CSV rows or a Shapefile feature).
  Its records don't map to parts, so there is no per-part line or
  feature number to record.  Left as it is.

## Questions for design

1. **Assembly errors on an imported network.**  The assembly checks
   fittings: bend radius, run lengths, predicted quality.  Its errors
   on a PCF-built assembly name `fitting #k` and its label (e.g.
   `ELBOW_1`), but not the file or line.  Two options:
   - (a) The builder passes each part's provenance to `Assembly.add`
     (a new keyword, e.g. `origin=`).  The assembler's wrap adds it to
     `where["source"]` and the message.  This is a small API addition
     on `Assembly`, used only by importers.
   - (b) The builder runs `validate()` at build time and re-raises with
     the part's description and source.  That moves the error earlier,
     to `to_assembly`, and validates twice.

   I lean to (a).  Which one, if either?

   **Answer (design, 2026-11-05; the user: "yes"):** (a), as a follow-up
   commit in this task, with three conditions:
   - *Diagnostic only.*  `origin` is not written to `to_dict` or to the
     `.msh` recipe (decision 0038: the recipe holds no paths).  It takes
     no part in comparisons, and `from_dict` assemblies have none.
   - *Dependency direction.*  `Assembly.add` / `close` / `prepend` take
     a plain JSON-safe mapping, copied as given, never
     `interchange.Provenance`.  The builder converts.
   - *Where it shows.*  Every error the assembler raises about the
     fitting carries it in `where["source"]`.  The message appends
     `, <file>:<line>` in the fitting's description.  Text changes only
     for fittings that have an origin.

   (b) was rejected: it copies the assembly's rules into the builder.

## Outcome

**Files.**
- `hexmesh/io/readers/pcf.py`: line tracking in the parser,
  `ComponentSpec.line`, provenance with `line` for parts, ports,
  terminals and declared connections, and `file:line` in the formatter.
- `hexmesh/interchange/model.py`: `Connection.provenance`.
- `API.md`: the `Connection` row and the formatter note.
- Tests:
  - `tests/test_io_readers.py`: `test_error_names_the_file_and_line`,
    `test_each_file_keeps_its_records_lines`;
  - `tests/test_errors.py`: the provenance sample asserts `line`;
  - `tests/test_pcf_insulation_equipment.py`: two `match=` patterns
    updated (`test_equipment_position_mismatch`, both cases).

**Messages changed.**
- Recorder over the full suite, 44a52a4 against the working tree.
- Every changed message differs only by the added `, <file>:<line>`
  inside a component's parentheses, or ` (<file>:<line>)` after a
  terminal.  This was checked by stripping those from the after-text,
  which then equals the before-text in every case.
- 27 recorded messages changed, plus the 2 whose test ids changed with
  their patterns.  Every message that describes a PCF part or terminal
  changes; by test:

  | test | messages |
  |------|----------|
  | `test_pcf_junctions::test_rejections_name_the_component` | 9 |
  | `test_pcf_insulation_equipment::test_insulation_errors_name_the_component` | 4 |
  | `test_io_readers::test_elbow_cross_check_names_the_component` | 3 |
  | `test_pcf_insulation_equipment::test_equipment_position_mismatch` (patterns updated) | 2 |
  | `test_io_readers`: `eccentric_reducer_rejected`, `elbow_leg_must_follow_the_incoming_pipe`, `gap_names_the_component`, `kinks_rejected_or_splined`, `lateral_offset_within_tolerance_is_absorbed`, `wrong_elbow_end_point` | 1 each |
  | `test_pcf_junctions::test_root_by_name_and_point` | 1 |
  | `test_pcf_robustness`: `angled_inline_component_rejected_by_name`, `equal_tee_message_says_planned`, `several_pieces_to_assembly_lists_them` | 1 each |
  | `test_errors::test_builder_error_carries_provenance` | 1 |

- Example, before → after:
  `component 1 (ELBOW ELBOW_1 at [1. 0. 0.]): ANGLE 46° disagrees …` →
  `component 1 (ELBOW ELBOW_1 at [1. 0. 0.], line.pcf:7): ANGLE 46° disagrees …`
- No error or warning changed type.

**Meshes unchanged.**  All 28 examples (the PCF networks among them)
were meshed at 44a52a4 and on the working tree.  The SHA-256 of `$Nodes`,
`$Elements` and the recipe are identical for every one.

**Full suite:** 3199 passed, 15 skipped (3197 before, plus 2 new tests).

**Proposed.**  Question 1 above: carry provenance into assembly-level
errors.

### Follow-up: origins on assembly fittings (design answer to Q1)

**Files.**
- `hexmesh/assembly/assembler.py`:
  - `Edge.origin`, and `Edge.at` (the `, <file>:<line>` suffix).
  - `Edge.where` (`fitting`, `label`, and `source` from `origin`);
    `Edge.__repr__` appends `at`.
  - `add` / `close` / `prepend(…, origin=None)`.  The mapping is copied
    with `dict()`.
  - The errors raised at `resolve` time carry it too (no edge exists
    yet).
  - Every fitting-located error and warning uses `edge.where`: validate,
    the quality warnings, switch classes, port types, the cell budget,
    fill failures, and the mesh-time projection, SJ and
    non-orthogonality checks.  The mesh-time messages, which start with
    the fitting's name, get the suffix after the name.
- `hexmesh/interchange/build.py`: each `asm.add` passes
  `origin=_source(part)`.  A `SplinePipe` joining several pipes takes
  its first pipe's origin.
- `API.md`: `origin=` on `add`, `close` and `prepend`.
- `tests/test_io_readers.py`:
  - `test_assembly_error_names_the_file_and_line`: the task's original
    example.  An ELBOW at line 7 of radius 50 mm on a 110 mm pipe gives
    `fitting #1 Bend(…), line.pcf:7: path bends with radius 0.05, …`,
    with `where["source"]["line"] == 7`;
  - `test_origin_is_diagnostic_only`: a PCF assembly (every edge has an
    origin) and its `from_dict` copy (none) give equal `to_dict` and
    identical `.msh` bytes, and the `.msh` holds no path.

`fill()` passes a fitting's own `AssemblyError` through unchanged, as
before, so those errors don't carry the origin.

**Checked.**
- Recorder over the full suite, d96fef1 against the working tree:
  - one existing message changed, `test_io_readers::test_spool_set_on_on_layered_spec`
    (an assembly error on a PCF-built tee), and only by the added
    `, line.pcf:<n>`;
  - no other message, and no type, changed;
  - the one new record is the new test's.
- All 28 example meshes: `$Nodes`, `$Elements` and the recipe hash are
  identical.
- Full suite: 3201 passed, 15 skipped (3199 before, plus 2 new).
