"""
Build-time benchmark (decision 0020, task 0036).  Not part of the test suite.

    python3 benchmarks/build_time.py                 # default sizes
    python3 benchmarks/build_time.py --pairs 4 16 64 --json out.json

Builds serpentines of ``Straight`` + ``Bend(180)`` pairs of growing size and
records, per network: volumes, surfaces, cells, ``occ.synchronize`` calls,
and wall time per phase (faces, fill, physical groups, constraints +
``generate``).  Fits the growth exponent of the total time against the
volume count (least squares on log–log).  Run it on an idle machine
(CLAUDE.md, shared machine): timings under contention are not comparable.
"""

from __future__ import annotations

import argparse
import json
import math
import time

import gmsh
import numpy as np

from hexmesh import Assembly, Bend, PipeSpec, Straight

SPEC = PipeSpec(nang=4).core("fluid", radius=0.05, nrad=3)


def network(pairs: int) -> Assembly:
    """*pairs* × (Straight, Bend 180°), alternating the turn side."""
    asm = Assembly(SPEC, direction=[1, 0, 0], up=[0, 0, 1])
    for k in range(pairs):
        asm.add(Straight(0.4, n_layers=4))
        asm.add(Bend(radius=0.1, angle=180, n_layers=6, roll=0 if k % 2 else 180))
    return asm


class _Timer:
    """Wraps a callable, accumulating calls and wall time."""

    def __init__(self, owner, name):
        self.owner, self.name = owner, name
        self.orig = getattr(owner, name)
        self.calls, self.seconds = 0, 0.0

        def wrapped(*a, **kw):
            t = time.perf_counter()
            try:
                return self.orig(*a, **kw)
            finally:
                self.calls += 1
                self.seconds += time.perf_counter() - t
        setattr(owner, name, wrapped)

    def restore(self):
        setattr(self.owner, self.name, self.orig)


def measure(pairs: int) -> dict:
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 0)
    try:
        asm = network(pairs)
        cells = asm.cell_count()
        sync = _Timer(gmsh.model.occ, "synchronize")
        groups = _Timer(Assembly, "write_physical_groups")
        generate = _Timer(gmsh.model.mesh, "generate")
        try:
            t0 = time.perf_counter()
            asm.build_faces()
            t1 = time.perf_counter()
            asm.fill()
            t2 = time.perf_counter()
            asm.mesh()
            t3 = time.perf_counter()
        finally:
            for t in (sync, groups, generate):
                t.restore()
        meshed = sum(len(t) for t in gmsh.model.mesh.getElements(3)[1])
        assert meshed == cells, (meshed, cells)
        return {
            "pairs": pairs, "fittings": 2 * pairs,
            "volumes": len(gmsh.model.getEntities(3)),
            "surfaces": len(gmsh.model.getEntities(2)),
            "cells": cells,
            "sync_calls": sync.calls, "sync_s": sync.seconds,
            "faces_s": t1 - t0, "fill_s": t2 - t1,
            "groups_s": groups.seconds,
            "constraints_generate_s": t3 - t2 - groups.seconds,
            "generate_s": generate.seconds,
            "total_s": t3 - t0,
        }
    finally:
        gmsh.finalize()


def exponent(rows: list[dict], key: str = "total_s") -> float:
    x = np.log([r["volumes"] for r in rows])
    y = np.log([r[key] for r in rows])
    return float(np.polyfit(x, y, 1)[0])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pairs", type=int, nargs="+", default=[2, 4, 8, 16, 32])
    ap.add_argument("--json", help="write the rows and exponents here")
    args = ap.parse_args(argv)
    rows = []
    head = (f"{'pairs':>5} {'vols':>5} {'surfs':>6} {'cells':>7} {'syncs':>6} "
            f"{'sync s':>7} {'faces s':>7} {'fill s':>7} {'groups s':>8} "
            f"{'gen s':>6} {'total s':>7}")
    print(head, flush=True)
    for p in args.pairs:
        r = measure(p)
        rows.append(r)
        print(f"{r['pairs']:5d} {r['volumes']:5d} {r['surfaces']:6d} {r['cells']:7d} "
              f"{r['sync_calls']:6d} {r['sync_s']:7.2f} {r['faces_s']:7.2f} "
              f"{r['fill_s']:7.2f} {r['groups_s']:8.2f} {r['generate_s']:6.2f} "
              f"{r['total_s']:7.2f}", flush=True)
    result = {"rows": rows}
    if len(rows) >= 2:
        result["exponent_total"] = exponent(rows)
        result["exponent_sync"] = exponent(rows, "sync_s")
        tail = rows[len(rows) // 2:]
        result["exponent_total_upper_half"] = exponent(tail) if len(tail) >= 2 else None
        print(f"growth exponent (total vs volumes): {result['exponent_total']:.2f}"
              f"  (upper half: {result['exponent_total_upper_half'] or math.nan:.2f};"
              f" sync only: {result['exponent_sync']:.2f})")
    if args.json:
        with open(args.json, "w") as f:
            json.dump(result, f, indent=1)
    return result


if __name__ == "__main__":
    main()
