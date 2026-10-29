# 0064 — PCF reader robustness: annotations, unknown inline components, several networks

- **Status:** ready
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

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
