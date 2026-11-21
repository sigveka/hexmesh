#        _.-------._
#    .-''     |     ''-.
#  .'  \      |      /  '.     _                                         _
# /     +-----+-----+     \   | |__   ___  __  __  _ __ ___   ___  ___  | |__
# |     |     |     |     |   | '_ \ / _ \ \ \/ / | '_ ` _ \ / _ \/ __| | '_ \
# |-----+-----+-----+-----|   | | | |  __/  >  <  | | | | | |  __/\__ \ | | | |
# |     |     |     |     |   |_| |_|\___| /_/\_\ |_| |_| |_|\___||___/ |_| |_|
# \     +-----+-----+     /
#  '.  /      |      \  .'    structured all-hex meshes for pipe networks
#    '-..     |     ..-'
#        '---------'
#
"""
Turbulent flow through a 90° bend, RANS k-ω SST, against the PTB LDA
measurements (decision 0012, task 0050).

    python3 validation/turbulent_bend/run.py --np 4             # k = 1, 2, 3
    python3 validation/turbulent_bend/run.py --levels 1 --np 4

**The rig** (Straka et al. 2020, as Ekat et al. 2023 report it): water at
30 °C, D = 0.1 m, w_vol = 0.40035 m/s, Re = 50 000; a 90° bend of
curvature radius 1.425 D after about 95 D of straight pipe; the axial
velocity w on the horizontal line through the axis at six planes, 2.43 to
30.82 D after the bend (``reference/lda_fig3.json``, read from their
Fig. 3's vector paths).

**The network.**  7 D of straight pipe, the bend, 32 D of straight pipe
at the same axial cell, then 10 D with the axial cells growing 4× to the
outlet (the paper's 42 D downstream).  The section: n_arc 8, the wall
cell 50 viscous units high at the design u_τ, the ring's radial growth at
most 1.15 (as task 0049's wall-function cases), an axial cell of D/4;
``refined(k)`` scales every count by k.

**The inlet** is fully developed: a precursor, the periodic pipe of task
0049 on the same section at the same k, solved first; its cell values of
U, k and ω are mapped face by face onto the bend's inlet (the sections
are identical, so each inlet face's centre is a precursor cell's centre
projected, to rounding).

**Model:** task 0049's gated wall-function set: k-ω SST, ``kqRWall``,
``omegaWall`` and Spalding's ``nutUSpaldingWallFunction`` (y⁺ 50 at k = 1,
about 17 at k = 3: Spalding's law holds across the buffer layer).
``potentialFoam`` starts the field; steady ``simpleFoam`` to residuals.

**Quantities.**
- w / U_b at the 19 LDA points of each plane, from the cell values in a
  slab two axial cells thick about the plane (linear in 3-D);
- the RMS difference from the LDA over those points (the gate: 10 % of
  w_vol at the finest level), and the side of the peak (the gate: the
  measured side, the outer wall, at every plane);
- the bend's loss coefficient K: the drop in area-mean pressure between
  1 D before the bend and 30 D after it, less the straight pipe's
  friction over the same axial length (f from the precursor), over
  ½ U_b²; reported with GCI, no gate.

OpenFOAM v2406 in Docker by default.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import shutil
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from hexmesh import Assembly, Bend, PipeSpec, Session, Straight   # noqa: E402
from hexmesh.study import openfoam as of                          # noqa: E402


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


conv = _load("convergence", "validation/tools/convergence.py")     # richardson() (task 0089)
stored = _load("stored", "validation/tools/results.py")            # results.json (task 0093)
tp = _load("turbulent_pipe_run", "validation/turbulent_pipe/run.py")   # task 0049's set-up

# --- the rig --------------------------------------------------------------------
D = 0.1
R = D / 2
U_B = 0.40035              # w_vol [m/s]
RE = 50_000
NU = U_B * D / RE          # water at 30 °C, as the Reynolds number gives it
R_K = 1.425 * D            # the bend's curvature radius
UPSTREAM, DOWNSTREAM, TAIL = 7 * D, 32 * D, 10 * D
TAIL_GROWTH = 4.0          # the last 10 D's axial cells grow to 4× toward the outlet
PRECURSOR = R              # the periodic pipe's length (task 0049's)

# --- the mesh at k = 1 ------------------------------------------------------------
N_ARC = 8
WALL_YPLUS = 50            # the wall cell's height in viscous units at the design u_τ
AXIAL = D / 4              # the axial cell in the straights and the bend
TAIL_LAYERS = 20
LEVELS = (1, 2, 3)         # here; k = 4 (3.8 M cells) is for volunteers (task 0169)

#: the planes, in D after the bend, and the K planes
PLANES = (2.43, 5.56, 10.7, 15.69, 20.82, 30.82)
K_BEFORE, K_AFTER = 1.0, 30.0
RMS_GATE = 0.10            # of w_vol (design answer Q1, 2026-11-15)
F_GATE = 0.05              # the precursor's f against McKeon (task 0049's wall-function gate)
START = "rest"             # the bend's start; the refined(k) levels ran from potentialFoam -writep
REFERENCE = HERE / "reference" / "lda_fig3.json"


def ito_k(re: float = RE, r_over_d: float = R_K / D, theta: float = 90.0) -> float:
    """Ito (1960)'s loss coefficient of a smooth 90° bend, for Re (a/R)² > 91,
    as Villegas-León et al. (2021) give it (their eqs. 8 and 10; Ito's
    paper isn't open): ξ = 0.004314 K θ Re^-0.17 (r/D)^0.84, K = 0.95 +
    4.421 (r/D)^-1.96 for 2 r/D < 19.7, θ in degrees.  Ito's range: Re 2e4
    to 4e5, 90° bends of r/D 1 to 3.3.  His ξ is the loss in the bend and
    the excess downstream, the straight pipe's friction taken out: as K
    here."""
    if 0.25 * re / r_over_d ** 2 <= 91 or 2 * r_over_d >= 19.7 or theta != 90:
        raise ValueError("outside the branch of Ito's correlation used here")
    k = 0.95 + 4.421 * r_over_d ** -1.96
    return 0.004314 * k * theta * re ** -0.17 * r_over_d ** 0.84


def design_u_tau() -> float:
    return U_B * math.sqrt(tp.mckeon(RE) / 8)


def first_cell(yplus: float = WALL_YPLUS) -> float:
    """The wall cell's height: *yplus* viscous units at the design u_τ."""
    return yplus * NU / design_u_tau()


def _ring(first: float) -> int:
    """The smallest n_radial whose growth toward the centre is at most
    task 0049's GROWTH_MAX."""
    for n in range(2, 200):
        try:
            s = PipeSpec(n_arc=N_ARC).core("fluid", radius=R, n_radial=n, first_cell=first)
        except Exception:                          # first cell too large for n cells
            continue
        if 1 / s.to_dict()["core"]["radial_grading"] <= tp.GROWTH_MAX:
            return n
    raise ValueError(f"no ring for a first cell of {first}")


def spec(k: int = 1, yplus: float = WALL_YPLUS) -> PipeSpec:
    """The section of a fixed-wall family at level *k* (design answers Q2,
    Q3): n_arc and the radial cells outside the wall cell × k, the wall
    cell *yplus* viscous units high at every level.  At k = 1 and
    WALL_YPLUS it is the k = 1 section of ``refined(k)`` too."""
    first = first_cell(yplus)
    n = 1 + (_ring(first) - 1) * k
    return PipeSpec(n_arc=N_ARC * k).core("fluid", radius=R, n_radial=n, first_cell=first)


def _network(sp: PipeSpec, k: int) -> Assembly:
    """The bend network on section *sp*, the axial counts × k: along +x,
    the bend turning toward +y in the horizontal plane z = 0 (the
    paper's y = 0 line lies in it)."""
    asm = Assembly(sp, position=[0, 0, 0], direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(UPSTREAM, n_layers=round(UPSTREAM / AXIAL) * k))
    asm.add(Bend(R_K, 90, n_layers=round(R_K * math.pi / 2 / AXIAL) * k, toward=(0, 1, 0)))
    asm.add(Straight(DOWNSTREAM, n_layers=round(DOWNSTREAM / AXIAL) * k))
    n = TAIL_LAYERS * k                                    # axial_grading: cell to cell
    asm.add(Straight(TAIL, n_layers=n, axial_grading=TAIL_GROWTH ** (1 / (n - 1))))
    return asm


def assembly(k: int = 1, fam: str = None) -> Assembly:
    """The bend network at level *k* of family *fam* (:data:`FAMILIES`):
    ``refined(k)`` of k = 1 (the first study, which shrinks the wall cell
    as 1/k), or a fixed-wall family."""
    yplus = FAMILIES[fam or REFINED]
    if yplus is not None:
        return _network(spec(k, yplus), k)
    asm = _network(spec(1), 1)
    return asm if k == 1 else asm.refined(k)


def precursor(k: int = 1, fam: str = None) -> Assembly:
    """The periodic pipe on the same section, placed so its inlet is the
    bend network's (task 0049's two layers at k = 1)."""
    yplus = FAMILIES[fam or REFINED]
    m = 1 if yplus is None else k
    asm = Assembly(spec(m, yplus or WALL_YPLUS), position=[0, 0, 0], direction=[1, 0, 0],
                   up=[0, 0, 1])
    asm.add(Straight(PRECURSOR, n_layers=tp.N_LAYERS * m))
    return asm if yplus is not None or k == 1 else asm.refined(k)


def meshes():
    """(label, caption, build) per mesh shown in README.md."""
    return [("bend", "the bend network, k = 1", lambda: assembly(1))]


# --- where the planes are -----------------------------------------------------------
#: the bend's start, its centre of curvature, and the axis after it
BEND_START = np.array([UPSTREAM, 0.0, 0.0])
CENTRE = BEND_START + [0.0, R_K, 0.0]
AXIS_X = UPSTREAM + R_K               # after the bend the axis runs along +y at x = AXIS_X
BEND_END_Y = R_K


def plane_points(z_over_d: float, x_over_r) -> np.ndarray:
    """The paper's line y = 0 at *z_over_d* after the bend: x/R = −1 is the
    outer wall, away from the bend's centre of curvature (+x here)."""
    x_over_r = np.asarray(x_over_r, float)
    return np.c_[AXIS_X - x_over_r * R, np.full(len(x_over_r), BEND_END_Y + z_over_d * D),
                 np.zeros(len(x_over_r))]


# --- OpenFOAM dictionaries -----------------------------------------------------------
H = of.header

BEND_CONTROL = tp.CONTROL
#: task 0049's solution settings, with potentialFoam's (the bend's start)
BEND_SOLUTION = (tp.SOLUTION
                 .replace("solvers\n{", "solvers\n{\n    Phi\n    {\n        solver          GAMG;\n"
                          "        smoother        GaussSeidel;\n        tolerance       1e-8;\n"
                          "        relTol          0.01;\n    }", 1)
                 .replace("SIMPLE\n{", "potentialFlow\n{\n    nNonOrthogonalCorrectors 3;\n}\n"
                          "SIMPLE\n{", 1))
#: task 0049's schemes, with the scheme potentialFoam -writep needed (kept: harmless without it)
BEND_SCHEMES = tp.SCHEMES.replace("    div(phi,U) ", "    div(div(phi,U)) Gauss linear;\n    div(phi,U) ", 1)
FIELDS = ("U", "p", "k", "omega", "nut")


def _common(case: Path, end_time: int) -> None:
    for d in ("0", "constant", "system"):
        (case / d).mkdir(parents=True, exist_ok=True)
    files = {
        "system/controlDict": H("dictionary", "controlDict", "system")
        + BEND_CONTROL.format(end_time=end_time),
        "system/fvSchemes": H("dictionary", "fvSchemes", "system") + BEND_SCHEMES,
        "system/fvSolution": H("dictionary", "fvSolution", "system") + BEND_SOLUTION,
        "constant/transportProperties": H("dictionary", "transportProperties", "constant")
        + f"transportModel  Newtonian;\nnu              {NU!r};\n",
        "constant/turbulenceProperties": H("dictionary", "turbulenceProperties", "constant")
        + tp.TURBULENCE,
    }
    for name, text in files.items():
        (case / name).write_text(text, encoding="utf-8")


def _start() -> tuple[float, float]:
    """k and ω to start from: 5 % intensity, a 0.07 D mixing length."""
    k = 1.5 * (0.05 * U_B) ** 2
    return k, math.sqrt(k) / (0.09 ** 0.25 * 0.07 * D)


def write_precursor(case: Path, end_time: int) -> None:
    _common(case, end_time)
    (case / "system/createPatchDict").write_text(
        H("dictionary", "createPatchDict", "system")
        + tp.CREATE_PATCH.format(L=repr(PRECURSOR)), encoding="utf-8")
    (case / "constant/fvOptions").write_text(
        H("dictionary", "fvOptions", "constant") + tp.FVOPTIONS.format(u=repr(U_B)),
        encoding="utf-8")
    k, omega = _start()
    internal = {"U": f"uniform ({U_B!r} 0 0)", "p": "uniform 0", "k": f"uniform {k!r}",
                "omega": f"uniform {omega!r}", "nut": "uniform 0"}
    for f in FIELDS:
        cls = "volVectorField" if f == "U" else "volScalarField"
        w = tp.WALL["wfs"][f].format(k=repr(k), omega=repr(omega))
        (case / "0" / f).write_text(
            H(cls, f, "0") + f"dimensions      {tp.DIMS[f]};\ninternalField   {internal[f]};\n"
            "boundaryField\n{\n    cyc_in      { type cyclic; }\n"
            f"    cyc_out     {{ type cyclic; }}\n    fluid_wall  {{ {w} }}\n}}\n",
            encoding="utf-8")


def _nonuniform(values: np.ndarray) -> str:
    if values.ndim == 1:
        body = "\n".join(repr(float(v)) for v in values)
        return f"nonuniform List<scalar> {len(values)}\n(\n{body}\n)"
    body = "\n".join("(" + " ".join(repr(float(c)) for c in v) + ")" for v in values)
    return f"nonuniform List<vector> {len(values)}\n(\n{body}\n)"


def write_bend(case: Path, end_time: int, inlet: dict) -> None:
    """The bend's fields: the precursor's U, k and ω on the inlet; the
    outlet at p = 0 (inletOutlet for the rest); the walls as task 0049's
    Spalding set."""
    _common(case, end_time)
    k, omega = _start()
    internal = {"U": "uniform (0 0 0)", "p": "uniform 0", "k": f"uniform {k!r}",
                "omega": f"uniform {omega!r}", "nut": "uniform 0"}
    inl = {"U": f"type fixedValue; value {_nonuniform(inlet['U'])};",
           "p": "type zeroGradient;",
           "k": f"type fixedValue; value {_nonuniform(inlet['k'])};",
           "omega": f"type fixedValue; value {_nonuniform(inlet['omega'])};",
           "nut": "type calculated; value uniform 0;"}
    out = {"U": "type inletOutlet; inletValue uniform (0 0 0); value uniform (0 0 0);",
           "p": "type fixedValue; value uniform 0;",
           "k": f"type inletOutlet; inletValue uniform {k!r}; value uniform {k!r};",
           "omega": f"type inletOutlet; inletValue uniform {omega!r}; value uniform {omega!r};",
           "nut": "type calculated; value uniform 0;"}
    for f in FIELDS:
        cls = "volVectorField" if f == "U" else "volScalarField"
        w = tp.WALL["wfs"][f].format(k=repr(k), omega=repr(omega))
        (case / "0" / f).write_text(
            H(cls, f, "0") + f"dimensions      {tp.DIMS[f]};\ninternalField   {internal[f]};\n"
            f"boundaryField\n{{\n    fluid_inlet  {{ {inl[f]} }}\n"
            f"    fluid_outlet {{ {out[f]} }}\n    fluid_wall   {{ {w} }}\n}}\n",
            encoding="utf-8")


# --- the mesh's geometry, read back ---------------------------------------------------

def geometry(case: Path) -> dict:
    mesh = case / "constant/polyMesh"
    pts, faces = of.read_points(mesh / "points"), of.read_faces(mesh / "faces")
    owner, neigh = of.read_labels(mesh / "owner"), of.read_labels(mesh / "neighbour")
    fc, sf = of.face_geometry(pts, faces)
    n_cells = int(max(owner.max(), neigh.max())) + 1
    cc, vol = of.cell_geometry(fc, sf, owner, neigh, n_cells)
    return {"fc": fc, "sf": sf, "owner": owner, "cc": cc, "vol": vol, "boundary": mesh / "boundary"}


def inlet_values(pre: Path, bend: Path, k: int) -> dict:
    """The precursor's last U, k, ω at the bend's inlet faces: each face
    takes the precursor cell of the first layer whose centre, projected
    on x = 0, is nearest (identical sections: the distance is rounding)."""
    from scipy.spatial import cKDTree
    g, b = geometry(pre), geometry(bend)
    t = of.latest_time(pre)
    U = of.read_internal(t / "U", 3)
    kk = of.read_internal(t / "k", 1).ravel()
    om = of.read_internal(t / "omega", 1).ravel()
    dx = PRECURSOR / (tp.N_LAYERS * k)                          # the axial cell
    first = g["cc"][:, 0] < g["cc"][:, 0].min() + 0.25 * dx     # the first layer's centres
    faces = of.read_patch_faces(b["boundary"], "fluid_inlet")
    dist, near = cKDTree(g["cc"][first][:, 1:]).query(b["fc"][faces][:, 1:])
    if len(np.unique(near)) != len(faces) or dist.max() > 1e-6 * D:
        raise RuntimeError(f"inlet mapping: {len(np.unique(near))} cells for {len(faces)} "
                           f"faces, worst distance {dist.max():.2e} m")
    idx = np.flatnonzero(first)[near]
    area = np.linalg.norm(b["sf"][faces], axis=1)
    return {"U": U[idx], "k": kk[idx], "omega": om[idx],
            "u_bulk": float(np.sum(U[idx, 0] * area) / area.sum()),
            "map_distance_max": float(dist.max())}


def _mean_p(cc, vol, p, mask) -> float:
    return float(np.sum(p[mask] * vol[mask]) / vol[mask].sum())


def results(case: Path, k: int, pre: dict) -> dict:
    """The six planes' w at the LDA points, the RMS and peak side, and K."""
    from scipy.interpolate import LinearNDInterpolator
    ref = json.loads(REFERENCE.read_text(encoding="utf-8"))
    g = geometry(case)
    cc, vol = g["cc"], g["vol"]
    t = of.latest_time(case)
    U = of.read_internal(t / "U", 3)
    p = of.read_internal(t / "p", 1).ravel()
    after = cc[:, 0] > CENTRE[0] + 0.5 * R_K          # past the bend: the downstream pipe
    planes = {}
    for z in PLANES:
        lda = ref["planes"][f"{z:g}"]
        xr = np.array(lda["x_over_R"])
        y = BEND_END_Y + z * D
        near = after & (np.abs(cc[:, 1] - y) < 1.5 * AXIAL / k) & (np.abs(cc[:, 2]) < 0.6 * R)
        w = LinearNDInterpolator(cc[near], U[near, 1])(plane_points(z, xr)) / U_B
        err = w - np.array(lda["w_over_wvol"])
        peak = float(xr[np.nanargmax(w)])
        planes[f"{z:g}"] = {"w_over_ub": [None if not np.isfinite(v) else float(v) for v in w],
                            "rms": float(np.sqrt(np.nanmean(err ** 2))),
                            "peak_x_over_r": peak, "peak_w": float(np.nanmax(w)),
                            "lda_peak_x_over_r": float(xr[int(np.argmax(lda["w_over_wvol"]))])}
    # K between 1 D before the bend and 30 D after: area-mean p in slabs one axial cell thick
    before = (np.abs(cc[:, 0] - (UPSTREAM - K_BEFORE * D)) < 0.5 * AXIAL / k)
    later = after & (np.abs(cc[:, 1] - (BEND_END_Y + K_AFTER * D)) < 0.5 * AXIAL / k)
    p1, p2 = _mean_p(cc, vol, p, before), _mean_p(cc, vol, p, later)
    length = K_BEFORE * D + R_K * math.pi / 2 + K_AFTER * D
    q = 0.5 * U_B ** 2
    k_total = (p1 - p2) / q
    k_bend = k_total - pre["f"] * length / D
    return {"planes": planes, "p_before": p1, "p_after": p2, "k_total": k_total,
            "k_bend": k_bend, "k_length_m": length}


def precursor_results(case: Path, log: str) -> dict:
    """f from the momentum balance of the periodic pipe (task 0049)."""
    g = geometry(case)
    wall = of.read_patch_faces(g["boundary"], "fluid_wall")
    a_wall = float(np.linalg.norm(g["sf"][wall], axis=1).sum())
    grads = [float(v) for v in re.findall(r"pressure gradient = ([-\d.eE+]+)", log)]
    tau = grads[-1] * g["vol"].sum() / a_wall
    U = of.read_internal(of.latest_time(case) / "U", 3)
    ub = float(np.sum(g["vol"] * U[:, 0]) / g["vol"].sum())
    f = 8 * tau / ub ** 2
    n = g["sf"][wall] / np.linalg.norm(g["sf"][wall], axis=1)[:, None]
    d = np.abs(np.einsum("ij,ij->i", g["cc"][g["owner"][wall]] - g["fc"][wall], n))
    yplus = math.sqrt(tau) * d / NU
    return {"f": f, "f_mckeon": tp.mckeon(RE), "f_err_mckeon": f / tp.mckeon(RE) - 1,
            "u_b": ub, "yplus_first_mean": float(yplus.mean()),
            "yplus_first_max": float(yplus.max())}


# --- one level ------------------------------------------------------------------------

def _mesh(case: Path, asm: Assembly, name: str) -> dict:
    with Session(name):
        cells = asm.cell_count()
        msh = case / "mesh.msh"
        asm.write_openfoam(str(msh))
        q = asm.check_quality("scaled_jacobian")
        sicn = asm.check_quality("minSICN").worst
    of.convert(case, msh, keep_orientation=q.worst > 0)     # task 0108
    return {"cells": cells, "min_sj": q.worst, "min_sicn": sicn, "msh": msh}


def setup(d: Path, k: int, end_time: int, fam: str = None) -> dict:
    """Mesh and set up the precursor (d/precursor) and the bend (d/bend)."""
    pre, bend = d / "precursor", d / "bend"
    for c in (pre, bend):
        if c.exists():
            shutil.rmtree(c)
        c.mkdir(parents=True)
    write_precursor(pre, end_time)
    fam = fam or REFINED
    mp = _mesh(pre, precursor(k, fam), f"bend-precursor-{k}")
    of.foam("createPatch -overwrite", pre, "log.createPatch")
    _common(bend, end_time)
    asm = assembly(k, fam)
    mb = _mesh(bend, asm, f"bend-{k}")
    check = of.check_mesh(bend)
    meta = {"k": k, "family": fam, "cells": mb["cells"],
            "precursor_cells": mp["cells"], "min_sj": mb["min_sj"], "min_sicn": mb["min_sicn"],
            "check": check, "counts": stored.counts(asm),
            "first_cell": (None if FAMILIES[fam] is None              # refined(k): split k ways
                           else first_cell(FAMILIES[fam]))}
    (d / "setup.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta


def solve(d: Path, k: int, end_time: int, n_proc: int) -> dict:
    """The precursor, the mapping, then the bend; returns the level."""
    pre, bend = d / "precursor", d / "bend"
    meta = json.loads((d / "setup.json").read_text(encoding="utf-8"))
    t0 = time.monotonic()
    # one process: decomposed, the cross-flow residuals (Uy, Uz, zero on
    # average) floor at 2-5e-7, above residualControl (fixed_k2, 2026-11-20)
    log = of.run_solver(pre, "simpleFoam", n_proc=1)
    pre_log = log
    pr = precursor_results(pre, log)
    pr["steps"] = int(re.findall(r"^Time = (\d+)", log, re.M)[-1])
    pr["converged"] = "solution converged in" in log
    inlet = inlet_values(pre, bend, k)
    write_bend(bend, end_time, inlet)
    # from rest (U = 0 inside, the precursor's profile at the inlet), no
    # potentialFoam: on fixed_k2 its first Phi solve stalled at 1000
    # iterations and its velocity reached 2.7e4 m/s in the thin wall cells,
    # blowing simpleFoam up at step 1 (2026-11-20)
    t1 = time.monotonic()
    log = of.run_solver(bend, "simpleFoam", n_proc=n_proc)
    steps = re.findall(r"^Time = (\d+)", log, re.M)
    out = {"k": k, "family": meta.get("family", REFINED), "cells": meta["cells"],
           "precursor_cells": meta["precursor_cells"],
           **meta["counts"], "min_sj": meta["min_sj"], "min_sicn": meta["min_sicn"],
           **{f"check_{key}": v for key, v in meta["check"].items()},
           "re": RE, "u_b": U_B, "nu": NU, "start": START,
           "precursor": {**pr, "wall_s": t1 - t0},
           "inlet_u_bulk": inlet["u_bulk"], "inlet_map_distance_max": inlet["map_distance_max"],
           "steps": int(steps[-1]) if steps else 0,
           "converged": "solution converged in" in log, "bend_wall_s": time.monotonic() - t1,
           "solve_s": stored.clock_s(pre_log, log)}
    out.update(results(bend, k, pr))
    return out


def run_level(k: int, work: Path, end_time: int, n_proc: int, fam: str = None) -> dict:
    d = work / level_name(k, fam)
    meta = setup(d, k, end_time, fam)
    print(f"[k={k}] {meta['cells']} cells (precursor {meta['precursor_cells']}), "
          f"min SJ {meta['min_sj']:.3f}, max non-orthogonality "
          f"{meta['check']['max_non_orthogonality']:.1f}", flush=True)
    return solve(d, k, end_time, n_proc)


# --- the families -------------------------------------------------------------------

REFINED, FIXED, FIXED25 = "refined", "fixed_wall", "fixed_wall_25"
#: family → the fixed wall cell's height in viscous units (None: refined(k) splits it)
FAMILIES = {REFINED: None, FIXED: WALL_YPLUS, FIXED25: 25}
#: family → its level names' prefix
PREFIX = {REFINED: "", FIXED: "fixed_", FIXED25: "fixed25_"}
#: the studies in order (design answer Q3): refined(k), the wall at 50, the wall at 25
STUDIES = (REFINED, FIXED, FIXED25)


def level_name(k: int, fam: str = None) -> str:
    """``k<k>`` (``refined(k)``), ``fixed_k<k>`` (the wall at 50) or
    ``fixed25_k<k>`` (the wall at 25)."""
    return f"{PREFIX[fam or REFINED]}k{k}"


def family(levels: list[dict], name: str) -> list[dict]:
    """*levels* of one family, coarse to fine (levels stored before the
    fixed-wall family have no ``family``: ``refined(k)``)."""
    return sorted((lv for lv in levels if lv.get("family", REFINED) == name),
                  key=lambda r: r["k"])


# --- analysis -------------------------------------------------------------------------

#: the convergence quantities: K, and the peak w at two planes
SERIES = ("k_bend", "peak_w_2.43", "peak_w_10.7")


def _series(lv: dict, q: str) -> float:
    if q.startswith("peak_w_"):
        return lv["planes"][q[len("peak_w_"):]]["peak_w"]
    return lv[q]


def analyse(levels: list[dict], name: str = REFINED) -> dict:
    """Richardson / GCI on :data:`SERIES` over k = 1, 2, 3 of family
    *name*.  ``refined(k)`` nests (spacing ratios 2 and 1.5); the
    fixed-wall levels don't, so their ratios are the representative cell
    size's, h = (V/N)^(1/3) (Celik et al. 2008), from the cell counts."""
    rows = [r for r in family(levels, name) if r["k"] in (1, 2, 3)]
    if len(rows) != 3:
        return {}
    if name == REFINED:
        r21, r32 = 1.5, 2.0
    else:
        n1, n2, n3 = (r["cells"] for r in rows)
        r21, r32 = (n3 / n2) ** (1 / 3), (n2 / n1) ** (1 / 3)
    return {q: conv.richardson(*(_series(r, q) for r in rows), r21=r21, r32=r32)
            for q in SERIES}


def recheck(data: dict) -> list[dict]:
    """The gates at the finest stored level (task 0050, design answer
    Q1): the RMS of w along y = 0 within 10 % of w_vol, and the peak on
    the measured side, at each plane; K and the peaks' convergence
    reported (GCI), with the paper's SST RMS beside ours."""
    ref = json.loads(REFERENCE.read_text(encoding="utf-8"))
    out = []
    # the verdict is on the fixed-wall family once it has levels (design
    # answer Q2); refined(k) is the first study
    name = next(f for f in reversed(STUDIES) if family(data["levels"], f) or f == REFINED)
    tag = "" if name == REFINED else f"wall y+ {FAMILIES[name]:g}, "
    for q, r in analyse(data["levels"], name).items():
        out.append(stored.row(f"{q} ({tag}k = 1, 2, 3)", rich=r,
                              note=f"GCI {r['gci_fine']:.2%}" if r["status"] == "converging"
                              else r["note"]))
    rows = family(data["levels"], name)
    if not rows:
        return out
    for r in rows:
        p = r["precursor"]
        out.append(stored.row(f"precursor f against McKeon ({tag}k = {r['k']})",
                              gate=f"|e| <= {F_GATE:g} (task 0049)",
                              ok=abs(p["f_err_mckeon"]) <= F_GATE,
                              value=f"{p['f_err_mckeon']:+.4f}",
                              note=f"first-cell y+ {p['yplus_first_mean']:.1f} mean"))
    lv = rows[-1]
    for z in PLANES:
        pl = lv["planes"][f"{z:g}"]
        theirs = ref["sst_ekat"]["planes"][f"{z:g}"]["rms_vs_lda"]
        out.append(stored.row(f"{z:g} D: RMS of w/w_vol along y = 0 ({tag}k = {lv['k']})",
                              gate=f"<= {RMS_GATE:g}", ok=pl["rms"] <= RMS_GATE,
                              value=f"{pl['rms']:.4f}",
                              note=f"Ekat et al.'s SST: {theirs:.4f}"))
        out.append(stored.row(f"{z:g} D: the peak's side ({tag}k = {lv['k']})",
                              gate="outer wall, as measured",
                              ok=(pl["peak_x_over_r"] < 0) == (pl["lda_peak_x_over_r"] < 0),
                              value=f"x/R {pl['peak_x_over_r']:+.3f}",
                              note=f"LDA x/R {pl['lda_peak_x_over_r']:+.3f}"))
    out.append(stored.row(f"K of the bend ({tag}k = {lv['k']})", value=f"{lv['k_bend']:.3f}",
                          note=f"Ito (1960): {ito_k():.3f}; reported, no gate (Q1, Q2)"))
    return out


def table(levels: list[dict]) -> str:
    lines = ["| family | k | cells | steps | K | "
             + " | ".join(f"RMS {z:g} D" for z in PLANES) + " |",
             "|---|---|---|---|---|" + "---|" * len(PLANES)]
    for r in [r for f in STUDIES for r in family(levels, f)]:
        lines.append(f"| {r.get('family', REFINED)} | {r['k']} | {r['cells']} | {r['steps']} | "
                     f"{r['k_bend']:.3f} | "
                     + " | ".join(f"{r['planes'][f'{z:g}']['rms']:.4f}" for z in PLANES) + " |")
    return "\n".join(lines)


# --- volunteer runs (validation/volunteer.py; decision 0044, task 0169) -------------
# A level is "k<k>"; the tool calls these with a run directory *d*.
END_TIME = 20000


def _parse(level: str) -> tuple[int, str]:
    """(k, family) of a level name."""
    m = re.fullmatch(r"(fixed25_|fixed_)?k([1-9])", level)
    if not m:
        raise ValueError(f"turbulent_bend has no level {level!r}: fixed25_k1 … (the wall cell "
                         "at 25), fixed_k1 … (at 50) or k1 … k9 (refined(k))")
    return int(m[2]), {v: f for f, v in PREFIX.items()}[m[1] or ""]


def check_level(level: str) -> None:
    """Raise ``ValueError`` unless this driver can build *level*."""
    _parse(level)


def prepare(level: str, d: Path, mesh_only: bool = False) -> dict:
    """Mesh *level*, and unless *mesh_only* set up its precursor and
    bend.  Returns ``{"msh": path, "check": …}``."""
    k, fam = _parse(level)
    d.mkdir(parents=True, exist_ok=True)
    if mesh_only:
        msh = d / f"{level}.msh"
        with Session(f"bend-{k}"):
            assembly(k, fam).write_openfoam(str(msh))
        return {"msh": msh, "check": None}
    meta = setup(d, k, END_TIME, fam)
    return {"msh": d / "bend" / "mesh.msh", "check": meta["check"]}


def run(level: str, d: Path, n_proc: int) -> None:
    """Solve *level* in *d*; the values go to d/level.json for collect."""
    k, _ = _parse(level)
    (d / "level.json").write_text(json.dumps(solve(d, k, END_TIME, n_proc)), encoding="utf-8")


def collect(level: str, d: Path) -> dict:
    path = d / "level.json"
    if not path.exists():
        raise ValueError(f"{level} isn't finished: run the job again")
    return {"values": json.loads(path.read_text(encoding="utf-8")), "extra": {}}


def recompute(values: dict) -> dict:
    """What a level's stored numbers must equal, from its own values."""
    ref = json.loads(REFERENCE.read_text(encoding="utf-8"))
    out = {"cells": assembly(values["k"], values.get("family", REFINED)).cell_count()}
    for z, pl in values["planes"].items():
        err = np.array(pl["w_over_ub"], float) - np.array(ref["planes"][z]["w_over_wvol"])
        out[f"rms_{z}"] = float(np.sqrt(np.nanmean(err ** 2)))
    return out


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--levels", nargs="+", type=int, default=list(LEVELS),
                    help="refinement levels k (refined(k): every count ×k, so 8× the cells "
                         "per doubling); default %(default)s; k = 4 is 3.8 M cells")
    ap.add_argument("--family", choices=STUDIES, default=FIXED25,
                    help="fixed_wall_25 / fixed_wall: the wall cell 25 / 50 viscous units high "
                         "at every level, the rest × k (design answers Q2, Q3); refined: "
                         "refined(k), the first study; default %(default)s")
    ap.add_argument("--work", type=Path, default=HERE / "work",
                    help="folder for each level's OpenFOAM cases (default: "
                         "validation/turbulent_bend/work/, not committed); a level's cases "
                         "are deleted once its results are stored, unless --keep-work")
    ap.add_argument("--end-time", type=int, default=END_TIME,
                    help="each solve's last iteration (default %(default)s); it stops "
                         "earlier once its residuals converge")
    ap.add_argument("--np", type=int, default=1, dest="n_proc",
                    help="MPI processes per solve (check other runs first, CLAUDE.md)")
    stored.add_arguments(ap, HERE)
    stored.add_openfoam_argument(ap, of.V2406)
    args = ap.parse_args(argv)
    of.set_runner(args.openfoam)
    store = stored.Store(args.json, "turbulent_bend")
    store.put_extra("reference", {"lda": str(REFERENCE.relative_to(ROOT).as_posix()),
                                  "planes_D": list(PLANES), "rms_gate": RMS_GATE})
    for k in args.levels:
        name = level_name(k, args.family)
        r = stored.run_level(store, name,
                             lambda k=k: run_level(k, args.work, args.end_time, args.n_proc,
                                                   args.family),
                             args.work / name, args.keep_work, cores=args.n_proc)
        print(f"[{name}] f {r['precursor']['f_err_mckeon']:+.4f} (y+ "
              f"{r['precursor']['yplus_first_mean']:.1f}), K {r['k_bend']:.3f}, RMS "
              + ", ".join(f"{z:g} D {r['planes'][f'{z:g}']['rms']:.4f}" for z in PLANES)
              + f", steps {r['steps']}", flush=True)
    for name in STUDIES:
        rich = analyse(store.levels(), name)
        if rich:
            store.put_extra("richardson" if name == REFINED else f"richardson_{name}", rich)
    print(table(store.levels()))
    return analyse(store.levels(), args.family)


if __name__ == "__main__":
    main()
