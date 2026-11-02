#!/usr/bin/env python3
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
Fully developed laminar flow in rectangular ducts (decision 0012, V1;
docs/tasks/0071): aspect ratios 1, 2 and 4, Re 100 on the hydraulic
diameter, against the exact series solution.

    hexmesh Assembly (RectShape core) → write_openfoam → gmshToFoam
    → apply_boundary_roles → checkMesh → topoSet (planes) → exact inlet
    → simpleFoam → Python post-processing

The inlet carries the exact developed profile (a nonuniform fixedValue,
written once at the face centres and scaled to the discrete flow rate),
and the initial field is the same profile, so the duct is developed from
end to end and can be short.  Three levels by ``Assembly.refined(k)``,
k = 1, 2, 4 (constant ratio 2).  Usage::

    python3 validation/rect_duct/run.py [--ratios 1 2 4] [--levels 1 2 4]
        [--work DIR] [--json FILE] [--keep-work] [--openfoam native|docker:IMAGE]
    python3 validation/rect_duct/run.py --check-series

Results go to ``results.json`` here (task 0093): levels already in it are
reused, and each level's case directory is deleted once its results are
stored.

OpenFOAM v2406 in Docker by default (decision 0012's toolchain).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from hexmesh import Assembly, PipeSpec, Session, Straight      # noqa: E402
from hexmesh.core.shape import RectShape                       # noqa: E402
from hexmesh.study import openfoam as of                       # noqa: E402

_spec = importlib.util.spec_from_file_location("poiseuille_run",
                                               ROOT / "validation/poiseuille/run.py")
pois = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pois)       # dictionaries, versions()
_spec = importlib.util.spec_from_file_location("convergence",
                                               ROOT / "validation/tools/convergence.py")
conv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conv)       # richardson() (task 0089)
_spec = importlib.util.spec_from_file_location("stored", ROOT / "validation/tools/results.py")
stored = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stored)                # results.json (task 0093)

# --- physics -----------------------------------------------------------------
DH = 0.02                 # hydraulic diameter, every aspect ratio [m]
NU = 1e-6                 # kinematic viscosity [m²/s]
RE = 100
U_MEAN = RE * NU / DH     # 5e-3 m/s
RATIOS = (1, 2, 4)        # aspect ratio a/b (width / height)
LENGTH = 10 * DH
X_A, X_M, X_B = 3 * DH, 5 * DH, 7 * DH        # Δp planes, profile plane
PLANES = {"planeA": X_A, "planeM": X_M, "planeB": X_B}
# Shah & London (1978), Table 46 (RESEARCH §7.8): f·Re on D_h, Darcy f
FRE_TABLE = {1: 56.91, 2: 62.19, 4: 72.93}
SERIES_TERMS = 4001       # odd n up to this; checked against twice as many

# --- mesh: every density parameter × k (k³ cells) ----------------------------
BASE = dict(nang_h=6, nrad=3, n_layers=(6, 4, 4, 6))    # 3, 2, 2, 3 D_h: D_h/2 each
LEVELS = (1, 2, 4)


def half_sides(ratio: float) -> tuple[float, float]:
    """(a, b): half width and half height for D_h = 4ab/(a + b) = DH."""
    b = DH * (ratio + 1) / (4 * ratio)
    return ratio * b, b


# --- exact solution ----------------------------------------------------------
#
# μ∇²u = dp/dx on |y| ≤ a, |z| ≤ b, u = 0 on the walls.  With s = b the
# half-side along the cosine (the shorter, for fast convergence) and
# G = −(dp/dx)/ρ (kinematic):
#
#   u = (G/2ν)(s² − z²)
#       − (16 s² G/(ν π³)) Σ_{n odd} (−1)^((n−1)/2) / n³
#             · cosh(nπy/2s) / cosh(nπa/2s) · cos(nπz/2s)
#
# (the parallel-plate parabola, whose own cosine series is the "1" of the
# usual form, minus the end-wall correction, which decays like
# exp(−nπ(a − |y|)/2s)), and
#
#   Q = (4 a s³ G / 3ν) [1 − (192 s/(π⁵ a)) Σ_{n odd} tanh(nπa/2s) / n⁵]
#
# [shah_and_london_1978], [white_2006] §3-3.

def _odd(terms: int) -> np.ndarray:
    return np.arange(1, terms + 1, 2, dtype=float)


