"""
The FEniCSx side of task 0077, run inside the dolfinx container by
``run.py``: one mesh, every solve asked of it.

    python3 solve.py MESH.msh JOBS.json OUT.json

JOBS.json: ``{"w": [a, b, c], "phases": [...], "jobs": [{"degree": 1|2,
"variant": "dirichlet"|"neumann"}, ...]}``.  Solves −∇²u = f, f = −∇²u_m
(UFL, symbolically), u_m = sin(a x + φ₀) sin(b y + φ₁) sin(c z + φ₂);
Dirichlet: u = u_m on every boundary; Neumann: ∂u/∂n = ∇u_m · n on the
wall (``*_wall`` facets), u = u_m on the rest, with n the **exact** wall's
normal (``walls``: capped cylinders and tori; at each point, the one whose
surface is nearest), not the mesh's: a straight-sided cell's normal is
wrong by O(h), and that is the geometry error measured.  Errors in L2 and
H1 (seminorm) with quadrature degree 8.
"""

import json
import resource
import sys
import time

import numpy as np
import ufl
from dolfinx import fem
from dolfinx.fem.petsc import LinearProblem
from dolfinx.io import gmsh as gio
from mpi4py import MPI

path, jobs_path, out_path = sys.argv[1:4]
spec = json.load(open(jobs_path, encoding="utf-8"))
data = gio.read_from_msh(path, MPI.COMM_WORLD, 0, gdim=3)
m, ft = data.mesh, data.facet_tags
groups = data.physical_groups                       # name -> (dim, tag)
wall_tags = [t for name, (d, t) in groups.items() if d == 2 and name.endswith("_wall")]
other_tags = [t for name, (d, t) in groups.items() if d == 2 and not name.endswith("_wall")
              and "interface" not in name]
w, ph = spec["w"], spec["phases"]
x = ufl.SpatialCoordinate(m)
um = (ufl.sin(w[0] * x[0] + ph[0]) * ufl.sin(w[1] * x[1] + ph[1])
      * ufl.sin(w[2] * x[2] + ph[2]))
f = -ufl.div(ufl.grad(um))
def _exact_normal(walls):
    """The exact wall's outward normal at x: per primitive, the unit
    vector from its centreline to x and the distance error |d − r|; the
    nearest primitive's normal (nested ``ufl.conditional``)."""
    best = None
    for p in walls:
        if p["kind"] == "seg":
            a, b = ufl.as_vector(p["a"]), ufl.as_vector(p["b"])
            L = float(np.linalg.norm(np.subtract(p["b"], p["a"])))
            u = (b - a) / L
            s = ufl.max_value(0.0, ufl.min_value(L, ufl.dot(x - a, u)))
            q = x - (a + s * u)
        else:
            c, ax = ufl.as_vector(p["c"]), ufl.as_vector(p["axis"])
            r = x - c
            plane = r - ufl.dot(r, ax) * ax
            q = x - (c + p["rb"] * plane / ufl.sqrt(ufl.dot(plane, plane)))
        d = ufl.sqrt(ufl.dot(q, q))
        nrm, miss = q / d, abs(d - p["r"])
        if best is None:
            best = (nrm, miss)
        else:
            closer = ufl.lt(miss, best[1])
            best = (ufl.as_vector([ufl.conditional(closer, nrm[i], best[0][i]) for i in range(3)]),
                    ufl.conditional(closer, miss, best[1]))
    return best[0]


n = _exact_normal(spec["walls"])
ds = ufl.Measure("ds", domain=m, subdomain_data=ft, metadata={"quadrature_degree": 8})
dxq = ufl.dx(domain=m, metadata={"quadrature_degree": 8})
rows = []
for job in spec["jobs"]:
    t0 = time.perf_counter()
    V = fem.functionspace(m, ("Lagrange", job["degree"]))
    uD = fem.Function(V)
    uD.interpolate(fem.Expression(um, V.element.interpolation_points))
    tags = other_tags if job["variant"] == "neumann" else other_tags + wall_tags
    facets = np.concatenate([ft.find(t) for t in tags])
    bc = fem.dirichletbc(uD, fem.locate_dofs_topological(V, 2, facets))
    u, v = ufl.TrialFunction(V), ufl.TestFunction(V)
    a = ufl.inner(ufl.grad(u), ufl.grad(v)) * dxq
    L = f * v * dxq
    if job["variant"] == "neumann":
        L += sum(ufl.inner(ufl.grad(um), n) * v * ds(t) for t in wall_tags)
    uh = LinearProblem(a, L, bcs=[bc], petsc_options_prefix=f"j{len(rows)}_",
                       petsc_options={"ksp_type": "cg", "pc_type": "hypre",
                                      # low-complexity BoomerAMG: the default
                                      # setup needs > 6 GB for Q2 at k = 4 (tee)
                                      "pc_hypre_boomeramg_coarsen_type": "HMIS",
                                      "pc_hypre_boomeramg_interp_type": "ext+i",
                                      "pc_hypre_boomeramg_P_max": 4,
                                      "pc_hypre_boomeramg_agg_nl": 1,
                                      "ksp_rtol": 1e-12, "ksp_atol": 1e-14,
                                      "ksp_max_it": 5000}).solve()
    err = lambda form: float(np.sqrt(m.comm.allreduce(fem.assemble_scalar(fem.form(form)),
                                                       op=MPI.SUM)))
    rows.append({**job, "dofs": V.dofmap.index_map.size_global,
                 "l2": err((uh - um) ** 2 * dxq),
                 "h1": err(ufl.inner(ufl.grad(uh - um), ufl.grad(uh - um)) * dxq),
                 "l2_norm": err(um ** 2 * dxq),
                 "seconds": round(time.perf_counter() - t0, 1),
                 "peak_rss_gb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 2)})
out = {"mesh": path, "geometry_degree": m.geometry.cmap.degree,
       "cells": m.topology.index_map(3).size_global, "rows": rows}
json.dump(out, open(out_path, "w", encoding="utf-8"), indent=1)
