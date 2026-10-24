# 0008 — Inlet and outlet extensions

- **Status:** ready
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

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
