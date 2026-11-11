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
Task 0116: the wye redesign, measured (decision 0043, measure first).

Each case is a junction between plain ``Straight`` runs, measured at
``nang`` 8, single layer and with one shell (0.1 R), against the gates
fixed in decision 0043:
- no inverted cells (predicted and meshed);
- min corner SJ ≥ 0.3 for no warning, ≥ 0.1 to build at all;
- crease chord error ≤ 1 % R;
- ports class-0 against a plain ``Straight``.

Reported, not gated: min SICN, max NES, the worst cells' block, the
projector's largest move, and the worst non-orthogonality, predicted
(task 0104) and meshed.

Crease chord error (as task 0056): the largest distance from the intended
wall (the tube union) of the wall quads' centres and edge midpoints, in
units of the inlet radius R.  A sample is on a crease when its second
nearest tube surface is within ``BAND`` R: the **mitre** where the inlet
tube meets a daughter's, the **crotch** where the daughters' meet.
Everything else is the rest of the wall.

    python3 -m validation.tools.wye_redesign      # from the repository root

Task 0118 adds the oriented junction cube (``K*`` cases,
``hexmesh.assembly._cube_probe``; RESEARCH §4.3): the same cases and
gates, with each case's cube orientation, its stations and the predicted
SJ over the layout's two shape parameters (the best is meshed).

