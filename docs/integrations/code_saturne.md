# code_saturne

## Role

**Export check** (decision 0057): `validation/exports/code_saturne/`
(task 0181) checks that gmsh's I-DEAS `.unv` from `write()` is read by
code_saturne's preprocessor with its groups, and solves laminar
Poiseuille on it.  code_saturne is **not** a hexmesh dependency; it runs
in Docker, locally only (decision 0055).

## Versions

| code_saturne | Image | Status |
|---|---|---|
| 9.2.0 (built 2026-07-13) | `simvia/code_saturne:9.2.0@sha256:7639bc95baf6e5c284f4e67ea418ae6d46809410b7e04ed477983a8e39513ed5` (593 MB compressed, about 2 GB unpacked) | **Tested** 2026-11-19, task 0181 |

- The `simvia/code_saturne` repository on Docker Hub publishes version
  tags (8.3.0, 9.0.0, 9.0.1, 9.1.0, 9.2.0) and `stable`/`latest`;
  `codesaturne/code_saturne` denies anonymous pulls.  Built with CGNS
  4.4.0, MED 5.0.0 (HDF5 1.12.3), OpenMPI.

## Running it

- The image's entrypoint is `code_saturne`, its user `code_saturne`
  (uid 1000).  Run with `--entrypoint ""`, `-u $(id -u):$(id -g)` and
  `-e HOME=/work` so the output belongs to the host user.
- **Preprocessor alone:** `/opt/code_saturne/libexec/code_saturne/cs_preprocess
  mesh.unv --no-write` prints what it read.
- **A run:** a study (`MESH/`, `<case>/DATA/setup.xml`, `<case>/SRC/`,
  `<case>/RESU/`), then `code_saturne run --id <name>` from `DATA/`.  The
  smallest `setup.xml` that names the mesh:
  `<solution_domain><meshes_list><mesh name="mesh.unv"/></meshes_list></solution_domain>`;
  the rest from C++ user sources in `SRC/`, compiled by the run
  (`mpic++`, in the image).

## Reading hexmesh's `.unv`

- The equal tee (8000 cells): `Number of cells: 8000`, `hexa8 : 8000`,
  `quad4 : 1888`; every group by name, as a family: `fluid` (8000
  cells), `fluid_inlet`, `fluid_main_end`, `fluid_branch_end` (192
  faces each), `fluid_wall` (1312 faces).  `Element orientation check.`
  passes silently.  Each group's family also carries `Group "7"`, the
  colour gmsh writes on every element.

## User sources (9.2.0)

- **C++ linkage.**  9.2.0's `REFERENCE` user files define the hooks
  without `extern "C"`.  Wrapped in `BEGIN_C_DECLS`, the file compiled
  and some hooks ran (the zones, the extra operations) while others were
  silently not the solver's.
- **Boundary types face by face.**  `cs_boundary_add(domain->boundaries,
  CS_BOUNDARY_INLET, …)` (in `cs_user_parameters` or in
  `cs_user_boundary_conditions_setup`) with
  `cs_boundary_conditions_open_set_velocity_by_value` left every face a
  smooth wall in the legacy finite-volume solver: the run's table showed
  `Smooth wall 5 1368`, the inlet's velocity imposed on wall faces.
  Setting `bc_type[face] = CS_INLET / CS_OUTLET / CS_SMOOTHWALL` and
  `CS_F_(vel)->bc_coeffs->get_val_ext_v()` in
  `cs_user_boundary_conditions` works.
- **Steady algorithm:** `idtvar = CS_TIME_STEP_STEADY` settled into a
  limit cycle of its residuals (about 6e-3, 9e-3) on the pipe.  A
  constant time step to steady state works (`CS_TIME_STEP_CONSTANT`,
  `dt_ref`, `nt_max`); its residual history repeats with a period of
  200 steps at about 1e-3, but the fields are steady: Δp at 500 and 1000
  steps agreed to 1e-5.
- **A steady scalar with the flow frozen** (MMS conduction, task 0181,
  `src/cs_user_mms.cpp`): `cs_parameters_add_variable("tmms", 1)` in
  `cs_user_model`; in `cs_user_parameters`,
  `cs_time_control_init_by_time_step(&vp_param->time_control, -1, -1,
  -1, false, false)` so the velocity and pressure are never solved (they
  stay at rest), the field's `diffusivity_ref` key, and its
  `cs_equation_param_t`: `iconv = 0`, `istat = 0` (no time term, so each
  step solves the whole steady problem), `nswrsm = 1000`, `epsrsm =
  1e-13`, `epsilo = 1e-14`.  The source in `cs_user_source_terms`
  (`st_exp` = volume × S; the hook runs for every variable, so test
  `f_id`); a Dirichlet value per face with `icodcl[f] = CS_BC_DIRICHLET`
  and `get_val_ext()`, every face's `bc_type` set too.  `setup.log`
  lists the values as read; the residual reaches 1e-16 to 1e-14 at the
  first step, and T doesn't change over the next four.  The gradient is
  9.2.0's default for a scalar (`imrgra 4`).
- The boundary mass flux is the field
  `CS_F_(vel)->get_key_int(cs_field_key_id("boundary_mass_flux_id"))`;
  summed over a zone's faces it matches the run's own table.
