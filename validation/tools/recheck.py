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
Recompute every validation case's Richardson rows and gates from its
stored ``results.json`` (task 0093), with no OpenFOAM::

    python3 -m validation.tools.recheck [case …]      # from the repository root

Each case's driver (``validation/<case>/run.py``) defines
``recheck(data) -> list[dict]`` (rows from ``validation/tools/results.row``);
this prints them as one table, like task 0089's, and exits 1 if a gate
fails.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASES = ("poiseuille", "heated_rod", "layered_conduction", "heated_pipe", "womersley",
         "stenosis", "stenosis_pulsatile", "rect_duct", "mms", "turbulent_pipe", "square_bend",
         "helical_pipe",
         "fenicsx_second_order")


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stored = _load("stored", "validation/tools/results.py")


def driver(case: str):
    return _load(f"{case}_run", f"validation/{case}/run.py")


def recheck(case: str) -> list[dict]:
    data = stored.load(ROOT / "validation" / case / "results.json")
    if data is None:
        raise FileNotFoundError(f"validation/{case}/results.json: none stored")
    rows = driver(case).recheck(data)
    rounded = sorted({lv["name"] for lv in data["levels"] if lv["precision"] != stored.FULL})
    for r in rows:
        r["case"] = case
        r["rounded"] = bool(rounded)
    return rows


def _fmt(v, spec):
    return "—" if v is None else format(v, spec)


def table(rows: list[dict]) -> str:
    lines = ["| case | quantity | status | order | gate | value | verdict |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        case = r["case"] + (" (rounded)" if r["rounded"] else "")
        lines.append(f"| {case} | {r['quantity']} | {r['status'] or '—'} | "
                     f"{_fmt(r['order'], '.2f')} | {r['gate'] or 'reported'} | "
                     f"{r['value'] or '—'} | {r['verdict'] or '—'} |")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cases", nargs="*", metavar="case", help=f"default: all of {', '.join(CASES)}")
    args = ap.parse_args(argv)
    unknown = sorted(set(args.cases) - set(CASES))
    if unknown:
        ap.error(f"unknown case(s) {', '.join(unknown)}; known: {', '.join(CASES)}")
    args.cases = args.cases or list(CASES)
    rows = [r for case in args.cases for r in recheck(case)]
    print(table(rows))
    failed = [r for r in rows if r["verdict"] == "fail"]
    for r in failed:
        print(f"FAIL {r['case']}: {r['quantity']}: {r['note']}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