Rows go to ``validation/tools/wye_redesign.json``; no mesh is kept.
"""

from __future__ import annotations

import json
import math
import sys
import time
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation" / "tools" / "wye_redesign.json"

R = 0.1                 # inlet radius
NANG = 8
NRAD = 3
SHELL = 0.1 * R         # one shell's thickness
BAND = 0.1              # crease band, × R
RUN, BRANCH, STRAIGHT = 0.4, 0.7, 0.2


def spec(radius=R, shell=False):
    from hexmesh.core.spec import PipeSpec
    s = PipeSpec(nang=NANG).core("fluid", radius=radius, nrad=NRAD)
    return s.shell("steel", dR=SHELL, nrad=2) if shell else s


def junction_assembly(fitting, inlet_spec, names):
    """Straight → *fitting* → Straight on every outlet."""
    from hexmesh.assembly import Assembly, Straight
    asm = Assembly(inlet_spec, direction=[1, 0, 0], up=[0, 0, 1], lc=0.05)
    asm.add(Straight(STRAIGHT, n_layers=4))
    outs = asm.add(fitting, names=names)
    for o in outs:
        asm.add(o, Straight(STRAIGHT, n_layers=4))
    return asm


def _hexes(vols):
    import gmsh
    tags, conn = [], []
    for v in vols:
        for t, et, n in zip(*gmsh.model.mesh.getElements(3, v)):
            if t == 5:
                tags.append(et)
                conn.append(n.reshape(-1, 8))
    return np.concatenate(tags), np.vstack(conn).astype(int)


def _quads(surfs):
    import gmsh
    out = []
    for s in surfs:
        for t, _, n in zip(*gmsh.model.mesh.getElements(2, s)):
            if t == 3:
                out.append(n.reshape(-1, 4))
    return np.vstack(out).astype(int) if out else np.empty((0, 4), int)


def chord_errors(wall, quads_xyz) -> dict:
    """Mitre, crotch and rest-of-wall chord errors (× R) of the wall
    quads (n, 4, 3) against the tube union *wall* (tube 0 the inlet)."""
    mids = 0.5 * (quads_xyz + np.roll(quads_xyz, -1, axis=1))
    pts = np.vstack([quads_xyz.mean(axis=1), mids.reshape(-1, 3)])
    f = np.stack([t.distance(pts) - t.radius for t in wall.tubes], axis=1)   # (n, m)
    err = np.abs(wall.signed_distance(pts)) / R
    order = np.argsort(f, axis=1)
    second = np.take_along_axis(f, order[:, 1:2], axis=1)[:, 0]
    on_crease = second < BAND * R
    pair = np.sort(order[:, :2], axis=1)
    mitre = on_crease & (pair[:, 0] == 0)
    crotch = on_crease & (pair[:, 0] > 0)
    worst = lambda m: float(err[m].max()) if m.any() else None
    return {"mitre": worst(mitre), "crotch": worst(crotch), "rest": worst(~on_crease)}


def measure(asm, kind=("Wye", "WyeProbe", "CubeProbe"), names=None) -> dict:
    """Every gate's and report's number for the junction in *asm*;
    *names* the block names for "where" (the wye's by default)."""
    import gmsh
    from hexmesh import Session
    from hexmesh.assembly.junction_quality import WYE_BLOCKS, _where
    WYE_BLOCKS = names or WYE_BLOCKS
    from hexmesh.assembly.signature import classify, signature
    from hexmesh.quality_hex import max_non_orthogonality, min_scaled_jacobians, nes
    e = next(x for x in asm._edges if type(x.fitting).__name__ in kind)
    frames, inlet = [p.frame for p in e.ports], e.ports[0].spec
    out_specs = [s for _, s in e.fitting.ports(frames[0], inlet)]
    row = {"ports_class0": all(classify(signature(s), signature(s)).cls == 0
                               and s.to_dict() == p.spec.to_dict()
                               for s, p in zip(out_specs, e.ports[1:]))}
    t0 = time.perf_counter()
    lay = e.fitting.layout(frames, inlet)
    row["predicted_min_sj"] = float(lay.validate()["min_corner_sj"])
    angle, b = lay.predicted_nonorth()
    stations = frozenset(v[0] if isinstance(v, tuple) else str(v) for v in lay.blocks[b][0])
    row["predicted_nonorth"] = round(float(angle), 2)
    row["predicted_nonorth_where"] = _where(stations, WYE_BLOCKS)
    pv, _, pb = lay.cells()
    centres = pv.mean(axis=1)
    with Session("wye-redesign"), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        asm.mesh()
        ntag, nx, _ = gmsh.model.mesh.getNodes()
        pos = np.full(int(ntag.max()) + 1, -1)
        pos[ntag.astype(int)] = np.arange(len(ntag))
        nx = nx.reshape(-1, 3)
        tags, conn = _hexes(asm._fitting_volumes[e.index])
        c = pos[conn]
        verts = nx[c]
        sj = min_scaled_jacobians(verts)
        sicn = np.asarray(gmsh.model.mesh.getElementQualities(tags.tolist(), "minSICN"))
        def where(k):
            b = int(pb[np.linalg.norm(centres - verts[k].mean(axis=0), axis=1).argmin()])
            return b, _where(frozenset(v[0] if isinstance(v, tuple) else str(v)
                                       for v in lay.blocks[b][0]), WYE_BLOCKS)
        k = int(sj.argmin())
        row.update({
            "cells": int(len(c)),
            "inverted": int((sj <= 0).sum()),
            "meshed_min_sj": float(sj.min()),
            "meshed_min_sj_where": where(k)[1],
            "inverted_where": sorted({f"block {b}: {name}" for b, name in
                                      map(where, np.flatnonzero(sj <= 0))}),
            "meshed_min_sicn": float(sicn.min()),
            "meshed_max_nes": float(max(nes(v) for v in verts)),
            "meshed_nonorth": round(max_non_orthogonality(verts, c), 2),
        })
        walls = [s for tags_ in asm._fitting_walls[e.index].values() for s in tags_]
        q = pos[_quads(walls)]
        wall = e.fitting.wall(frames[0], inlet)
        # the outer wall only: shell boundaries are offsets, measured alike
        outer = wall if not inlet.shells else e.fitting.wall(
            frames[0], inlet, radius=inlet.outlines[-1].radius)
        row["chord"] = chord_errors(outer, nx[q]) if len(q) else None
        rep = asm.projection_report.get(e.name)
        row["projector_move_R"] = float(rep["move"]) / R if rep else None
    row["seconds"] = round(time.perf_counter() - t0, 1)
    return row


def measure_folded(asm, names=None) -> dict:
    """A case whose wall projection folds cells: measured with
    ``mesh()``'s fold check passed (only here), so the folds are counted
    and located in the projected mesh."""
    from unittest import mock
    from hexmesh.assembly import _checks        # mesh()'s cell checks (task 0136)
    real = _checks.min_scaled_jacobians
    with mock.patch.object(_checks, "min_scaled_jacobians",
                           lambda v: np.abs(real(v)) + 1e-12):
        row = measure(asm, names=names)
    row["fold_check_bypassed"] = True
    return row


def gates(row: dict) -> dict:
    """Each gate: pass, or the miss and by how much."""
    worst_chord = max((v for v in (row.get("chord") or {}).values() if v is not None),
                      default=None)
    sj = min(row["predicted_min_sj"], row["meshed_min_sj"])
    return {
        "no_inverted": row["inverted"] == 0 and row["predicted_min_sj"] > 0,
        "sj_no_warning": sj >= 0.3,
        "sj_builds": sj >= 0.1,
        "chord_1pct": worst_chord is not None and worst_chord <= 0.01,
        "ports_class0": row["ports_class0"],
        "min_sj": sj,
        "worst_chord_R": worst_chord,
    }


def control(shell: bool, angle=60):
    """Today's symmetric wye (60°: the task's control), r = R."""
    from hexmesh.assembly import Wye
    return junction_assembly(Wye(angle, run_length=RUN, branch_length=BRANCH),
                             spec(shell=shell), ["left", "right"])


def probe(theta_left, theta_right, ratio=1.0, inlet_station=None):
    """Route A: the hub generalised (``hexmesh.assembly._wye_probe``)."""
    def build(shell: bool):
        from hexmesh.assembly._wye_probe import WyeProbe
        return junction_assembly(
            WyeProbe(run_length=RUN, branch_length=BRANCH, theta_left=theta_left,
                     theta_right=theta_right, r_left=ratio, r_right=ratio,
                     inlet_station=inlet_station), spec(shell=shell), ["left", "right"])
    return build


# The cube's blocks by their stations (task 0118), most specific first.
CUBE_BLOCKS = [(frozenset({"F", "C", "S" + p}), f"the {w} port's ring")
               for p, w in (("A", "inlet"), ("L", "left"), ("R", "right"))] + [
    (frozenset({"C", "S" + p}), f"the {w} port's shell")
    for p, w in (("A", "inlet"), ("L", "left"), ("R", "right"))] + [
    (frozenset({"F", "S" + p}), f"the {w} port's column")
    for p, w in (("A", "inlet"), ("L", "left"), ("R", "right"))] + [
    (frozenset({p, "S" + p}), f"the {w} run")
    for p, w in (("A", "inlet"), ("L", "left"), ("R", "right"))] + [
    (frozenset({"F", "C"}), "a wall side"), (frozenset({"C"}), "a wall side's shell"),
    (frozenset({"F"}), "the centre hex")]

HUBS = (0.3, 0.4, 0.5, 0.6)          # the cube's two shape parameters, tuned by
STATIONS = (0.25, 0.5, 1.0, 2.0, 3.0)   # predicted SJ (pure); the best is meshed


def cube(theta_left, theta_right, ratio=1.0):
    """The oriented cube (``hexmesh.assembly._cube_probe``), its shape
    parameters tuned per case by the predicted min corner SJ."""
    def build(shell: bool, hub=None, station=None):
        from hexmesh.assembly._cube_probe import CubeProbe
        kw = dict(run_length=RUN, branch_length=BRANCH, theta_left=theta_left,
                  theta_right=theta_right, r_left=ratio, r_right=ratio)
        if hub is None:
            best = None
            for h in HUBS:
                for s in STATIONS:
                    try:
                        asm = junction_assembly(CubeProbe(hub=h, station=s, **kw),
                                                spec(shell=shell), ["left", "right"])
                        e = asm.edges[1]
                        sj = e.fitting.layout([p.frame for p in e.ports],
                                              e.ports[0].spec).validate()["min_corner_sj"]
                    except Exception:
                        continue
                    if best is None or sj > best[0]:
                        best = (sj, h, s)
            _, hub, station = best
        return junction_assembly(CubeProbe(hub=hub, station=station, **kw),
                                 spec(shell=shell), ["left", "right"])
    build.cube = True
    return build


def cube_report(asm) -> dict:
    """The cube's orientation and stations, and its tuning grid."""
    e = next(x for x in asm._edges if type(x.fitting).__name__ == "CubeProbe")
    f, inlet = e.fitting, e.ports[0].frame
    E, sides, align = f.cube(inlet)
    o, rays = f.rays(inlet)
    start = np.array([inlet.normal, inlet.right, inlet.up])
    Rm = E.T @ start                    # cube axes = Rm · inlet frame
    angle = math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(Rm) - 1) / 2))))
    lay = f.layout([p.frame for p in e.ports], e.ports[0].spec)
    st = {p: float((np.mean([lay.coords[("S" + p, 1, k)] for k in range(4)], axis=0) - o)
                   @ rays[p]) / R for p in "ALR"}
    names = {"A": "inlet", "L": "left", "R": "right"}
    axes = {(0, 1): "+e1", (0, -1): "-e1", (1, 1): "+e2", (1, -1): "-e2", (2, 1): "+e3",
            (2, -1): "-e3"}
    return {"hub": f.hub, "station": f.station,
            "rotation_from_inlet_frame_deg": round(angle, 3),
            "sides": {names[p]: axes[sides[p]] for p in "ALR"},
            "pipe_to_side_plane_deg": {names[p]: round(math.degrees(math.asin(min(1.0, align[p]))), 3)
                                       for p in "ALR"},
            "stations_R": {names[p]: round(st[p], 4) for p in "ALR"}}


