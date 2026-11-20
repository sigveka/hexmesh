/*
 * hexmesh export check (validation/exports/code_saturne/run.py, task 0181):
 * steady conduction with the MMS case's manufactured field
 * (validation/mms/run.py) on a hexmesh .unv.  A user scalar, diffusivity 1,
 * the flow frozen at rest:  -div(grad T) = S,  S = (a² + b² + c²) T_m,
 * T = T_m on every boundary face (at its centre), the source at the cell
 * centres.  The run writes the cell values to cells.csv at its end.
 * HEXMESH_W0..2 (the wave numbers), HEXMESH_P0..2 (the phases) and
 * HEXMESH_NT_MAX: the driver writes them in (run.py, write_mms).
 */
#include "base/cs_defs.h"
#include <math.h>
#include <stdio.h>
#include "cs_headers.h"

/* C++ linkage, as 9.2.0's REFERENCE user files */

static const cs_real_t w[3] = {HEXMESH_W0, HEXMESH_W1, HEXMESH_W2};
static const cs_real_t phase[3] = {HEXMESH_P0, HEXMESH_P1, HEXMESH_P2};

static cs_real_t
t_m(const cs_real_t x[3])
{
  return sin(w[0] * x[0] + phase[0]) * sin(w[1] * x[1] + phase[1])
         * sin(w[2] * x[2] + phase[2]);
}

void
cs_user_model(void)
{
  cs_get_glob_time_step_options()->idtvar = CS_TIME_STEP_CONSTANT;
  cs_get_glob_turb_model()->model = CS_TURB_NONE;
  cs_parameters_add_variable("tmms", 1);
}

void
cs_user_parameters([[maybe_unused]] cs_domain_t *domain)
{
  /* the flow is never solved: it stays at rest */
  cs_velocity_pressure_param_t *vp_param = cs_get_glob_velocity_pressure_param();
  cs_time_control_init_by_time_step(&(vp_param->time_control), -1, -1, -1, false, false);

  cs_fluid_properties_t *fp = cs_get_glob_fluid_properties();
  fp->ro0 = 1.0;
  fp->viscl0 = 1.0;
  cs_time_step_t *ts = cs_get_glob_time_step();
  ts->nt_max = HEXMESH_NT_MAX;
  ts->dt_ref = 1.0;

  cs_field_t *f = cs_field_by_name("tmms");
  f->set_key_double(cs_field_key_id("diffusivity_ref"), 1.0);
  cs_equation_param_t *eqp = cs_field_get_equation_param(f);
  eqp->iconv = 0;            /* no convection */
  eqp->istat = 0;            /* steady: each step solves the whole problem */
  eqp->nswrsm = 1000;        /* sweeps for the non-orthogonal reconstruction */
  eqp->epsrsm = 1e-13;
  eqp->epsilo = 1e-14;
}

void
cs_user_source_terms([[maybe_unused]] cs_domain_t *domain,
                     int f_id,
                     cs_real_t *st_exp,
                     cs_real_t *st_imp)
{
  if (f_id != cs_field_by_name("tmms")->id)
    return;
  const cs_mesh_t *m = cs_glob_mesh;
  const cs_mesh_quantities_t *mq = cs_glob_mesh_quantities;
  const cs_real_3_t *xc = (const cs_real_3_t *)mq->cell_cen;
  const cs_real_t k2 = w[0] * w[0] + w[1] * w[1] + w[2] * w[2];
  for (cs_lnum_t i = 0; i < m->n_cells; i++) {
    st_imp[i] = 0.;
    st_exp[i] = mq->cell_vol[i] * k2 * t_m(xc[i]);
  }
}

/* every boundary face: a wall for the (frozen) flow, T = T_m for the scalar */
void
cs_user_boundary_conditions([[maybe_unused]] cs_domain_t *domain, int bc_type[])
{
  const cs_mesh_t *m = cs_glob_mesh;
  const cs_real_3_t *xf = (const cs_real_3_t *)cs_glob_mesh_quantities->b_face_cog;
  cs_field_t *f = cs_field_by_name("tmms");
  int *icodcl = f->bc_coeffs->icodcl;
  auto val = f->bc_coeffs->get_val_ext();
  for (cs_lnum_t j = 0; j < m->n_b_faces; j++) {
    bc_type[j] = CS_SMOOTHWALL;
    icodcl[j] = CS_BC_DIRICHLET;
    val[j] = t_m(xf[j]);
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
  const cs_real_t *t = cs_field_by_name("tmms")->val;
  FILE *f = fopen("cells.csv", "w");
  fprintf(f, "x,y,z,volume,T\n");
  for (cs_lnum_t i = 0; i < m->n_cells; i++)
    fprintf(f, "%.16e,%.16e,%.16e,%.16e,%.16e\n", xc[i][0], xc[i][1], xc[i][2],
            mq->cell_vol[i], t[i]);
  fclose(f);
}
