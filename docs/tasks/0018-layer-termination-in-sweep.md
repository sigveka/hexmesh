# 0018 — Layer termination in `Sweep` (insulation stops and starts)

- **Status:** done
- **Decision:** [0006 — Layer-stack changes inside sweep fittings](../decisions/0006-layer-stack-changes-in-sweeps.md)
- **Depends on:** 0013 (it changes spec handling along sweep paths in the
  same code; finish it first to avoid conflicting edits)

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Insulation and cladding stop and start at flanges, valves,
supports and inspection points.  For CHT, the uninsulated stretches are
where heat losses concentrate.  DESIGN A4 allows layer-stack changes
inside a fitting, but no fitting implements one.  Removing an outermost
layer leaves the inner layers' mesh untouched (RESEARCH §9.1), so this is
a cheap topology change.

**Where.**
- `hexmesh/assembly/sweep.py`:
  - `Path.spec_at` (spec per station);
  - `_fill_slab`, which pairs layers **by position** via
    `zip(in_face.layers, out_face.layers)`;
  - `sweep_fill`, which builds internal stations with
    `build_face(path.spec_at(k, spec), …)`;
  - `Sweep.validate`, `Sweep.cell_count`.
- `hexmesh/assembly/interface.py`: `build_face`.
- `hexmesh/assembly/assembler.py`: `write_physical_groups` names the wall
  group after the **inlet's** outermost layer
  (`self.inlet.spec.layer_names[-1]`).
- `hexmesh/assembly/fittings.py`: `Straight`, `Bend` (port specs).

**Do.**
1. **Semantics.**  A layer may end or start only at a **station**:
   - The station face is built with the *fuller* stack, so the ending
     layer's annulus exists on it.
   - The slab on the side without the layer fills only the remaining
     layers.
   - The ending layer's annulus surfaces on that station become **end
     walls**.
   - On the side without the layer, the new outermost layer's side
     surfaces are **walls**, not material interfaces.
2. **Pairing.**  Pair layers in `_fill_slab` **by name**, not position.
   Layers present on one side only are handled as in step 1.  Never
   connect layers with different names.
3. **Validation, in `validate()` with no GMSH.**  Errors must name the
   fitting and the layer:
   - only outermost layers may stop or start.  Removing a middle layer is
     an error;
   - the remaining layers must have identical names, radii (`dR`), `nrad`,
     `mprg` and `mbmp` on both sides.  Otherwise use a Reducer.
4. **API.**  Choose the smallest user-facing form, and record the choice
   under *Agent notes*.  Candidates:
   - `Straight(length, n_layers, spec_out=…)`, ending the layer at the
     outlet;
   - an internal station list, e.g. `stations=[(0.3, spec_bare),
     (0.7, spec_insulated)]` as length fractions, so a single `Straight`
     can carry a bare gap.
   `Straight` currently has one slab, so it needs internal stations at the
   termination points.  For `Bend` and `Closure` (one layer per slab),
   termination must coincide with a slab boundary, or a station must be
   inserted there.  The port specs returned by `ports()` must reflect the
   stack at each end.
5. **Physical groups (A7).**  Every surface stays in exactly one group.
   - End annuli go into `{layer}_end`.
   - Wall groups are named after the layer that is outermost *where the
     wall is*.  For example, `insulation_wall` along insulated stretches
     and `pipe_wall_wall` along bare ones (use the actual layer names).
     The inlet's spec alone no longer decides the name.
   - The material interface between two layers exists only where both are
     present.
   - If task 0009 is done, per-fitting wall naming applies to end walls
     too.
6. **Switch class (decision 0011, task 0019).**  If 0019 is done, add
   class `1` to the `strategies` of sweeps that support termination, and
   let 0019's classifier do the port-pair check instead of a separate
   one.  If 0019 isn't done yet, keep the check local and note it under
   *Agent notes*.
7. **Cell count (task 0003).**  `cell_count()` must count each layer only
   in the slabs where it is present.

**Accept.**
- Validation tests (no GMSH): removing a non-outermost layer raises.
  Mismatched remaining layers (radius, `nrad`, `mprg`) raise.  Both
  messages name the fitting and the layer.
