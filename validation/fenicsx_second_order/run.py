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
Second-order export checked end to end with FEniCSx (task 0077, V1;
decision 0034).

    python3 validation/fenicsx_second_order/run.py --work DIR
    python3 validation/fenicsx_second_order/run.py --work DIR --cases straight --levels 1 2

**The method.**  The manufactured field is task 0074's,

    u_m = sin(a x + 0.3) · sin(b y + 0.7) · sin(c z + 1.1),

with a, b, c from the case's bounding box (1.5 wavelengths along each
extent, none shorter than the diameter).  dolfinx solves −∇²u = f,
f = −∇²u_m, with u = u_m on every boundary (*dirichlet*), or with the
exact flux ∇u_m · n on the curved wall and u = u_m on the ends
(*neumann*: n comes from the mesh's own geometry, so it tests where the
wall nodes are).  Three rows per level:

- Hex8 mesh, Q1: L2 order 2 expected;
- Hex8 mesh, Q2: geometry-limited, about 2;
- Hex27 mesh (``mesh(order=2)``), Q2: order 3 expected.

The levels are ``refined(k)``, k = 1, 2, 4 (``nang`` doubling).  The wye
and the equal tee are left out: ``mesh(order=2)`` rejects them
(``second_order_unsupported``, task 0076).

FEniCSx runs in Docker (``dolfinx/dolfinx`` at :data:`IMAGE`), as the
host user; it is not one of hexmesh's dependencies (decision 0034).
``results.json`` holds every level's errors (one level per case, k and
mesh); levels already stored are reused.  The meshes are written to
``--work`` and deleted unless ``--keep-work``.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import math
import os
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

import gmsh                                                    # noqa: E402
from hexmesh import Assembly, Bend, PipeSpec, Session, Straight, Tee   # noqa: E402
from hexmesh.study.manifest import versions                    # noqa: E402

_spec = importlib.util.spec_from_file_location("stored", ROOT / "validation/tools/results.py")
stored = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stored)                # results.json (task 0093)

#: the dolfinx image: v0.11.0 (2026-06-11), pinned by digest (task 0077)
IMAGE = ("dolfinx/dolfinx:v0.11.0@sha256:"
         "2ae4bfbc0d9077268880faf04c72750528bee986c94ab223a2c159969bd56fa8")
LEVELS = (1, 2, 4)
PHASES = (0.3, 0.7, 1.1)
R = 0.05
#: the gate: Hex27/Q2's observed L2 order, every consecutive pair of levels
ORDER_MIN = 2.7
#: per mesh: Hex8 gets both degrees, Hex27 the Q2 rows
JOBS = {1: [(1, "dirichlet"), (2, "dirichlet"), (1, "neumann"), (2, "neumann")],
        2: [(2, "dirichlet"), (2, "neumann")]}


# --- the cases ---------------------------------------------------------------

def _pipe():
    return PipeSpec(nang=6).core("body", radius=R, nrad=3)


def _asm():
    return Assembly(_pipe(), position=[0, 0, 0], direction=[1, 0, 0], up=[0, 0, 1])


def straight():
    a = _asm()
    a.add(Straight(8 * R, n_layers=8))
    return a


def bend():
    a = _asm()
    a.add(Straight(2 * R, n_layers=2))
    a.add(Bend(3 * R, 90, n_layers=8))
    a.add(Straight(2 * R, n_layers=2))
    return a


def tee():
    a = _asm()
    a.add(Straight(2 * R, n_layers=2))
    main, branch = a.add(Tee(branch_length=4 * R, branch_radius=0.5 * R))
    a.add(main, Straight(2 * R, n_layers=2))
    return a


CASES = {"straight": straight, "bend": bend, "tee": tee}


def meshes():
    """(label, caption, build) per mesh shown in README.md."""
    order = ("tee", "bend", "straight")             # the first gets the overview
    return [(name, f"{name}, k = 1", CASES[name]) for name in order]


# --- running -----------------------------------------------------------------

