# 0117 — Written nodes (route B3): one hex block placed by hexmesh, between two transfinite straights

- **Status:** done
- **Decision:** [0043 — The wye-layout redesign](../decisions/0043-wye-layout-redesign.md), amendment 2026-11-09 (B3 provisional, gates fixed there)
- **Depends on:** 0116 (done).  An experiment: no library change.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0116 closed routes A, B1 and B2 for the wye redesign.  B3
remains: hexmesh places a junction's nodes itself and writes them as a
discrete mesh, outside gmsh's transfinite meshing (0116's scope page).
Before it is taken, one minimal case must show that a written block can
sit between gmsh-meshed neighbours, conformal by construction, and go
through the OpenFOAM path unchanged.

**Where.**  A script under `docs/integrations/evidence/`
(`gmsh_discrete_block.py`), so it documents gmsh behaviour; results in
*Outcome* and in `docs/integrations/gmsh.md`.  Scratch output in your
scratchpad, deleted after.

**Do.**
0. **First, the OCC question.**  gmsh's tutorial x2 says OpenCASCADE
   entities can't have discrete entities on their boundary
   (`docs/integrations/gmsh.md`, *Open questions*), and hexmesh builds
   with OCC.  Check whether hexes in a discrete volume can reference the
   node tags of OCC-meshed surfaces without a declared boundary, and
   survive `write` and `gmshToFoam`.  If not, stop and report: that ends
   B3 on OCC.
1. **The case:** two straights (the 5-patch O-H section, `nang` 4,
   `nrad` 2, a few axial layers each), with a gap of one slab between
   them.  Mesh both, including their facing port surfaces, by gmsh's
   transfinite meshing as hexmesh does today.
2. **The written block:** fill the gap with hexes whose nodes hexmesh
   computes (plain transfinite interpolation in numpy is enough; this
   isn't about quality).
   - The block's port-face nodes are **read back** from the two
     straights' meshed port surfaces (`getNodes` on those entities) and
     reused by tag.  Only interior nodes are new.
   - The block is a discrete volume (`addDiscreteEntity(3, …)`, bounded
     by the two port surfaces and its own discrete wall surfaces),
     filled with `addNodes` and `addElements`.
   - Its wall faces are a discrete surface carrying quads, so the wall
     physical group covers it as it covers the straights.
3. **Through the pipeline:** physical groups as `Assembly.mesh()` makes
   them (inlet, outlet, wall, the fluid volume), write `.msh` 2.2 and 4.1,
   then `would_invert`, `gmshToFoam` (with the `keep_orientation` rule of
   task 0108) and `checkMesh` (v2406, Docker if needed).
4. **Report against the gates** (decision 0043's amendment, fixed
   before the run):
   - **conformal by construction:** the port-face node tags shared with
     the straights; no `removeDuplicateNodes`; the total node count
     equals the straights' plus the block's interior nodes;
   - **OpenFOAM:** `checkMesh` passes with no failed check, one region,
     and the physical groups as patches;
   - **no inverted cells** (`would_invert` 0; min scaled Jacobian > 0);
   - **reproducible:** the `.msh` byte-identical on a second run;
   - **on gmsh 4.12 and 4.15.**
   A gate that misses is reported as a miss, with how far.  Don't change
   a gate after seeing a result.
5. **Note, don't solve:** what second order (`setOrder(2)`) does with
   the discrete block; whether `refined(k)` would need anything beyond
   rewriting the nodes; any ordering constraint found (the ports' surfaces
   meshed before the block is written).

**Accept.**
- Every gate answered with evidence; the script runs from the
  repository.
- `docs/integrations/gmsh.md` records what gmsh does with discrete
  entities next to transfinite ones, with versions and the date.
- No change under `hexmesh/`; meshes and cases deleted.

**Out of scope.**  The wye's B3 layout itself (Decroocq/Marcinnó node
placement), its quality, and any API.  Those follow decision 0043's
next amendment.

## Agent notes

