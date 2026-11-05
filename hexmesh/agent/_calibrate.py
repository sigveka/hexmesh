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
The resolution advisor's calibration, ``calibration.json``, generated from
the committed validation results (task 0098, step 3).  Not imported at run
time: ``advise`` reads only the JSON.

    python3 -m hexmesh.agent._calibrate            # rewrite calibration.json
    python3 -m hexmesh.agent._calibrate --check    # exit 1 if it is stale

**What it measures.**  Each validated laminar case gives, per refinement
level k, the cells across the diameter (``n``) and the error in its gated
quantities.  A class's level is where the worse of them (design answer
Q1) is within the class's error:

- **coarse** ≤ 1 %, **medium** ≤ 0.3 %, **fine** ≤ 0.1 %.

The error between two measured levels follows each quantity's order
between them, so a class can sit between levels (``basis``
"interpolated").  Past the finest level it is extrapolated along the
observed order, only from a ``converging`` series (task 0089), and at
most 2× in k.  Such a class has ``"validated": false``.  Past that it is
out of range, with no counts (design answer Q2).

**The series** (design answer Q3):

- circle: ``poiseuille`` (Δp and u_max); ``n = nang + 2 nrad``, the cells
  along a diameter, with the run's ``nrad = nang / 2``;
- rectangle: the uniform H series ``h_ar{1,2,4}`` of ``rect_duct``
  (f·Re and u_c); ``n = n_short · D_h / (2 short half-side)``, the cells
  across D_h, square cells.  The graded ``hg_ar2`` series is a check, not
  a class.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_name("calibration.json")
FORMAT = "hexmesh.agent.calibration"
VERSION = 1

#: class → the largest error of its gated quantities (fraction)
CLASSES = {"coarse": 0.01, "medium": 0.003, "fine": 0.001}
#: extrapolation reaches at most this many times the finest measured k
EXTRAPOLATE_MAX = 2.0
SCOPE = ("calibrated on developed laminar flow in straight runs; bends, junctions and "
         "switches may be less accurate at the same counts")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _series(levels: list[dict], n_of, quantities: dict[str, str]) -> list[dict]:
    """One series' levels in k order: k, n, and each quantity's signed error."""
    rows = [{"k": lv["k"], "level": lv["name"], "n": n_of(lv),
             "errors": {q: lv[key] for q, key in quantities.items()}} for lv in levels]
    return sorted(rows, key=lambda r: r["k"])


def _local_orders(rows: list[dict], q: str) -> list[float | None]:
    """The order of |error| in *q* between each pair of adjacent levels."""
    out = []
    for a, b in zip(rows, rows[1:]):
        ea, eb = abs(a["errors"][q]), abs(b["errors"][q])
        out.append(math.log(ea / eb) / math.log(b["k"] / a["k"]) if ea > 0 and eb > 0 else None)
    return out


def _k_needed(e: float, k0: float, p: float | None, target: float) -> float | None:
    """The k where e·(k0/k)^p falls to *target* (k0 if already there)."""
    if e <= target:
        return k0
    if p is None or p <= 0:
        return None
    return k0 * (e / target) ** (1.0 / p)


def _classify(rows: list[dict], conv, target: float) -> dict:
    """The smallest k (and n) at which every quantity is within *target*."""
    qs = sorted(rows[0]["errors"])
    orders = {q: _local_orders(rows, q) for q in qs}
    n1 = rows[0]["n"] / rows[0]["k"]                     # n is k × n at k = 1

    def errors_at(k, i, p):
        return {q: abs(rows[i]["errors"][q]) * (rows[i]["k"] / k) ** (p[q] or 0) for q in qs}

    for i, row in enumerate(rows):
        if max(abs(row["errors"][q]) for q in qs) <= target:
            if i == 0:
                return {"k": row["k"], "n": row["n"], "validated": True,
                        "basis": f"measured at k = {row['k']:g} ({row['level']})",
                        "errors": {q: abs(row["errors"][q]) for q in qs}}
            prev = rows[i - 1]
            p = {q: orders[q][i - 1] for q in qs}
            ks = [_k_needed(abs(prev["errors"][q]), prev["k"], p[q], target) for q in qs]
            k = min(max(row["k"] if x is None else x for x in ks), row["k"])
            basis = (f"measured at k = {row['k']:g} ({row['level']})" if k == row["k"] else
                     f"interpolated between measured k = {prev['k']:g} and {row['k']:g}, "
                     f"at each quantity's order between them")
            return {"k": round(k, 4), "n": round(n1 * k, 4), "validated": True,
                    "basis": basis, "errors": errors_at(k, i - 1, p)}
    fine = rows[-1]
    rich = {q: conv.richardson(*(r["errors"][q] for r in rows[-3:])) for q in qs}
    p, ks = {}, {}
    for q in qs:
        e = abs(fine["errors"][q])
        if e <= target:
            p[q], ks[q] = orders[q][-1], fine["k"]
            continue
        if rich[q]["status"] != "converging":
            return {"validated": False, "out_of_range": True,
                    "basis": f"{q} is {rich[q]['status']} at the finest levels: "
                             "no extrapolation", "nearest": _nearest(fine)}
        # the more cautious of the Richardson order and the last levels' order
        p[q] = min(rich[q]["order"], orders[q][-1])
        ks[q] = _k_needed(e, fine["k"], p[q], target)
    k = max(ks.values())
    governing = max(ks, key=ks.get)
    if k > EXTRAPOLATE_MAX * fine["k"]:
        return {"validated": False, "out_of_range": True,
                "basis": f"needs k = {k:.3g}, past {EXTRAPOLATE_MAX:g}× the finest "
                         f"measured k = {fine['k']:g}", "nearest": _nearest(fine)}
    return {"k": round(k, 4), "n": round(n1 * k, 4), "validated": False,
            "basis": f"extrapolated at order {p[governing]:.2f} ({governing}) from "
                     f"k = {fine['k']:g}", "errors": errors_at(k, len(rows) - 1, p),
            "nearest": _nearest(fine)}


