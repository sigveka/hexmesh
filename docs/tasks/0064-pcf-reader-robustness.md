# 0064 — PCF reader robustness: annotations, unknown inline components, several networks

- **Status:** done (2026-11-02)
- **Decision:** [0023 — PCF input](../decisions/0023-pcf-branched-networks-insulation-equipment.md) (reader behaviour)
- **Depends on:** —  (independent of the junction work)

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  New sample PCFs (spoolyard's test fixtures, AGPL, local use
only; `docs/integrations/pcf.md`, "More sample files", 2026-10-29)
expose three gaps:
- **Noise:** annotation records (`MESSAGE-SQUARE`, `TEXT`, a `WELD`
  given by `CO-ORDS`, `END-POSITION-OPEN`, …) are reported as
  "unsupported component".
- **A misleading error:** an unknown component between two pipes is
  skipped, so the next pipe "starts 0.3 m from the open end"; the
  message doesn't name the real cause.
- **Several pipelines in one file** that don't connect fail as "the
  network must be one connected piece", with no way to read them.

**Where.**  `hexmesh/io/readers/pcf.py` (`_classify`, the skip and
absorb logic, `NetworkSpec`), tests, `API.md`, `docs/integrations/pcf.md`.

**Do.**
1. **Annotation records** (no geometry, nothing to mesh): read and
   ignore quietly, counted in `NetworkSpec.report["ignored"]` by type.
   Take the list from the PCF guide's non-component records (messages,
   text, supports, bolts, iso-split points, end-position markers, welds
   given only by `CO-ORDS`, …), and record it in `pcf.md`.  "Unsupported"
   warnings remain for genuinely unknown records.
2. **Inline components the reader doesn't know** (any type with two
   `END-POINT`s):
   - **collinear, same bore:** a `Straight`, with one warning per type
     ("UNION treated as an inline straight").  That covers `UNION`,
     `MISC-COMPONENT` and invented types like spoolyard's `FROBNICATOR`;
   - **different bores:** a `Reducer`, with the same kind of warning, if
     collinear;
   - **direction change inside the component** (`VALVE-ANGLE`, end
     points at 90°): `AssemblyError` naming the component, its type and
     the angle.  Angle valves are out of scope; say so in the message.
3. **Several connected pieces:** `NetworkSpec.to_assemblies(spec, …)`
   returns one `Assembly` per connected piece, in file order, each named
   after its first pipeline reference.  `to_assembly` on a multi-piece
   file raises, listing the pieces (pipeline references and component
   ranges) and pointing to `to_assemblies`.
4. **Tests:**
   - hand-written fixtures for each behaviour, in our own text (no
     copied content);
   - optionally, a test that runs the spoolyard fixtures when an
     environment variable points at a local directory of them (skipped
     otherwise, never committed).
5. Update `pcf.md`'s results table for the spoolyard fixtures.

**Accept.**
- Imperial fixture: the only error is the equal tee (unchanged); no
  warnings for annotation records.
- Metric fixture: `FROBNICATOR`, `UNION` and `MISC-COMPONENT` become
  straights with warnings, `VALVE-ANGLE` is rejected by name, and
  `to_assemblies` returns two networks (or the angle-valve error first;
  report which).
- Existing reader tests unchanged.
- Full suite: no new failures.

**Equal tees** (decision 0031's amendment): keep rejecting them, but say
they're planned: "equal tees (branch radius = main radius) are planned
through the wye-family layout; not available yet".  A tee with
τ < r/R < 1 gets 0031's hint once τ exists in `limits.py`.

**Out of scope.**  Angle valves as fittings; building equal tees; eccentric reducers as anything but their concentric
equivalent (record what the reader does today).

## Agent notes

- **Annotation list** from the guide's "Information Items" (messages,
  reference dimensions, TML, other information items) and "End Connection
  and Position Types": `pcf.ANNOTATION_TYPES`, recorded in `pcf.md`.
  Also a `WELD` with `CO-ORDS` and no `END-POINT`s.  The existing
  `ignore_types` (supports, bolts, …) are counted in `report["ignored"]`
  too, since they are the same kind of record.  An annotation before the
  first `PIPELINE-REFERENCE` was read as a header keyword; now it isn't.
- **`report["ignored"]`** is filled by `read_pcf` (summed over a list of
  files) and kept through `to_assembly`, which used to replace the report.
- **Unknown inline components** are classified at read time
  (`_inline_kind`): `"fitting"` (a straight), `"reducer"`, or
  `"angled"` when the legs turn at `CENTRE-POINT` by more than
  `INLINE_ANGLE_TOL` (1°).  Without a `CENTRE-POINT` there is no angle to
  see: the two end points make a straight chord, and a turn shows up as a
  kink against the next component (the existing check).
- **Several pieces.**  `_pieces` finds them by end points (and a set-on's
  or Y piece's CENTRE-POINT on its host pipe), before any host is split.
  `to_assembly` keeps its existing gap message (tests rely on it, and it
  names the nearest gap, which is right for a single pipeline with a
  real gap) and appends the piece list and `to_assemblies`.  I first
  checked for pieces before the graph; that hid the set-on and elbow
  errors, so it moved into the tree check.
- **`to_assemblies` returns `{name: Assembly}`**: the task asks for each
  to be named after its pipeline, and `Assembly` has no name.  Each
  piece's fittings keep their whole-file labels and indices (a
  `labels=` argument to `_build_assembly`).
- **Equal tees:** the message now says they're planned.  The τ hint
  (task's last paragraph) waits for τ in `limits.py`; there is none yet.

## Questions for design

_None._

## Outcome

Done 2026-11-02.

- **Files:** `hexmesh/io/readers/pcf.py` (`ANNOTATION_TYPES`,
  `INLINE_ANGLE_TOL`, `_inline_kind`, `_reject_unsupported`, `_pieces`,
  `NetworkSpec.to_assemblies`, the equal-tee message);
  `tests/test_pcf_robustness.py` (new: 11 tests, plus one that runs local
  sample files when `HEXMESH_PCF_SAMPLES` is set); `API.md`;
  `docs/integrations/pcf.md` (the annotation list; the spoolyard table
  after this task).
- **Tests:** the 76 existing PCF tests pass unchanged.  Full suite 2156
  passed, 15 skipped (the local-samples test skips without its directory).
- **Spoolyard fixtures** (local only, `pcf.md`):
  - imperial: the only error is the equal tee; no annotation warnings.
    One warning remains: a `CAP` with one `END-POINT` is skipped;
  - metric: `FROBNICATOR`, `UNION` and `MISC-COMPONENT` become straights
    with one warning each; **the angle-valve error comes first**, naming
    `VALVE-ANGLE` and 90.0°.  Cut before the angle valve, `to_assembly`
    lists the two pieces and `to_assemblies` builds both, once the bend's
    `ANGLE 90.0` is corrected to the guide's hundredths (`9000`).
- **Surprise:** spoolyard writes `ANGLE` in degrees (`90.0`); the guide
  says hundredths.  Our cross-check rejects it, naming the bend and both
  angles, which is right by the guide.
- **Proposed follow-ups (for design):**
  - a one-`END-POINT` `CAP` (or `FLANGE-BLIND`) at an open end could
    mark the end closed (a wall patch) instead of warning;
  - `ANGLE` given with a decimal point: read as degrees, or keep
    rejecting?  The guide shows only integers.
