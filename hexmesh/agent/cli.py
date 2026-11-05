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
"""The ``hexmesh`` command: the agent tools as one CLI (task 0098, decision 0040).

    hexmesh schema
    hexmesh validate  NETWORK
    hexmesh estimate  NETWORK
    hexmesh describe  NETWORK
    hexmesh preview   NETWORK --out view.png
    hexmesh advise    NETWORK --inputs inputs.json
    hexmesh apply     NETWORK --table table.json
    hexmesh build     NETWORK --out mesh.msh [--order 2]

*NETWORK* is an ``Assembly`` description (``Assembly.save``, ``.json``).
A PCF file waits for task 0066 (``hexmesh.agent`` may not import
``io.readers``): build it with ``read_pcf(...).to_assembly(spec)`` and
``save()`` that.

Output: one JSON object on stdout, ``{"version", "command", "ok",
"result"}`` or ``{…, "ok": false, "error"}``, with sorted keys and
``\\n`` line endings (decision 0039), so two runs give the same bytes.
Exit code 0 when ``ok``, 1 for invalid input, 2 for a failure (an
unreachable budget, a mesh that fails).  Only ``build`` needs GMSH; it
writes the ``.msh`` with its recipe block (decision 0038).
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

from hexmesh import Assembly, HexmeshError, HexmeshWarning, __version__

EXIT_OK, EXIT_INVALID, EXIT_FAILURE = 0, 1, 2
COMMANDS = ("schema", "validate", "estimate", "describe", "preview", "advise", "apply",
            "build")


class _Failure(Exception):
    """A failure that is not the input's fault: exit code 2."""

    def __init__(self, error: dict):
        super().__init__(error.get("message"))
        self.error = error


def _read_json(path: str, what: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise HexmeshError(f"{what} {path}: {e}", code="cli_input_unreadable",
                           where={"source": {"file": str(path)}}) from None


def _network(args) -> Assembly:
    path = Path(args.network)
    if path.suffix.lower() == ".pcf":
        # hexmesh.agent may not import io.readers (DESIGN §3.1); task 0066
        # moves the readers into interchange.importers
        raise HexmeshError(f"{path}: PCF input waits for task 0066; build the assembly with "
                           "read_pcf(...).to_assembly(spec) and save() it", code=
                           "cli_input_unreadable", where={"source": {"file": str(path)}},
                           hint="pass an Assembly description (.json)")
    return Assembly.from_dict(_read_json(path, "network"))


def _validate(asm: Assembly) -> dict:
    """``{ok, errors, warnings, complete}``: ``validate()`` stops at its
    first error, so ``complete`` is false when there is one."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            asm.validate()
            errors = []
        except HexmeshError as e:
            errors = [e.to_dict()]
    found = [w.message.to_dict() if isinstance(w.message, HexmeshWarning)
             else {"code": None, "message": str(w.message)} for w in caught]
    return {"ok": not errors, "errors": errors, "warnings": found, "complete": not errors}


def _run(args) -> tuple[bool, object]:
    from hexmesh import agent
    if args.command == "schema":
        return True, agent.schema()
    if args.command == "validate":
        try:
            asm = _network(args)
        except HexmeshError as e:          # the description itself: one error, then stop
            return False, {"ok": False, "errors": [e.to_dict()], "warnings": [],
                           "complete": False}
        out = _validate(asm)
        return out["ok"], out
    asm = _network(args)
    if args.command == "estimate":
        counts = asm.cell_counts()
        return True, {"cells": sum(counts.values()), "exact": True,
                      "per_fitting": {str(i): n for i, n in sorted(counts.items())}}
    if args.command == "describe":
        return True, agent.describe(asm)
    if args.command == "preview":
        if not args.out:
            raise HexmeshError("preview needs --out PATH.png", code="cli_input_unreadable",
                               where={"field": "out"})
        agent.preview(asm, args.out)
        return True, {"path": str(args.out)}
    if args.command == "advise":
        if not args.inputs:
            raise HexmeshError("advise needs --inputs inputs.json", code="cli_input_unreadable",
                               where={"field": "inputs"})
        report = agent.advise(asm, _read_json(args.inputs, "inputs"))
        if report["error"] is not None:
            raise _Failure({**report["error"], "report": report})
        return report["ok"], report
    if args.command == "apply":
        if not args.table:
            raise HexmeshError("apply needs --table table.json", code="cli_input_unreadable",
                               where={"field": "table"})
        return True, agent.apply(asm.to_dict(), _read_json(args.table, "table"))
    if args.command == "build":
        if not args.out:
            raise HexmeshError("build needs --out PATH.msh", code="cli_input_unreadable",
                               where={"field": "out"})
        from hexmesh import Session
        with Session("hexmesh-cli"):
            asm.write(str(args.out), order=args.order)
        return True, {"path": str(args.out), "cells": asm.cell_count(), "order": args.order}
    raise AssertionError(args.command)                       # pragma: no cover


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="hexmesh", description=__doc__.strip().split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    for name in COMMANDS:
        p = sub.add_parser(name)
        if name == "schema":
            continue
        p.add_argument("network", help="an Assembly description (.json, Assembly.save)")
        if name == "advise":
            p.add_argument("--inputs", help="the advisor's inputs (JSON)")
        if name == "apply":
            p.add_argument("--table", help="a resolution table from advise (JSON)")
        if name in ("preview", "build"):
            p.add_argument("--out", help="the file to write")
        if name == "build":
            p.add_argument("--order", type=int, default=1, choices=(1, 2))
    return ap


def _emit(payload: dict) -> None:
    text = json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False,
                      default=str) + "\n"
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.flush()


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    head = {"version": __version__, "command": args.command}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")   # validate and advise report them as data
            ok, result = _run(args)
    except HexmeshError as e:
        _emit({**head, "ok": False, "error": e.to_dict()})
        return EXIT_INVALID
    except _Failure as e:
        _emit({**head, "ok": False, "error": e.error})
        return EXIT_FAILURE
    except Exception as e:                                    # noqa: BLE001
        _emit({**head, "ok": False, "error": {"code": None, "message": f"{type(e).__name__}: "
                                                                    f"{e}"}})
        return EXIT_FAILURE
    _emit({**head, "ok": ok, "result": result})
    if ok:
        return EXIT_OK
    return EXIT_INVALID if args.command == "validate" else EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())
