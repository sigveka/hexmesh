# 0053 — Multi-layer wye: shells as offset level sets

- **Status:** ready (design answered Q1 2026-10-30: the thickness limit, error wrapping, 45° for shelled wyes)
- **Decision:** [0028 — Multi-layer junctions](../decisions/0028-multi-layer-junctions.md)
- **Depends on:** 0051.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The same as 0052, for the wye.  It is also the vessel wall
through a bifurcation (decision 0018).

**Where.**  `hexmesh/assembly/wye.py` (`Skeleton`, `check`, `layout`),
`blocks.py`, kit, `API.md`, `README.md`.

**Do.**
0. **Thin-shell probe first** (design, 2026-10-29, after 0056's Q3).
   Projection moves wall nodes about 0.14 R through the knee, which folds
   thin cells.  A realistic pipe wall is about 0.04 R thick.  Before
   anything else, a 90° and a 120° wye with one shell of T/R = 0.04,
   with the wall and shell boundary projected.  Does it fold, and what
   is the min corner SJ?  If it folds (or SJ < 0.1), stop and report
   under *Questions for design*: the wye-layout redesign then comes
   before this task.
1. **Level sets:** generalise `Skeleton` to a wall at any distance
   (`to_wall(p, radius)`, `curve(points, radius)`); shell l's outer
   boundary is `dist = R + T_l`.
2. **Levels:** as 0052, one block level per shell around every ring
   block, vertices projected onto `dist = R + T_l` along the same rays as
   the level-1 vertices, with exact surfaces (0051).
3. **Crotch limit:** the daughters' offset surfaces merge in the crotch;
   check before GMSH that every shell level keeps the crotch blocks
   valid (`BlockLayout.corner_jacobians` > 0 at least), naming the angle
   and thickness.  Measure angle ∈ {30, 60, 90, 120}° × T/R ∈ {0.05,
   0.2, 0.5} × one and two shells, `nang` 4 and 8.  Report min corner SJ
   and max non-orthogonality, and propose a limit under *Questions for
   design*.
4. Remove the single-layer rejection (circular shells only).

**Accept.**
- Kit cases (fluid + wall; fluid + wall + insulation) at 60° and 90°:
  all-hex, meshed = predicted, continuous `interface_*` groups, wall
  and interface nodes on their level sets (0051's tolerance), port
  signatures class 0.
- Single-layer wye meshes unchanged (node coordinates to 1e-12).
- The quality table and a proposed limit.
- Full suite: no new failures.

**Out of scope.**  Unequal daughters; non-coplanar wyes.

## Agent notes

**2026-10-30: steps 0, 1, 2 and 4 done; step 3 measured; the limit is Q1.**
- **Implementation** (`wye.py`):
  - `Skeleton.to_wall` / `curve` take a radius.
  - Shell level l repeats level 1 at R_l = R + T_l: station arcs, runs,
    daughter outer edges and hub top/bottom curves at R_l, crotch
    corners W(l) further out along W(1)'s ray from the daughter axis,
    and the crotch polylines with the crease apex at R_l·cot h.
  - One ring of blocks per shell between levels l − 1 and l; run
    blocks take their material from `face_patches`.
  - `lay.walls` has one projector per level: the tube union at R_l.
  - `check` accepts circular shells (rejects others, naming the shell);
    `thicknesses` is shared with the tee.
- **Single-layer wyes are unchanged:** node coordinates identical
  (difference 0.0) at 30°, 60°, 90°, 120°.
- **Step 0, thin-shell probe** (T/R = 0.04, shell `nrad` 1 and 2,
  `nang` 8, resolved counts): no fold.  Min corner SJ 0.164 at 90° and
  0.117 at 120°, the single-layer values (they are in the fluid; the
  shell's own cells are 0.218 / 0.162).  Projection moves 0.013–0.015 R.
  So the task went ahead.
- **Step 3, quality** (one shell `nrad` 2, R 0.1, run 0.4, branch 0.7;
  min corner SJ of the wye's cells by material; max non-orthogonality
  of faces touching them).  `nang` 4 / 8 and one or two shells agree
  closely, so per angle and total thickness:

  | angle | total T/R ≤ limit: fluid SJ | shell SJ | max non-orth. | largest total T/R | past it |
  |---|---|---|---|---|---|
  | 30° | 0.065 | 0.037–0.052 | 80–82° | 0.188 | projection folds the shells (`mesh()`) |
  | 45° | 0.133 | 0.149–0.165 | 77–80° | 0.281 | projection fold |
  | 60° | 0.156 | 0.20–0.24 | 74–78° | 0.398 | projection fold |
  | 90° | 0.164 | 0.21–0.22 | 73–77° | 0.586 | **OCC fails, uncaught** ("GeomFill_BSplineCurves: Courbes non jointives", "curve … has 0 end points"); from about 0.65 a hub shell block inverts (`validate()`) |
  | 120° | 0.117 | 0.16 | 78–80° | 0.844 | a hub shell block inverts (`validate()`) |

  - The largest thickness was bisected (one shell, to ±0.012 R) and is
    the same at `nang` 4 and 8.  The fluid's SJ never changes with the
    shell; checked monotone at intermediate thicknesses.
  - **The non-orthogonality is the single-layer wye's** (78° at 60°,
    80° at 120° without a shell); shells add nothing.
  - **Below 90° the limit is 0.69·tan(angle/2)·R** (0.185 / 0.286 /
    0.398 predicted at 30° / 45° / 60°).  The folded cells are shell
    cells just downstream of the daughter stations, near the mirror
    plane: the two daughters' shells meet there, since the stations are
    placed for the core radius.
- **Two layout variants tried and rejected** (scripts in the
  scratchpad, `0053/`):
  - *Crotch corner grown with the level* (t_crotch(R_l), as the tee's
    "level-1 construction with R grown"): folds more (60° at 2 × 0.2 R).
  - *Daughter stations placed for the outer radius*: raises the limit
    below 90° (30°: 0.42 R, 60°: 0.48 R), but at 120° it folds a 0.2 R
    shell while 0.04, 0.4 and 0.6 R work, and lowers the fluid's SJ at
    60° (0.156 → 0.134).  Not monotone, so not kept.  It's input for the
    wye-layout redesign.
- **Kit:** `wye-60-2layer`, `wye-90-2layer`, `wye-60-3layer`,
  `wye-90-3layer-oblique` (fluid + wall + insulation at 0.3 R; the kit's
  usual `_three`, 0.55 R, is past the 60° limit).  `wall_deviations`
  measures every level set.
- **Tests:** `test_wye.py`: the thin-shell probe at 90° and 120°; a
  rectangular shell rejected (replaces the single-layer rejection).

**Note from design (2026-10-29, decision 0029):** the wye's wall is
exact by **node projection**, not by OCC surfaces (task 0051 steps
5–8).  Build the shells the same way: each shell boundary gets the
projector at `dist = R + T_l`, applied in `Assembly.mesh()`.  The
crease-aware rule applies to every level, since offset surfaces crease
too.

## Questions for design

**Q1. Which shell-thickness limit should `Wye.check` enforce before
gmsh?**  Today a thick shell fails three ways: a fold caught only in
`mesh()`, an uncaught OCC exception at 90°, or a layout inversion caught
by `validate()` without naming angle and thickness.  Step 3 asks for a
check before gmsh naming both.
- **Proposal:** total shell thickness T ≤ R · min(0.65 tan(angle/2),
  0.55), i.e. 0.17 / 0.27 / 0.38 / 0.55 / 0.55 R at 30° / 45° / 60° /
  90° / 120°.  Each is under the measured limit (0.19 / 0.28 / 0.40 /
  0.59 / 0.84 R) with margin; the 0.55 cap stops short of the 90° OCC
  failure and is conservative at 120°.  The error names the angle, the
  thickness and the limit.
- **Alternatives:** a table interpolated in angle (tighter at 120°); or
  the 0.69 tan law alone plus a check that catches the OCC error and
  re-raises it as `AssemblyError`.
- **Also yours:** at 30° the shell cells' min corner SJ is 0.04–0.05
  even for thin shells (the fluid's is 0.065, already low).  Accept and
  document, or raise the narrowest supported angle for shelled wyes?
- The real fix for both is the wye-layout redesign; the
  outer-station experiment (*Agent notes*) suggests the daughter
  stations should depend on the outer radius there.

### Design answer to Q1 (2026-10-30)

The thin-shell probe passed (no fold at T/R 0.04), so the wye-layout
redesign stays after 0054.

1. **Thickness limit: your proposal.**
   - `T ≤ R · min(0.65 tan(angle/2), 0.55)`, in `limits.py`
     (`WYE_SHELL_TAN_FACTOR = 0.65`, `WYE_SHELL_MAX = 0.55`).
   - Checked in `Wye.check` before GMSH; the error names the angle, the
     total thickness and the limit.
   - Record the measured limits beside it (the margin is the point).
2. **No raw OCC or GMSH exception may escape a fill**, in any fitting,
   not only the wye.
   - Wrap the fill step (`Assembly.fill`, per fitting) so any OCC or
     GMSH error becomes an `AssemblyError` naming the fitting and
     quoting the original message.
   - Test it with a forced failure.
3. **Narrow shelled wyes:**
   - Measure the shell cells' min corner SJ at 40° (thin and at the
     limit).  The narrowest angle for a wye **with shells** is 40° if
     that's ≥ 0.1, else 45° (shell SJ ≥ 0.15 measured).
     `WYE_SHELL_MIN_ANGLE` in `limits.py`; the error names it.
   - **Single-layer wyes keep 30°–120°** (decision 0017, "be practical"),
     but warn when the layout's predicted min corner SJ is below 0.1
     (30°, 35° today), naming the value: the two tiers of 0047/0052,
     with the reject tier left off for the wye until the redesign.
4. Then finish: the check's tests (each side of the limit, at two
   angles), README/API wording, *Outcome*.

The outer-station experiment goes into the wye-layout redesign's
inputs (decision 0029, item 5).  Thanks for trying both variants.

## Outcome

**Partial (2026-10-30): steps 0–2 and 4 done, step 3 measured; blocked
on Q1 (the limit to enforce).**
- **Files:** `hexmesh/assembly/wye.py` (`Skeleton` level sets, shell
  levels in `layout`, per-level projectors, circular-shell check),
  `tests/test_fitting_conformance.py` (four kit cases, every level set
  measured), `tests/test_wye.py` (thin-shell probe, rectangular shell
  rejected), `tests/test_layer_outlines.py` (message), `API.md`,
  `README.md`.
- **Accept so far:** kit cases at 60° and 90°, fluid + wall and fluid +
  wall + insulation: all-hex, meshed = predicted, walls and interfaces
  on their level sets, signatures class 0 (all kit tests pass).
  Single-layer meshes identical.  Quality table under *Agent notes*.
- **Suite:** 1969 passed, 14 skipped; the one failure (an old
  "single-layer" message in `test_layer_outlines.py`) fixed, file
  re-run 48 passed.
- **Left for after Q1:** the pre-gmsh thickness check with its message,
  and its test.
