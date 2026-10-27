# 0038 — PCF reader: insulation and equipment connections

- **Status:** done
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

- **Absent `INSULATION` reads as off.**  The guide gives no default and
  says insulation is drawn when it is `ON`.  `INSULATION-SPEC` (a spec
  code such as `01400`, `THICK` or `NONE`) is not read as a status;
  pcf.md records both facts.
- **Keypoint overrides.**  An `INSULATION-ON/-SINGLE/-OFF` word on an
  `END-POINT` sets the status at that end.  A straight whose two ends
  differ switches at its middle cell.  Any other component whose ends
  differ is rejected.
- **Where a switch goes.**  Each change of status between neighbours goes
  one cell inside a straight neighbour; if both are straight, the bare
  one takes it.  A bare valve between insulated pipes therefore gets
  insulation one cell in from each side, as **Do** says.  A bare `TEE`
  between insulated pipes is fine: the pipes stop the insulation one
  cell before and after it.  A junction is "insulated", and rejected,
  when its own status or a keypoint is on, or, for a set-on or Y piece,
  when its host pipe is insulated (the host is welded through the
  junction).
- **Cell counts.**  `stack_changes` need an explicit `n_layers`.  The
  reader computes `ceil(L / axial_cell)` itself and raises it to the
  minimum the switches need: 2 for one switch, up to 4 with a middle
  switch.
- `axial_cell`'s default stays the outer radius of the **bare** spec, so
  turning insulation on doesn't change axial resolution.
- **Equipment mark.**
  - `Interface.equipment` replaces the special case of `from_nozzle`'s
    inlet in `extend_open_ends` and `prepend`.  The prepend error keeps
    the words "drum nozzle".
  - `to_dict` writes `"equipment"` only when an end is marked, so
    existing saved files and dicts are unchanged.  No version bump:
    older readers ignore the key.
- **Parser fixes.**
  - `EQUIPMENT-REFERENCE` blocks before the first pipeline (the guide's
    own layout) were swallowed into the header.
  - Repeated `NOZZLE` entries overwrote each other.
  - Connection blocks dropped their `END-POINT`s.
  - Pipeline insulation thickness goes to a new
    `NetworkSpec.insulation_thickness`, keeping `pipelines` as the raw
    attributes.

## Questions for design

_None._

## Outcome

Done 2026-10-28.

**Files.**
- `hexmesh/io/readers/pcf.py`
  - Insulation:
    - per-component and per-keypoint status, and
      `NetworkSpec.insulation_thickness`;
    - `_resolve_insulation`, `_plan_insulation` (where each switch goes)
      and `_stack_changes` (cell counts and changes);
    - `to_assembly(insulation=False, insulation_nrad=2)`.
  - Equipment: `EQUIPMENT-REFERENCE` with nozzle lists, connection
    positions, the column-1 `NOZZLE` form, and `_equipment_ends`.
  - The parser fixes in *Agent notes*.
- `hexmesh/assembly/interface.py`: `Interface.equipment`.
- `hexmesh/assembly/assembler.py`: `from_nozzle` marks its inlet;
  `prepend` and `extend_open_ends` use the mark.
- `hexmesh/assembly/intent.py`: `"equipment"` saved and loaded (omitted
  when empty).
- `tests/test_pcf_insulation_equipment.py` (new, 17 tests):
  - the bare-valve line with a bare flange at its end, meshed;
  - a keypoint override that switches mid-pipe;
  - a bare tee between insulated pipes, meshed;
  - 4 insulation errors and a spec that already has an `insulation`
    shell;
  - two vessels with nozzle naming, no extension, the round trip, the
    column-1 `NOZZLE` form, and 2 position mismatches.
- `docs/integrations/pcf.md` (facts, row 8), `API.md`, `README.md`.

**Acceptance.**
- The insulated line validates and meshes all-hex, with meshed =
  predicted and quality ok.  Every `insulation` volume lies inside the
  insulated pipes plus one cell (0.05 m) into the valve and the flange,
  checked by bounding box.
- There are 12 `insulation_end` patches (3 switches × 4) and an
  `interface_steel_insulation` group.
- Every error names a component or pipeline.
- Nozzle ends: `V_101_N1`, `V_102_N2`; `extend_open_ends()` moves
  neither; the marks survive `to_dict` → `from_dict`.
- With `insulation=False`, every existing reader test passes unchanged.

**Tests.**  Full suite: 1385 passed, 5 skipped (was 1368), in 3 min 55 s
in parallel.  No OpenFOAM output is touched.

**Surprises.**  The guide's own equipment example (vessels before the
first pipeline) was being read into the header.  Real files often give
insulation as an `INSULATION-SPEC` code rather than `INSULATION ON`; with
`insulation=True` those lines get no shell.

**Proposed follow-ups (for design).**
- Should `INSULATION-SPEC` (anything but `NONE`) count as insulated,
  with the thickness from the pipeline?  The guide doesn't tie the two
  together.
- Insulated junctions: a layered `Tee` would remove the largest
  rejection for plant files (also listed in 0037).
- A network that *ends* at a nozzle still can't `close()` onto a drum
  (task 0010's open question).  The PCF ends here are marked but have no
  drum geometry.