def flow_per_gradient(a: float, b: float, terms: int = SERIES_TERMS) -> float:
    """Q / G for G = −(dp/dx)/ρ = 1 (ν = NU)."""
    n = _odd(terms)
    s = b
    return 4 * a * s**3 / (3 * NU) * (1 - 192 * s / (math.pi**5 * a)
                                      * float(np.sum(np.tanh(n * math.pi * a / (2 * s)) / n**5)))


def velocity_per_gradient(y, z, a: float, b: float, terms: int = SERIES_TERMS) -> np.ndarray:
    """u / G at (y, z) (arrays), G = 1."""
    y, z = np.abs(np.asarray(y, float)), np.asarray(z, float)
    s = b
    n = _odd(terms)[:, None]
    k = n * math.pi / (2 * s)
    # cosh(k y)/cosh(k a) without overflow
    ratio = np.exp(k * (y - a)) * (1 + np.exp(-2 * k * y)) / (1 + np.exp(-2 * k * a))
    sign = np.where(((n - 1) / 2) % 2 == 0, 1.0, -1.0)
    corr = np.sum(sign / n**3 * ratio * np.cos(k * z), axis=0)
    return (s**2 - z**2) / (2 * NU) - 16 * s**2 / (NU * math.pi**3) * corr


def exact(ratio: float) -> dict:
    """The developed solution at U_MEAN: pressure gradient, f·Re, centre
    velocity."""
    a, b = half_sides(ratio)
    area = 4 * a * b
    g = U_MEAN * area / flow_per_gradient(a, b)
    return {"a": a, "b": b, "area": area, "G": g,
            "fRe": 2 * DH**2 * g / (NU * U_MEAN),
            "u_c": g * float(velocity_per_gradient([0.0], [0.0], a, b)[0])}


def check_series() -> dict:
    """The series against Shah & London's f·Re, the parallel-plate limit
    (96, u_c/Ū = 3/2) and itself at twice the terms."""
    out = {}
    for ratio in list(RATIOS) + [1000]:
        e = exact(ratio)
        a, b = half_sides(ratio)
        y, z = np.meshgrid(np.linspace(-a, a, 41)[1:-1], np.linspace(-b, b, 21)[1:-1])
        u1 = velocity_per_gradient(y.ravel(), z.ravel(), a, b)
        u2 = velocity_per_gradient(y.ravel(), z.ravel(), a, b, 2 * SERIES_TERMS)
        out[ratio] = {"fRe": e["fRe"], "fRe_table": FRE_TABLE.get(ratio, 96.0),
                      "u_c/U": e["u_c"] / U_MEAN,
                      "terms_change": float(np.max(np.abs(u1 - u2)) / np.max(np.abs(u2)))}
    return out


# --- mesh ----------------------------------------------------------------------

def assembly(ratio: float, k: int = 1) -> Assembly:
    a, b = half_sides(ratio)
    nh = BASE["nang_h"]
    nw = int(round(nh * ratio))           # cells roughly square in the core
    spec = PipeSpec(nang=nh).core("fluid", RectShape(a, b, nw, nh), nrad=BASE["nrad"])
    asm = Assembly(spec, position=[0, 0, 0], direction=[1, 0, 0], up=[0, 0, 1])
    lengths = (X_A, X_M - X_A, X_B - X_M, LENGTH - X_B)
    for i, (L, n) in enumerate(zip(lengths, BASE["n_layers"])):
        asm.add(Straight(L, n_layers=n), **({"names": ["outlet"]} if i == 3 else {}))
    return asm if k == 1 else asm.refined(k)


def meshes():
    """(label, caption, build) per mesh shown in README.md
    (``docs/gallery/build.py --validation``): the coarse level of each
    aspect ratio, and the square at every level."""
    nh, nr = BASE["nang_h"], BASE["nrad"]
    out = [(f"ar{r}_k1", f"a/b = {r}, k = 1: nang_w {nh * r}, nang_h {nh}, nrad {nr}",
            lambda r=r: assembly(r, 1)) for r in RATIOS]
    out += [(f"ar1_k{k}", f"a/b = 1, k = {k}: nang {nh * k}, nrad {nr * k}",
             lambda k=k: assembly(1, k)) for k in LEVELS[1:]]
    return out


# --- case ----------------------------------------------------------------------
H = of.header


