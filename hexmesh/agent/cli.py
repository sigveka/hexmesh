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
    hexmesh manifest                  # what all of this is: read it first (task 0102)

``hexmesh`` is the console script a ``pip install`` (``-e .`` from a
checkout) creates; ``python3 -m hexmesh.agent.cli`` is the same command
without it.

*NETWORK* is an ``Assembly`` description (``Assembly.save``, ``.json``),
or a PCF file (``.pcf``) with ``--spec SPEC.json`` (task 0066).  *SPEC*
is a ``PipeSpec`` description (``PipeSpec.to_dict``) for every part, or a
list of ``{"nominal": metres, "spec": {...}}``, one per nominal size.
``--insulation`` adds the PCF file's insulation where it says, as
``to_assembly(insulation=True)`` does (task 0114); a description carries
its own, so there it is an input error.

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

from hexmesh import Assembly, HexmeshError, HexmeshWarning, PipeSpec, __version__

from ._commands import COMMANDS, EXIT_FAILURE, EXIT_INVALID, EXIT_OK  # noqa: F401 (re-export)
from ._commands import parser as _commands_parser


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
        from hexmesh.interchange import read_pcf
        if not args.spec:
            raise HexmeshError(f"{path}: a PCF network needs --spec SPEC.json (a PipeSpec "
                               "description, or one per nominal size)",
                               code="cli_input_unreadable", where={"field": "spec"},
                               hint=f"hexmesh <command> {path} --spec SPEC.json")
        return read_pcf(path).to_assembly(_spec(_read_json(args.spec, "spec"), args.spec),
                                          insulation=args.insulation)
    if args.insulation:
        raise HexmeshError(f"{path}: --insulation is for a PCF network; a description "
                           "already says where its insulation is",
                           code="cli_input_unreadable", where={"field": "insulation"},
                           hint="add an insulation shell to the description's PipeSpec, "
                                "or drop --insulation")
    return Assembly.from_dict(_read_json(path, "network"))


def _spec(d, path: str):
    """``--spec``: a ``PipeSpec`` description, or ``[{"nominal", "spec"}, …]``
    as a callable of the nominal bore (metres, to 1e-6 relative)."""
    if isinstance(d, dict):
        return PipeSpec.from_dict(d)
    try:
        sizes = [(float(e["nominal"]), PipeSpec.from_dict(e["spec"])) for e in d]
    except (TypeError, KeyError, ValueError) as e:
        raise HexmeshError(f"spec {path}: a PipeSpec description or a list of "
                           f'{{"nominal", "spec"}}: {e}', code="cli_input_unreadable",
                           where={"source": {"file": str(path)}}) from None

    def by_bore(bore: float) -> PipeSpec:
        for nominal, spec in sizes:
            if abs(nominal - bore) <= 1e-6 * max(nominal, bore):
                return spec
        raise HexmeshError(f"spec {path} has no entry for nominal size {bore:g} m "
                           f"(it has {', '.join(f'{n:g}' for n, _ in sizes)})",
                           code="cli_spec_size_missing", where={"source": {"file": str(path)}},
                           value=bore, limit=[n for n, _ in sizes],
                           hint=f"add an entry for nominal {bore:g} to {path}")
    return by_bore


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
    if args.command == "manifest":
        return True, agent.manifest()
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
                               where={"field": "out"},
                                                               hint="hexmesh preview NETWORK --out view.png")
        agent.preview(asm, args.out)
        return True, {"path": str(args.out)}
    if args.command == "advise":
        if not args.inputs:
            raise HexmeshError("advise needs --inputs inputs.json", code="cli_input_unreadable",
                               where={"field": "inputs"},
                                                                    hint="hexmesh advise NETWORK --inputs inputs.json")
        report = agent.advise(asm, _read_json(args.inputs, "inputs"))
        if report["error"] is not None:
            raise _Failure({**report["error"], "report": report})
        return report["ok"], report
    if args.command == "apply":
        if not args.table:
            raise HexmeshError("apply needs --table table.json", code="cli_input_unreadable",
                               where={"field": "table"},
                                                                 hint="hexmesh apply NETWORK --table table.json")
        return True, agent.apply(asm.to_dict(), _read_json(args.table, "table"))
    if args.command == "build":
        if not args.out:
            raise HexmeshError("build needs --out PATH.msh", code="cli_input_unreadable",
                               where={"field": "out"},
                                                             hint="hexmesh build NETWORK --out mesh.msh")
        from hexmesh import Session
        with Session("hexmesh-cli"):
            asm.write(str(args.out), order=args.order)
        return True, {"path": str(args.out), "cells": asm.cell_count(), "order": args.order}
    raise AssertionError(args.command)                       # pragma: no cover


def _parser() -> argparse.ArgumentParser:
    return _commands_parser(__doc__.strip().split("\n\n")[0])


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
