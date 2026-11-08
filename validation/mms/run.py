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
Manufactured solutions for steady conduction on every fitting's mesh
(task 0074, V1; RESEARCH §7.9).

    python3 validation/mms/run.py                  # every case, k = 1, 2, 4
    python3 validation/mms/run.py --cases tee bend --levels 1 2

**The method.**  The exact field is

    T_m = sin(a x + 0.3) · sin(b y + 0.7) · sin(c z + 1.1),

with a, b, c set per case from its bounding box (:func:`wave_numbers`).
It is not symmetric about any plane, and −∇²T_m = (a² + b² + c²) T_m.
``laplacianFoam`` solves ∇·(D_T ∇T) + S = 0 steadily, with D_T = 1, the
source S = (a² + b² + c²) T_m as an ``exprField`` in a
``scalarSemiImplicitSource``, and T = T_m on every patch
(``exprFixedValue``).  Both are evaluated by OpenFOAM at the cell and face
centres (v2406; docs/integrations/openfoam.md).  The exact solution is
T_m: the error is T − T_m at the cell centres, whose amplitude is 1.

One conductivity in every layer: layers, stack changes and shells are mesh
topology here, not interface physics.  The levels are ``refined(k)``,
k = 1, 2, 4 (8× the cells per level).

**Per level** (``results.json``): the L2 and max error overall and in the
case's fittings under test (*focus*) and the rest; where the max error
sits (its fitting, and whether its cell touches a boundary); the mesh
checks.  Each OpenFOAM cell is matched to its fitting by the nearest hex
centroid of the gmsh mesh.

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

import gmsh                                                    # noqa: E402
from hexmesh import (Assembly, Bend, CircleShape, MiterBend, PipeSpec, Reducer,   # noqa: E402
                     Session, SplinePipe, Straight, Tee, Transition, Wye)
from hexmesh.core.shape import RectShape                       # noqa: E402
from hexmesh.study import openfoam as of                       # noqa: E402

_spec = importlib.util.spec_from_file_location("convergence",
                                               ROOT / "validation/tools/convergence.py")
conv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conv)       # richardson() (task 0089)
_spec = importlib.util.spec_from_file_location("stored", ROOT / "validation/tools/results.py")
stored = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stored)                # results.json (task 0093)

LEVELS = (1, 2, 4)
PHASES = (0.3, 0.7, 1.1)
#: a fitting whose order falls this far below the straight's is flagged (task 0074)
ORDER_FLAG = 0.3
R = 0.05                  # main radius [m]; lengths are in R


# --- the cases ---------------------------------------------------------------

def _pipe(radius=R, shells=0):
    spec = PipeSpec(nang=6).core("body", radius=radius, nrad=3)
    for i in range(shells):
        spec = spec.shell(f"shell{i + 1}", dR=0.2 * radius, nrad=2)
    return spec


def _asm(spec):
    return Assembly(spec, position=[0, 0, 0], direction=[1, 0, 0], up=[0, 0, 1])


def straight():
    a = _asm(_pipe())
    a.add(Straight(8 * R, n_layers=8))
    return a, [0]


def bend():
    a = _asm(_pipe())
    a.add(Straight(2 * R, n_layers=2))
    a.add(Bend(3 * R, 90, n_layers=8))
    a.add(Straight(2 * R, n_layers=2))
    return a, [1]


def miter():
    a = _asm(_pipe())
    a.add(Straight(2 * R, n_layers=2))
    a.add(MiterBend(radius=4 * R, angle=90, n_cuts=3, n_layers=2))
    a.add(Straight(2 * R, n_layers=2))
    return a, [1]


def spline():
    a = _asm(_pipe())
    a.add(Straight(2 * R, n_layers=2))
    a.add(SplinePipe([(2 * R, 0, 0), (6 * R, 2 * R, 1.5 * R), (10 * R, 1 * R, 4 * R)],
                     n_layers=16))
    return a, [1]


def reducer():
    a = _asm(_pipe())
    a.add(Straight(2 * R, n_layers=2))
    # a cosine constriction to 60 % of the radius, back to the inlet's.  The
    # exact field is defined everywhere, so the chords' distance from the
    # true profile doesn't enter the error: chord_tol is relaxed
    a.add(Reducer(_pipe(), length=4 * R, n_layers=8, profile=("cosine", 0.4), chord_tol=0.05))
    a.add(Straight(2 * R, n_layers=2))
    return a, [1]