def _nearest(row: dict) -> dict:
    return {"k": row["k"], "n": row["n"], "level": row["level"],
            "errors": {q: abs(e) for q, e in row["errors"].items()}}


def _rounded(x):
    if isinstance(x, float):
        return float(f"{x:.6g}")
    if isinstance(x, dict):
        return {k: _rounded(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_rounded(v) for v in x]
    return x


def _entry(case: str, rows: list[dict], conv, quantities: dict[str, str]) -> dict:
    return {"case": case, "quantities": quantities,
            "levels": rows,
            "classes": {c: _classify(rows, conv, t) for c, t in CLASSES.items()}}


def build(root: Path = ROOT) -> dict:
    """The calibration, from ``validation/*/results.json``."""
    conv = _load("convergence", root / "validation/tools/convergence.py")
    res = _load("results", root / "validation/tools/results.py")

    pois = res.load(root / "validation/poiseuille/results.json")
    q_pipe = {"dp": "dp_err_signed", "u_max": "u_max_err_signed"}
    levels = [{**lv, "k": lv["factor"]} for lv in pois["levels"]]
    circle = _entry("poiseuille", _series(levels, lambda lv: lv["nang"] + 2 * lv["nrad"], q_pipe),
                    conv, q_pipe)
    circle.update(metric="cells along a diameter: nang + 2 nrad", nrad_per_nang=0.5)

    duct = res.load(root / "validation/rect_duct/results.json")
    q_duct = {"fRe": "fRe_err_signed", "u_c": "u_c_err_signed"}

    def n_duct(lv):
        g = duct["extra"]["exact"][str(lv["ratio"])]
        a, b = g["a"], g["b"]
        short, n_short = (b, lv["nang_h"]) if b <= a else (a, lv["nang_w"])
        return n_short * (4 * a * b / (a + b)) / (2 * short)

    def series(mesh, ratio):
        return _series([lv for lv in duct["levels"]
                        if lv.get("mesh") == mesh and lv["ratio"] == ratio], n_duct, q_duct)

    rect = {"metric": "cells across D_h: n_short · D_h / (2 · short half-side), square cells",
            "aspect": {str(r): _entry("rect_duct", series("h", r), conv, q_duct)
                       for r in (1, 2, 4)}}
    graded, uniform = series("hg", 2), series("h", 2)
    rect["checks"] = {"hg_ar2": {
        "note": "the H section graded to the wall (hg), against uniform h, a/b 2: a "
                "check, not a class (design answer Q3)",
        "levels": [{"k": g["k"], "level": g["level"],
                    "errors": {q: abs(g["errors"][q]) for q in q_duct},
                    "worse_than_uniform": max(abs(g["errors"][q]) for q in q_duct)
                    / max(abs(u["errors"][q]) for q in q_duct) - 1}
                   for g, u in zip(graded, uniform)]}}
    return _rounded({
        "format": FORMAT, "version": VERSION,
        "generated_by": "python3 -m hexmesh.agent._calibrate (task 0098)",
        "classes": {c: {"max_error": t} for c, t in CLASSES.items()},
        "rule": "the worse of the gated quantities sets the class; between measured levels "
                "at each quantity's order; past the finest only from a converging series, "
                f"at most {EXTRAPOLATE_MAX:g}× in k, and then not validated",
        "regime": "laminar",
        "scope": SCOPE,
        "shapes": {"circle": circle, "rect": rect},
    })


def dumps(data: dict) -> str:
    return json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if calibration.json differs from what the results give")
    args = ap.parse_args(argv)
    text = dumps(build())
    if args.check:
        same = OUT.read_text(encoding="utf-8") == text
        print("calibration.json is current" if same else "calibration.json is stale")
        return 0 if same else 1
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
