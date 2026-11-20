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
code_saturne: the .unv export checked end to end (decision 0057, task 0181).

    python3 validation/exports/code_saturne/run.py              # import, k = 1, 2, 3

**The import:** code_saturne's preprocessor on the equal tee's ``.unv``
(``hexmesh.examples.fittings.equal_tee``) and on each Poiseuille level:
its cell count must be ``cell_count()``, its hexahedra all the cells, and
every group of the mesh a group of the preprocessor's by name.

**The solve:** OpenFOAM Poiseuille's pipe (``validation/poiseuille/run.py``,
the same ``assembly(k)``), laminar at Re 100 in code_saturne's
finite-volume solver: a uniform inlet velocity, a free outlet, no-slip
walls (C++ user sources in ``src/``), time-marched to steady state (dt =
1/k s, 400 s: four diffusive times R²/ν).  The pressure gradient is the
slope of the cell-layer mean pressure between 15 D and 25 D; the exact
value is Poiseuille's at the bulk velocity U_b of the outlet's mass flow
over ρπR².  Gated at the finest level (2 %), its order over k = 1, 2, 3
reported (Richardson).

**MMS conduction:** the MMS case's fittings and manufactured field
(``validation/mms/run.py``, the same ``assembly(case, k)`` and wave
numbers), as a user scalar with diffusivity 1 and the flow frozen at rest:
the source at the cell centres, T = T_m at every boundary face's centre
(``src/cs_user_mms.cpp``).  The error T − T_m at code_saturne's cell
centres, volume-weighted L2 overall and in the fitting under test; its
order over k = 1, 2, 4 beside OpenFOAM's on the same meshes.

    python3 validation/exports/code_saturne/run.py --mms tee --mms-levels 1 2
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

import gmsh                                                    # noqa: E402

from hexmesh import Session                                    # noqa: E402


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


conv = _load("convergence", "validation/tools/convergence.py")     # richardson() (task 0089)
stored = _load("stored", "validation/tools/results.py")            # results.json (task 0093)
pois = _load("poiseuille_run", "validation/poiseuille/run.py")     # the mesh and the flow
mms = _load("mms_run", "validation/mms/run.py")                     # the MMS cases and field

IMAGE = ("simvia/code_saturne:9.2.0@sha256:"
         "7639bc95baf6e5c284f4e67ea418ae6d46809410b7e04ed477983a8e39513ed5")
VERSION = "9.2.0"
PREPROCESS = "/opt/code_saturne/libexec/code_saturne/cs_preprocess"
LEVELS = (1, 2, 3)               # 5 184, 41 472, 139 968 cells
ERROR_MAX = 0.02                 # Δp against Poiseuille at U_b, finest level
PHYSICAL_TIME = 400.0            # [s]: four diffusive times R²/ν
SOURCE = HERE / "src" / "cs_user_poiseuille.cpp"
GROUPS = ("fluid", "fluid_inlet", "fluid_outlet", "fluid_wall")
MMS_SOURCE = HERE / "src" / "cs_user_mms.cpp"
MMS_CASES = tuple(n for n in mms.CASES if n not in mms.DIAGNOSTIC)   # all 16: cheap
MMS_LEVELS = (1, 2, 4)                               # as the OpenFOAM MMS case
MMS_STEPS = 5          # steady scalar (istat 0): each step solves it whole; the rest check it

D, R, NU, U_IN = pois.D, pois.R, pois.NU, pois.U_MEAN
X_A, X_B = pois.X_A, pois.X_B

SETUP = """<?xml version="1.0" encoding="utf-8"?><Code_Saturne_GUI case="pipe" \
solver_version="" study="study" version="2.0">
  <solution_domain>
    <meshes_list>
      <mesh name="mesh.unv"/>
    </meshes_list>
  </solution_domain>
  <calculation_management/>
</Code_Saturne_GUI>
"""


def meshes():
    """(label, caption, build) per mesh shown in README.md."""
    return [("pipe", "OpenFOAM Poiseuille's pipe, k = 1, as code_saturne reads it",
             lambda: pois.assembly(1))]