def write_case(case: Path, end_time: int, ratio: float) -> None:
    a, b = half_sides(ratio)
    for d in ("0", "constant", "system"):
        (case / d).mkdir(parents=True, exist_ok=True)
    files = {
        "system/controlDict": H("dictionary", "controlDict", "system")
        + pois.CONTROL.format(end_time=end_time),
        "system/fvSchemes": H("dictionary", "fvSchemes", "system") + pois.SCHEMES,
        "system/fvSolution": H("dictionary", "fvSolution", "system") + pois.SOLUTION,
        "system/topoSetDict": H("dictionary", "topoSetDict", "system")
        + pois.TOPOSET.format(actions="\n".join(
            pois.ZONE.format(n=n, x0=x - 1e-3 * DH, x1=x + 1e-3 * DH)
            for n, x in PLANES.items())),
        "constant/transportProperties": H("dictionary", "transportProperties", "constant")
        + f"transportModel  Newtonian;\nnu              {NU};\n",
        "constant/turbulenceProperties": H("dictionary", "turbulenceProperties", "constant")
        + "simulationType  laminar;\n",
        "0/U": H("volVectorField", "U", "0") + pois.U0.format(u=U_MEAN),
        "0/p": H("volScalarField", "p", "0") + pois.P0,
    }
    for name, text in files.items():
        (case / name).write_text(text, encoding="utf-8")


def exact_inlet(case: Path, ratio: float) -> float:
    """The exact profile at the inlet face centres, scaled so the discrete
    flow rate is Ū · A_mesh, and with the same scale in every cell as the
    initial field.  Returns the scale."""
    e = exact(ratio)
    mesh = case / "constant/polyMesh"
    pts, faces = of.read_points(mesh / "points"), of.read_faces(mesh / "faces")
    owner, neigh = of.read_labels(mesh / "owner"), of.read_labels(mesh / "neighbour")
    ids = of.read_patch_faces(mesh / "boundary", "fluid_inlet")
    c, sf = of.face_geometry(pts, [faces[i] for i in ids])
    area = np.linalg.norm(sf, axis=1)

    def profile(x):
        return e["G"] * velocity_per_gradient(x[:, 1], x[:, 2], e["a"], e["b"])
    u = profile(c)
    scale = U_MEAN * area.sum() / float((u * area).sum())
    u *= scale
    fc, fsf = of.face_geometry(pts, faces)
    cc, _ = of.cell_geometry(fc, fsf, owner, neigh, int(owner.max()) + 1)
    uc = scale * profile(cc)

    def vectors(v):
        return f"nonuniform List<vector>\n{len(v)}\n(\n" + "\n".join(
            f"({x:.15g} 0 0)" for x in v) + "\n)"
    path = case / "0/U"
    text = re.sub(r"fluid_inlet\s*\{[^}]*\}",
                  f"fluid_inlet {{ type fixedValue; value {vectors(u)}; }}", path.read_text(encoding="utf-8"))
    text = text.replace("internalField   uniform (0 0 0);", f"internalField   {vectors(uc)};")
    assert "nonuniform" in text.split("boundaryField")[0], "initial field not written"
    path.write_text(text, encoding="utf-8")
    return scale


# --- post-processing -----------------------------------------------------------

#: the centre velocity: a fit u = c0 + c1 y² + c2 z² + c3 y²z² to the faces
#: of the profile plane within this fraction of each half-side; c0
CENTRE_WINDOW = 0.4


def centre_fit(y, z, u, a, b) -> tuple[float, int]:
    near = (np.abs(y) < CENTRE_WINDOW * a) & (np.abs(z) < CENTRE_WINDOW * b)
    Y, Z = (y[near] / a) ** 2, (z[near] / b) ** 2
    A = np.column_stack([np.ones(near.sum()), Y, Z, Y * Z])
    return float(np.linalg.lstsq(A, u[near], rcond=None)[0][0]), int(near.sum())


