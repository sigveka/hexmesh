# 0183 — Export check: `.su2` in SU2

- **Status:** done (2026-11-20; the local check's part handed to 0178)
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

- **Step 1:** no official SU2 image or pip package exists (Docker Hub and
  GHCR deny anonymous pulls), so `validation/exports/su2/Dockerfile`
  builds one from the v8.6.0 release zip (OpenMP build), with the zip's
  SHA-256 and the Ubuntu base's digest pinned.
- **Step 3, the inlet:** uniform.  SU2 is vertex-based, so the inlet's
  wall nodes take the no-slip and the inlet carries less than U·A (0.84
  of it at k = 1, a deficit falling at order 1).  The exact values are
  Poiseuille's at the bulk velocity SU2 reports through the outlet
  (`MARKER_ANALYZE`), not at the inlet's U.
- **Step 3, the stop:** a residual stop at 1e-12 on the pressure ended at
  152 iterations with Δp 5 % off; SU2's convergence monitor and its
  `history.csv` report different `rms[P]` (−17.5 against −21.0 at
  k = 1), so no threshold proved reliable.  The stored levels ran to a
  20 000-iteration cap; the driver now runs a fixed 2000 (the same Δp
  and u_max to four digits at k = 3).  `docs/integrations/su2.md`.
- **Step 4, "joins the local check":** `tools/local_check.py` doesn't
  exist yet (task 0178 is `ready`).  Noted in 0178's *Agent notes*: k = 1
  here has 1/27 of k = 3's cells: a few minutes at most.
- **Card hooks:** `check_level`, `prepare`, `run`, `collect`,
  `recompute`, as in the cases that have them; 0179's `python3 -m
  validation run` isn't there yet either.

## Questions for design

## Outcome

- **Passes.**  SU2 v8.6.0 reads every hexahedron and marker of the
  `.su2` at k = 1, 2, 3 (5 184, 41 472, 139 968 cells; all volume
  elements correctly oriented; one end face's 108 k² quads re-oriented
  by SU2 on reading, recorded per level).  Poiseuille's Δp and u_max:
  +2.41 %, +0.60 %, +0.26 % and +2.38 %, +0.59 %, +0.26 %; order 2.02
  for both; GCI 0.33 %; gate 2 % at the finest level.
- **Files:** `validation/exports/su2/` (`Dockerfile`, `run.py`,
  `case.json`, `README.md`, `RESULTS.md`, `results.json`, `figure.png`);
  `docs/integrations/su2.md` (new) and its row in the index;
  `tests/test_export_formats.py` (`read_su2`, the straight pipe and the
  tee); `validation/tools/plots.py`, `recheck.py`; `case.schema.json`
  (the `su2` toolchain); README, GUIDE, API.md, CHANGELOG (with 0181).
- **Cost:** 2000 iterations at k = 3 took 46 min (the thread count of that
  run wasn't recorded: 2 or 3).  Levels stored from now on carry `wall_s`
  and `cores` (task 0185).
- **Surprises:** the monitor/history disagreement above; the stop
  criterion matters more than the mesh at k = 3.
- **Follow-ups:** the local check (0178) and the card command (0179) pick
  this case up; CGNS into SU2 after 1.0 (decision 0057).