- Realisation test: insulated → bare gap → insulated in one network,
  e.g. a `Straight` with internal stations, or Straight–Straight–Straight
  with stack changes inside fittings.  It meshes all-hex.
  - Predicted cell count = meshed count.
  - `{layer}_end` groups exist with the expected number of surfaces (2 ×
    the layer's patch count per gap).
  - No surface is in two groups.
- Conformance kit: add the case to `CASES` in
  `tests/test_fitting_conformance.py`.  It must pass all checks,
  including fill-order independence.
- Uniform-stack sweeps mesh identically to before (existing tests
  unchanged).

**Out of scope.**  Changing radii or `nrad` of remaining layers (Reducer,
task 0013).  Layers that end at an *interface* (A4 forbids it).
Insulation on tees and other junctions (the multi-layer tee has no
decision yet).

## Agent notes

- **API choice: `stack_changes=((i, spec), …)` on `Straight` and
  `Bend`.**  From axial **cell index** *i* on (`0 < i < n_layers`), the
  stack is *spec*.
  - Neither candidate in step 4 was used as written.  `spec_out` alone
    ends a layer at the outlet port, which A4 forbids (a layer may not
    end at an interface).  Length fractions would need rounding to
    cells.
  - Cell indices need no rounding, work unchanged with `axial_grading`,
    and mean the same in `Bend`, where every cell is a slab.
  - One field covers a gap (two changes) and a one-way end (one change).
  - Saved and loaded by the intent layer: `_plain` / `_tuples` now
    convert specs nested in tuples.
- **Path model:**
  - `Path.fill` gives the layers filled per slab; `Path.slab_spec(k)`
    and `Path.cells(spec)` follow from it (step 7);
  - `Sweep.stacked(path, spec)` sets the station specs and fill counts.
    Each internal station gets the fuller adjacent stack (step 1);
  - in a `Straight`, a change splits the run into slabs at
    `station_fractions(n, grading)[i]`.  A sub-slab with the same
    progression ratio continues the same geometric series, so the nodes
    are those of the unsplit run.
- **Fill:**
  - `_fill_slab(n_fill=…)` fills the innermost *n* layers, paired by
    name.  It raises if two names differ (step 2);
  - `sweep_fill` marks each internal-station layer filled on exactly one
    side as end wall `{layer}_end`.
  - The bare stretch's outermost side surfaces become
    `{pipe_wall}_wall` automatically.  The material interface exists
    only where both layers are filled.
- **Groups (step 5).**  `FillResult.wall_groups` maps wall surface →
  group base name.
  - A fill that names none (the tee) gets `{inlet outermost}_wall`, as
    before.
  - `write_physical_groups` merges by base name, or appends
    `_{fitting}` with `walls_by_fitting`.
  - Groups get the role `wall` in the manifest (task 0023).
- **Validation (step 3)**, in `Sweep.check`, with messages naming the
  fitting, the cell and the layer:
  - changes must sit at increasing cells 1 … n−1;
  - a change must add or remove layers ("keeps the layers" otherwise);
  - a removed middle layer gives "only outermost layers may stop or
    start; `pipe_wall` is not outermost";
  - `nrad` or `mprg` of a remaining layer, via the 0019 classifier,
    gives "the remaining layers must match (shell `pipe_wall` nrad
    (2 vs 4)); use a Reducer";
  - a radius gives "(`pipe_wall` radius 0.01 vs 0.02)", and `rot` is
    checked too.
- **Switch class (step 6).**  `Straight` and `Bend` declare `{0, 1}`, and
  the 0019 classifier checks the port pair.
  - `strategies` is a capability, not per instance.  A `Straight`
    without changes whose outlet spec was edited by hand passes the class
    check but is rejected by the exact A4 type check.
  - That error now lists the difference, e.g. "port type … (shells:
    layer `wall` present only at the inlet)".  The 0019 negative test
    was updated to match; class 1 on a fitting that doesn't declare it
    is still tested (`MiterBend`).
- **Not done:** `Closure` (it joins two given interfaces, so its port
  specs are not its own) and the other sweeps.  `MiterBend`, `Elbow` and
  `SplinePipe` could reuse `stacked()` in the same way.  They are left
  for when a case needs them.

## Questions for design

_None._

## Outcome

- **Files:**
  - `hexmesh/assembly/sweep.py`: `trim_spec`, `Path.fill` / `slab_spec`
    / `cells`, `FillResult.wall_groups`, `_fill_slab(n_fill)`, end walls
    in `sweep_fill`, and `Sweep.stack_changes` / `cell_specs` /
    `outlet_spec` / `check_stack_changes` / `stacked`, plus
    `_check_termination`;
  - `fittings.py`: `Straight` and `Bend` get `stack_changes` and
    strategies `{0, 1}`; `_radii` moved to `sweep.py`;
  - `assembler.py`: per-layer wall and end groups, and the port-type
    error lists differences;
  - `intent.py`: specs nested in fitting fields.
  - **Tests:**
    - new `tests/test_layer_termination.py` (16);
    - `test_fitting_conformance.py`: cases `straight-insulation-gap`
      and `bend-insulation-ends`; `test_walls_by_fitting` generalised
      to per-layer walls and ends by role;
    - `test_signature.py`: 2 tests updated, 1 added.
  - **Docs:** README (*Insulation gaps*, groups table, fitting rows) and
    API.md.
- **Accept:**
  - validation tests raise before GMSH, naming the fitting and the
    layer;
  - the insulated → bare → insulated gap in a `Straight` (10 cells,
    gap 3–6) and in a `Bend` meshes all-hex, with the predicted count;
  - `insulation_end` has 8 surfaces (2 × 4 patches); no surface is in
    two groups; `pipe_wall_wall` covers the bare stretch;
  - both kit cases pass every check, including fill-order independence;
  - uniform-stack sweeps keep one slab and `fill = None`.
- **Measurement: termination costs no quality.**  min SICN with a gap
  equals the uniform-stack baseline: 0.134 (Straight), 0.072 (Straight,
  grading 1.2) and 0.114 (Bend), each identical to the same fitting
  without changes.
- **Tests:** 630 passed + 1 failed (default run), 5 passed (`-m openfoam`).  The failure, `test_examples.py::test_every_example_is_tested`, came from another session adding examples mid-run (5 new example files, not yet listed in `EXAMPLES`); it passes once their edit landed.  No failures from this task.
