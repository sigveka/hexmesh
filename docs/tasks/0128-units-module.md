# 0128 — `hexmesh.units`: length constants, and an audit of absolute tolerances

- **Status:** done (the design session, at the user's request, 2026-11-11)
- **Decision:** [0047 — Length units](../decisions/0047-length-units.md); [0018](../decisions/0018-future-vascular-networks.md) (constraint 8)
- **Depends on:** none.  If task 0121 (the aorta) hasn't landed, leave
  its file to the design session and do step 3 for it afterwards.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Decision 0047: users write `CM = 0.01` and `INCH = 0.0254`
in every script.  One module of plain constants, metres underneath.

**Where.**  `hexmesh/units.py` (new), `hexmesh/interchange/importers/pcf.py`,
`hexmesh/examples/applications/idealised_aorta.py`, `API.md`,
`docs/GUIDE.md`, `CHANGELOG.md`, `tests/`.

**Do.**
1. **The module:** `m`, `cm`, `mm`, `um`, `inch`, `ft` as floats (metres
   per unit), with a docstring showing `radius=13.25 * mm`.  Not
   re-exported from `hexmesh`.  Listed in API.md beside "lengths are in
   metres".
2. **One source:** the PCF reader's `INCH` (and any other unit constant
   found by `grep`) imports from `hexmesh.units`.  Meshes unchanged.
3. **Use it** where an example's numbers come in other units (the aorta;
   any example that writes `* 1e-3` or `/ 1000` for a source in mm).
   Meshes byte-identical.
4. **Audit absolute lengths** (decision 0018, constraint 8): list every
   tolerance or default in `limits.py` and the fittings that is an
   absolute length in metres rather than relative to a radius or a cell
   (e.g. a merge or snap tolerance, a minimum length).  For each: what it
   is, its value, and whether a 1 mm vessel (radius 0.5 mm) would trip it.
   Fix it only if the fix is a one-line change to a relative tolerance
   with no mesh change; list the rest under *Questions for design*.
5. **The docs disagree today:** `hexmesh/core/params.py` says the
   `length` unit is "the user's length unit: hexmesh never converts",
   while API.md says lengths are metres (the architecture review,
   2026-11-10).  After step 4's audit, make both say the same thing,
   matching what the audit finds (metres, or any one unit if hexmesh is
   scale-free); the agent schema's `x-unit` text follows.
6. **Test:** a scaled build: the README's first example and one junction
   example with every length × 1e-3 (millimetre scale) validate and mesh
   with the same cell count and the same min SJ (to 1e-9) as at full
   size.  If one doesn't, that's an audit finding.

**Accept.**
- `from hexmesh.units import mm` works; API.md and GUIDE say so.
- No unit constant defined twice in the library.
- The audit table in *Outcome*; the scaled-build test passes or its
  failure is a question for design.
- *Outcome* says plainly whether hexmesh is scale-free (every length × k
  gives the same mesh scaled by k, to rounding), and what would have to
  change if not: decision 0047's note weighs an output `scale=` on it.
- Meshes byte-identical; full suite: no new failures.

**Out of scope.**  Quantity types, a per-assembly unit (decision 0047
rejects both); JSON in other units.

## Agent notes

- **Leaf module.**  `hexmesh/units.py` sits beside `errors.py`: anyone
  may import it (`tests/test_architecture.py` `LEAVES`, and the agent's
  `AGENT_IMPORTS`).