def transition():
    a = _asm(_pipe())
    a.add(Straight(2 * R, n_layers=2))
    duct = PipeSpec(nang_w=6, nang_h=6).core("body", half_w=1.2 * R, half_h=0.8 * R)
    a.add(Transition(duct, length=4 * R, n_layers=6))
    a.add(Straight(2 * R, n_layers=2))
    return a, [1]


def _tee(shells):
    a = _asm(_pipe(shells=shells))
    a.add(Straight(2 * R, n_layers=2))
    main, branch = a.add(Tee(run_length=2 * R, branch_length=3 * R, branch_radius=0.5 * R))
    a.add(main, Straight(2 * R, n_layers=2))
    a.add(branch, Straight(2 * R, n_layers=2))
    return a, [1]


def tee():
    return _tee(0)


def tee_shells():
    return _tee(2)


def stack_change():
    """Insulation stopping inside a straight: the shell ends at cell 4."""
    a = _asm(_pipe(shells=2))
    a.add(Straight(8 * R, n_layers=8, stack_changes=((4, _pipe(shells=1)),)))
    return a, [0]


def _wye(angle, shells):
    a = _asm(_pipe(shells=shells))
    a.add(Straight(2 * R, n_layers=2))
    left, right = a.add(Wye(angle, run_length=1.5 * R, branch_length=4 * R))
    a.add(left, Straight(2 * R, n_layers=2))
    a.add(right, Straight(2 * R, n_layers=2))
    return a, [1]


def wye60():
    return _wye(60, 0)


def wye90():
    return _wye(90, 0)


def wye60_shell():
    return _wye(60, 1)


def wye90_shell():
    return _wye(90, 1)


def _duct(n=8):
    return PipeSpec(nang_w=n, nang_h=n).core("body", half_w=2 * R, half_h=R)


def duct_tap(branch):
    a = _asm(_duct())
    a.add(Straight(2 * R, n_layers=2))
    main, tap = a.add(Tee(branch=branch, branch_length=3 * R))
    a.add(main, Straight(2 * R, n_layers=2))
    a.add(tap, Straight(2 * R, n_layers=2))
    return a, [1]


def duct_tap_rect():
    return duct_tap(RectShape(0.8 * R, 0.6 * R, 8, 8))


def duct_tap_round():
    return duct_tap(CircleShape(0.6 * R, 8))


def duct():
    a = _asm(PipeSpec(nang_w=12, nang_h=6).core("body", half_w=2 * R, half_h=R))
    a.add(Straight(8 * R, n_layers=8))
    return a, [0]


CASES = {f.__name__: f for f in (
    straight, bend, miter, spline, reducer, transition, tee, tee_shells, stack_change,
    wye60, wye90, wye60_shell, wye90_shell, duct_tap_rect, duct_tap_round, duct)}
#: diagnostic series: a case's mesh with other schemes, as ``fvSchemes``
#: edits (old, new).  The duct taps' explicit non-orthogonal correction stops
#: contracting at k = 3 (task 0074, Agent notes); "limited corrected 0.5"
#: converges but is a different scheme
LIMITED = [("Gauss linear corrected", "Gauss linear limited corrected 0.5")]
SCHEME_EDITS = {"duct_tap_rect_lim": LIMITED, "duct_tap_round_lim": LIMITED}
CASES.update({"duct_tap_rect_lim": duct_tap_rect, "duct_tap_round_lim": duct_tap_round})
#: the fittings flagged in the first study (task 0074, Q1), and the design
#: answer's checks on them: ``_loc`` the same scheme again, for where the
#: error sits; ``_lsq`` least-squares cell gradients; ``_skew`` skew-corrected
#: interpolation.  Orders that recover with a skew-aware scheme point at the
#: scheme on the mesh, not at the mesh's geometry
FLAGGED = ("miter", "reducer", "transition", "tee", "tee_shells")
VARIANTS = {"loc": [],
            "lsq": [("gradSchemes     { default Gauss linear; }",
                     "gradSchemes     { default pointCellsLeastSquares; }")],
            "skew": [("interpolationSchemes { default linear; }",
                      "interpolationSchemes { default skewCorrected linear; }")]}
