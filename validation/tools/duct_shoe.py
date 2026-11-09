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
Task 0063: the shoe tap, measured (decision 0031, stage 4).

Each case is ``Straight → Tee(angle=α) → Straight`` on both outlets, on
the kit's 2:1 duct (half-extents 0.1 × 0.05, 4 cells per side, nrad 3),
the tap on the wide face, with ``run_length`` resolved as a user gets it
and the branch the hole's acute end + the face's half-width.  Over α ∈
{30, 45, 60, 90}°, branch ratio (reach across / the face's half-width) ∈
{0.3, 0.6}, a square rectangular branch and a round one, plus full-width
taps (0.6 of the face along the main), it reports:
- the predicted min corner scaled Jacobian and worst non-orthogonality
  (the block layout, before GMSH) and the block of the worst;
- ``validate()``'s verdict: the error code if it rejects the case;
- the meshed ones over the tee's hexes, for the cases it accepts.

    python3 -m validation.tools.duct_shoe       # from the repository root

Rows go to ``validation/tools/duct_shoe.json``; no mesh is kept.
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation" / "tools" / "duct_shoe.json"

B = 0.05            # the duct's half-depth; 2:1, so the wide face's half-width is 2B
N = 4
ANGLES = (30.0, 45.0, 60.0, 90.0)
RATIOS = (0.3, 0.6)
KINDS = ("rect", "round", "full")


def assembly(kind: str, ratio: float, angle: float):
    from hexmesh.assembly import Assembly, Straight, Tee
    from hexmesh.core.shape import CircleShape, RectShape
    from hexmesh.core.spec import PipeSpec
    from hexmesh.assembly.interface import lean
    a = 2 * B
    spec = PipeSpec(nang_w=N, nang_h=N).core("fluid", RectShape(a, B, N, N), nrad=3, layout="oh")
    if kind == "full":
        shape, reach = RectShape(a, ratio * a, N, N), ratio * a
    elif kind == "rect":
        shape, reach = RectShape(ratio * a, ratio * a, N, N), ratio * a
    else:
        shape, reach = CircleShape(radius=ratio * a, nang=N), ratio * a
    ca, sa = lean(angle)
    asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1], lc=0.1)
    asm.add(Straight(0.2, n_layers=N))
    main, branch = asm.add(Tee(branch=shape, angle=angle, n_run=N, n_branch=N,
                               branch_length=(B + reach * ca) / sa + a),
                           names=["main", "branch"])
    asm.add(main, Straight(0.2, n_layers=N))
    asm.add(branch, Straight(0.1, n_layers=N))
    return asm


def measure(asm) -> dict:
    import gmsh
    from hexmesh import Session
    from hexmesh.assembly import Tee
    from hexmesh.assembly.junction_quality import TAP_BLOCKS, _where
    from hexmesh.quality_hex import max_non_orthogonality, min_scaled_jacobians
    e = next(x for x in asm._edges if isinstance(x.fitting, Tee))
    frames, spec = [p.frame for p in e.ports], e.ports[0].spec
    lay = e.fitting.layout(frames, spec)
    angle, b = lay.predicted_nonorth()
    where = lambda b: _where(frozenset(v[0] if isinstance(v, tuple) else str(v)
                                       for v in lay.blocks[b][0]), TAP_BLOCKS)
    sj = lay.corner_jacobians()
    row = {"run_length": round(e.fitting.run_length, 5),
           "predicted_min_sj": round(float(sj.min()), 4),
           "predicted_min_sj_where": where(int(np.argmin(sj)) // 8),
           "predicted_nonorth": round(float(angle), 2),
           "predicted_nonorth_where": where(b)}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            asm.validate()
    except Exception as err:
        row["rejected"] = getattr(err, "code", type(err).__name__)
        return row
    t0 = time.perf_counter()
    with Session("duct-shoe"), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            asm.mesh()
        except Exception as err:            # the meshed SJ check of a round tap
            row["rejected"] = getattr(err, "code", type(err).__name__)
            return row
        row["warnings"] = sorted({getattr(w.message, "code", type(w.message).__name__)
                                  for w in caught})
        ntag, nx, _ = gmsh.model.mesh.getNodes()
        pos = np.full(int(ntag.max()) + 1, -1)
        pos[ntag.astype(int)] = np.arange(len(ntag))
        nx = nx.reshape(-1, 3)
        conn = np.vstack([n.reshape(-1, 8) for v in asm._fitting_volumes[e.index]
                          for t, _, n in zip(*gmsh.model.mesh.getElements(3, v)) if t == 5])
        c = pos[conn.astype(int)]
        verts = nx[c]
        row.update({"cells": int(len(c)),
                    "meshed_min_sj": round(float(min_scaled_jacobians(verts).min()), 4),
                    "meshed_nonorth": round(max_non_orthogonality(verts, c), 2)})
    row["seconds"] = round(time.perf_counter() - t0, 1)
    return row


def main(argv=None) -> int:
    rows = {}
    for kind in KINDS:
        for ratio in RATIOS:
            for angle in ANGLES:
                key = f"{kind}-r{ratio:g}-a{angle:g}"
                try:
                    asm = assembly(kind, ratio, angle)
                except Exception as err:        # rejected when added (resolve)
                    rows[key] = {"rejected": getattr(err, "code", type(err).__name__)}
                    print(key, json.dumps(rows[key]), flush=True)
                    continue
                try:
                    rows[key] = measure(asm)
                except Exception as err:        # a case that can't be built is a result
                    rows[key] = {"failed": f"{type(err).__name__}: {err}",
                                 "code": getattr(err, "code", None)}
                print(key, json.dumps(rows[key]), flush=True)
    OUT.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
