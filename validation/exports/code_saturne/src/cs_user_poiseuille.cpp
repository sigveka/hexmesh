/*
 * hexmesh export check (validation/exports/code_saturne/run.py, task 0181):
 * laminar Poiseuille on a hexmesh .unv.  The zones are the mesh's groups
 * by name; the run writes the cell values to cells.csv at its end.
 * HEXMESH_U, HEXMESH_NU, HEXMESH_DT and HEXMESH_NT_MAX: the driver writes
 * them in (run.py, write_case).
 */
#include "base/cs_defs.h"
#include <stdio.h>
#include "cs_headers.h"

/* C++ linkage, as 9.2.0's REFERENCE user files: inside extern "C" some hooks
   are not the ones the solver calls */

void
cs_user_zones(void)
{
  cs_boundary_zone_define("inlet", "fluid_inlet", 0);
  cs_boundary_zone_define("outlet", "fluid_outlet", 0);
  cs_boundary_zone_define("wall", "fluid_wall", 0);
}

void
cs_user_model(void)
{
  /* time-marched to steady state: the steady algorithm (idtvar -1) settled
     into a limit cycle of its residuals on this case (9.2.0) */
  cs_get_glob_time_step_options()->idtvar = CS_TIME_STEP_CONSTANT;
  cs_get_glob_turb_model()->model = CS_TURB_NONE;
}

void
cs_user_parameters([[maybe_unused]] cs_domain_t *domain)
{
  cs_fluid_properties_t *fp = cs_get_glob_fluid_properties();
  fp->ro0 = 1.0;
  fp->viscl0 = HEXMESH_NU;
  cs_time_step_t *ts = cs_get_glob_time_step();
  ts->nt_max = HEXMESH_NT_MAX;
  ts->dt_ref = HEXMESH_DT;
}

/* The faces' types and the inlet's velocity, face by face.  (In 9.2.0's
   finite-volume solver, cs_boundary_add and the open-boundary helpers left
   every face a smooth wall.) */
void
cs_user_boundary_conditions([[maybe_unused]] cs_domain_t *domain, int bc_type[])
{
  auto vel = CS_F_(vel)->bc_coeffs->get_val_ext_v();
  const char *names[3] = {"inlet", "outlet", "wall"};
  const int types[3] = {CS_INLET, CS_OUTLET, CS_SMOOTHWALL};
  for (int k = 0; k < 3; k++) {
    const cs_zone_t *z = cs_boundary_zone_by_name(names[k]);
    for (cs_lnum_t j = 0; j < z->n_elts; j++) {
      const cs_lnum_t f = z->elt_ids[j];
      bc_type[f] = types[k];
      if (types[k] == CS_INLET) {
        vel(f, 0) = HEXMESH_U;
        vel(f, 1) = 0;
        vel(f, 2) = 0;
      }
    }
  }
}

void
cs_user_extra_operations([[maybe_unused]] cs_domain_t *domain)
{
  const cs_time_step_t *ts = cs_glob_time_step;
  if (ts->nt_cur != ts->nt_max || cs_glob_n_ranks > 1)
    return;
  const cs_mesh_t *m = cs_glob_mesh;
  const cs_mesh_quantities_t *mq = cs_glob_mesh_quantities;
  const cs_real_3_t *xc = (const cs_real_3_t *)mq->cell_cen;
  const cs_real_t *vol = mq->cell_vol;
  const cs_real_t *p = CS_F_(p)->val;
  const cs_real_3_t *v = (const cs_real_3_t *)CS_F_(vel)->val;
  FILE *f = fopen("cells.csv", "w");
  fprintf(f, "x,y,z,volume,p,u,v,w\n");
  for (cs_lnum_t i = 0; i < m->n_cells; i++)
    fprintf(f, "%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e\n", xc[i][0], xc[i][1],
            xc[i][2], vol[i], p[i], v[i][0], v[i][1], v[i][2]);
  fclose(f);
  /* the mass flux through each open zone */
  const int kbmasf = cs_field_key_id("boundary_mass_flux_id");
  const cs_real_t *bflux = cs_field_by_id(CS_F_(vel)->get_key_int(kbmasf))->val;
  f = fopen("massflow.csv", "w");
  fprintf(f, "zone,massflow\n");
  const char *names[2] = {"inlet", "outlet"};
  for (int k = 0; k < 2; k++) {
    const cs_zone_t *z = cs_boundary_zone_by_name(names[k]);
    cs_real_t q = 0;
    for (cs_lnum_t j = 0; j < z->n_elts; j++)
      q += bflux[z->elt_ids[j]];
    fprintf(f, "%s,%.16e\n", names[k], q);
  }
  fclose(f);
}

