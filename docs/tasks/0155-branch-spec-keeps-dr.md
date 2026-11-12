# 0155 — A tee's branch keeps its shells' given thicknesses exactly

- **Status:** done
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

- **Step 1:** `branch_spec` passes `sh.dR` when the shell has one.  A
  shell given by `outer=` has `dR = None` and keeps `t1 - t0`.  A shell
  given by `first_cell=` still has its `dR` (and its solved `mprg`, copied
  as before), so it takes the exact path.  No other derivation exists on
  this path.
- **Moved meshes (acceptance asks to report them):** 33 of 35 examples
  byte-identical to `HEAD`.  `pcf_line` (817 of 38171 nodes) and
  `rocket_injector_manifold` (4134 of 86997) move by at most 1.6e-13 of
  the size: the branch shells' outer radii, now the given dR instead of
  the rounded difference.  Same node counts.

## Questions for design

## Outcome

Done 2026-11-12.

- `hexmesh/assembly/tee.py` `branch_spec`: the given `dR`, exactly.
  `_layer_difference` unchanged (exact comparison).
- `tests/test_tee.py::test_branch_keeps_the_given_dR_so_a_stack_change_matches`:
  the repro (ring spec, branch r 0.01215, insulation starting at cell 2
  of the branch line) builds and meshes; `branch_spec`'s steel `dR` is
  exactly 0.0015.  It fails without the fix (`0.0015000000000000013 ==
  0.0015`).
- Tests: junction, stack-change and example set (24 files), 1775
  passed, 1 skipped.  Meshes: see *Agent notes* (two examples move at
  rounding level, 1.6e-13 of the size).

