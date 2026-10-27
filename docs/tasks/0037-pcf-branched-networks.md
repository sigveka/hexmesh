# 0037 — PCF reader: branched networks and junctions

- **Status:** ready
- **Decision:** [0023 — PCF input: branched networks, junctions, insulation and equipment](../decisions/0023-pcf-branched-networks-insulation-equipment.md)
- **Depends on:** —  (0038 builds on it)

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Real plant lines branch.  Today the reader chains components
greedily and skips every junction (`docs/integrations/pcf.md`, rows 6
and 7), so a branched file is mis-ordered or loses its tees silently.

**Where.**
- `hexmesh/io/readers/pcf.py`: `_sort_by_connectivity`, `_classify`,
  `_build_assembly`, `NetworkSpec`, `read_pcf`.
- `hexmesh/assembly/tee.py`, `wye.py`: limits and port order (read only;
  don't relax limits here).
- `docs/integrations/pcf.md` (TEE / set-on / OLET / Y-piece facts; the
  guide itself is local only, `docs/manuals/`, never copied).
- `tests/test_io_readers.py`; `README.md` "Reading plant data";
  `API.md`.

**Do.**
1. **Graph.**  Components become nodes joined at shared end points
   (existing tolerance) and by `END-CONNECTION-PIPELINE`, across every
   pipeline in the file.  `read_pcf` also accepts a list of files read
   into one network.  Joint absorption (task 0021) keeps working on each
   run.
2. **Junctions.**
   - `TEE` → `Tee`: run length from the two `END-POINT`s, branch from
     `CENTRE-POINT` → `BRANCH1-POINT`, branch spec from the branch bore
     through the spec callable.
   - `TEE-SET-ON`, `TEE-STUB`, `OLET` → split the host `PIPE` at
     `CENTRE-POINT` into straight + `Tee` + straight.  Choose the Tee's
     run length (e.g. the branch diameter plus margins the Tee needs) and
     reject the component if the host pipe is too short for it.
   - `Y-PIECE-FABRICATED` → `Wye` when symmetric, coplanar, equal
     daughters, 30°–120°.
   - Everything else (equal tees, angled, tangential or offset SKEYs,
     crosses, asymmetric Y pieces): `AssemblyError` naming the PCF
     component (type, index, SKEY) and the limit it breaks.
   - Accept the real-world `TEE` dialect with the branch as a third
     `END-POINT` (pcf.md, IsoSurvey sample).
3. **Root.**  `to_assembly(..., inlet=None)`: an end point or end name.
   By default, pick a root from which every junction is entered through
   its inlet (a tee's run end, a wye's stem), deterministically (e.g.
   the first qualifying open end in file order).  If none exists, raise
   naming a junction that can't be entered.  Reject cycles, naming a
   component on one.  Check the guide for a flow-direction attribute;
   if one exists, prefer it as the default root and record the fact in
   pcf.md.
4. **Names (A7, decision 0019 constraint 4).**  Fittings labelled
   `<pcf-type>_<n>` (file order) unless the component carries its own
   reference; open ends named from the pipeline reference (e.g.
   `<pipeline>_end<k>`, or `inlet` for the root if nothing better).
   Labels unique and stable across runs.
5. **Fixtures.**  Hand-written from the guide's syntax (no copied text):
   a header with two tees, a set-on tee on a straight, an olet, a Y-piece,
   two pipelines joined by `END-CONNECTION-PIPELINE`, and one file per
   rejection.  Export realistic fixtures with an open-source writer if
   useful (pcf.md: PipeCAD, OpenPulse exporters), never third-party
   project files.

**Accept.**
- Each fixture builds an `Assembly` that validates and meshes all-hex,
  meshed = predicted, every junction present (count fittings by type).
- Every `END-POINT` and `BRANCH1-POINT` lands on the placed geometry
  within the tolerance (check all, not only the chain).
- Each rejection fixture raises `AssemblyError` naming the component and
  the limit; none is skipped silently.
- Same file twice → identical `to_dict()` (deterministic root and names).
- The pcf2iso samples and every existing reader test still pass.
- `pcf.md` rows 6 and 7 updated (fixed / rejected by design, with dates).
- Full suite: no new failures.

**Out of scope.**  Insulation and equipment (task 0038); loops; entering
a fitting by a port other than its inlet; equal tees; relaxing any
`Tee`/`Wye` limit.

## Agent notes

_None yet._

**Note from design (2026-10-27, decision 0024):** `Tee` has no `roll`
today: its branch points along the incoming `up`.  Task 0040 adds a
`roll` restricted to multiples of 90°.  Until then, a branch not along
`up` is rejected; after 0040, a set-on branch at a multiple of 90° from
the incoming `up` maps directly and any other angle is rejected naming
the angle.  The root's `up` is free: choose it so the first junction's
branch lands on an allowed direction.  If 0040 isn't done when you
start, do 0037 against today's `Tee` and leave the roll for 0040.

## Questions for design

_None._

## Outcome

_Not done._
