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
The validation summary that ``hexmesh.agent.manifest()`` reports (task
0102), generated from every case's ``case.json`` and ``results.json``
into package data, ``hexmesh/agent/validation.json``::

    python3 -m validation.tools.summary            # from the repository root

``tests/test_agent_manifest.py`` regenerates it and fails, naming this
command, when the committed file differs.  The installed package has no
``validation/`` directory, so the manifest reads the committed copy.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "hexmesh" / "agent" / "validation.json"
FORMAT = "hexmesh.agent.validation"

_spec = importlib.util.spec_from_file_location("cases", ROOT / "validation/tools/cases.py")
where = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(where)


def _case(name: str, path: Path) -> tuple[dict, list]:
    meta = json.loads((path / "case.json").read_text(encoding="utf-8"))
    out = {"case": name, "title": meta["title"], "status": meta["status"],
           "task": meta.get("task")}
    if meta.get("kind") == "export":
        out.update(format=meta["format"], consumer=meta["consumer"], checks=meta["checks"],
                   features=meta["tags"].get("features", []))
    else:
        out.update(category=meta["category"],
                   gates=[{"quantity": g["quantity"], "limit": g["limit"]}
                          for g in meta["gates"]])
    results = path / "results.json"
    if results.exists():
        levels = json.loads(results.read_text(encoding="utf-8"))["levels"]
        cells = [lv["cells"] for lv in levels if isinstance(lv.get("cells"), int)]
        out["levels"] = len(levels)
        out["cells"] = [min(cells), max(cells)] if cells else None
    else:
        out["levels"], out["cells"] = 0, None
    return out, meta["tags"].get("features", [])


def summary() -> dict:
    """``{format, version, cases, features, exports}``: every validation
    case, per feature tag the validation cases that cover it, by name, in
    order, and every export check apart (decision 0057, task 0182)."""
    cases, features, exports = {}, {}, {}
    for name, path in sorted(where.found(ROOT).items()):
        if not (path / "case.json").exists():
            continue
        case, tags = _case(name, path)
        if "consumer" in case:
            exports[name] = case
            continue
        cases[name] = case
        for tag in tags:
            features.setdefault(tag, []).append(name)
    return {"format": FORMAT, "version": 1,
            "generated_by": "python3 -m validation.tools.summary (tasks 0102, 0182)",
            "cases": cases, "features": dict(sorted(features.items())), "exports": exports}


def dumps(data: dict) -> str:
    return json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False,
                      allow_nan=False) + "\n"


def main() -> int:
    OUT.write_text(dumps(summary()), encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
