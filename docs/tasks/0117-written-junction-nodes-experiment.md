# 0117 — Written nodes (route B3): one hex block placed by hexmesh, between two transfinite straights

- **Status:** ready (next: 0118's cube missed the crease gate; design, 2026-11-09)
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