def _docker(d: Path, workdir: str, *cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "run", "--rm", "--entrypoint", "",
                           "-u", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/work",
                           "-v", f"{d.resolve()}:/work", "-w", workdir, IMAGE, *cmd],
                          capture_output=True, text=True)


def preprocess(d: Path, unv: str) -> dict:
    """code_saturne's preprocessor on d/*unv*: what it read."""
    out = _docker(d, "/work", PREPROCESS, unv, "--no-write")
    log = out.stdout
    (d / f"log.preprocess.{Path(unv).stem}").write_text(log + out.stderr, encoding="utf-8")
    if out.returncode or "Preprocessor finish" not in log:
        raise RuntimeError(f"cs_preprocess failed on {unv} ({out.returncode})")
    groups = {m[1]: int(m[3]) for m in re.finditer(
        r'Group \d+ "([^"]+)"\n\s+Number of (faces|cells)\s+:\s+(\d+)', log)}
    cells = re.search(r"Main mesh properties.*?Number of cells:\s+(\d+)", log, re.S)
    hexa = re.search(r"Number of elements\s+hexa8 :\s+(\d+)", log)
    return {"cells": int(cells[1]), "hexa8": int(hexa[1]) if hexa else 0, "groups": groups,
            "warnings": len(re.findall(r"[Ww]arning", log))}


