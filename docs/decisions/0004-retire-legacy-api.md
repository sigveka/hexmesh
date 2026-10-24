# 0004 — Retire the legacy API

- **Status:** accepted
- **Date:** 2026-10-24
- **Tasks:** 0011–0017

## Context

The package has two implementations.

- **Legacy:** `hexmesh/connectors/`, `network.py` and `model.py`, about
  7,000 lines.  It produces every row of DESIGN §9 "Current deviations"
  except the last three:
  - producer-owned faces;
  - cursor-chained placement;
  - `occ.fragment()` and `removeDuplicateNodes()`;
  - topology detected by surface count;
  - no validation before GMSH.

  Its Y-junction no longer meshes on either installed gmsh version
  (memory: legacy Y regression, 2026-03-28).
- **Assembly:** `hexmesh/assembly/`.  It follows DESIGN §2–§8 and passes
  the conformance kit.  It has `Straight`, `Bend`, `Closure` and a
  single-layer `Tee`.

The README, `API.md`, the examples and the package root (`hexmesh/__init__`)
document only legacy.  New users start on the code DESIGN says not to
extend.  The user wants a single API and examples that match it.

Legacy features the assembly does not have yet:

| Legacy | Status in assembly |
|---|---|
| `Straight`, `Bend` | done |
| `TJunction` (side tap) | `Tee`: single-layer, `rot = 0`, perpendicular, centred |
| `MiterBend`, `Elbow` | missing; a sweep |
| `Reducer`, `Expander`, `Transition` | missing; a sweep whose port specs differ |
| `SplinePipe` | missing; a sweep along Bishop frames |
| `YJunction` | missing; design open (CLAUDE.md Stage 6, RESEARCH §4) |
| multi-layer / general tee | missing; design open (tasks README) |
| wall classifier (`examples/wall_zones.py`) | missing; task 0009 covers per-fitting walls |
| `io.readers.pcf` / `bathymetry` → `Network` | must be re-targeted to `Assembly` |
| `Model` (session context, `show()`) | small; keep a version without `removeDuplicateNodes()` |

The assembly also still imports three things from legacy:
- `connectors.fittings._connect_layer_aligned`, from `assembly/corners.py:24`;
- `network.QualityReport` and `RegionQuality`, from
  `assembly/assembler.py:33`;
- `core.cursor` helpers, from `assembly/interface.py` and
  `assembly/fittings.py`.

## Options

### A. Port, then delete
- Make the assembly independent of legacy.
- Port the sweep-type fittings and re-target `io`.
- Make the assembly the public API with new examples.
- Delete legacy, and tag the last commit that still has it.

The wye, the multi-layer tee and the wall classifier stay missing until
their own decisions.

### B. Delete now
Fastest.  It loses every feature in the table until each is rebuilt, and
the PCF reader stops working.

### C. Quarantine (`hexmesh/legacy/`), delete later
No feature loss.  But it keeps two APIs alive, and the quarantine tends
to become permanent.

## Decision

Option A (chosen by the user, 2026-10-24).  Each port is a `Sweep` or a
block layout that passes the conformance kit.  Nothing is ported by
wrapping legacy code.  Deletion is the last task, and it requires every
other task of this decision to be `done`.

The tag `legacy-final` marks the last commit that still contains legacy,
so its features can be read back when their decisions are made.

## Consequences

- Tasks 0011–0017.  They come before the remaining tasks of decision
  0001.  The tasks README ground rule "do not touch the legacy
  connectors" does not apply to them.
- "Miter bends in `Sweep`" leaves the README's *Not part of any task*
  list; task 0012 does it.
- The public API changes incompatibly, so the version goes 0.2.0 → 0.3.0
  (task 0016).
- **DESIGN.md**, applied by the design session after task 0017 is done:
  - delete the §9 rows that name `connectors/`, `network.py` or
    `model.py` (rows 1–9 of the table today);
  - drop the "legacy connectors only" qualifier in the corner-matching row
    (the row goes, with the code).
- **CLAUDE.md:** the sections on legacy internals go away with task 0017.
  They are: the `n_outer` staged plan (it names connector files), the
  Y-junction constraints, the Reducer constraints and the T-junction
  stages.  The `n_outer` topology and `refinement` text stays, rewritten
  against `PipeSpec` and `Assembly`.
- **Lost until their own decisions:** the Y-junction, the multi-layer and
  general tee, and the wall classifier.  The legacy Y fails today anyway,
  so this loses nothing that works.
- The 10 known `TestYJunctionQuality` failures disappear with the legacy
  tests.

## Verified vs. assumed

- Verified (coding agent, 2026-10-24):
  - the three assembly → legacy imports above;
  - `io.readers.pcf` builds `Network` with `Straight`, `Bend` and
    `Reducer` only (`pcf.py:113`);
  - `smooth_bend` runs, and the assembly demo (straight + tee + bend)
    meshes 1808 cells as predicted, min SICN 0.238.
- Assumed, to check in the tasks:
  - a miter station can be a sweep station.  The cut face is an
    ellipse, not an OH face built from the spec (task 0012);
  - a reducer fits `Path` with per-station specs (task 0013).
