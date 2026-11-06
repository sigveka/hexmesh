# 0100 — Trace why rectangle side counts are tied next to circles and shells

- **Status:** ready
- **Decision:** [0041 — Per-side counts on rectangles](../decisions/0041-per-side-counts-on-rectangles.md) (step 1)
- **Depends on:** none.  Investigation only: no library change.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0098 found `nang = nang_w = nang_h` in two cases:
- a `Transition` from a circle to a rectangle;
- a rectangular core with shell layers ("the spec's own rule").

The tie makes `hvac_branched` 10M cells and `cooling_channels` 20M at
"medium".  Decision 0041 picks a fix per case (B for shells, C for
transitions, A otherwise), but only once the cause of each tie is
known.  The design session found no tying check in `core/spec.py` on a
quick look.

**Do.**
1. **For each case, find what forces the tie**, naming the file and line:
   - a validation check (which one, which error code);
   - a construction that can't build otherwise (which function, and what
     fails when the counts differ: an error, a non-conformal face, an
     invalid transfinite surface);
   - or only the advisor's choice (`hexmesh/agent/advise.py`).
2. **Try untied counts** on a minimal case of each, in a scratch script
   (not committed):
   - a rectangle with `nang_w ≠ nang_h` and one shell (`dR`), then a
     rounded shell and a circular outer outline if supported;
   - a circle → rectangle `Transition` with `nang_w ≠ nang_h` on the
     rectangle.
   - For each: does it build, mesh and pass `validate()` and the meshed
     checks?  If it fails, record the error or the defect.
3. **Other tie sites.**  Search for any other place where per-side
   counts must equal `nang` (the O-H ↔ H switch, `Reducer`, junctions
   on ducts, `BundleSpec`).  List each with its reason.
4. **Estimate the gain.**  With `advise` (water at 2 mm/s, "medium"),
   recount the five tied examples as if the tie were lifted where step
   2 shows it can be.  Use the cell count only; don't mesh them.

**Accept.**
- A table under *Outcome*: per tie site, the cause (check / construction
  / advisor), file:line, and whether untied counts build and mesh.
- The five examples' cell counts, tied and untied.
- No library change; full suite unchanged.  Scratch meshes deleted.

**Out of scope.**  Lifting any tie.  That is a follow-up task per
option, written by the design session from this outcome.