def wall_primitives(asm: Assembly) -> list[dict]:
    """The exact wall, as the solver needs it for the Neumann data's
    normal: a capped cylinder per straight and per tee run and branch, a
    torus per bend (centre, axis, bend radius)."""
    from hexmesh.assembly.sweep import Arc
    out = []
    pos = lambda port: np.asarray(port.frame.position, float)
    for e in asm.edges:
        f = e.fitting
        r = float(e.ports[0].spec.core_shape.max_extent)
        if isinstance(f, Bend):
            arc = f.path(e.ports[0].frame, e.ports[1].frame, e.ports[0].spec).axial
            assert isinstance(arc, Arc)
            c, ax = np.asarray(arc.centre, float), np.asarray(arc.axis, float)
            ax = ax / np.linalg.norm(ax)
            q = pos(e.ports[0]) - c
            rb = float(np.linalg.norm(q - (q @ ax) * ax))
            out.append({"kind": "torus", "c": c.tolist(), "axis": ax.tolist(), "rb": rb, "r": r})
        elif isinstance(f, Tee):
            a, b = pos(e.ports[0]), pos(e.ports[1])
            out.append({"kind": "seg", "a": a.tolist(), "b": b.tolist(), "r": r})
            tip = pos(e.ports[2])
            u = (b - a) / np.linalg.norm(b - a)
            base = a + ((tip - a) @ u) * u
            out.append({"kind": "seg", "a": base.tolist(), "b": tip.tolist(),
                        "r": float(f.branch_radius)})
        else:
            out.append({"kind": "seg", "a": pos(e.ports[0]).tolist(),
                        "b": pos(e.ports[1]).tolist(), "r": r})
    return out


def wave_numbers(lo: np.ndarray, hi: np.ndarray, d: float) -> np.ndarray:
    return 2 * math.pi / np.maximum((hi - lo) / 1.5, d)


def write_meshes(case: str, k: int, work: Path) -> tuple[dict, list[float], list[dict]]:
    """The case's Hex8 and Hex27 meshes at level *k*; its wave numbers and
    wall primitives."""
    out = {}
    w = walls = None
    for order in (1, 2):
        path = work / f"{case}_k{k}_o{order}.msh"
        with Session(path.stem), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            asm = CASES[case]()
            asm = asm if k == 1 else asm.refined(k)
            asm.write(str(path), order=order)
            walls = wall_primitives(asm)
            if w is None:
                x = gmsh.model.mesh.getNodes()[1].reshape(-1, 3)
                w = wave_numbers(x.min(axis=0), x.max(axis=0), 2 * R).tolist()
        out[order] = path
    return out, w, walls


def solve(mesh: Path, w: list[float], walls: list[dict], order: int, work: Path,
          memory: str | None = None) -> dict:
    """Every job of *order*'s mesh, one container each (memory is freed
    between them; *memory* caps each container, ``docker run --memory``)."""
    user = f"{os.getuid()}:{os.getgid()}"
    cap = ["--memory", memory, "--memory-swap", memory] if memory else []
    out = None
    for i, (d, v) in enumerate(JOBS[order]):
        jobs = work / f"{mesh.stem}.{i}.jobs.json"
        res = work / f"{mesh.stem}.{i}.out.json"
        jobs.write_text(json.dumps({"w": w, "phases": PHASES, "walls": walls,
                                    "jobs": [{"degree": d, "variant": v}]}), encoding="utf-8")
        subprocess.run(["docker", "run", "--rm", "-u", user, "-e", "HOME=/tmp", *cap,
                        "-v", f"{work}:/work", "-v", f"{HERE}:/case:ro", "-w", "/work", IMAGE,
                        "python3", "/case/solve.py", mesh.name, jobs.name, res.name],
                       check=True, capture_output=True, text=True)
        r = json.loads(res.read_text(encoding="utf-8"))
        out = r if out is None else {**out, "rows": out["rows"] + r["rows"]}
    return out


def _l2(level: dict, degree: int, variant: str) -> float:
    return next(r["l2"] for r in level["solves"]
                if r["degree"] == degree and r["variant"] == variant)


def orders(data: dict, case: str, geometry: str, degree: int, variant: str) -> list[float]:
    """Observed L2 orders between consecutive stored levels of one row."""
    lv = sorted(stored.series(data, case=case, geometry=geometry), key=lambda l: l["k"])
    e = [_l2(l, degree, variant) for l in lv]
    return [math.log(e[i] / e[i + 1]) / math.log(lv[i + 1]["k"] / lv[i]["k"])
            for i in range(len(lv) - 1)]


