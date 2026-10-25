# 0008 — Inlet and outlet extensions

- **Status:** done
- **Decision:** [0001 — Complete A5/A7 in the assembly prototype](../decisions/0001-complete-assembly-prototype.md)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  CFD boundary conditions need straight run before and after the
region of interest, typically 5–10 D upstream and more downstream.

**Do.**  Add `Assembly.extend_open_ends(upstream=5.0, downstream=10.0,
n_layers=...)`, in diameters.  It must run before `build()`:
- downstream: `add(iface, Straight(length))` on each open outlet
- upstream: needs a new inlet *before* the current one.  This fits the
  graph without hacks: place a new inlet frame `L` back along the current
  inlet's normal, add an edge `[new, old]` with a `Straight` (whose
  `validate` already checks that placement), and make the new interface
  `Assembly.inlet`.  Add this as `Assembly.prepend(fitting)`, limited to
  fittings that can be placed backwards (`Straight`).

Patch names of the extended ends must keep the original names.

**Accept.**  Outlet patch names are unchanged after extension, and the
total length is correct.

## Agent notes

- **Signature (refined).**  The task left `n_layers=...` open.  It is now
  `extend_open_ends(upstream=5.0, downstream=10.0,
  cells_per_diameter=4.0)`: each run gets `round(diameters ×
  cells_per_diameter)` axial cells, at least 1.  One `n_layers` would
  give a 5 D and a 10 D run different cell sizes.
- **Diameter** = 2 × the core radius of *that end's* spec, which is the
  flow passage, not the outer wall.  After a reducer, the downstream run
  uses the outlet's own diameter (tested).  0 skips a side.
- **`prepend(straight)`.**  It places the new inlet `length` back along
  the inlet normal, with the same `up`, and adds the edge `[new, old]`;
  `Straight.validate` checks the placement.  Anything but an exact
  `Straight` raises `TypeError`.  A non-open inlet (one closed into a
  loop) raises `AssemblyError`, and `extend_open_ends` then skips the
  upstream side.
- **Names.**  `patch_name` derives unnamed ends from the graph:
  `outlet` for a single end, else `port<index>`.  A new outlet would get
  a new index, so the old end's patch name is written onto the
  extension's outlet, and the old name is cleared.  The inlet name moves
  with `prepend`.  The tail follows its extension.
- **`Edge.kind`** is `"add"`, `"close"` or `"prepend"`.  The 0006 format
  inferred close edges from the graph, which a prepend edge would have
  confused.  The format now writes `prepend: true` edges, and a
  top-level `names` map (index → name, final state) in place of
  per-edge `names`.  `inlet` is interface 0, the first one created,
  because after a prepend `Assembly.inlet` is a later interface.  Still
  `version: 1`: the format is not yet in use outside this repo.

## Questions for design

_None._

## Outcome

- **Files:**
  - `assembly/assembler.py`: `Edge.kind`, `prepend`, `extend_open_ends`;
  - `assembly/intent.py`: prepend edges and the `names` map;
  - new `tests/test_extensions.py` (12 tests);
  - docs: `API.md`, `README.md`.
- **Accept:**
  - the total length is exact (−5 D … L + 10 D on a straight);
  - the patch physical-group names are identical before and after
    extension, for a straight, a named tee, an unnamed tee (`port<N>`)
    and a half-named tee;
  - the meshed cell count equals `cell_count()`.

  Extended assemblies round trip through JSON.
- **Tests:** 452 passed, 0 failed.
