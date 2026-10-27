# 0021 — PCF reader: conform to the PCF reference guide (bug fixes)

- **Status:** done
- **Decision:** [0004 — Retire the legacy API](../decisions/0004-retire-legacy-api.md)
  (task 0015 ported the PCF reader onto the assembly; this fixes it
  against the format specification)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Checked against the *Piping Component File Reference Guide*
(2016/2018), the reader **rejects spec-conformant bends** and mis-reads
units.  Reproduction: the guide's own BEND example (`PIPE` → `BEND` →
`PIPE`, with a standard header) fails in `to_assembly` with "elbow is not
tangent to the incoming pipe".  Details, spec facts and the evidence are
in [`docs/integrations/pcf.md`](../integrations/pcf.md), "Current reader
vs. the guide", rows 1–5.  The guide is local at
`docs/manuals/pcf-reference-guide.pdf` (sections cited there).

**Where.**  `hexmesh/io/readers/pcf.py`: `read_pcf`, `_iter_records`,
`_elbow_params`, `_build_assembly`.  `tests/test_io_readers.py`.

**Do.**
1. **Header and sections.**  Parse header keywords before the first
   `PIPELINE-REFERENCE`: `ISOGEN-FILES`, `UNITS-*`.  Recognise
   `PIPELINE-REFERENCE` (with its column-5 attributes),
   `END-CONNECTION-PIPELINE`, `END-CONNECTION-EQUIPMENT` and
   `EQUIPMENT-REFERENCE` blocks, and the trailing `MATERIALS` section, as
   non-components.  No "unsupported component" warnings for them.  Keep
   pipeline attributes in `NetworkSpec`, keyed by pipeline (row 8's
   features will need them).
