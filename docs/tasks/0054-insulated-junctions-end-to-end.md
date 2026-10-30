# 0054 — Insulated junctions end to end: PCF, example, docs

- **Status:** done
- **Decision:** [0028 — Multi-layer junctions](../decisions/0028-multi-layer-junctions.md); PCF rule from [0023](../decisions/0023-pcf-branched-networks-insulation-equipment.md)
- **Depends on:** 0052, 0053 (and their limits answered by design).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Once tees and wyes take shells, the places that reject
insulated junctions must stop doing so, and users need to see it.

**Where.**  `hexmesh/io/readers/pcf.py` (`ins_junction` rule, task
0038), `docs/integrations/pcf.md`, a new example, `README.md`
limitations, `API.md`.

**Do.**
1. **PCF:** an insulated junction maps to a multi-layer `Tee` or `Wye`
   instead of an error.  The insulation layer runs through it.  A
   junction whose legs differ (insulated main, bare branch) places the
   switch with `stack_changes` one cell into the bare leg's first
   straight (the 0038 placement rule).  Update the 0038 fixtures that
   expected an error.
2. **Example** `sections/insulated_network` (or extend
   `insulated_route`): a three-layer header (fluid, steel, insulation)
   with a tee and a wye, one branch left bare via `stack_changes`;
   gallery entry (`docs/gallery/build.py --only insulated_network`).
3. **Docs:** remove "junctions are single-layer" from the README
   limitations and `API.md`; state the new limits (from 0052/0053).
4. DESIGN rows: tell design which can close (design edits DESIGN).

**Accept.**
- The PCF fixture "insulated line with a tee" builds, validates and
  meshes; the insulation is continuous through the tee.  A bare branch
  gets `insulation_end` at its switch.
- The example meshes all-hex, meshed = predicted, quality ok; gallery
  entry generated.
- Full suite: no new failures.

**Out of scope.**  Insulated duct tees (decision 0027 + 0026).

## Agent notes

**2026-10-30.**
- **PCF reader:**
  - `ComponentSpec.ins_junction` is now the junction's insulation
    thickness (0 bare), not a flag.  Legs with two thicknesses are an
    error naming the junction.
  - A run into a junction plans its switches to end at that thickness
    (`_plan_insulation`'s `to_junction` is a thickness).  A run leaving
    it starts from the junction's port spec, so the existing rule puts a
    bare leg's switch one cell into its first straight; no new
    placement code.
  - A junction reached with another thickness (junction straight after
    junction, or the inlet) is rejected, naming it.
- **Set-on run** (design's note): `_split_hosts` takes the run from
  `Tee(run_length=None).resolve(...)` on the host's spec, dressed with
  the junction's insulation.  It depends on radii and shells only (the
  layout's corner SJ doesn't depend on densities), so a refined spec
  gives the same split.  The spool's set-on goes from 1" (0.0254) to
  0.0375 single-layer and 0.0475 with a wall.  The layered spool, once
  rejected (SJ < 0.1), now validates.  It still warns, because its
  branch ratio 0.25 keeps the SJ under 0.3 at any run.
- **Example** `sections.insulated_network`:
  - three-layer header (fluid, steel 6 mm, insulation 25 mm, R 0.1),
    tee (r 0.06, run resolved 0.141), 60° wye;
  - the tee's branch is bare from cell 1 via `stack_changes`;
  - 18 012 cells (= predicted), min SICN 0.059, no warnings, about 9 s;
  - gallery entry generated.
- **DESIGN rows (step 4)** are under *Outcome*.

**Note from design (2026-10-29, task 0052 Q1):** a PCF set-on tee with a
wall inverts at the PCF's run of about 2r.  The reader takes the Tee's
run from the host pipe, so it should use `Tee(run_length=None)` (the
default from 0052: `r + T + 0.5 R`, or longer to reach SJ 0.3).  Reject
only when the host pipe is too short for that, naming the component and
the length needed.

## Questions for design

_None._

## Outcome

**Done (2026-10-30).**
- **Files:**
  - `hexmesh/io/readers/pcf.py`;
  - `hexmesh/examples/sections/insulated_network.py`, listed in
    `examples/__init__.py`;
  - tests: `test_pcf_insulation_equipment.py`, `test_io_readers.py`;
  - docs: `API.md`, `README.md`, `docs/integrations/pcf.md`;
  - gallery: `docs/GALLERY.md`, `metrics.json`, two images.
- **Tests:**
  - New `test_insulated_tee`: the fixture is extended with an insulated
    main pipe and a bare branch pipe.  It checks a three-layer tee, the
    branch's switch at cell 1, meshed = predicted, the
    `interface_steel_insulation`, `insulation_wall` and `insulation_end`
    groups, and quality ok.
  - New rejection case: a branch pipe on another pipeline with a
    different thickness, named.
  - The old "insulated junction" rejection is removed.
  - The spool set-on tests are updated for the new run.
- **Suite:** 1978 passed, 14 skipped, 1 failed.  The failure was my
  new layered-spool test, which expected no warning; the branch-ratio
  warning is correct, so the test now expects it.  The file re-ran 31
  passed.
- **DESIGN rows (for design):**
  - No row closes because of this task.  The Tee row stays
    (perpendicular, centred), and the wye's shell limits never had a
    row.
  - Rows 1–8 of "Current deviations" name legacy files deleted in task
    0017 (`straight.py`, `bend.py`, `y_block.py`, `junction.py`,
    `model.py`, `network.py`, `connect()`, `_connect_layer`).  A grep of
    `hexmesh/` finds none of their practices left (`occ.fragment`,
    `removeDuplicateNodes`, extrude/revolve fills, `connect(`), so they
    look closable.