def recheck(data: dict) -> list[dict]:
    """Per case, from ``results.json``: the gate, Hex27/Q2's L2 order ≥
    :data:`ORDER_MIN` between every pair of levels, Dirichlet and Neumann;
    the Hex8 rows reported in the note (Q2 on Hex8 with the exact wall's
    flux is the geometry-limited row)."""
    out = []
    for case in CASES:
        if not stored.series(data, case=case):
            continue
        for variant in ("dirichlet", "neumann"):
            o27 = orders(data, case, "Hex27", 2, variant)
            o8 = orders(data, case, "Hex8", 2, variant)
            q1 = orders(data, case, "Hex8", 1, variant)
            fmt = lambda o: ", ".join(f"{v:.2f}" for v in o)
            out.append(stored.row(
                f"{case}, {variant}: L2 order, Q2 on Hex27", gate=f">= {ORDER_MIN}",
                ok=bool(o27) and min(o27) >= ORDER_MIN, value=fmt(o27),
                note=f"Q2 on Hex8 {fmt(o8)}; Q1 on Hex8 {fmt(q1)}"))
    return out


def _environment() -> dict:
    return {**versions(), "fenicsx": IMAGE, "runner": "docker",
            "date": datetime.date.today().isoformat()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--work", type=Path, default=HERE / "work",
                    help='folder for the meshes (default: validation/fenicsx_second_order/work/, not committed); deleted once each level is stored')
    ap.add_argument("--cases", nargs="+", choices=list(CASES), default=list(CASES),
                    help='geometries to solve on (default: all of %(choices)s)')
    ap.add_argument("--levels", nargs="+", type=int, default=list(LEVELS),
                    help="refinement levels k to run: k multiplies the coarsest mesh's cells along each refined direction (default: %(default)s)")
    ap.add_argument("--memory", help="cap each container's memory (docker run --memory), "
                                     "e.g. 6g")
    stored.add_arguments(ap, HERE)
    args = ap.parse_args(argv)
    args.work.mkdir(parents=True, exist_ok=True)
    store = stored.Store(args.json, "fenicsx_second_order")
    store.put_extra("method", {"field": "sin(a x + 0.3) sin(b y + 0.7) sin(c z + 1.1)",
                               "equation": "-lap u = f, f = -lap u_m",
                               "dirichlet": "u = u_m on every boundary",
                               "neumann": "grad u_m . n on the wall, n the exact wall's normal; "
                                          "u = u_m on the ends",
                               "quadrature_degree": 8, "image": IMAGE})
    for case in args.cases:
        for k in args.levels:
            names = {o: f"{case}_k{k}_{'Hex27' if o == 2 else 'Hex8'}" for o in (1, 2)}
            if all((lv := store.level(n)) and lv["precision"] == stored.FULL
                   for n in names.values()):
                print(f"[{case} k={k}] reused from {store.path}", flush=True)
                continue
            paths, w, walls = write_meshes(case, k, args.work)
            spec = CASES[case]()
            spec = spec if k == 1 else spec.refined(k)
            for order, path in paths.items():
                res = solve(path, w, walls, order, args.work, args.memory)
                geometry = "Hex27" if order == 2 else "Hex8"
                store.put(names[order], {"case": case, "k": k, "geometry": geometry,
                                         "cells": res["cells"], **stored.counts(spec),
                                         "w": w, "solves": res["rows"]}, env=_environment())
                for r in res["rows"]:
                    print(f"{case} k={k} {geometry} Q{r['degree']} {r['variant']}: "
                          f"L2 {r['l2'] / r['l2_norm']:.3e} H1 {r['h1']:.3e}", flush=True)
                if not args.keep_work:
                    path.unlink()
            if not args.keep_work:
                for p in args.work.glob(f"{case}_k{k}_*.json"):
                    p.unlink()
    if not args.keep_work and args.work.exists() and not any(args.work.iterdir()):
        args.work.rmdir()
    for r in recheck(store.data):
        print(f"{r['quantity']}: {r['value']} ({r['verdict']}); {r['note']}")


if __name__ == "__main__":
    main()
