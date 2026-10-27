# PCF (Piping Component File)

## Role

**Input format.**  Plant piping data (Isogen/Spoolgen, exported by most
plant-design systems) read by `hexmesh/io/readers/pcf.py` into the
Intent layer (`NetworkSpec.to_assembly()` → `Assembly`).

## Versions

- Reference: *Piping Component File Reference Guide*, Version 2016
  (13.0), updated April 2018, Alias Limited (Isogen).  Local copy:
  `docs/manuals/pcf-reference-guide.pdf` (388 pages, gitignored).
  Source:
  https://pypeserverdocs.blob.core.windows.net/enterprise/content/PCFReferenceGuide.pdf
- The guide carries a proprietary-information notice and allows printing
  "for non-commercial use at your company", but **no redistribution
  outside it**.  Keep it local (gitignored), and summarise facts here
  rather than copying text.
- Reader tested against hand-written fixtures in
  `tests/test_io_readers.py`, written from the guide's syntax.  These
  include the guide's BEND example rebuilt with our own coordinates, and
  equivalents of pcf2iso's demos.
  - pcf2iso's three example files (commit `ab0764b`) were run locally
    on 2026-10-26 (task 0021) and all build an `Assembly`.  They are not
    in the repository: it has no `LICENSE` file.
  - **No real PCF exported by a plant system has been tested.**

## Format facts that matter for hexmesh (from the guide)

**Layout (§1, "PCF Syntax").**
- Header keywords start in **column 1** and come first: `ISOGEN-FILES`,
  `UNITS-BORE`, `UNITS-CO-ORDS`, `UNITS-BOLT-DIA`, `UNITS-BOLT-LENGTH`,
  `UNITS-WEIGHT`, …
- `PIPELINE-REFERENCE` (column 1) starts each pipeline; its attributes
  are in column 5.  A file may hold several pipelines.
- Component identifiers are in column 1, their attributes in column 5.
- `END-CONNECTION-PIPELINE` / `END-CONNECTION-EQUIPMENT` records connect
  pipelines to each other and to equipment.
- `MATERIALS` (column 1) is the **last** section.  Its
  `MATERIAL-IDENTIFIER n` lines are also in column 1.
- No tabs; lines ≤ 1024 characters.