2. **Units.**
   - Coordinates scale from `UNITS-CO-ORDS` (`MM` → 1e-3,
     `MM-HUNDREDTHS` → 1e-5, `INCH` → 0.0254).
   - Bore from `UNITS-BORE` (`MM`, `INCH`, `INCH-SIXTEENTH` = 1/16").
   - Store bore as **nominal size in metres**, and document that it is
     nominal, not the inside diameter.
   - `unit_scale=` stays as an explicit override; if given, it wins and
     a mismatch with the header warns.  A file with no header: keep
     today's default (mm) and warn once.
3. **Bends and elbows: corner convention.**
   - `CENTRE-POINT` is the tangent-leg intersection.  With a = start −
     C and b = end − C:
     - bend angle θ = 180° − ∠(a, b);
     - radius R = |a| / tan(θ/2);
     - incoming direction = −â; bend plane from â × b̂.
   - Cross-check against `ANGLE` (hundredths of a degree) and
     `BEND-RADIUS` (`nD` × nominal bore, or absolute) when present.
     Disagreement beyond tolerance raises, naming the component.
   - Replace the tangency check accordingly: C − start must be
     **parallel** to the incoming direction.
4. **Fix the test fixture.**  `tests/test_io_readers.py:31–34` encodes
   the arc-centre convention.  Rewrite it to the guide's convention, and
   add fixtures for:
   - the guide's BEND example (90°, 3D) with a full header;
   - a 45° elbow (where the conventions give different radius and
     angle);
   - `UNITS-CO-ORDS INCH` and `MM-HUNDREDTHS`;
   - `UNITS-BORE INCH` / `INCH-SIXTEENTH`;
   - a file with `MATERIALS` at the end.
   Write fixtures from the guide's syntax rules (columns 1/5, no tabs).
   Don't paste guide text beyond short coordinate examples.
5. **Joints by spec, and real-file dialects** (`docs/integrations/pcf.md`
   rows 9–10 and "Spec status"; dialect source: pcf2iso
   `references/pcf_format.md`).
   - **By spec:** absorb the guide's `GAP` component and zero-length
     `WELD` records.
   - **Documented deviations** (accept, and name them in docstrings and
     tests as non-spec): `COCP` gap couplings, lateral offsets within
     tolerance, and `ITEM-CODE` in column 1 under `MATERIALS`.  The
     guide gives no tolerance value, so the 1/16" floor below is
     pcf2iso's empirical choice; make it a parameter.
   - Treat `COUPLING`, `GASKET` and zero-length `WELD` records shorter
     than a threshold (default: just above 1/16" = 1.6 mm, in metres
     after unit conversion) as **joints**.  Absorb their length into the
     adjacent straight runs; never mesh them as separate fittings, which
     would create sliver cells.
   - Make the connectivity tolerance scale with the model, with a floor
     just above the weld gap (pcf2iso uses 0.11"; see its
     `geometry.model_tolerance`).  Accept lateral offsets within it, and
     report the largest offset absorbed.
   - Accept `ITEM-CODE n` in column 1 inside `MATERIALS`.
6. **Do not add** tees, olets, insulation, equipment or branched
   ordering (rows 6–8).  If the corner convention reveals other code
   that relied on the old one (e.g. `examples/`, bathymetry routes),
   fix it and list it under *Agent notes*.

**Third-party fixtures.**  pcf2iso's three example files
(`examples/simple_spool/demo_spool.pcf`,
`examples/split_merge_demo/lower_run.pcf`, `…/upper_riser.pcf`, commit
`ab0764b`) may be added under `tests/fixtures/pcf/pcf2iso/` with a
`NOTICE` naming the source, the commit, and its MIT licence as declared
in its README.  The repository has no `LICENSE` file: if that seems too
weak, re-create equivalent fixtures yourself and record the choice under
*Agent notes*.

**Accept.**
- The guide's BEND example builds an `Assembly` with a `Bend` of radius
  304.8 mm and 90°.  The outlet lands on the PCF end point within `tol`.
- The 45° elbow gives R and θ matching its `BEND-RADIUS`/`ANGLE`.
- A minimal valid PCF (header + pipeline + components + `MATERIALS`)
  raises **no** warnings.
- pcf2iso's `demo_spool` and `lower_run` build an `Assembly`:
  - coordinates read as inches;
  - couplings absorbed;
  - the elbow is a 90° `Bend` of radius 6" (152.4 mm);
  - the outlet lands on its PCF end point.
  `TEE-SET-ON` is still skipped with one warning, which is out of scope.
- Unit tests for every `UNITS-CO-ORDS` and `UNITS-BORE` value.
- `docs/integrations/pcf.md` rows 1–5 and 9–10 marked fixed, with the date.
- Full suite: no new failures.

**Out of scope.**  Rows 6–8 of `docs/integrations/pcf.md` (they need
decisions).  Mapping nominal size to inside diameter (pipe schedules).

## Agent notes

- **Third-party fixtures: re-created, not copied.**  pcf2iso has no
  `LICENSE` file, so I wrote equivalent fixtures from the guide's syntax
  (`SPOOL`; its trailing-coupling variant stands in for `lower_run`).
  - The real `demo_spool`, `lower_run` and `upper_riser` (commit
    `ab0764b`) were run locally once and all build:
    - `demo_spool`: a 6" 90° `Bend`, 4 couplings absorbed, outlet on the
      cap's end point, one `TEE-SET-ON` warning;
    - `lower_run`: no warnings, outlet on the elbow's end point;
    - `upper_riser`: builds, one `TEE-SET-ON` warning.
- **Parser** (`_iter_records(path, net)`): column-1 keywords before the
  first component or `PIPELINE-REFERENCE` are header.
  - `PIPELINE-REFERENCE` opens a pipeline block (attributes →
    `NetworkSpec.pipelines`, and each component's `pipeline`).
  - `END-CONNECTION-*` and `EQUIPMENT-REFERENCE` go to
    `NetworkSpec.connections`.
  - Reading stops at `MATERIALS`, which covers `MATERIAL-IDENTIFIER` and
    column-1 `ITEM-CODE` alike.
  - Tabs are expanded (not allowed by the spec, but harmless).
- **Units:**
  - **constants:** `COORD_UNITS` and `BORE_UNITS` in metres.  Bore is the
    nominal size in metres;
  - **coordinates:** `unit_scale=None` takes the header;
    an explicit value wins, and a mismatch warns;
  - **no `UNITS-CO-ORDS`:** mm, with one warning;
  - **no `UNITS-BORE`:** mm, with no separate warning;
  - **unknown unit words:** raise.
- **Elbows** (`_elbow_params` → `ElbowGeometry`): the formulas from the
  task.
  - The incoming leg (start → C) must be along the incoming pipe: the
    cross product × leg length ≤ `tol`, and same sense.
  - The roll comes from the in-plane outgoing direction.
  - **Cross-checks:** `ANGLE` within 0.05°; `BEND-RADIUS` within 1 %,
    either `nD` × nominal size or an absolute value in coordinate units.
- **Joints** (`_absorb_joints`), applied after ordering:
  - preceding straight-meshed run → extended to the joint's end;
  - otherwise the following run starts at the joint's start;
  - at an open end with no straight neighbour → dropped (pcf2iso's
    `lower_run` ends with a coupling after its elbow);
  - between two non-straight fittings → `AssemblyError`.
  - `GAP` is always a joint.  `WELD`, `COUPLING` and `GASKET` are joints
    up to `joint_max` (1.6 mm), else fittings.  `WELD` and `GASKET` were
    previously ignored outright.
- **Straight runs go from the placed outlet to the PCF end point**, using
  the axial projection; the lateral remainder must be ≤ `tol` and is
  recorded.  So gaps and offsets never accumulate, which was the
  pcf2iso failure.  Reducers do the same.
- **Tolerance:** `to_assembly(tol=None)` defaults to max(1e-4 × model
  diagonal, 0.11").  An explicit `tol` still wins.
  - Existing tests are unaffected: their gap tests use gaps of 10 mm and
    50 mm.
  - `NetworkSpec.report` holds the tolerance, the joints and the max
    offset.  No warnings are issued for absorption, so a valid file stays
    silent.
- **Nothing else relied on the old convention:** no example reads a PCF.
  The bathymetry reader builds `kind="pipe"` components only, and its
  test passes unchanged.
- `ComponentSpec` gained `pipeline`.  `NetworkSpec` gained `header`,
  `pipelines`, `connections`, `coord_scale` and `report`.

## Questions for design

_None._

## Outcome

- **Files:**
  - `hexmesh/io/readers/pcf.py`: parser, units, elbows, joints and
    tolerance;
  - `tests/test_io_readers.py`: fixture moved to the corner convention
    with a header, plus 22 new tests;
  - `README.md` and `API.md`;
  - `docs/integrations/pcf.md`: rows 1–5, 9 and 10 marked fixed, and the
    test-data note (untracked).
- **Accept:**
  - **guide BEND example:** a 90° `Bend` of R = 304.8 mm, outlet on the
    end point;
  - **45° elbow:** R = 228.6 mm and θ = 45°, matching
    `BEND-RADIUS 1.5D` and `ANGLE 4500`;
  - **minimal valid file:** reads with warnings as errors;
  - **spool equivalents:** read as inches, couplings absorbed, a 6"
    90° bend, outlet on the end point, one `TEE-SET-ON` warning;
  - **units:** each `UNITS-CO-ORDS` and `UNITS-BORE` value tested.
- **Tests:** 659 passed (default run), 0 failed.
