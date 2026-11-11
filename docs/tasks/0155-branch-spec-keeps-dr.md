# 0155 — A tee's branch keeps its shells' given thicknesses exactly

- **Status:** ready (after 0145; before 0143)
- **Decision:** none new (a bug).  Found by the design session building
  the rocket example (task 0140), 2026-11-12.
- **Depends on:** 0145 (it edits `assembly/tee.py`).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `hexmesh/assembly/tee.py` `branch_spec` rebuilds each branch
shell as `dR = t1 - t0`, from the main's outline radii, instead of
copying the shell's given `dR`.  The result differs in the last bits: a
main with steel `dR=0.0015` gives the branch 0.0015000000000000013.

A stack change on the branch line compares outlines exactly
(`sweep._check_termination`, `_layer_difference`), so starting a layer
there is rejected:

> stack change at cell 2: the remaining layers must match (`steel`
> radius 0.0015000000000000013 vs 0.0015); use a Reducer

**Repro.**  A ring spec: core r 0.0149, steel dR 0.0015.  A `Tee` with
branch r 0.01215.  On the branch,
`Straight(0.12, n_layers=8, stack_changes=((2, PipeSpec(nang=8).core("lox", radius=0.01215, nrad=4).shell("steel", dR=0.0015, nrad=2).shell("insulation", dR=0.02, nrad=2)),))`.

**Do.**
1. `branch_spec` copies a shell's given `dR` (with `nrad` and `mprg`, as
   now).  A shell given another way (`outer=`, `first_cell=`) keeps
   today's derivation.  Say under *Agent notes* if one exists on this
   path.
2. **No tolerance** in `_layer_difference`: the exact comparison stays.
   Other fittings rely on it, and loosening it would need a decision.
3. A regression test from the repro: the stack change on the branch is
   accepted, and the mesh builds.
4. Tell the design session.  The rocket example then drops its
   `copy.deepcopy(port.spec)` workaround for `spec(D, insulated=True)`.

**Accept.**
- The repro passes.
- Every example mesh byte-identical: copying `dR` should change no node.
  Report any that moves.
- Full suite: no new failures.

## Agent notes

## Questions for design

## Outcome