def results(case: Path, ratio: float) -> dict:
    e = exact(ratio)
    a, b = e["a"], e["b"]
    mesh = case / "constant/polyMesh"
    pts, faces = of.read_points(mesh / "points"), of.read_faces(mesh / "faces")
    owner, neigh = of.read_labels(mesh / "owner"), of.read_labels(mesh / "neighbour")
    t = of.latest_time(case)
    p, U = of.read_internal(t / "p", 1), of.read_internal(t / "U", 3)

    def plane(name):
        ids = of.read_zone(mesh / "faceZones", name)
        c, sf = of.face_geometry(pts, [faces[i] for i in ids])
        # the axial spacing is uniform (D_h/2 per cell at every level), so
        # the face value is the mean of its two cells
        return ids, c, np.linalg.norm(sf, axis=1)

    p_avg = {}
    for name in ("planeA", "planeB"):
        ids, _, ar = plane(name)
        p_avg[name] = float(np.sum(ar * 0.5 * (p[owner[ids]] + p[neigh[ids]])) / ar.sum())
    dp = p_avg["planeA"] - p_avg["planeB"]
    q_in = -float(of.read_patch_values(t / "phi", "fluid_inlet").sum())
    q_out = float(of.read_patch_values(t / "phi", "fluid_outlet").sum())
    _, sf_in = of.face_geometry(pts, [faces[i] for i in
                                      of.read_patch_faces(mesh / "boundary", "fluid_inlet")])
    area = float(np.linalg.norm(sf_in, axis=1).sum())
    u_bulk = q_out / area
    fre = 2 * DH**2 * (dp / (X_B - X_A)) / (NU * u_bulk)

    ids, c, ar = plane("planeM")
    u = 0.5 * (U[owner[ids], 0] + U[neigh[ids], 0])
    ue = e["G"] * velocity_per_gradient(c[:, 1], c[:, 2], a, b)
    u_c, n_fit = centre_fit(c[:, 1], c[:, 2], u, a, b)
    u_c_sampled, _ = centre_fit(c[:, 1], c[:, 2], ue, a, b)
    fre_e, uc_e = e["fRe"], e["u_c"]
    return {
        "dp": dp, "u_bulk": u_bulk, "fRe": fre, "fRe_err_signed": (fre - fre_e) / fre_e,
        "u_c": u_c, "u_c_err_signed": (u_c - uc_e) / uc_e, "u_c_fit_faces": n_fit,
        "u_c_sampling_err": (u_c_sampled - uc_e) / uc_e,
        "profile_max_err": float(np.max(np.abs(u - ue)) / uc_e),
        "profile_rms_err": float(np.sqrt(np.sum(ar * (u - ue) ** 2) / ar.sum()) / uc_e),
        "area": area, "area_err_signed": (area - e["area"]) / e["area"],
        "q_in": q_in, "q_out": q_out, "mass_err": abs(q_out - q_in) / q_in,
        "q_err": abs(q_in - U_MEAN * e["area"]) / (U_MEAN * e["area"]),
    }


# --- Cartesian control (decision 0015 amendment 2; task 0071 step 5) -----------
#
# The same duct, inlet, planes and post-processing on a uniform blockMesh
# grid: no O-H corners, so a second-order reference for the setup.

MESHES = ("oh", "cartesian")


def control_cells(ratio: int) -> tuple[int, int]:
    """(ny, nz) across and up at k = 1: square cells, about as many per
    section as the O-H level."""
    per_section = assembly(ratio, 1).cell_count() // sum(BASE["n_layers"])
    nz = max(1, round(math.sqrt(per_section / ratio)))
    return nz * ratio, nz


def block_mesh_dict(ratio: int, k: int) -> str:
    """Four blocks along x, split at the Δp and profile planes."""
    a, b = half_sides(ratio)
    ny, nz = (n * k for n in control_cells(ratio))
    xs = (0.0, X_A, X_M, X_B, LENGTH)
    verts = "\n".join(f"    ({x:.15g} {y:.15g} {z:.15g})" for x in xs
                      for y, z in ((-a, -b), (a, -b), (a, b), (-a, b)))
    blocks, walls = [], []
    for i, n in enumerate(BASE["n_layers"]):
        o, p = 4 * i, 4 * i + 4
        blocks.append(f"    hex ({' '.join(str(o + j) for j in range(4))} "
                      f"{' '.join(str(p + j) for j in range(4))}) ({ny} {nz} {n * k}) "
                      "simpleGrading (1 1 1)")
        walls += [f"            ({o} {o + 1} {p + 1} {p})", f"            ({o + 1} {o + 2} {p + 2} {p + 1})",
                  f"            ({o + 2} {o + 3} {p + 3} {p + 2})", f"            ({o + 3} {o} {p} {p + 3})"]
    nl = "\n"
    return (f"convertToMeters 1;\n\nvertices\n(\n{verts}\n);\n\n"
            f"blocks\n(\n{nl.join(blocks)}\n);\n\nedges ();\n\nboundary\n(\n"
            "    fluid_inlet  { type patch; faces ((0 3 2 1)); }\n"
            "    fluid_outlet { type patch; faces ((16 17 18 19)); }\n"
            f"    fluid_wall\n    {{\n        type wall;\n        faces\n        (\n{nl.join(walls)}\n        );\n    }}\n"
            ");\n")


def _new_case(work: Path, name: str) -> Path:
    case = work / name
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    return case


