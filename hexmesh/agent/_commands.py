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
"""The ``hexmesh`` command's table: its subcommands, their arguments and
results, and the exit codes (task 0102).  A leaf: ``cli`` runs the
commands and ``_manifest`` reports them, both from here.
"""

from __future__ import annotations

import argparse

EXIT_OK, EXIT_INVALID, EXIT_FAILURE = 0, 1, 2
COMMANDS = ("manifest", "schema", "validate", "estimate", "describe", "preview", "advise",
            "apply", "build")
#: Each command's ``result`` (the manifest's ``commands``).
RESULTS = {
    "manifest": "the manifest: commands, workflow, support, limits, errors, advise, "
                "validation, conventions",
    "schema": "the JSON Schema (draft 2020-12) of an Assembly description",
    "validate": "{ok, errors, warnings, notices, complete}; complete is false when validation "
                "stopped at its first error; notices are facts, not faults (elements hexmesh "
                "writes, decision 0046)",
    "estimate": "{cells, exact, per_fitting}: the exact cell count, per fitting index",
    "describe": "describe(): fittings, ports, materials, bounds, cells",
    "preview": "{path}: the PNG written (--out)",
    "advise": "the advisor's report: {ok, table, error, notes, …}; the table goes to apply",
    "apply": "the description with the resolution table written in",
    "build": "{path, cells, order, corrections}: the .msh written, with its recipe block; "
             "corrections, per fitting, what hexmesh changed in gmsh's mesh (decision 0046)",
}
NEEDS_GMSH = ("build",)


def parser(description: str = "") -> argparse.ArgumentParser:
    """The ``hexmesh`` argument parser: one subcommand per :data:`COMMANDS`."""
    ap = argparse.ArgumentParser(prog="hexmesh", description=description)
    sub = ap.add_subparsers(dest="command", required=True)
    for name in COMMANDS:
        p = sub.add_parser(name)
        if name in ("manifest", "schema"):
            continue
        p.add_argument("network", help="an Assembly description (.json, Assembly.save), "
                                       "or a PCF file (.pcf) with --spec")
        p.add_argument("--spec", help="for a .pcf network: a PipeSpec description, or a "
                                      'list of {"nominal", "spec"} (JSON)')
        p.add_argument("--insulation", action="store_true",
                       help="for a .pcf network: add the file's insulation where it says "
                            "(to_assembly(insulation=True))")
        if name == "advise":
            p.add_argument("--inputs", help="the advisor's inputs (JSON)")
        if name == "apply":
            p.add_argument("--table", help="a resolution table from advise (JSON)")
        if name in ("preview", "build"):
            p.add_argument("--out", help="the file to write")
        if name == "build":
            p.add_argument("--order", type=int, default=1, choices=(1, 2))
    return ap
