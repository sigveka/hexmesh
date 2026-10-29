# 0054 — Insulated junctions end to end: PCF, example, docs

- **Status:** ready (after 0052, 0053)
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

_None yet._

**Note from design (2026-10-29, task 0052 Q1):** a PCF set-on tee with a
wall inverts at the PCF's run of about 2r.  The reader takes the Tee's
run from the host pipe, so it should use `Tee(run_length=None)` (the
default from 0052: `r + T + 0.5 R`, or longer to reach SJ 0.3).  Reject
only when the host pipe is too short for that, naming the component and
the length needed.

## Questions for design

_None._

## Outcome

_Not done._
