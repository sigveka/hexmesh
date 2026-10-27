# 0037 — PCF reader: branched networks and junctions

- **Status:** done
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

- **Joints are contracted in the graph.**  A zero-length weld puts both
  of a component's ports on one point.  Joints aren't graph parts: each
  joint's two ends are merged into one node, and the joints at a node are
  put back into the run that crosses it, so joint absorption (task 0021)
  keeps working per run.
- **Split lengths come from nominal sizes, not the spec.**  Set-ons and Y
  pieces are split before anything is placed.  Run each side of a set-on
  = the branch's nominal bore.  Y-piece stem cut = r·(tan h + 0.1 + 0.5),
  with r the stem's nominal radius.  That makes the split the same for
  every spec, but a spec much fatter than its nominal size can fail the
  `Tee` / `Wye` length checks.  Those failures raise, naming the
  component.
- **Branch radius with a single spec** = the incoming radius × branch
  bore / main bore, like a `Reducer` outlet.  With a spec callable it is
  `spec(branch_bore)`'s core radius.
- **Root roll.**  Placement runs once.  If the first junction's branch
  misses a multiple of 90°, the root's `up` is rolled by the miss and the
  network is placed again (at most twice).
- **Flow direction.**  The guide's `FLOW` attribute (1, 2, 3) exists.
  Open ends it marks as upstream are tried first as the default root
  (recorded in pcf.md).
- **Existing fixtures changed.**  `SPOOL`'s set-on used to be skipped
  with a warning.  It is now read, so on the suite's layered spec it is
  rejected ("single-layer specs only").
  - The joint tests use `SPOOL_NO_SETON`.
  - New tests cover the set-on meshing on a single-layer spec, and its
    rejection on the layered one.
  - The two-elbows fixture was always disconnected after its edit.  The
    old greedy loop failed on the joint before reaching the gap; the
    fixture now ends at the second elbow.
- Error messages keep the `component <i> (<TYPE> <label> at …)` form, now
  with the label and SKEY.

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

Done 2026-10-28.

**Files.**
- `hexmesh/io/readers/pcf.py`
  - Parsing: `TEE`, `TEE-SET-ON` / `TEE-STUB` / `OLET`, and
    `Y-PIECE-FABRICATED`, with branch points, bores and `SKEY`.  A `TEE`
    may give its branch as a third `END-POINT`.  Crosses and
    `Y-PIECE-FITTING` are read and rejected later.  `read_pcf` accepts a
    list of files.
  - Build: the greedy `_sort_by_connectivity` and the linear loop are
    replaced by a graph (`_graph`, `_check_tree`), a root choice
    (`_choose_root`, `_entries`, `FLOW`), host splitting (`_split_hosts`)
    and a depth-first placement (`_place`, `_place_chain`).
  - New `to_assembly(..., inlet=)`.  New labels (`_labels`) and open-end
    names (`_end_names`).
- `tests/test_pcf_junctions.py` (new, 27 tests).  A two-file network: a
  `TEE`, a set-on, an olet on the branch, a Y piece and a second pipeline.
  It meshes all-hex with meshed = predicted, and every `END-POINT` and
  branch point is checked.  Also: root by name or point, `FLOW`, the root
  roll on a skew line, `COMPONENT-IDENTIFIER` labels, a spec callable, a
  loop, and 10 rejection fixtures.
- `tests/test_io_readers.py`: +2 tests (the spool's set-on meshing on a
  single-layer spec, and its rejection on the layered spec).  Fixture
  edits are described in *Agent notes*.
- `docs/integrations/pcf.md`: `FLOW`, the identifiers and the Y-piece
  keypoints.  Rows 6 and 7 fixed or rejected by design.
- `API.md` and `README.md`: "Reading plant data".

**Tests.**  Full suite: 1368 passed, 5 skipped (was 1339 passed), in 4 min
42 s in parallel.  No OpenFOAM output is touched.

**Measurements.**  Every existing linear fixture (`LINE`, `ELBOW_45`,
`KINKED`, `GUIDE_BEND`, `MINIMAL`, the spool without its set-on) gives the
same `to_dict()` as before this task, apart from names.  This was compared
against a worktree of HEAD, with both `kinks` modes.

**Surprises.**
- Zero-length joints made the graph see four components at one point.
  Joints are now contracted (see *Agent notes*).
- The suite's spool fixture uses a layered spec, so its set-on, now
  read, is rejected.  The `Tee` and `Wye` prototypes are single-layer
  only, which rejects most real insulated lines with a junction.

**Proposed follow-ups (for design).**
- Layered specs at junctions are the largest remaining gap for plant
  files.
- Set-on run length: the nominal bore is a convention.  A
  quality-based choice (the shortest run the `Tee` meshes well) may be
  better.
- Y-piece daughters of another size than the stem are rejected.  A
  `Wye` with a `Reducer` after each daughter would cover the common
  reducing Y.
