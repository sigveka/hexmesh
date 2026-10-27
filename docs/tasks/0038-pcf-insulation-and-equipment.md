# 0038 — PCF reader: insulation and equipment connections

- **Status:** ready (after 0037)
- **Decision:** [0023 — PCF input: branched networks, junctions, insulation and equipment](../decisions/0023-pcf-branched-networks-insulation-equipment.md)
- **Depends on:** 0037 (graph, names).  Uses `stack_changes` (task 0018)
  and the nozzle naming of decision 0002.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  PCF files say where lines are insulated and which ends attach
to equipment (`docs/integrations/pcf.md`, row 8).  hexmesh can mesh
insulation that stops and starts (decision 0006) and names nozzle
boundaries (decision 0002), but the reader drops both.

**Where.**
- `hexmesh/io/readers/pcf.py`.
- `hexmesh/assembly/assembler.py`: `extend_open_ends`, the interface
  record and `to_dict` / `from_dict` (the equipment mark).
- `hexmesh/assembly/interface.py`.
- Tests, `README.md`, `API.md`, `pcf.md`.

**Do.**
1. **Insulation** (`to_assembly(..., insulation=False)`).
   - Off: unchanged behaviour (the spec callable decides the layers).
   - On: append a shell named `insulation` of the pipeline's
     `INSULATION-THICKNESS` (coordinate units) to the spec of insulated
     components.  Component `INSULATION ON|OFF` and per-end-point
     overrides decide where it is.
   - Where it switches, place the change with `stack_changes` inside the
     adjacent straight component (a valve or flange left bare: insulation
     stops one cell into it and restarts one cell before its end, or as
     the PCF says).  If no straight component can take a switch, or an
     insulated stretch reaches a junction (single-layer today), raise
     `AssemblyError` naming the component.
   - Pipelines without `INSULATION-THICKNESS` but with insulation on:
     error naming the pipeline.
2. **Equipment.**
   - Read `EQUIPMENT-REFERENCE` blocks (nozzle reference, position,
     size) and `END-CONNECTION-EQUIPMENT`.
   - An end attached to equipment is named `<equipment>_<nozzle>` and
     marked as an equipment end.  Check the nozzle position against the
     pipe end (tolerance) and raise on a mismatch.
   - Add the mark to the interface (saved in `to_dict`, read by
     `from_dict`; decision 0019 constraint 2).  `extend_open_ends` never
     extends a marked end (today it only skips the `from_nozzle` inlet:
     make that use the same mark).
   - No equipment geometry.
3. Fixtures (hand-written): an insulated line with a bare valve; an
   insulation end at a flange; an insulated line reaching a tee
   (error); a line from a vessel nozzle to another vessel's nozzle; a
   nozzle position mismatch (error).

**Accept.**
- Insulation fixture: validates, meshes all-hex, meshed = predicted;
  `insulation` volumes only where the PCF says; `insulation_end` walls
  at each switch; interfaces `interface_steel_insulation` (or with the
  user's outer layer name).
- Every error fixture raises naming the component or pipeline.
- Equipment fixture: open ends named after the nozzles; after
  `extend_open_ends()` neither nozzle end moved; the mark survives
  `to_dict` → `from_dict`.
- `insulation=False` (default): all existing reader tests unchanged.
- `pcf.md` row 8 updated.  Full suite: no new failures.

**Out of scope.**  Equipment bodies (drums from PCF `SHAPE`), heat
tracing, jacketed pipe, insulated junctions.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
