# SU2

## Role

**Export check** (decision 0057): `validation/exports/su2/` (task 0183)
checks that gmsh's `.su2` from `write()` is read by SU2 with its markers,
and solves laminar Poiseuille on it.  SU2 is **not** a hexmesh
dependency; it runs in Docker, locally only (decision 0055).

## Versions

| SU2 | Image | Status |
|---|---|---|
| v8.6.0 "Harrier" (released 2026-10-30) | `hexmesh-su2:8.6.0`, built from `validation/exports/su2/Dockerfile`: the release's `SU2_v8.6.0_linux64-omp.zip` (sha256 `b306dcb7…41ac`, checked in the build) on `ubuntu:24.04@sha256:008173c2…3ca3` | **Tested** 2026-11-19, task 0183 |

## Getting it

- **No official image or pip package** (2026-11-19): `su2code/su2` and
  `ghcr.io/su2code/su2` on Docker Hub and GHCR deny anonymous pulls,
  and SU2's download page lists only the release binaries and source.
  The Dockerfile pins both the base image (digest) and the zip
  (SHA-256); `docker build -t hexmesh-su2:8.6.0 validation/exports/su2`.
- The **OpenMP** build (`-omp`) needs only `libgomp1`; the `-mpi` build
  would need MPICH in the image.  Threads: `SU2_CFD -t <n>` with
  `OMP_NUM_THREADS=<n>`.

## Reading hexmesh's `.su2`

- gmsh writes `NDIME= 3`, `NELEM` with the volume cells as VTK types
  (12, hexahedron), `NPOIN`, then `NMARK` and per boundary group a
  `MARKER_TAG= <group name>` with its faces (VTK 9, quad).  **The
  volume groups' names are not in the file**: SU2 has no cell zones, so
  a layered mesh's zones merge into one volume (`tests/test_export_formats.py`).
- **SU2 reads it as written:** its log lists every hexahedron (`5184
  hexahedra.`), the three markers by name with their face counts, and
  `All volume elements are correctly oriented.`
- **One end face is re-oriented on reading:** `There has been a
  re-orientation of 108 QUADRILATERAL surface elements.`: one end
  face's quads at each level (108 k²), so gmsh writes one of the two
  end faces with its normal the other way from SU2's convention.  SU2
  fixes it itself; the solution is unaffected.  Recorded per level as
  `reoriented_surface`.

## Solving (incompressible, laminar)

- `SOLVER= INC_NAVIER_STOKES`, `KIND_TURB_MODEL= NONE`,
  `INC_DENSITY_MODEL= CONSTANT`, `INC_NONDIM= DIMENSIONAL`,
  `MARKER_INLET= ( name, T, |U|, nx, ny, nz )` with
  `INC_INLET_TYPE= VELOCITY_INLET`, `MARKER_OUTLET= ( name, p )`,
  `MARKER_HEATFLUX= ( wall, 0.0 )` for a no-slip wall; the keys taken
  from SU2's own `TestCases/incomp_navierstokes/bend/lam_bend.cfg` at
  the v8.6.0 tag.
- **Vertex-based:** values sit at the nodes.  The inlet's nodes on the
  wall take the wall's no-slip, so a uniform inlet velocity U passes
  less than U·A on a coarse mesh: 0.84 of it at k = 1 (n_arc 6), 0.92 at
  k = 2, 0.94 at k = 3.  Compare against the realised bulk velocity, not
  the inlet's U.
- **The mass flow:** `MARKER_ANALYZE= ( markers )` with
  `HISTORY_OUTPUT= (…, FLOW_COEFF_SURF)` writes
  `Avg_Massflow(<marker>)` per marker to `history.csv` (the plain
  `FLOW_COEFF` group sums the markers: in + out ≈ 0, density 2.0).
- **Convergence on the pressure residual stops too early:** with
  `CONV_FIELD= RMS_PRESSURE` at −12 the k = 3 pipe stopped at 152
  iterations with the inlet's and outlet's mass flows 1.6 % apart and
  Δp off by 5 %.  `CONV_FIELD= RMS_VELOCITY-X` at −14 (184 iterations)
  was still short: Δp +2.7 %.  Run for a fixed 2000 iterations, the
  k = 3 pipe was stationary from about 1000 (the pressure residual at
  −21.9 in `history.csv`) with Δp and u_max both within +0.26 %.
- **The convergence monitor and `history.csv` disagree:** at k = 1 the
  history's `rms[P]` sits at −21.0 from early on while the monitor's
  table reports `rms[P] −17.54` against its criterion, so a threshold
  means different things in the two.  At −20 (and at −18, tried at
  k = 1) no level stopped; the stored levels ran to a 20 000-iteration
  cap (`converged: false`, the values stationary).  The driver now runs
  a fixed 2000 iterations (`ITER= 2000`, the residual stop off).
- **The reported mass flows differ at convergence:** inlet 1.4768e-6,
  outlet 1.4841e-6 at k = 3 (0.5 %), unchanged from iteration 1000 to
  2000; a difference in how `MARKER_ANALYZE` integrates over the end
  faces, not a drift.  The driver takes the outlet's.
- `OUTPUT_FILES= (RESTART_ASCII)` writes `restart.csv`: `PointID, x, y,
  z, Pressure, Velocity_x, …` per node.
