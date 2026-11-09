# 0121 — Example: an idealised aorta (arch, branches, taper and the iliac bifurcation)

- **Status:** ready (after 0118 settles the wye route)
- **Decision:** [0018 — Idealised vascular networks](../decisions/0018-future-vascular-networks.md) (a showcase within today's fittings, not 0018's input formats); [0043](../decisions/0043-wye-layout-redesign.md) (the bifurcation)
- **Depends on:** 0118 (and 0117 if it runs): the wye layout that will
  carry the iliac fork.  0062 (roll at any angle) for the arch branches.

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
   - the iliac bifurcation: the wye layout 0118 (or 0117) settles, with
     the daughters' own radius if that layout supports it; otherwise
     equal daughters followed by `Reducer`s, noted as a stand-in.
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