for _case in FLAGGED:
    for _v, _edits in VARIANTS.items():
        CASES[f"{_case}_{_v}"] = CASES[_case]
        SCHEME_EDITS[f"{_case}_{_v}"] = _edits
#: the baseline under the least-squares gradients, for the ``_lsq`` orders
CASES["straight_lsq"] = CASES["straight"]
SCHEME_EDITS["straight_lsq"] = VARIANTS["lsq"]


def assembly(case: str, k: int = 1) -> tuple[Assembly, list[int]]:
    asm, focus = CASES[case]()
    return (asm if k == 1 else asm.refined(k)), focus


def meshes():
    """(label, caption, build) per mesh shown in README.md."""
    return [(name, f"{name}, k = 1", lambda n=name: assembly(n)[0]) for name in CASES
            if name not in SCHEME_EDITS]


# --- the manufactured solution ----------------------------------------------

def wave_numbers(lo: np.ndarray, hi: np.ndarray, d: float) -> np.ndarray:
    """a, b, c: 1.5 wavelengths along each extent of the bounding box, but
    no wavelength shorter than the main diameter *d*."""
    return 2 * math.pi / np.maximum((hi - lo) / 1.5, d)


def exact(x: np.ndarray, w: np.ndarray) -> np.ndarray:
    return np.prod([np.sin(w[i] * x[:, i] + PHASES[i]) for i in range(3)], axis=0)


def _expr(w: np.ndarray, scale: float = 1.0) -> str:
    """T_m (times *scale*) as an OpenFOAM expression of ``pos()``."""
    parts = [f"sin({w[i]!r}*pos().{c}()+{PHASES[i]!r})" for i, c in enumerate("xyz")]
    return "*".join([repr(scale)] + parts)


# --- OpenFOAM dictionaries ---------------------------------------------------

H = of.header

CONTROL = """application     laplacianFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};
deltaT          1;
writeControl    timeStep;
writeInterval   {end_time};
writeFormat     ascii;
writePrecision  17;
timeFormat      general;
runTimeModifiable false;
"""

SCHEMES = """ddtSchemes      { default steadyState; }
gradSchemes     { default Gauss linear; }
divSchemes      { default none; }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }
"""

# Each "time step" runs the non-orthogonal correctors again from the last
# T; residualControl stops at the first step that starts converged.
SOLUTION = """solvers
{
    T { solver PCG; preconditioner DIC; tolerance 1e-14; relTol 0; }
}
SIMPLE
{
    nNonOrthogonalCorrectors 10;
    residualControl { T 1e-11; }
}
"""


def schemes(edits=()) -> str:
    """``fvSchemes``' body with *edits* (old, new) applied."""
    text = SCHEMES
    for old, new in edits:
        if text.count(old) != 1:
            raise ValueError(f"fvSchemes edit: {old!r} not found once")
        text = text.replace(old, new)
    return text


def write_case(case: Path, end_time: int, w: np.ndarray, edits=()) -> None:
    for d in ("0", "constant", "system"):
        (case / d).mkdir(parents=True, exist_ok=True)
    source = f"""mms
{{
    type            scalarSemiImplicitSource;
    active          true;
    selectionMode   all;
    volumeMode      specific;
    sources
    {{
        T
        {{
            explicit
            {{
                type        exprField;
                expression  "{_expr(w, float(np.sum(w ** 2)))}";
            }}
            implicit none;
        }}
    }}
}}
"""
    t0 = f"""dimensions      [0 0 0 1 0 0 0];
internalField   uniform 0;
boundaryField
{{
    ".*"
    {{
        type        uniformFixedValue;
        uniformValue
        {{
            type        expression;
            expression  "{_expr(w)}";
        }}
    }}
}}
"""
    files = {
        "system/controlDict": H("dictionary", "controlDict", "system")
        + CONTROL.format(end_time=end_time),
        "system/fvSchemes": H("dictionary", "fvSchemes", "system")
        + schemes(edits),
        "system/fvSolution": H("dictionary", "fvSolution", "system") + SOLUTION,
        "constant/transportProperties": H("dictionary", "transportProperties", "constant")
        + "DT              DT [0 2 -1 0 0 0 0] 1;\n",
        "constant/fvOptions": H("dictionary", "fvOptions", "constant") + source,
        "0/T": H("volScalarField", "T", "0") + t0,
    }
    for name, text in files.items():
        (case / name).write_text(text, encoding="utf-8")