def _solve(case: Path, ratio: float, out: dict) -> dict:
    """checkMesh, planes, exact inlet, simpleFoam and the results."""
    check = of.check_mesh(case)
    of.foam("topoSet", case, "log.topoSet")
    scale = exact_inlet(case, ratio)
    solve = of.foam("simpleFoam", case, "log.simpleFoam")
    m = re.search(r"SIMPLE solution converged in (\d+) iterations", solve)
    times = re.findall(r"^Time = (\d+)$", solve, re.M)
    out.update({"inlet_scale": scale, "converged": m is not None,
                "iterations": int(m.group(1)) if m else int(times[-1]),
                "exec_time": float(re.findall(r"ExecutionTime = ([\d.e+-]+) s", solve)[-1]),
                **{f"check_{key}": v for key, v in check.items()}})
    out.update(results(case, ratio))
    return out


def run_level(ratio: float, k: int, work: Path, end_time: int) -> dict:
    name = f"ar{ratio}_k{k}"
    case = _new_case(work, name)
    with Session(f"rect-duct-{name}"):
        asm = assembly(ratio, k)
        cells = asm.cell_count()
        print(f"[{name}] predicted cells: {cells}", flush=True)
        msh = case / "duct.msh"
        asm.write_openfoam(str(msh))
        sj = asm.check_quality("scaled_jacobian").worst
    write_case(case, end_time, ratio)
    retyped = of.convert(case, msh)
    return _solve(case, ratio, {"mesh": "oh", "ratio": ratio, "k": k, "cells": cells,
                                "min_scaled_jacobian": sj, "retyped": retyped})


def run_control(ratio: int, k: int, work: Path, end_time: int) -> dict:
    name = f"cart_ar{ratio}_k{k}"
    case = _new_case(work, name)
    ny, nz = (n * k for n in control_cells(ratio))
    cells = ny * nz * sum(BASE["n_layers"]) * k
    print(f"[{name}] {ny} × {nz} per section, predicted cells: {cells}", flush=True)
    write_case(case, end_time, ratio)
    (case / "system/blockMeshDict").write_text(
        H("dictionary", "blockMeshDict", "system") + block_mesh_dict(ratio, k), encoding="utf-8")
    of.foam("blockMesh", case, "log.blockMesh")
    return _solve(case, ratio, {"mesh": "cartesian", "ratio": ratio, "k": k, "cells": cells,
                                "section": [ny, nz]})


def extrapolate(rows: list[dict]) -> dict:
    """Richardson per mesh and aspect ratio over k = 1, 2, 4 (ratio 2)
    [celik_and_ghia_etal_2008], on f·Re, u_c, and u_c net of the centre
    fit's own bias (decision 0015 amendment 3): the fit applied to the
    solution minus the fit applied to the exact field at the same faces,
    over u_c, whose exact limit is 0."""
    out = {}
    for mesh in MESHES:
        for ratio in sorted({r["ratio"] for r in rows if r.get("mesh", "oh") == mesh}):
            lv = sorted((r for r in rows if r.get("mesh", "oh") == mesh and r["ratio"] == ratio),
                        key=lambda r: r["k"])
            if [r["k"] for r in lv] != list(LEVELS):
                continue
            e = exact(ratio)
            out.setdefault(mesh, {})[ratio] = {}
            for key, ref in (("fRe", e["fRe"]), ("u_c", e["u_c"])):
                rich = conv.richardson(*(r[key] for r in lv))
                rich["ext_err_signed"] = (None if rich["extrapolated"] is None
                                          else (rich["extrapolated"] - ref) / ref)
                out[mesh][ratio][key] = rich
            net = conv.richardson(*(r["u_c_err_signed"] - r["u_c_sampling_err"] for r in lv),
                                  scale=1.0)
            net["ext_err_signed"] = net["extrapolated"]
            net["fit_bias_fine"] = lv[-1]["u_c_sampling_err"]
            out[mesh][ratio]["u_c_net"] = net
    return out


def versus_control(rows: list[dict]) -> list[dict]:
    """The O-H error over the control's, per ratio and level (about the
    same cells per section, the same axial cells)."""
    by = {(r.get("mesh", "oh"), r["ratio"], r["k"]): r for r in rows}
    out = []
    for (mesh, ratio, k), oh in sorted(by.items()):
        cart = by.get(("cartesian", ratio, k))
        if mesh != "oh" or cart is None:
            continue
        out.append({"ratio": ratio, "k": k, "cells_oh": oh["cells"], "cells_cartesian": cart["cells"],
                    **{f"{q}_ratio": abs(oh[f"{q}_err_signed"]) / abs(cart[f"{q}_err_signed"])
                       for q in ("fRe", "u_c")}})
    return out


