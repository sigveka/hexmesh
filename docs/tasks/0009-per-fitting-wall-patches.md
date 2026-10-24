# 0009 — Per-fitting wall patches

- **Status:** ready
- **Decision:** [0001 — Complete A5/A7 in the assembly prototype](../decisions/0001-complete-assembly-prototype.md)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  All walls go into one `"{outer}_wall"` group (`assembler.py:292`).
Per-fitting wall patches give per-fitting wall shear, heat flux and
erosion results in post-processing.  DESIGN A7 already allows "optionally
also by fitting" for volumes.

**Do.**
1. `Assembly.write_physical_groups(walls_by_fitting=False)`.  When true,
   emit `"{outer}_wall_{fitting_name}"` per edge instead of one wall group,
   with each surface still in exactly one group (A7).
2. Fitting names: an optional `label` on `add()`, defaulting to
   `f"{type}{index}"`.  Not `name`: `add(..., names=...)` already names
   the outlet interfaces.

**Accept.**  The kit's "each surface belongs to exactly one physical group"
check passes with the option on.  The wall groups' union equals the
original wall group.

**Do not** add internal interface surfaces as physical groups in this
task.  How `gmshToFoam` treats internal physical surfaces is unverified.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