# --- one level ----------------------------------------------------------------

def _centroids(asm: Assembly) -> tuple[np.ndarray, np.ndarray, int, np.ndarray, float]:
    """Every hex's vertex centroid and its fitting index, from the mesh in
    the current gmsh session; how many hexes gmshToFoam's orientation test
    would flip; each hex's gmsh volume (its block); and the largest ratio of
    a hex's longest to shortest edge."""
    tags, x, _ = gmsh.model.mesh.getNodes()
    pos = np.full(int(tags.max()) + 1, -1)
    pos[tags.astype(int)] = np.arange(len(tags))
    x = x.reshape(-1, 3)
    cents, owners, flips, blocks, ratio = [], [], 0, [], 0.0
    for index, vols in asm.fitting_volumes().items():
        for v in vols:
            for t, _, nodes in zip(*gmsh.model.mesh.getElements(3, v)):
                p = x[pos[nodes.reshape(len(nodes) // 8, 8).astype(int)]]
                cents.append(p.mean(axis=1))
                owners.append(np.full(len(p), index))
                blocks.append(np.full(len(p), v))
                flips += int(of.foam_would_invert(p).sum())
                ends = np.asarray(_HEX_EDGES)
                e = np.linalg.norm(p[:, ends[:, 1]] - p[:, ends[:, 0]], axis=2)
                ratio = max(ratio, float((e.max(axis=1) / e.min(axis=1)).max()))
    return np.vstack(cents), np.concatenate(owners), flips, np.concatenate(blocks), ratio


#: a hex's 12 edges (gmsh vertex order)
_HEX_EDGES = ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
              (0, 4), (1, 5), (2, 6), (3, 7))


def _errors(err, vol, mask) -> dict | None:
    if not mask.any():
        return None
    v = vol[mask]
    return {"l2": float(math.sqrt(np.sum(v * err[mask] ** 2) / v.sum())),
            "max": float(np.abs(err[mask]).max()), "cells": int(mask.sum())}


def results(case: Path, w: np.ndarray, cents: np.ndarray, owners: np.ndarray,
            focus: list[int], names: dict[int, str], blocks: np.ndarray | None = None) -> dict:
    from scipy.spatial import cKDTree
    mesh = case / "constant/polyMesh"
    pts, faces = of.read_points(mesh / "points"), of.read_faces(mesh / "faces")
    owner, neigh = of.read_labels(mesh / "owner"), of.read_labels(mesh / "neighbour")
    T = of.read_internal(of.latest_time(case) / "T", 1)
    fc, sf = of.face_geometry(pts, faces)
    cc, vol = of.cell_geometry(fc, sf, owner, neigh, len(T))
    err = T - exact(cc, w)
    dist, near = cKDTree(cents).query(cc)
    fit = owners[near]
    in_focus = np.isin(fit, focus)
    boundary = np.zeros(len(T), bool)
    boundary[owner[len(neigh):]] = True
    worst = int(np.argmax(np.abs(err)))
    per = {names[i]: _errors(err, vol, fit == i) for i in sorted(set(fit.tolist()))}
    split = {}
    if blocks is not None:
        # cells with a face on a block interface: a face between two gmsh
        # volumes, where grid lines may kink (task 0074, Q1 check 2)
        blk = blocks[near]
        inner = np.arange(len(neigh))
        cut = blk[owner[inner]] != blk[neigh]
        at = np.zeros(len(T), bool)
        at[owner[inner][cut]] = at[neigh[cut]] = True
        split = {"focus_block_interface": _errors(err, vol, in_focus & at),
                 "focus_block_interior": _errors(err, vol, in_focus & ~at),
                 "max_at_block_interface": bool(at[worst])}
    return {
        "volume": float(vol.sum()),
        "all": _errors(err, vol, np.ones(len(T), bool)),
        "focus": _errors(err, vol, in_focus),
        "rest": _errors(err, vol, ~in_focus) if (~in_focus).any() else None,
        "per_fitting": per,
        "boundary_cells": _errors(err, vol, boundary),
        "interior_cells": _errors(err, vol, ~boundary),
        "max_at": {"fitting": names[int(fit[worst])], "boundary_cell": bool(boundary[worst]),
                   "position": cc[worst].tolist()},
        "match_distance_max": float(dist.max()),
        **split,
    }


def run_level(name: str, k: int, work: Path, end_time: int, n_proc: int = 1) -> dict:
    case = work / f"{name}_k{k}"
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    asm, focus = assembly(name, k)
    with Session(f"mms-{name}-{k}"):
        cells = asm.cell_count()
        print(f"[{name} k={k}] predicted cells: {cells}", flush=True)
        msh = case / "mesh.msh"
        asm.write_openfoam(str(msh))
        sj = asm.check_quality("scaled_jacobian").worst
        cents, owners, flips, blocks, edge_ratio = _centroids(asm)
        lo, hi = cents.min(axis=0), cents.max(axis=0)
    names = {e.index: e.name for e in asm.edges}
    d = 2 * R
    # the wave numbers come from the k = 1 mesh, so every level solves the same problem
    a1, _ = assembly(name, 1)
    if k != 1:
        with Session(f"mms-{name}-box"):
            a1.mesh()
            c1 = _centroids(a1)[0]
            lo, hi = c1.min(axis=0), c1.max(axis=0)
    w = wave_numbers(lo, hi, d)
    write_case(case, end_time, w, SCHEME_EDITS.get(name, ()))
    # every hex right-handed (gmsh's corner Jacobians), so gmshToFoam's
    # orientation test, which flips warped junction hexes, is skipped
    retyped = of.convert(case, msh, keep_orientation=sj > 0)
    check = of.check_mesh(case)
    solve = of.run_solver(case, "laplacianFoam", n_proc=n_proc)
    res = [float(v) for v in re.findall(r"Initial residual = ([\d.e+-]+)", solve)]
    out = {"case": name, "k": k, "cells": cells, "focus": [names[i] for i in focus],
           "laplacian": dict(SCHEME_EDITS.get(name, ())).get("Gauss linear corrected",
                                                              "Gauss linear corrected"),
           "scheme_edits": [list(e) for e in SCHEME_EDITS.get(name, ())],
           "max_edge_ratio": edge_ratio,
           "wave_numbers": w.tolist(), "min_scaled_jacobian": sj, "retyped": retyped,
           "keep_orientation": sj > 0, "gmshToFoam_would_invert": flips,
           **{f"check_{key}": v for key, v in check.items()},
           **stored.counts(asm),
           "fvoptions_read": "Selecting finite volume options type scalarSemiImplicitSource"
                             in solve,
           "steps": len(re.findall(r"^Time = ", solve, re.M)),
           "last_initial_residual": res[-1] if res else None,
           "converged": "reached convergence" in solve or (bool(res) and res[-1] < 1e-10)}
    out.update(results(case, w, cents, owners, focus, names, blocks))
    return out


# --- analysis -----------------------------------------------------------------

def orders(values: list[float], ks: list[int]) -> list[float]:
    """Observed order between successive levels k (refinement ratio k_b / k_a)."""
    return [math.log(a / b) / math.log(kb / ka)
            for a, b, ka, kb in zip(values, values[1:], ks, ks[1:])]


def analyse(levels: list[dict]) -> dict:
    """Per case: L2 and max errors by level, their orders overall and in the
    focus fittings, and the flags (order more than ORDER_FLAG below the
    straight's)."""
    by, failed = {}, {}
    for lv in levels:
        if lv["converged"]:
            by.setdefault(lv["case"], []).append(lv)
        else:
            failed.setdefault(lv["case"], []).append(lv["k"])
    out = {}
    for name, rows in by.items():
        rows = sorted(rows, key=lambda r: r["k"])
        if len(rows) < 2:
            continue
        ks = [r["k"] for r in rows]
        out[name] = {
            "k": [r["k"] for r in rows], "cells": [r["cells"] for r in rows],
            "l2": [r["all"]["l2"] for r in rows], "max": [r["all"]["max"] for r in rows],
            "focus_l2": [r["focus"]["l2"] for r in rows],
            "order_l2": orders([r["all"]["l2"] for r in rows], ks),
            "order_max": orders([r["all"]["max"] for r in rows], ks),
            "order_focus_l2": orders([r["focus"]["l2"] for r in rows], ks),
            "order_focus_max": orders([r["focus"]["max"] for r in rows], ks),
            "not_converged_k": failed.get(name, []),
            "falls": all(b < a for a, b in zip([r["all"]["l2"] for r in rows],
                                                 [r["all"]["l2"] for r in rows][1:])),
            "max_at": rows[-1]["max_at"],
        }
    base = out.get("straight")
    if base:
        ref = base["order_focus_l2"][-1]
        for name, a in out.items():
            a["flag"] = a["order_focus_l2"][-1] < ref - ORDER_FLAG
    return out


def table(analysis: dict) -> str:
    lines = ["| case | k | cells (finest) | L2 | order L2 (all) | order L2 (fitting) | "
             "order max (fitting) | max error at | flag |", "|---|---|---|---|---|---|---|---|---|"]
    for name, a in analysis.items():
        at = a["max_at"]
        lines.append(
            f"| {name} | {', '.join(map(str, a['k']))} | {a['cells'][-1]} | "
            + ", ".join(f"{v:.3g}" for v in a["l2"])
            + " | " + ", ".join(f"{v:.2f}" for v in a["order_l2"])
            + " | " + ", ".join(f"{v:.2f}" for v in a["order_focus_l2"])
            + " | " + ", ".join(f"{v:.2f}" for v in a["order_focus_max"])
            + f" | {at['fitting']}{' (boundary cell)' if at['boundary_cell'] else ''} | "
            + ("**yes**" if a.get("flag") else "") + " |")
    return "\n".join(lines)


def recheck(data: dict) -> list[dict]:
    """Per case, from ``results.json`` (task 0093): the gate, the L2 error
    falls with refinement over the converged levels; the orders (overall
    and in the fittings under test) and the flag are reported."""
    out = []
    for name, a in analyse(data["levels"]).items():
        ks = ", ".join(map(str, a["k"]))
        note = (f"order L2 {', '.join(f'{v:.2f}' for v in a['order_l2'])}; in the fitting "
                f"{', '.join(f'{v:.2f}' for v in a['order_focus_l2'])}"
                + ("; flagged (more than 0.3 below the straight)" if a.get("flag") else "")
                + (f"; not converged at k = {a['not_converged_k']}" if a["not_converged_k"] else ""))
        out.append(stored.row(f"{name}: L2 error of T (k = {ks})", gate="falls with refinement",
                              ok=a["falls"], value=", ".join(f"{v:.3g}" for v in a["l2"]),
                              note=note))
    return out


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--cases", nargs="+", choices=list(CASES), default=list(CASES))
    ap.add_argument("--levels", nargs="+", type=int, default=list(LEVELS))
    ap.add_argument("--work", type=Path, default=HERE / "work")
    ap.add_argument("--end-time", type=int, default=200)
    ap.add_argument("--np", type=int, default=1, dest="n_proc",
                    help="MPI processes per solve (check other runs first, CLAUDE.md)")
    stored.add_arguments(ap, HERE)
    ap.add_argument("--openfoam", default=of.V2406,
                    help="runner: native, or docker:IMAGE (default: v2406 in Docker)")
    args = ap.parse_args(argv)
    of.set_runner(args.openfoam)
    store = stored.Store(args.json, "mms")
    store.put_extra("method", {"field": "sin(a x + 0.3) sin(b y + 0.7) sin(c z + 1.1)",
                               "source": "(a² + b² + c²) T_m", "D_T": 1,
                               "wave_numbers": "2π / max(extent / 1.5, 2 R)"})
    failed = {}
    for name in args.cases:
        for k in args.levels:
            try:
                r = stored.run_level(store, f"{name}_k{k}",
                                     lambda name=name, k=k: run_level(name, k, args.work,
                                                                      args.end_time,
                                                                      args.n_proc),
                                     args.work / f"{name}_k{k}", args.keep_work)
            except Exception as e:                 # the next case still runs
                failed[f"{name}_k{k}"] = f"{type(e).__name__}: {e}"
                print(f"[{name} k={k}] FAILED {failed[f'{name}_k{k}']}", flush=True)
                break
            print(f"[{name} k={k}] L2 {r['all']['l2']:.4g}, max {r['all']['max']:.4g}, "
                  f"focus L2 {r['focus']['l2']:.4g}, steps {r['steps']}", flush=True)
    if failed:
        print("failed: " + json.dumps(failed, indent=1))
    analysis = analyse(store.levels())
    print(table(analysis))
    return analysis


if __name__ == "__main__":
    main()