**Units (§2).**
- `UNITS-CO-ORDS`: `MM`, `INCH`, or `MM-HUNDREDTHS` (integers, 0.01 mm).
- `UNITS-BORE`: `MM`, `INCH`, or `INCH-SIXTEENTH` (96 = 6").  Bore is
  **nominal size**, not a dimension in coordinate units.
- Coordinates and bore have **independent** units.  A common combination
  is `UNITS-BORE INCH` with `UNITS-CO-ORDS MM`.

**Keypoints (§4, "Coordinates").**
- External keypoints: `END-POINT`, `BRANCH1-POINT`, `BRANCH2-POINT`,
  `PORT-POINT`, given as x y z, nominal size, then optional connection
  type, gender and insulation/tracing keywords in any order.
- Internal keypoints: `CENTRE-POINT`, `CO-ORDS`.

**Bends and elbows (§5 "Bends", component sheets BEND/ELBOW).**
- `CENTRE-POINT` is the **intersection point of the two tangent legs**
  (the corner), not the arc centre.  The guide's BEND example: incoming
  along −y, `CENTRE-POINT` on the incoming line, 304.8 mm from both end
  points = 3D radius (12") × tan 45°.
- `ANGLE` is in **hundredths of a degree** (9000 = 90°).
- `BEND-RADIUS` is a multiple of nominal size (`1D`, `1.5D`, `3D`, `5D`)
  or an absolute radius in coordinate units.
- Relations for checking: leg length = R·tan(θ/2); the arc centre lies
  along the bisector of the corner.

**Tees and branches.**
- `TEE`: two `END-POINT`s (run), `CENTRE-POINT` (on the run centreline),
  `BRANCH1-POINT`.
- `TEE-SET-ON` / `TEE-STUB` and `OLET`: **no END-POINTs**, only
  `CENTRE-POINT` (on the main pipe centreline) and `BRANCH1-POINT`.  They
  sit on a pipe; the main pipe is not split in the PCF.  The SKEY selects
  the variant: set-on, stub-in, pulled, reinforced, **tangential
  (TTSO/TTRF) and offset (TOSO/TORF)**.  These map to RESEARCH §3.1's
  offset h and angle α.
- `Y-PIECE-FABRICATED` (SKEY TYSO): Y-tee, with `BRANCH1-POINT` and
  `BRANCH2-POINT`.
- `CROSS`, `CROSS-SET-ON`: `BRANCH1-POINT` and `BRANCH2-POINT`.

**Reducers.**  `REDUCER-CONCENTRIC`, and `REDUCER-ECCENTRIC` with
`FLAT-DIRECTION`.

**Insulation and tracing.**
- Pipeline attribute `INSULATION-THICKNESS` (insulation width from inner
  to outer surface), plus `INSULATION-SPEC` and `TRACING-SPEC`.
- Per component: `INSULATION ON|OFF`, `TRACING OFF|ON|SINGLE|…`.
- Per keypoint: `INSULATION-ON/-OFF/-SINGLE` on an `END-POINT` line
  overrides the component (e.g. a tee's branch leg).
- These map directly to layer termination (decision 0006, task 0018).

**Equipment (§10).**
- `EQUIPMENT-REFERENCE` blocks with `LOCATION`, `CENTRE-POINT`,
  `ORIENTATION`, `SHAPE`, and repeated `NOZZLE` entries.  Each nozzle has
  `REFERENCE`, `DIRECTION` (a compass/elevation word such as `EAST`,
  `WEST` or `UP`, not a vector), `CO-ORDS` x y z with size and
  connection, and `POSITION`.
- Pipelines attach through `END-CONNECTION-EQUIPMENT` /
  `CONNECTION-REFERENCE`.  This is the data decision 0002 (equipment
  nozzles) needs.

**Jacketed pipe (§5).**  Core and jacket are separate pipelines bridged
by 3-port jacket flanges (`JACKET-POINT`).  An annular jacket flow
around a core pipe is a possible multi-layer use, not planned.

## Current reader vs. the guide

**Verified 2026-10-25** by running `read_pcf` and `to_assembly` on the
guide's BEND example with a full header (`PIPE` → `BEND` → `PIPE`,
`UNITS-BORE INCH`, `UNITS-CO-ORDS MM`).

| # | Behaviour | Spec | Effect |
|---|---|---|---|
| 1 | **Elbow/bend `CENTRE-POINT` read as the arc centre** (`_elbow_params`, and the tangency check in `_build_assembly`) | Tangent-leg intersection (corner) | **Spec-conformant bends are rejected**: "elbow is not tangent to the incoming pipe".  For non-90° bends, radius and angle would also be wrong (the leg is R·tan(θ/2), and the corner angle is 180° − θ).  The test fixture (`tests/test_io_readers.py:31–34`) uses the arc-centre convention, so tests pass **Fixed 2026-10-26 (task 0021).** |
| 2 | Bore scaled by the **coordinate** unit factor | `UNITS-BORE` independent; nominal size | 4" read as 0.004 m **Fixed 2026-10-26 (task 0021).** |
| 3 | Header ignored; `unit_scale=1e-3` assumed | `UNITS-CO-ORDS` decides | `INCH` or `MM-HUNDREDTHS` files are silently mis-scaled **Fixed 2026-10-26 (task 0021).** |
| 4 | Every column-1 line is treated as a component | Header, `PIPELINE-REFERENCE`, `END-CONNECTION-*`, `MATERIALS` and `MATERIAL-IDENTIFIER` are column-1 non-components | 9 spurious "unsupported component" warnings on a minimal valid file **Fixed 2026-10-26 (task 0021).** |
| 5 | `ANGLE`, `BEND-RADIUS` ignored | Present on bends | No cross-check of geometry **Fixed 2026-10-26 (task 0021).** |
| 6 | One greedy chain (`_sort_by_connectivity`); disconnected parts appended | Several pipelines and branches per file | Branched files mis-ordered |
| 7 | `TEE`, `OLET`, `TEE-SET-ON`, `CROSS`, `Y-PIECE-FABRICATED` skipped | Defined (above) | Junctions dropped, although the assembly now has `Tee` |
| 8 | Insulation, equipment, nozzles ignored | Defined (above) | Lost information that decisions 0002 and 0006 can use |

**Rows 1–5, 9 and 10 fixed 2026-10-26 (task 0021).**  Rows 1–5 were bugs against the spec, and rows 9–10 (below) are robustness
against real-file dialects: both are task 0021.  Rows 6–8 are features
needing decisions (branched networks from PCF; tees and olets mapped to
`Tee`; insulation mapped to layer termination; equipment nozzles).
**Rows 6–8 decided 2026-10-27 (decision 0023): tasks 0037 (graph,
junctions) and 0038 (insulation, equipment).**  ISOGEN's older IDF
format (Isogen Data File, PDS/PDMS/Tribon era) is not read: most
systems export PCF, and no public IDF specification was found.  Not to
be confused with the PCB "Intermediate Data Format" (`.emn`/`.emp`)
that Inventor's IDF translator reads.

## Other readers and sample files (surveyed 2026-10-25)

**Not the same format.**  `pySourceSDK/ValvePCF` (GPL-3.0, last push
2023) parses Valve Source-engine *particle* files that share the `.pcf`
extension.  It is unrelated to piping, and its tests are of no use here.

**Other piping PCF readers** (useful for comparison, not as references):
- `MOPT-UFSC/OpenPulse` (GPL-3.0, active, pulsation analysis of
  pipelines), `pulse/interface/handler/pcf_handler.py`.  It takes the bend
  radius as the mean distance from `CENTRE-POINT` to the end points,
  which is correct only for 90° bends under the corner convention, and
  hard-codes mm (`/1000`).  It shares hexmesh's simplification, so don't
  treat it as an oracle.  The guide is the reference.
- `eryar/PipeCAD` (`lib/pipecad/PcfExporter.py`, licence "other") and
  OpenPulse's `pcf_exporter.py` **write** PCFs.  Exporting a model you
  built yourself gives realistic fixtures without third-party copyright.

**Real-looking sample files** (all in repositories **without a
licence**, so they must not be copied into hexmesh):
- `Cszabi/IsoSurvey` `samples/sample.pcf`: DN100, header with
  `UNITS-BORE MM`, `UNITS-CO-ORDS MM`.  Its `ELBOW` follows the
  **corner** convention (`CENTRE-POINT` on the incoming line), agreeing
  with the guide.  Its `TEE` gives the branch as a **third `END-POINT`**
  instead of `BRANCH1-POINT`: a real-world deviation a tolerant reader
  should accept.
- `bobydo/file_analyze` `orig/…/ISO-*.PCF`: about 20 files that look
  like a real project's exported isometrics.  They may be someone's
  proprietary project data published by accident.  Don't use them.

**`ProcessQualitySolutions/pcf2iso`** (Python; renders PCFs as
isometric drawings; **MIT per its README**, but the repository has no
`LICENSE` file; last push 2026-08-24, commit `ab0764b`).  The most useful
source found:
- `references/pcf_format.md` independently confirms the guide:
  - `CENTRE-POINT` of elbows and bends = tangent intersection (corner);
  - `UNITS-CO-ORDS` and `UNITS-BORE` are independent ("never assume they
    match");
  - `ANGLE` is in hundredths of a degree.
  Its demo `ELBOW` (4" LR, `ANGLE 9000`) uses the corner convention, with
  legs of 6" = 1.5D·tan 45°.
- It documents **three weld dialects in real files**:
  1. explicit, often zero-length `WELD` records;
  2. **gap couplings** (the dominant Revit-exporter dialect): a
     `COUPLING` with `SKEY COCP` whose end points are the weld root gap
     apart (1/16" = 1.59 mm).  The gap is modelled in the geometry, and
     adjacent components may be **laterally offset by up to the gap**;
  3. set-on attachments (`TEE-SET-ON`, `OLET`) welded at their
     `CENTRE-POINT`.
  Its connectivity tolerance therefore has a floor just above 1/16"
  (`geometry.model_tolerance`).
- `MATERIALS` dialect: `ITEM-CODE n` lines in **column 1** under
  `MATERIALS` (instead of `MATERIAL-IDENTIFIER`).
- Example files: `examples/simple_spool/demo_spool.pcf` and
  `examples/split_merge_demo/{lower_run,upper_riser}.pcf`.  They are
  synthetic demos in inches, with flanges, couplings, an elbow, a set-on
  tee and caps.

**hexmesh's reader on the three pcf2iso samples** (run 2026-10-25):
- `demo_spool`, `lower_run`: **fail**, "ELBOW … starts 0.000125 m from the
  previous outlet".  The `COCP` couplings are skipped as unsupported,
  leaving 1/16" gaps.  With inches mis-read as mm, each gap is 0.0625 mm,
  within the 1e-4 m tolerance on its own.  But components are placed from
  the previous *placed* outlet, so the gaps **accumulate**: after two
  skipped couplings the elbow is 0.125 mm off and is rejected.  With
  correct inch scaling, a single gap (1.59 mm) would already fail.
- `upper_riser`: "succeeds", but is **silently wrong**: coordinates in
  inches are scaled as mm (100 in → 0.1 m), the bore is 0.004 m, and the
  `TEE-SET-ON` and couplings are dropped.
- Every file: 10–12 spurious "unsupported component" warnings (header,
  `PIPELINE-REFERENCE`, `MATERIALS`, `ITEM-CODE`).

| # | Behaviour | Real files | Effect |
|---|---|---|---|
| 9 | `COUPLING` unsupported; position tolerance fixed at 1e-4 m | Revit dialect: `COCP` gap couplings of 1/16", lateral offsets up to the gap | Revit exports fail **Fixed 2026-10-26 (task 0021).** |

**Spec status of rows 9–10** (checked against the guide 2026-10-25):
- `COUPLING` with `SKEY COCP` **is** in the guide (a two-`END-POINT`
  component; `COCP` is a valid SKEY, meaning not explained).
- Using it to carry the **weld root gap is not**: that is an exporter
  convention.  The guide's own means are a **`GAP` component** (two
  `END-POINT`s, no SKEY) and `WELD` (SKEY `WW`), and its examples have
  zero-length welds.
- **Lateral offsets** are not in the guide.  Its *Definitions* say
  components connect when coordinates match "within the tolerance
  currently defined" (an Isogen setting), but give no value.
- **`ITEM-CODE` in column 1** under `MATERIALS` contradicts the syntax
  rules (column 5; only `MATERIAL-IDENTIFIER` is in column 1).
- So the reader handles `GAP` and zero-length `WELD` *by the spec*, and
  the `COCP` gap, the offsets and column-1 `ITEM-CODE` *as documented
  deviations*.

| # | Behaviour | Real files | Effect |
|---|---|---|---|
| 10 | — | Sub-millimetre components (couplings, gaskets, zero-length welds) | Meshing them as `Straight`s would create sliver cells; they must be **absorbed** into adjacent runs, not meshed **Fixed 2026-10-26 (task 0021).** |

**Recommendation for test data:** keep writing fixtures from the
guide's syntax (task 0021).  Add realistic files generated with an
open-source exporter from models we define.  Use unlicensed samples only
to *learn* deviations, like the 3-`END-POINT` tee, and re-create them as
our own fixtures.

## Open questions

- Behaviour on real exported PCFs (AVEVA E3D/PDMS, SmartPlant,
  CADWorx, …): obtain a few sample files.  None are in the repository.
- Nominal size → actual inside diameter: needs a pipe schedule table, or
  a user callback.  `to_assembly(spec=callable)` already takes
  `bore -> PipeSpec`; document that `bore` is nominal.
