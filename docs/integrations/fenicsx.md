# FEniCSx (dolfinx)

## Role

**Secondary solver** (decision 0034), the first consumer of hexmesh's
second-order export: `validation/fenicsx_second_order/` (task 0077)
checks that a Hex27 mesh from `mesh(order=2)` is read and used as curved
geometry.  FEniCSx is **not** a hexmesh dependency; it runs in Docker.

## Versions

| dolfinx | Image | Status |
|---|---|---|
| 0.11.0 (`0.11.0.post0`) | `dolfinx/dolfinx:v0.11.0@sha256:2ae4bfbc0d9077268880faf04c72750528bee986c94ab223a2c159969bd56fa8` (published 2026-06-11; 1.1 GB compressed, 3.4 GB unpacked) | **Tested** 2026-11-10, task 0077 |

## Running it

- **Docker, as the host user:** `docker run --rm -u $(id -u):$(id -g)
  -e HOME=/tmp -v <work>:/work -v <case>:/case:ro -w /work <image>
  python3 /case/solve.py …`, as the OpenFOAM runner does (no root-owned
  output).  `HOME=/tmp` gives the non-root user a writable home for
  FFCx's JIT cache (set from the start; running without it wasn't
  tried).
- One container per solve, each capped with `--memory 6g --memory-swap
  6g` (`run.py --memory`).  The mesh is read again for each solve, but
  each solve's memory is released when its container exits, and a solve
  that runs out of memory is killed alone (exit 137) instead of the
  machine reaching its limit.  An earlier version ran every solve on one
  mesh in a single process; Claude Code's memory guard stopped it during
  the tee at k = 4 (2026-11-10).

## Reading hexmesh's `.msh`

- **Reader:** `dolfinx.io.gmsh.read_from_msh(path, comm, rank, gdim=3)`
  (`dolfinx.io.gmshio` before 0.10).  It returns `mesh`, `cell_tags`,
  `facet_tags` and `physical_groups` (name → (dim, tag)), read from the
  physical groups hexmesh writes: `body` as cell tags, `body_wall`,
  `body_inlet`, … as facet tags.  The reader merges the file with gmsh
  inside the container (gmsh's Python module ships in the image).
- **MSH 4.1** (hexmesh's `write()` default) reads, `$Comments` block
  (hexmesh's recipe and logo) included.
- **Element types** (task 0077, 2026-11-10):

  | hexmesh | gmsh type | dolfinx |
  |---|---|---|
  | `write()` (Hex8) | 5 | read; geometry degree 1 |
  | `write(order=2)` (Hex27) | 12 | read; geometry degree 2 (`m.geometry.cmap.degree`) |
  | `write(order=2, incomplete=True)` (Hex20) | 17 | **rejected**: `KeyError: np.int32(17)` in the reader's cell-type map; dolfinx has no serendipity hexahedron geometry |

## Known quirks

### Exact Dirichlet or flux data hide the geometry error — *verified*

A manufactured solution defined everywhere (task 0074's product of sines)
with u = u_m on the mesh's boundary, or ∂u/∂n = ∇u_m · n with n the
mesh's own `FacetNormal`, is consistent on the meshed (polygonal) domain:
Q2 on a Hex8 mesh then converges at order 3, like Hex27, and the
geometry isn't tested at all (straight pipe, k = 1 → 2: L2 9.0e-3 →
1.2e-3 on both).  The wall's position enters only through data taken from
the **exact** wall: the Neumann data with the exact normal (task 0077's
`solve.py`).  Evidence: task 0077, 2026-11-10.

### BoomerAMG's default setup runs out of memory on Q2 at about 1.1 M dofs — *verified*

CG with `pc_type hypre` (BoomerAMG with PETSc's defaults), Q2 on the tee
at k = 4 (138 240 cells, 1 131 505 dofs): the container was killed at its
6 GB cap.  The low-complexity settings `pc_hypre_boomeramg_coarsen_type
HMIS`, `interp_type ext+i`, `P_max 4` and `agg_nl 1` solve the same
system at a 4.4 GB peak (`ru_maxrss`), in 150–185 s.  At the same 1e-12
tolerance the results are unchanged: the tee at k = 2 matches the
default setup's errors to four digits.  Evidence: task 0077, 2026-11-10.

## Open questions

- MPI partitioning of a mesh with several volume groups: not tried (all
  of task 0077's runs are serial).