- **Step 2 found three sources, not one:** the PCF reader's `INCH` and
  its `1e-3`/`1e-5` tables, `interchange/graph.py`'s `TOL_FLOOR = 0.11 *
  0.0254`, and `agent/advise.py`'s `LENGTH_UNITS`.  All read
  `hexmesh.units` now; the floats are the same (`mm / 100 == 1e-5`
  exactly), so meshes and PCF reads are unchanged.
- **Step 3:** only the aorta writes another unit (`CM = 0.01`, now
  `from hexmesh.units import cm as CM`); no example writes `* 1e-3` or
  `/ 1000`.
- **Step 4 went past `limits.py`:** every registered limit is already
  relative (units `1`, `R`, `t`, `deg`, `layers`), so the audit searched
  the code for literal tolerances (`grep` for `1e-N` comparisons and
  gmsh/OCC calls with length defaults) and measured scale directly.
- **Step 5:** after the audit, "lengths are metres" everywhere:
  `core/params.py`'s `length` unit, API.md's units list and `describe`
  section, the agent manifest's line, and `describe`'s
  `units.length`, `"as given"` → `"m"` (a visible change; CHANGELOG
  says so).  `x-unit` stays `length`, whose meaning is now metres.
- **Step 6:** scale-free doesn't hold, so the test was split:
  `test_scaled_build_same_cells_and_quality` (the README tee at 1:20, a
  wye at 1:1000: same count, same min SJ to 1e-9) and a strict `xfail`,
  `test_small_tee_builds` (the README tee at 1:50), which will XPASS
  when the limitation is lifted.

## Questions for design

1. **Make the interior plates' tolerance relative?**  `blocks.py`'s
   interior `addSurfaceFilling(loop)` and `corners.py`'s side surfaces
   take gmsh's default `tol3d = 1e-4`, an absolute length.  Passing
   `tol3d` relative to the face (as the wall plates already do,
   `_WALL_TOL * scale`) made the README tee exact at half size (node
   drift 1e-15, from 7e-5) and let it build at 1:33.  But it changes
   full-size meshes (every junction's interior nodes move by up to
   ~1e-4 of the size), so the gallery numbers and pinned tests would
   move.  Options: (a) do it, regenerate the gallery, a CHANGELOG line;
   (b) leave it and keep "metres, not scale-free" as the documented rule.
   Either way the B-spline fill still fails near 1 mm radius
   (`Courbes non jointives`), which (a) alone doesn't fix.
2. **`interchange/graph.py` `TOL_FLOOR`**, 0.11" (2.8 mm), is an
   absolute connectivity floor (pcf2iso's weld gap).  Right for plant
   data; a vascular reader (decision 0018) would join points 2.8 mm
   apart.  Leave it per reader, or make it relative to the bore?  Not
   blocking: no vascular reader exists.

Neither blocks this task: the acceptance allows the scale test's failure
to be a question for design.

## Design answer (2026-11-11, the user: "It seems reasonable that to scale with bore, right?")

Q2: the connectivity floor scales with the bore, keeping the weld gap
for plant data: `min(0.11", 0.25 × the model's smallest bore)`.  Every
plant line from ½" up keeps 0.11" (0.25 × 15.8 mm ≈ 4 mm), so PCF
reads are unchanged; a 1 mm vessel gets 0.25 mm.  Task 0138.

Q1 (relative `tol3d` on the interior plates): the user's reasoning
points the same way; open until they confirm, since it moves
full-size junction meshes (gallery and pinned numbers regenerated).

## Outcome

**Done 2026-11-11.**  **hexmesh is not scale-free.**  The same network
with every length × s gives the same cell count and minimum scaled
Jacobian, but not the same nodes, and junctions fail below a few
millimetres.  Lengths are metres, and the docs now say so everywhere.

**Audit (step 4)**, absolute lengths found, and whether a 1 mm vessel
(radius 0.5 mm) trips them:

| Where | What | Value | Relative? | Trips at 1 mm? |
|---|---|---|---|---|
| `assembly/limits.py` | every registered limit | — | yes (`1`, `R`, `t`, `deg`, `layers`) | no |
| `profile.py` `CHORD_TOL` | profiled reducer chord gap | 1e-3 | yes (inlet radii) | no |
| `blocks.py` `_WALL_TOL` | wall plate `tol3d` | 1e-6 | yes (× face extent) | no |
| `blocks.py` interior `addSurfaceFilling(loop)`, `corners.py` | interior plate `tol3d` (gmsh default) | 1e-4 m | **no** | **yes**: drift from any scale; the README tee fails at 1:50 (2 mm radius) |
| `addBSplineFilling` (`sweep.py`, `blocks.py`) | OCC's own curve-join tolerance | (internal; *assumed* 1e-7 m) | **no** | **yes**: fails at 1:100 even with the plates scaled |
| `interchange/graph.py` `TOL_FLOOR` | PCF connectivity floor | 0.11" = 2.8 mm | **no** (by design) | yes, for a vascular reader (Q2) |
| `quality_hex._frob_cond` | singular-Jacobian guard | 1e-14 (m³) | **was no; fixed** | was: a perfect 10 µm cube scored mean ratio 0 |
| `quality_hex` face normals, lengths | zero guards | 1e-14 (m², m) | no | no (cells under ~0.1 µm) |
| `fittings.py` closure, `interchange/build.py` bore and insulation compares | equality guards | 1e-12, 1e-9 m | no | no (2e-6 of a 0.5 mm radius) |
| `projection.py`, `sweep.py`, `tee.py`, `wye.py`, `switch.py` port checks | position checks | 1e-9 | yes (× a length) | no |
| `Assembly.lc` default | gmsh characteristic length | outer radius / 4 | yes | no |
| gmsh `Geometry.Tolerance` | default 1e-8 | — | no | no effect measured (set to 1e-8 × s: nothing changed) |

The one-line fix made: `_frob_cond`'s guard is `1e-14 · ‖A‖ⁿ`; no mesh
changes (quality metrics only, and only for cells under ~20 µm or
near-degenerate ones).

**Measurements** (README tee, main radius 0.1 m; nodes compared with the
full-size mesh × s, relative to its size; `docs/integrations/gmsh.md`):

| s | builds | node drift | ΔSJ_min |
|---|---|---|---|
| 0.5 | yes | 7.4e-5 | 6e-17 |
| 0.2 | yes | 8.8e-5 | 7e-16 |
| 0.1 | yes | 1.7e-4 | 3e-16 |
| 0.05 | yes | 2.5e-4 | 4e-16 |
| 1/33 | yes | — | — |
| 0.03, 0.02, 0.001 | **no** ("Could not build surface filling") | | |

A wye (radius 0.1 m, no tee plates): exact (≤ 1e-13) to s = 0.01, drift
3.9e-6 at 0.001, builds.

**What would make it scale-free:** relative `tol3d` on the interior
plates (Q1; changes full-size meshes), then the B-spline filling's
fixed tolerance, which hexmesh can't set: either a different fill for
small faces, or building at a reference size and scaling the nodes on
output, the `scale=` decision 0047's note weighs.  The second is the
cheaper route to millimetre vessels: build the network ×1000 in
"metres" internally, mesh, and multiply the nodes by 1e-3 on write.

- **Files:** `hexmesh/units.py` (new); `hexmesh/interchange/importers/pcf.py`,
  `interchange/graph.py`, `agent/advise.py`, `agent/_describe.py`,
  `agent/_manifest.py`, `core/params.py`, `quality_hex.py`;
  `hexmesh/examples/applications/idealised_aorta.py`; `tests/test_units.py`
  (new), `tests/test_architecture.py`; `API.md` ("Length units"
  section, units list, `describe`), `docs/GUIDE.md` (metres and
  `hexmesh.units` under *Cross-section specification*; a *Current
  limitations* line), `CHANGELOG.md`, `docs/integrations/gmsh.md`.
- **Tests:** `tests/test_units.py` 8 passed, 1 xfailed (strict).
  Full suite (`-n 4`, 2026-11-11): 4079 passed, 15 skipped, 1 xfailed, 0 failed, 23.2 min.
- **Meshes:** unchanged (the same floats).
