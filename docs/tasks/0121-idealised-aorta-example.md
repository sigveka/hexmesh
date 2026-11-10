# 0121 — Example: an idealised aorta (arch, branches, taper and the iliac bifurcation)

- **Status:** done (the design session, at the user's request, 2026-11-10)
- **Decision:** [0018 — Idealised vascular networks](../decisions/0018-future-vascular-networks.md) (a showcase within today's fittings, not 0018's input formats); [0043](../decisions/0043-wye-layout-redesign.md) (the bifurcation)
- **Depends on:** 0118 and 0117 (done): the iliac fork is today's
  `Wye` (the hub), with equal daughters and `Reducer`s (decision 0043,
  amendment 2026-11-10).  0062 (roll at any angle) for the arch branches.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  An illustrative case, agreed with the user (2026-11-09: "an
idealised aorta is the best place to start"): a recognisable vascular
geometry in the gallery, built only from hexmesh's fittings.  It shows
spline pipes, small-ratio branches at odd rolls, a taper and a
bifurcation in one model, and it is the first step towards decision
0018.  Inspired by Bošnjak et al. 2024's aorta (RESEARCH §4.3), but
idealised: no patient data (the AVT dataset, `radl_and_jin_etal_2022`,
has no stated data licence and needs a segmentation pipeline).

**Where.**  `hexmesh/examples/applications/` (an example module beside
the plant and HVAC ones), the gallery (`docs/gallery/build.py`), the
example registry, `docs/GALLERY.md`, `README.md`'s gallery rows if it
earns one.

**Do.**
1. **The geometry from a cited source.**  Take the dimensions from a
   published idealised aorta or from published typical adult values
   (ascending aorta and arch diameter, arch radius, the three arch
   branches' diameters and positions, the descending taper, the iliac
   diameters and bifurcation angle).  Cite each in the module's
   docstring and add the source to `docs/references.bib`.  No number
   without a source; where a source gives a range, take its middle and
   say so.
2. **Build it from fittings:**
   - the ascending aorta and arch: a `SplinePipe` (non-planar if the
     source's arch is);
   - the brachiocephalic, left common carotid and left subclavian
     arteries: `Tee`s on the arch, rolled to their directions (0062),
     each with a short branch run;
   - the descending and abdominal aorta: a `SplinePipe` and `Reducer`s
     for the taper;
   - the iliac bifurcation: today's `Wye` with equal daughters followed
     by `Reducer`s to the iliac radius, noted as a stand-in (unequal
     daughters wait for task 0124).
   - **Lumen only** (one fluid layer); a vessel wall shell is optional
     if it builds without new limits.
3. **Mesh and report** as the other examples: cell count before
   meshing, min SJ, non-orthogonality, every `validate()` warning and
   what it names; the gallery image and a section image.
4. **Inlet and outlets** named for what they are (`aortic_root`,
   `brachiocephalic`, …), so a user could set up a flow case from it.
   No CFD run in this task.

**Accept.**
- `python3 -m hexmesh.examples.applications.<name>` writes the mesh;
  the gallery shows it with its numbers.
- Every dimension cited.
- No new fitting or limit; anything the model needs that hexmesh lacks
  goes under *Questions for design*, not into the code.
- Full suite: no new failures; the gallery's other meshes unchanged.

**Out of scope.**  Patient-specific geometry (AVT, VMTK input: decision
0018); flow or pulsatile runs (a later case could use the Womersley
setup); new fittings.

## Agent notes

- **Sources** (all open access): Mansouri et al. 2024 Table 10 (the
  thoracic aorta, Normal type), Minichil et al. 2022 Table 1 (abdominal
  and common iliac diameters), Góes Junior et al. 2020 (bifurcation
  angle, 45°).  In `docs/references.bib`; Mansouri's PDF in
  `docs/papers/`.
- **Not found:** normative centreline lengths of the descending and
  abdominal aorta and the common iliacs.  20, 13 and 5 cm are stated in
  the docstring as modelling choices: a miss against step 1's "no number
  without a source".
- **The cited arch can't carry three straight tees** (the user chose
  option 1, 2026-11-10: "yes"): its top's radius of curvature is about
  4 cm on a 2.65 cm lumen, each tee needs about two branch diameters of
  straight run, and the spline between tees then bends tighter than the
  lumen's radius (`SplinePipe` rejects it).  The arch is 1.2 × the cited
  W and H, the smallest 0.1 step that builds; the left common carotid
  and left subclavian sit 1.66 and 1.40 cm downstream of their cited
  positions (`GAP`, half an arch diameter of curved arch between tees).
- **Splines between tees** follow a cubic Hermite curve between the two
  poses: sampling the ellipse itself left kinks where a tee's straight
  run leaves the curve.
- **Built at HEAD in a detached worktree** (the shared tree had task
  0123's edits in progress): 40 448 cells = predicted, min SICN 0.089,
  no inverted cells; warnings: the three arch tees' predicted SJ (0.20,
  0.14, 0.15; small r/R), the left common carotid's non-orthogonality
  (70.6°), the wye's crotch (79°).

## Outcome

**Status:** done, with one miss against step 1 (three lengths without a
source, stated in the docstring).

**Files.**  `hexmesh/examples/applications/idealised_aorta.py` (new),
registered in `hexmesh/examples/__init__.py`; the applications package's
docstring; `docs/references.bib` (`mansouri_and_kemerli_etal_2024`,
`minichil_and_tesfaye_etal_2022`, `goes_and_albuquerque_etal_2020`);
`docs/papers/mansouri_and_kemerli_etal_2024.pdf` (CC BY, gitignored);
`docs/GALLERY.md`, `docs/gallery/metrics.json`,
`docs/gallery/img/idealised_aorta{,_section,_cutaway}.png`;
`tests/test_second_order.py` (the aorta joins `WYES`: its iliac wye
rejects `order=2`, as every wye does).

**Gallery cut-away** (the user asked, 2026-11-10: "cooler colours and
maybe a cut-out on the part where the tees merge"):
`docs/gallery/build.py` gained an optional hook.  An example defining
`gallery_cutaway()` gets `img/<name>_cutaway.png`: whole cells removed by
its `keep` mask, faces coloured by kind (wall red, cut faces pale, open
ends blue; `CUTAWAY`).  Other examples' images are unchanged.  The
aorta's removes the arch's front half, along its bowed mid-surface, and
the first 2 cm of each branch.

**Numbers** (`nang` 8, gmsh 4.12.1): 40 448 cells = predicted; min
SICN 0.089, min SJ 0.133; no inverted cells.  Build 17.3 s in the
gallery's row.  This ran in the shared tree, with the coding session's
CPU-only byte-identity check running.  A first build measured 44.7 s
while the Re 3000 run was still reconstructing: contended, discarded.  Patches `fluid_aortic_root`, `fluid_brachiocephalic`,
`fluid_left_common_carotid`, `fluid_left_subclavian`,
`fluid_right_common_iliac`, `fluid_left_common_iliac`, `fluid_wall`;
the outlets point where they should (branches cranial, iliacs to the
patient's right and left).  Warnings: the three arch tees' predicted SJ
(0.20, 0.14, 0.15), the left common carotid's non-orthogonality (70.6°),
the wye's crotch (79°).

**Checks.**  At HEAD 3bdc2d0 plus this task's files (a detached
worktree): `tests/test_examples.py` for the aorta and the listing (2),
`tests/test_readme.py` and `tests/test_architecture.py` (82) pass.  The
coding session's full suite (2026-11-10) found the aorta failing
`test_second_order.py` (wye at order 2); fixed via `WYES`, and its case
passes.  The gallery rebuild above ran in the shared tree; the
gallery's other rows unchanged (`--only`); README unchanged.  The full
suite wasn't run (the example adds one parametrised case).

**Lessons** (the user asked, 2026-11-10): decision 0047 (length units),
decision 0048 (branches on curved vessels, proposed), task 0128 (units,
scale-freedom audit), task 0129 (two error messages).

