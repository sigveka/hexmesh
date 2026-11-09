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
Task 0061: the offset tee, measured (decision 0031, stage 2).

Each case is ``Straight → Tee(offset=h) → Straight`` on both outlets, at
``nang`` 8, single layer, with the run and branch lengths resolved as a
user gets them (``run_length=None``; the branch the turning station's
distance + R).  Over h/R ∈ {0, 0.2, 0.4, 0.6}, r/R ∈ {0.3, 0.5, 0.6}
with |h| + r < R, at α 90° and 45°, it reports (r/R 0.6 added: at 45° the
lateral builds from r/R 0.50, task 0060, so 0.3 is out of range there):
- the predicted min corner scaled Jacobian and worst non-orthogonality
  (the block layout, before GMSH) and the block of the worst;
- ``validate()``'s verdict: the error code if it rejects the case;
- the meshed ones over the tee's hexes, for the cases it accepts;
- the projector's largest move, in R.

    python3 -m validation.tools.tee_offset       # from the repository root

With ``--map``, every r/R 0.2–0.9 and h/R 0–0.7 in steps of 0.1 with
|h| + r < R, at 90° and 45°, gets its outcome: meshed, or the code that
stopped it (at ``validate()`` or in ``mesh()``), with the predicted SJ.
The committed map was run before ``TEE_MAX_OFFSET_RATIO`` existed: it is
that limit's evidence.  Run now, every h > r is ``tee_offset_out_of_range``.

Rows go to ``validation/tools/tee_offset.json`` (the map's under
``"map"``); no mesh is kept.
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation" / "tools" / "tee_offset.json"

R = 0.1
NANG = 8
RATIOS = (0.3, 0.5, 0.6)
OFFSETS = (0.0, 0.2, 0.4, 0.6)
ANGLES = (90.0, 45.0)


def assembly(ratio: float, h: float, angle: float):
    from hexmesh.assembly import Assembly, Straight, Tee
    from hexmesh.assembly.tee import turning_height
    from hexmesh.core.spec import PipeSpec
    spec = PipeSpec(nang=NANG).core("fluid", radius=R, nrad=3)
    asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1], lc=0.05)
    asm.add(Straight(0.2, n_layers=4))
    tee = Tee(branch_radius=ratio * R, offset=h * R, angle=angle,
              branch_length=turning_height(R, ratio * R, 0.0, angle) + R)
    main, branch = asm.add(tee, names=["main", "branch"])
    asm.add(main, Straight(0.2, n_layers=4))
    asm.add(branch, Straight(0.2, n_layers=4))
    return asm


def measure(asm) -> dict:
    import gmsh
    from hexmesh import Session
    from hexmesh.assembly import Tee
    from hexmesh.assembly.junction_quality import TEE_BLOCKS, _where
    from hexmesh.quality_hex import max_non_orthogonality, min_scaled_jacobians
    e = next(x for x in asm._edges if isinstance(x.fitting, Tee))
    frames, spec = [p.frame for p in e.ports], e.ports[0].spec
    lay = e.fitting.layout(frames, spec)
    angle, b = lay.predicted_nonorth()
    where = lambda b: _where(frozenset(v[0] if isinstance(v, tuple) else str(v)
                                       for v in lay.blocks[b][0]), TEE_BLOCKS)
    sj = lay.corner_jacobians()
    row = {"run_length_R": e.fitting.run_length / R,
           "predicted_min_sj": float(sj.min()),
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
    with Session("tee-offset"), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        asm.mesh()
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
        sj = min_scaled_jacobians(verts)
        row.update({"cells": int(len(c)), "meshed_min_sj": float(sj.min()),
                    "meshed_nonorth": round(max_non_orthogonality(verts, c), 2)})
        rep = asm.projection_report.get(e.name)
        row["projector_move_R"] = float(rep["move"]) / R if rep else None
    row["seconds"] = round(time.perf_counter() - t0, 1)
    return row


def outcome(ratio: float, h: float, angle: float) -> dict:
    """Meshed or the stopping code, and the predicted SJ when it has one."""
    from hexmesh import Session
    from hexmesh.assembly import Tee
    row = {}
    try:
        asm = assembly(ratio, h, angle)
        e = next(x for x in asm._edges if isinstance(x.fitting, Tee))
        frames, spec = [p.frame for p in e.ports], e.ports[0].spec
        row["predicted_min_sj"] = round(float(
            e.fitting.layout(frames, spec).corner_jacobians().min()), 3)
        with Session("tee-offset-map"), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            asm.mesh()
        row["outcome"] = "meshed"
    except Exception as err:
        row["outcome"] = getattr(err, "code", None) or type(err).__name__
    return row


def map_(rows: dict) -> None:
    out = {}
    for angle in ANGLES:
        for ri in range(2, 10):
            for hi in range(0, 8):
                if ri + hi >= 10:
                    continue
                key = f"a{angle:g}-r{ri / 10:g}-h{hi / 10:g}"
                out[key] = outcome(ri / 10, hi / 10, angle)
                print(key, json.dumps(out[key]), flush=True)
    rows["map"] = out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    rows = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if "--map" in argv:
        map_(rows)
        OUT.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
        return 0
    for angle in ANGLES:
        for ratio in RATIOS:
            for h in OFFSETS:
                if h + ratio >= 1:
                    continue
                key = f"a{angle:g}-r{ratio:g}-h{h:g}"
                try:
                    asm = assembly(ratio, h, angle)
                except Exception as err:        # rejected when added (resolve)
                    rows[key] = {"rejected": getattr(err, "code", type(err).__name__)}
                    print(key, json.dumps(rows[key]), flush=True)
                    continue
                try:
                    row = measure(asm)
                except Exception as err:        # a case that can't be built is a result
                    row = {"failed": f"{type(err).__name__}: {err}",
                           "code": getattr(err, "code", None)}
                rows[key] = row
                print(key, json.dumps(row), flush=True)
    OUT.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