def level_name(mesh: str, ratio: int, k: int) -> str:
    """The level's name in results.json: its case directory's."""
    return f"{'cart_' if mesh == 'cartesian' else ''}ar{ratio}_k{k}"


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ratios", nargs="+", type=int, default=list(RATIOS))
    ap.add_argument("--levels", nargs="+", type=int, default=list(LEVELS))
    ap.add_argument("--meshes", nargs="+", choices=MESHES, default=list(MESHES),
                    help="hexmesh's O-H section, the Cartesian control, or both")
    ap.add_argument("--work", type=Path, default=HERE / "work")
    ap.add_argument("--end-time", type=int, default=20000)
    stored.add_arguments(ap, HERE)
    ap.add_argument("--openfoam", default=of.V2406,
                    help="runner: native, or docker:IMAGE (default: v2406 in Docker)")
    ap.add_argument("--check-series", action="store_true",
                    help="print the exact solution's checks and stop")
    args = ap.parse_args(argv)
    if args.check_series:
        data = check_series()
        print(json.dumps(data, indent=1))
        return data
    of.set_runner(args.openfoam)
    # levels already in results.json are reused, so they can run separately
    store = stored.Store(args.json, "rect_duct")
    store.put_extra("exact", {r: exact(r) for r in RATIOS})
    store.put_extra("series", check_series())
    rows = []
    for mesh in args.meshes:
        for ratio in args.ratios:
            for k in args.levels:
                name = level_name(mesh, ratio, k)
                run = run_level if mesh == "oh" else run_control
                r = stored.run_level(
                    store, name, lambda run=run, ratio=ratio, k=k: run(ratio, k, args.work,
                                                                       args.end_time),
                    args.work / name, args.keep_work)
                print(json.dumps(r, default=float), flush=True)
                rows.append(r)
    data = {"levels": rows, "richardson": extrapolate(rows),
            "versus_control": versus_control(rows)}
    print(json.dumps(data["richardson"], indent=1, default=float))
    return data


#: "observed order near 2 (else the setup is suspect)": within 0.2
#: (task 0093's reading)
ORDER_TOL = 0.2


def recheck(data: dict) -> list[dict]:
    """Every Richardson row and gate from ``results.json`` (task 0093;
    decision 0015 amendments 2 and 3), per aspect ratio: the Cartesian
    control's extrapolated f·Re and u_c (net of the centre fit's bias)
    within 0.1 % of exact, its finest |error| < 1 % and its observed order
    near 2; the O-H rows reported."""
    rich = extrapolate(data["levels"])
    out = []
    for ratio in RATIOS:
        c = rich["cartesian"][ratio]
        fine = stored.series(data, name=level_name("cartesian", ratio, LEVELS[-1]))[0]
        for key, what in (("fRe", "f·Re"), ("u_c_net", "u_c, net of the fit's bias")):
            r = c[key]
            ok, why = (conv.gate_extrapolated(r, 0.0, 1e-3, relative=False) if key == "u_c_net"
                       else conv.gate_extrapolated(r, exact(ratio)["fRe"], 1e-3))
            out.append(stored.row(f"{what}, extrapolated (control, a/b {ratio})", rich=r,
                                  gate="within 0.1 % of exact", ok=ok,
                                  value="" if r["ext_err_signed"] is None
                                  else f"{r['ext_err_signed']:+.3%}", note=why))
        for key in ("fRe", "u_c"):
            err = fine[f"{key}_err_signed"]
            out.append(stored.row(f"{key}, finest |error| (control, a/b {ratio})", gate="< 1 %",
                                  ok=abs(err) < 0.01, value=f"{err:+.3%}"))
            r = c[key]
            ok = r["status"] == "converging" and abs(r["order"] - 2) <= ORDER_TOL
            out.append(stored.row(f"{key}, observed order (control, a/b {ratio})", rich=r,
                                  gate=f"near 2 (± {ORDER_TOL})", ok=ok, value=conv.describe(r)))
        for key in ("fRe", "u_c", "u_c_net"):
            out.append(stored.row(f"{key} (O-H, a/b {ratio})", rich=rich["oh"][ratio][key],
                                  note="reported against the control (amendment 2)"))
    return out

if __name__ == "__main__":
    main()
