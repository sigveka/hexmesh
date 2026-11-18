# 0183 — Export check: `.su2` in SU2

- **Status:** ready (after 0182)
- **Decision:** [0057](../decisions/0057-two-kinds-validation-and-export-checks.md)
  rule 3
- **Depends on:** 0182 (the framework and the format test helper).
- **Blocks:** 1.0 (decision 0057 rule 5).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  gmsh writes `.su2` with the group names as markers (probed
2026-11-18, `docs/integrations/gmsh.md`).  SU2 is open source.  An
export check makes `.su2` a checked path instead of an untested one.

**Do.**
1. **The consumer:** SU2, pinned.  Use a container image, or
   `pip`/conda in an isolated environment.  Record which, the version, and
   how to reproduce, in a new `docs/integrations/su2.md`.  It runs
   locally only (decision 0055).
2. **The format test (CI, no solver):** write a straight pipe and the
   tee to `.su2` through the 0182 helper.  Parse `NDIME`, `NELEM` with
   the element types (VTK hexahedron, 12), `NMARK` and the `MARKER_TAG`
   names.  Assert the counts against `cell_count()` and that every
   boundary group is a marker.  Say where volume groups (cell zones) go,
   since SU2 has no cell zones.
3. **The solve:** laminar incompressible Poiseuille in SU2's
   incompressible solver.
   - Inlet: a uniform or parabolic velocity, whichever SU2 takes simply.
   - Outlet: pressure.  Walls: no slip.
   - Use 2 or 3 levels of `refined(k)`, coarse to medium (under about
     200 000 cells).  Compare Δp over the developed length, and u_max,
     with the exact values.  Give the order.
   - OpenFOAM's Poiseuille case is the comparison.
4. **`validation/exports/su2/`**: a `case.json` of `kind: export`,
   `run.py` with the card hooks (0179's form), README and RESULTS.md.
   Its coarsest level joins the local check.
5. If SU2 rejects the file or loses markers, record the cause under
   *Questions for design*, and the status is `fails` (decision 0057:
   reported, and the format stays experimental).
6. Docs: `.su2` listed with its status where 0181 lists `.unv`.
   CHANGELOG.

**Accept.**
- The format test passes in CI.
- The solve reaches the exact Δp within a stated tolerance, with the
  order recorded.  Otherwise `fails` with the cause.
- The local check runs it.

**Out of scope.**  Compressible or turbulent SU2 runs; CGNS into SU2
(after 1.0, decision 0057 rule 3).

## Agent notes

## Questions for design

## Outcome
