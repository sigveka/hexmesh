# 0096 — PCF errors name the line: record `Provenance.line`

- **Status:** ready
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
