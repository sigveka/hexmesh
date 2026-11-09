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
Task 0062: a twisted ``Straight``'s quality against its twist per layer.

A twisted straight has a station per axial layer, each rolled by
Δθ = twist / n_layers from the one before.  A hex joins a section quad to
the same quad rolled by Δθ, Δz further on: at radius ρ it is sheared by
γ = atan(ρ Δθ / Δz).  This tool predicts each case's min corner scaled
Jacobian and max non-orthogonality from the section's quads alone (three
stations, pure numpy; ``section_quality.twist_quality``), and its
largest face warp, and meshes it to compare, over Δθ ∈ {5…40}° (45° is half a circle's period: the corners are ambiguous),
Δz / R ∈ {0.25, 0.5, 1, 2} and ``nrad`` ∈ {2, 3, 5}, at ``nang`` 8.

    python3 -m validation.tools.straight_twist       # from the repository root

Rows go to ``validation/tools/straight_twist.json``; no mesh is kept.
"""

from __future__ import annotations

import json
import math
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation" / "tools" / "straight_twist.json"

R = 0.1
TWISTS = (5, 10, 15, 20, 30, 40)          # per layer, degrees
DZ = (0.25, 0.5, 1.0, 2.0)                # layer length over R
NRADS = (2, 3, 5)
N_LAYERS = 4


def spec_for(nrad: int, shells: int = 0):
    from hexmesh.core.spec import PipeSpec
    s = PipeSpec(nang=8).core("fluid", radius=R, nrad=nrad)
    for i in range(shells):
        s = s.shell(f"s{i}", dR=0.1 * R, nrad=2)
    return s


def predicted(spec, dtheta: float, dz: float) -> tuple[float, float, float]:
    from hexmesh.assembly.section_quality import twist_quality
    return twist_quality(spec, dtheta, dz)


def meshed(spec, dtheta: float, dz: float) -> tuple[float, float, float, int]:
    import gmsh
    from hexmesh import Session
    from hexmesh.assembly import Assembly, Straight
    from hexmesh.assembly.section_quality import face_warp
    from hexmesh.quality_hex import max_non_orthogonality, min_scaled_jacobians
    asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1], lc=0.05)
    asm.add(Straight(N_LAYERS * dz, n_layers=N_LAYERS, twist=N_LAYERS * dtheta))
    with Session("twist"), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        asm.mesh()
        ntag, nx, _ = gmsh.model.mesh.getNodes()
        pos = np.full(int(ntag.max()) + 1, -1)
        pos[ntag.astype(int)] = np.arange(len(ntag))
        conn = np.vstack([n.reshape(-1, 8) for t, _, n in zip(*gmsh.model.mesh.getElements(3))
                          if t == 5])
        c = pos[conn.astype(int)]
        verts = nx.reshape(-1, 3)[c]
        return (float(min_scaled_jacobians(verts).min()),
                float(max_non_orthogonality(verts, c)), float(face_warp(verts).max()), len(c))


def main(argv=None) -> int:
    rows = {}
    for nrad in NRADS:
        spec = spec_for(nrad)
        for dz in DZ:
            for tw in TWISTS:
                key = f"nrad{nrad}-dz{dz:g}-tw{tw}"
                psj, pno, pwarp = predicted(spec, tw, dz * R)
                row = {"wall_shear_deg": round(math.degrees(math.atan(math.radians(tw) * R
                                                                       / (dz * R))), 2),
                       "predicted_min_sj": round(psj, 4), "predicted_nonorth": round(pno, 2),
                       "predicted_warp_deg": round(pwarp, 2)}
                if nrad == 3 or tw in (15, 40):
                    try:
                        msj, mno, mwarp, cells = meshed(spec, tw, dz * R)
                        row.update(meshed_min_sj=round(msj, 4), meshed_nonorth=round(mno, 2),
                                   meshed_warp_deg=round(mwarp, 2), cells=cells)
                    except Exception as err:          # a case that can't be built is a result
                        row["failed"] = f"{type(err).__name__}: {err}"[:200]
                rows[key] = row
                print(key, json.dumps(row), flush=True)
    OUT.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