CASES = {
    "control-60": control,                            # today's Wye
    # references, not gated: today's wye at the included angles of A1, A2
    "ref-wye-45": lambda shell: control(shell, 45),
    "ref-wye-90": lambda shell: control(shell, 90),
    "A-control-60": probe(30, 30),                    # the probe's path: must match it
    "A1-equal-tee": probe(0, 90),                     # default inlet station: tan 90°
    "A1-equal-tee-station": probe(0, 90, inlet_station=math.tan(math.pi / 4) + 0.1),
    "A2-equal-lateral-45": probe(0, 45),
    # sensitivity: the symmetric 45° wye's station distance, R (tan 22.5° + 0.1)
    "A2-equal-lateral-45-station": probe(0, 45, inlet_station=math.tan(math.pi / 8) + 0.1),
    "A3-unequal-60": probe(30, 30, ratio=1 / math.sqrt(2)),
    # task 0118: the oriented junction cube on the same cases
    "K-control-60": cube(30, 30),
    "K1-equal-tee": cube(0, 90),
    "K2-equal-lateral-45": cube(0, 45),
    "K3-unequal-60": cube(30, 30, ratio=1 / math.sqrt(2)),
}


def main(argv=None) -> int:
    rows = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    names = argv or sorted(CASES)
    for name in names:
        for shell in (False, True):
            key = f"{name}{'-shell' if shell else ''}"
            is_cube = getattr(CASES[name], "cube", False)
            try:
                asm = CASES[name](shell)
                row = measure(asm, names=CUBE_BLOCKS if is_cube else None)
                if is_cube:
                    row["cube"] = cube_report(asm)
            except Exception as err:          # a case that can't be built is a result
                row = {"failed": f"{type(err).__name__}: {err}"}
                if getattr(err, "code", None) == "wall_projection_folded":
                    asm = CASES[name](shell)
                    row.update(measure_folded(asm, names=CUBE_BLOCKS if is_cube else None))
                    if is_cube:
                        row["cube"] = cube_report(asm)
            if "inverted" in row:
                row["gates"] = gates(row)
            rows[key] = row
            print(key, json.dumps(row), flush=True)
            OUT.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