def write_case(d: Path, k: int) -> dict:
    """The study in *d*: MESH/mesh.unv, pipe/DATA/setup.xml and the user
    source with this level's values."""
    if d.exists():
        shutil.rmtree(d)
    for sub in ("MESH", "pipe/DATA", "pipe/SRC", "pipe/RESU"):
        (d / sub).mkdir(parents=True)
    asm = pois.assembly(k)
    with Session(f"cs-{k}"), asm.to_mesh() as m:
        m.write(str(d / "MESH" / "mesh.unv"))
    (d / "pipe/DATA/setup.xml").write_text(SETUP, encoding="utf-8")
    (d / "pipe/DATA/run.cfg").write_text("[job_defaults]\n\nn_procs: 1\nn_threads: \n",
                                         encoding="utf-8")
    dt = 1.0 / k
    src = SOURCE.read_text(encoding="utf-8")
    for name, value in (("HEXMESH_NU", NU), ("HEXMESH_DT", dt), ("HEXMESH_U", U_IN),
                        ("HEXMESH_NT_MAX", round(PHYSICAL_TIME / dt))):
        src = src.replace(name, repr(value))
    (d / "pipe/SRC" / SOURCE.name).write_text(src, encoding="utf-8")
    meta = {"cells": asm.cell_count(), **stored.counts(asm), "dt": dt,
            "steps": round(PHYSICAL_TIME / dt)}
    (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return meta


def solve(d: Path, k: int) -> dict:
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    imp = preprocess(d / "MESH", "mesh.unv")
    out = _docker(d, "/work/pipe/DATA", "code_saturne", "run", "--id", "run")
    res = d / "pipe/RESU/run"
    (d / "log.code_saturne").write_text(out.stdout + out.stderr, encoding="utf-8")
    if out.returncode or not (res / "cells.csv").exists():
        raise RuntimeError(f"code_saturne failed ({out.returncode}): see {res}")
    return {"k": k, **meta, "import": imp, **results(res, k)}


def results(res: Path, k: int) -> dict:
    """dp/dx from the cell-layer mean pressure; U_b from the outlet."""
    c = np.genfromtxt(res / "cells.csv", delimiter=",", names=True)
    x, p, vol = c["x"], c["p"], c["volume"]
    dx = (X_B - X_A) / (pois.BASE["n_layers"][1] * k)        # the axial cell there
    layer = np.floor(x / dx + 1e-6).astype(int)
    ids = np.unique(layer)
    xs = np.array([np.sum(x[layer == i] * vol[layer == i]) / vol[layer == i].sum() for i in ids])
    ps = np.array([np.sum(p[layer == i] * vol[layer == i]) / vol[layer == i].sum() for i in ids])
    sel = (xs > X_A) & (xs < X_B)
    grad = float(-np.polyfit(xs[sel], ps[sel], 1)[0])
    q = dict(np.genfromtxt(res / "massflow.csv", delimiter=",", names=True, dtype=None,
                           encoding="utf-8")[["zone", "massflow"]].tolist())
    u_b = q["outlet"] / (np.pi * R ** 2)                     # ρ = 1
    exact = 32 * NU * u_b / D ** 2
    return {"u_b": u_b, "massflow_in": q["inlet"], "massflow_out": q["outlet"],
            "dpdx": grad, "dpdx_exact_at_u_b": exact, "dp_err": grad / exact - 1,
            "dp_err_at_u_in": grad / (32 * NU * U_IN / D ** 2) - 1}


def tee_import(work: Path) -> dict:
    """The preprocessor on the equal tee's .unv (the format test's example)."""
    d = work / "tee"
    d.mkdir(parents=True, exist_ok=True)
    asm = importlib.import_module("hexmesh.examples.fittings.equal_tee").build()
    with Session("cs-tee"), asm.to_mesh() as m:
        want = {name: sum(len(a) for a in g.values()) for name, g in m.groups.items()}
        m.write(str(d / "tee.unv"))
    return {"cells_expected": asm.cell_count(), "groups_expected": want,
            **preprocess(d, "tee.unv")}


def _import_ok(imp: dict, cells: int, groups: dict | None = None) -> bool:
    return (imp["cells"] == imp["hexa8"] == cells
            and (groups is None and set(GROUPS) <= set(imp["groups"])
                 or groups is not None and imp["groups"] == groups))


# --- MMS conduction ---------------------------------------------------------------------

def write_mms(d: Path, case: str, k: int) -> dict:
    """The MMS study of *case* at level *k* in *d*, with the hexes'
    centroids and fittings (``mms._centroids``) for the error by fitting."""
    if d.exists():
        shutil.rmtree(d)
    for sub in ("MESH", "pipe/DATA", "pipe/SRC", "pipe/RESU"):
        (d / sub).mkdir(parents=True)
    asm, focus = mms.assembly(case, k)
    with Session(f"cs-mms-{case}-{k}"):
        asm.write(str(d / "MESH" / "mesh.unv"))
        cents, owners = mms._centroids(asm)[:2]
        groups = group_sizes()
    # the wave numbers from the k = 1 mesh, as the OpenFOAM case: every level
    # solves the same problem
    with Session(f"cs-mms-{case}-box"):
        a1 = mms.assembly(case, 1)[0]
        a1.mesh()
        c1 = mms._centroids(a1)[0]
    w = mms.wave_numbers(c1.min(axis=0), c1.max(axis=0), 2 * mms.R)
    np.savez(d / "fittings.npz", cents=cents, owners=owners)
    (d / "pipe/DATA/setup.xml").write_text(SETUP, encoding="utf-8")
    (d / "pipe/DATA/run.cfg").write_text("[job_defaults]\n\nn_procs: 1\nn_threads: \n",
                                         encoding="utf-8")
    src = MMS_SOURCE.read_text(encoding="utf-8").replace("HEXMESH_NT_MAX", str(MMS_STEPS))
    for i in range(3):
        src = src.replace(f"HEXMESH_W{i}", repr(float(w[i])))
        src = src.replace(f"HEXMESH_P{i}", repr(float(mms.PHASES[i])))
    (d / "pipe/SRC" / MMS_SOURCE.name).write_text(src, encoding="utf-8")
    names = {e.index: e.name for e in asm.edges}
    meta = {"case": case, "k": k, "cells": asm.cell_count(), **stored.counts(asm),
            "focus": [names[i] for i in focus], "wave_numbers": w.tolist(),
            "groups_expected": groups,
            "names": {str(i): n for i, n in names.items()}}
    (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return meta


def group_sizes() -> dict[str, int]:
    """Each physical group of the current gmsh model: its name and how many
    elements (cells or faces) it holds, as the preprocessor counts them."""
    out = {}
    for dim, tag in gmsh.model.getPhysicalGroups():
        n = 0
        for ent in gmsh.model.getEntitiesForPhysicalGroup(dim, tag):
            n += sum(len(t) for t in gmsh.model.mesh.getElements(dim, ent)[1])
        out[gmsh.model.getPhysicalName(dim, tag)] = n
    return out


def solve_mms(d: Path) -> dict:
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    imp = preprocess(d / "MESH", "mesh.unv")
    out = _docker(d, "/work/pipe/DATA", "code_saturne", "run", "--id", "run")
    res = d / "pipe/RESU/run"
    (d / "log.code_saturne").write_text(out.stdout + out.stderr, encoding="utf-8")
    if out.returncode or not (res / "cells.csv").exists():
        raise RuntimeError(f"code_saturne failed ({out.returncode}): see {res}")
    log = (res / "run_solver.log").read_text(encoding="utf-8")
    resid = [float(m) for m in re.findall(r"^c  tmms\s+\S+\s+\d+\s+(\S+)", log, re.M)]
    return {**meta, "import": imp, "last_residual": resid[-1] if resid else None,
            **mms_errors(res, d, meta)}


def mms_errors(res: Path, d: Path, meta: dict) -> dict:
    """T − T_m at the cell centres: volume-weighted L2 and max, overall,
    in the focus fittings and per fitting (cells matched to the nearest
    gmsh hex centroid, as the OpenFOAM case)."""
    from scipy.spatial import cKDTree
    c = np.genfromtxt(res / "cells.csv", delimiter=",", names=True)
    x = np.c_[c["x"], c["y"], c["z"]]
    err = c["T"] - mms.exact(x, np.asarray(meta["wave_numbers"]))
    vol = c["volume"]
    fit = np.load(d / "fittings.npz")
    dist, near = cKDTree(fit["cents"]).query(x)
    owner = fit["owners"][near]
    names = {int(i): n for i, n in meta["names"].items()}
    focus = [i for i, n in names.items() if n in meta["focus"]]
    every = np.ones(len(err), bool)
    return {"volume": float(vol.sum()), "all": mms._errors(err, vol, every),
            "focus_errors": mms._errors(err, vol, np.isin(owner, focus)),
            "per_fitting": {names[i]: mms._errors(err, vol, owner == i)
                            for i in sorted(set(owner.tolist()))},
            "match_distance_max": float(dist.max())}


def _pipe(levels: list[dict]) -> list[dict]:
    """The Poiseuille levels (the MMS levels carry their ``case``)."""
    return [lv for lv in levels if "k" in lv and "case" not in lv]


def analyse_mms(levels: list[dict]) -> dict:
    """Per MMS case: the L2 errors (overall, focus) by k and their orders
    between successive levels, beside OpenFOAM's on the same meshes where
    it converged at every one of those levels."""
    path = ROOT / "validation/mms/results.json"
    foam = json.loads(path.read_text(encoding="utf-8"))["levels"] if path.exists() else []
    out = {}
    for case in sorted({lv["case"] for lv in levels if "case" in lv}):
        rows = sorted((lv for lv in levels if lv.get("case") == case), key=lambda r: r["k"])
        ks = [r["k"] for r in rows]
        # OpenFOAM's converged levels only (its duct taps' k = 4 didn't converge)
        of = {r["k"]: r for r in foam
              if r.get("case") == case and r["k"] in ks and r.get("converged")}
        entry = {"k": ks}
        for q, key in (("l2", "all"), ("focus_l2", "focus_errors")):
            e = [r[key]["l2"] for r in rows]
            entry[q] = e
            entry[f"{q}_orders"] = mms.orders(e, ks)
        if len(of) == len(ks):
            for q, key in (("l2", "all"), ("focus_l2", "focus")):
                e = [of[k][key]["l2"] for k in ks]
                entry[f"openfoam_{q}"] = e
                entry[f"openfoam_{q}_orders"] = mms.orders(e, ks)
        out[case] = entry
    return out


# --- analysis -------------------------------------------------------------------------

def analyse(levels: list[dict]) -> dict:
    rows = sorted((r for r in _pipe(levels) if r["k"] in (1, 2, 3)), key=lambda r: r["k"])
    if len(rows) != 3:
        return {}
    return {"dp_err": conv.richardson(*(r["dp_err"] for r in rows), r21=1.5, r32=2.0,
                                      scale=1.0)}


def recheck(data: dict) -> list[dict]:
    """The import (tee and every level); Δp within 2 % of Poiseuille at
    U_b at the finest level; its order reported."""
    out = []
    tee = data["extra"].get("tee_import")
    if tee:
        out.append(stored.row("import: the equal tee", gate="cells = hexa8 = cell_count(), "
                              "every group by name and size",
                              ok=_import_ok(tee, tee["cells_expected"], tee["groups_expected"]),
                              value=f"{tee['cells']} / {tee['cells_expected']}",
                              note=", ".join(sorted(tee["groups"]))))
    levels = sorted(_pipe(data["levels"]), key=lambda r: r["k"])
    for lv in levels:
        out.append(stored.row(f"import (k = {lv['k']})", gate="cells = hexa8 = cell_count()",
                              ok=_import_ok(lv["import"], lv["cells"]),
                              value=f"{lv['import']['cells']} / {lv['cells']}"))
    for q, r in analyse(levels).items():
        out.append(stored.row(f"{q} (k = 1, 2, 3)", rich=r,
                              note=f"order {r['order']:.2f}" if r["status"] == "converging"
                              else r["note"]))
    if levels:
        lv = levels[-1]
        out.append(stored.row(f"dp_err (k = {lv['k']})", gate=f"|e| <= {ERROR_MAX:g}",
                              ok=abs(lv["dp_err"]) <= ERROR_MAX, value=f"{lv['dp_err']:+.4f}",
                              note="Poiseuille at U_b (outlet mass flow over ρπR²)"))
    out += recheck_mms(data["levels"])
    return out


def recheck_mms(levels: list[dict]) -> list[dict]:
    """Per MMS case: the import at every level (gated), and the focus L2
    order between the two finest levels beside OpenFOAM's (reported)."""
    out = []
    for case, a in analyse_mms(levels).items():
        rows = [lv for lv in levels if lv.get("case") == case]
        ok = all(_import_ok(lv["import"], lv["cells"], lv["groups_expected"]) for lv in rows)
        out.append(stored.row(f"MMS {case}: import (k = {', '.join(map(str, a['k']))})",
                              gate="cells = hexa8 = cell_count(), every group by name and size",
                              ok=ok,
                              value=", ".join(f"{lv['import']['cells']} / {lv['cells']}"
                                              for lv in sorted(rows, key=lambda r: r["k"]))))
        if a["focus_l2_orders"]:
            p = a["focus_l2_orders"][-1]
            foam = a.get("openfoam_focus_l2_orders")
            note = (f"OpenFOAM {foam[-1]:.2f} on the same meshes" if foam
                    else "OpenFOAM not converged at every level (validation/mms)")
            if foam and p < foam[-1] - mms.ORDER_FLAG:
                note += f"; more than {mms.ORDER_FLAG} below it"
            out.append(stored.row(f"MMS {case}: focus L2 order (k = {a['k'][-2]} → "
                                  f"{a['k'][-1]})", value=f"{p:.2f}", note=note))
    return out


def table(levels: list[dict]) -> str:
    lines = ["| k | cells | preprocessor cells | U_b/U_in | Δp error | Δp error at U_in |",
             "|---|---|---|---|---|---|"]
    for r in sorted(_pipe(levels), key=lambda r: r["k"]):
        lines.append(f"| {r['k']} | {r['cells']} | {r['import']['cells']} | "
                     f"{r['u_b'] / U_IN:.4f} | {r['dp_err']:+.4f} | {r['dp_err_at_u_in']:+.4f} |")
    return "\n".join(lines)


def _environment(store) -> dict:
    """The store's start (task 0184), with the code_saturne image."""
    return {**store.start, "code_saturne": IMAGE, "runner": "docker"}


# --- volunteer runs (validation/volunteer.py; decision 0044, task 0179) -------------

def _parse(level: str) -> int:
    m = re.fullmatch(r"k([1-9])", level)
    if not m:
        raise ValueError(f"code_saturne has no level {level!r}: k1 … k9 (refined(k))")
    return int(m[1])


def check_level(level: str) -> None:
    """Raise ``ValueError`` unless this driver can build *level*."""
    _parse(level)


def prepare(level: str, d: Path, mesh_only: bool = False) -> dict:
    """Write *level*'s study in *d*."""
    write_case(d, _parse(level))
    return {"msh": d / "MESH" / "mesh.unv", "check": None}


def run(level: str, d: Path, n_proc: int) -> None:
    """Solve *level* in *d* (one process: cells.csv is written by rank 0
    alone); the values go to d/level.json."""
    (d / "level.json").write_text(json.dumps(solve(d, _parse(level))), encoding="utf-8")


def collect(level: str, d: Path) -> dict:
    path = d / "level.json"
    if not path.exists():
        raise ValueError(f"{level} isn't finished: run the job again")
    return {"values": json.loads(path.read_text(encoding="utf-8")), "extra": {}}


def recompute(values: dict) -> dict:
    """What a level's stored numbers must equal, from its own values."""
    return {"cells": pois.assembly(values["k"]).cell_count(),
            "dp_err": values["dpdx"] / values["dpdx_exact_at_u_b"] - 1}


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--levels", nargs="*", type=int, default=list(LEVELS),
                    help="refinement levels k (every count ×k: k³× the cells); "
                         "default %(default)s")
    ap.add_argument("--mms", nargs="*", default=list(MMS_CASES), metavar="CASE",
                    help=f"MMS cases ({', '.join(mms.CASES)}); default %(default)s; "
                         "--mms alone runs none")
    ap.add_argument("--mms-levels", nargs="+", type=int, default=list(MMS_LEVELS),
                    help="MMS levels k; default %(default)s")
    ap.add_argument("--work", type=Path, default=HERE / "work",
                    help="folder for the studies (default: validation/exports/code_saturne/"
                         "work/, not committed); deleted once stored, unless --keep-work")
    stored.add_arguments(ap, HERE)
    args = ap.parse_args(argv)
    store = stored.Store(args.json, "code_saturne_poiseuille")
    store.put_extra("method", {"image": IMAGE, "code_saturne": VERSION, "re": pois.RE,
                               "exact": "Poiseuille at U_b (the outlet's mass flow over "
                                        "rho pi R^2); dp/dx the slope of the cell-layer "
                                        "mean p between 15 D and 25 D",
                               "physical_time_s": PHYSICAL_TIME, "error_max": ERROR_MAX,
                               "mms": "validation/mms's field and meshes; a user scalar, "
                                      "diffusivity 1, the flow frozen at rest; T = T_m at "
                                      "every boundary face centre; L2 of T - T_m at the cell "
                                      "centres; the import gated, the orders reported"})
    if "tee_import" not in store.data["extra"]:
        store.put_extra("tee_import", tee_import(args.work))
        if not args.keep_work:
            stored.remove_work(args.work / "tee")
    for k in args.levels:
        name = f"k{k}"
        if (lv := store.level(name)) and lv["precision"] == stored.FULL:
            print(f"[k={k}] reused from {store.path}", flush=True)
            continue
        d = args.work / name
        store.begin()
        write_case(d, k)
        r = solve(d, k)
        store.put(name, r, env=_environment(store), cores=1)
        print(f"[k={k}] {r['import']['cells']} cells of {r['cells']}, U_b/U_in "
              f"{r['u_b'] / U_IN:.4f}, Δp {r['dp_err']:+.4f}", flush=True)
        if not args.keep_work:
            stored.remove_work(d)
    for case in args.mms:
        for k in args.mms_levels:
            name = f"mms_{case}_k{k}"
            if (lv := store.level(name)) and lv["precision"] == stored.FULL:
                print(f"[{name}] reused from {store.path}", flush=True)
                continue
            d = args.work / name
            store.begin()
            write_mms(d, case, k)
            r = solve_mms(d)
            store.put(name, r, env=_environment(store), cores=1)
            print(f"[{name}] {r['import']['cells']} cells of {r['cells']}, L2 "
                  f"{r['all']['l2']:.3e}, focus {r['focus_errors']['l2']:.3e}", flush=True)
            if not args.keep_work:
                stored.remove_work(d)
    rich = analyse(store.levels())
    if rich:
        store.put_extra("richardson", rich)
    if args.mms:
        store.put_extra("mms", analyse_mms(store.levels()))
    print(table(store.levels()))
    for r in recheck(store.data):
        print(f"{r['quantity']}: {r['value']} ({r['verdict']}); {r['note']}")
    return rich


if __name__ == "__main__":
    main()