- **Order.**  The user chose 0117 next (2026-11-09), after 0118.
- **The straights are plain gmsh, not hexmesh** (the evidence script
  documents gmsh): each is an OCC O-H section (core square, four ring
  patches; `nang` 4, `nrad` 2) extruded 3 slabs, the ten volumes
  fragmented, every curve, surface and volume set transfinite and
  recombined, as `Assembly` does.  The gap holds 4 written slabs
  (`NGAP`), on a straight line between the ports: the TFI of two
  parallel faces.
- **Two variants of step 0.**  `bounded`: the discrete volume declares
  the ten OCC port surfaces and its own discrete wall as its boundary
  (the x2 way).  `unbounded`: no declared boundary; the hexes only use
  the ports' node tags.  Both were run through every step.
- **Port nodes** are paired by (x, y): A's and B's port faces are meshed
  the same way.  A real junction would pair them by the port map
  (`check_port_pairs`), which is how hexmesh already matches faces.
- Physical groups as `Assembly.mesh()` names them: `fluid`,
  `fluid_inlet`, `fluid_outlet`, `wall`.
- gmsh 4.15.2 ran from a venv in the scratchpad (`pip install
  gmsh==4.15.2`), deleted after.

## Outcome

**Step 0, the OCC question: no obstacle.**  On gmsh 4.12.1 and 4.15.2 a
discrete volume holding hand-written hexes sits between OCC volumes, with
or without its OCC port surfaces declared as its boundary.  The hexes
reference the OCC surfaces' node tags and survive `write` (2.2 and 4.1),
a re-read and `gmshToFoam`.  Tutorial x2's warning ("OpenCASCADE does not
support" hybrid entities) didn't apply here: `addDiscreteEntity(3, -1,
[OCC surfaces…])` was accepted, and `getBoundary` returns them.

**Gates** (decision 0043's amendment), both variants, both versions:

| gate | result |
|---|---|
| conformal by construction | **pass.**  Port tags reused; no `removeDuplicateNodes`; nodes 627 = 456 (straights) + 171 (block interior).  Every interior face in exactly two hexes; boundary quads 256 = 256 expected (inlet 48, outlet 48, wall 96 + 64) |
| OpenFOAM (v2406, Docker) | **pass.**  `checkMesh`: Mesh OK, no failed check, 480 cells, 627 points, 1 region; patches `fluid_inlet` 48, `wall` 160, `fluid_outlet` 48 (the wall one singly connected patch over straights and block); cellZone `fluid`; max non-orthogonality 20.1° |
| no inverted cells | **pass.**  `would_invert` 0; min corner SJ 0.707 (the core's corners, in the straights) |
| reproducible | **pass.**  Both `.msh` versions byte-identical on a second run, on each gmsh version.  The 2.2 and 4.1 files are also identical between 4.12.1 and 4.15.2 |
| on gmsh 4.12 and 4.15 | **pass**, 4.12.1 and 4.15.2 |

`gmshToFoam` ran with `-keepOrientation` by task 0108's rule (min SJ > 0).

**Step 5, noted, not solved.**
- **Second order:** `setOrder(2)` turns the written hexes into Hex27
  with the rest.  The block's wall gets its high-order nodes on the
  straight chords (radius 0.981–1.0 R); the straights' are on the
  circle.  hexmesh would place them itself, as `_second_order` already
  does for projected walls.
- **Refinement:** gmsh's `refine()` splits the written block with the
  straights, still conformal (3840 hexes, 1024 boundary quads as
  expected).  A hexmesh `refined(k)` would instead rewrite the block's
  nodes at the new counts; nothing more appeared to be needed.
- **Ordering:** the ports must be meshed before the block is written
  (its nodes come from `getNodes` on them).  A second `generate(3)`
  after writing the block left it in place and conformal (627 nodes).

**Files.**
- `docs/integrations/evidence/gmsh_discrete_block.py` (new): the
  experiment; `--foam` adds the OpenFOAM step.
- `docs/integrations/gmsh.md`: the finding, replacing the open question.

No change under `hexmesh/`.  Meshes, cases and the 4.15 venv deleted.

**Follow-up** (design's): the B3 layout itself by decision 0043's next
amendment.  Its open items from here: the junction's own wall nodes need
placing on the wall (first and second order), and its port nodes pairing
through the port map.
