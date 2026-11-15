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
Check the built wheel and sdist before they go on a GitHub release
(task 0149; the ``release`` workflow).  From the repository root::

    python -m build                                # dist/: the wheel and the sdist
    python3 tools/check_dist.py dist --tag v0.7.0

It refuses, and says why, unless ``dist`` holds exactly one pure-Python
wheel and one sdist, and:
- both carry the tag's version (``v0.7.0`` → ``0.7.0``);
- the wheel holds only ``hexmesh/`` and its ``.dist-info``: no tests, no
  ``docs/``;
- the wheel holds every non-Python file git tracks under ``hexmesh/``
  (the package data: ``hexmesh/agent/support.json`` and the others);
- the wheel declares the ``hexmesh`` and ``hexmesh-study`` commands.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ("hexmesh", "hexmesh-study")


def package_data(root: Path = ROOT) -> list[str]:
    """The non-Python files git tracks under ``hexmesh/``."""
    out = subprocess.run(["git", "ls-files", "hexmesh"], cwd=root, check=True,
                         capture_output=True, text=True).stdout
    return sorted(p for p in out.splitlines() if not p.endswith(".py"))


def problems(dist: Path, tag: str, data: list[str]) -> list[str]:
    """What is wrong with ``dist`` for *tag*; empty when nothing is."""
    version = tag.removeprefix("v")
    wheels, sdists = sorted(dist.glob("*.whl")), sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        return [f"{dist}: expected one wheel and one sdist, found "
                f"{[p.name for p in wheels + sdists]}"]
    wheel, sdist = wheels[0], sdists[0]
    found = []
    if wheel.name != f"hexmesh-{version}-py3-none-any.whl":
        found.append(f"{wheel.name}: not hexmesh-{version}-py3-none-any.whl "
                     f"(the tag's version, pure Python)")
    if sdist.name != f"hexmesh-{version}.tar.gz":
        found.append(f"{sdist.name}: not hexmesh-{version}.tar.gz (the tag's version)")
    with zipfile.ZipFile(wheel) as z:
        names = z.namelist()
        infos = {n.split("/")[0] for n in names if n.split("/")[0].endswith(".dist-info")}
        info = infos.pop() if len(infos) == 1 else f"hexmesh-{version}.dist-info"
        meta = (Parser().parsestr(z.read(f"{info}/METADATA").decode("utf-8"))
                if f"{info}/METADATA" in names else {})
        entry = (z.read(f"{info}/entry_points.txt").decode("utf-8")
                 if f"{info}/entry_points.txt" in names else "")
    if meta.get("Version") != version:
        found.append(f"{wheel.name}: METADATA version {meta.get('Version')!r}, "
                     f"the tag says {version!r}")
    stray = sorted({n.split("/")[0] for n in names} - {"hexmesh", info})
    if stray:
        found.append(f"{wheel.name}: holds {stray} besides hexmesh/ and {info}/")
    missing = [p for p in data if p not in names]
    if missing:
        found.append(f"{wheel.name}: package data missing: {missing}")
    for command in COMMANDS:
        if f"\n{command} = " not in f"\n{entry}":
            found.append(f"{wheel.name}: no {command!r} command in entry_points.txt")
    with tarfile.open(sdist) as t:
        top = {n.split("/")[0] for n in t.getnames()}
    if top != {f"hexmesh-{version}"}:
        found.append(f"{sdist.name}: top directory {sorted(top)}, "
                     f"expected hexmesh-{version}/")
    return found


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("dist", type=Path, help="the directory python -m build wrote")
    ap.add_argument("--tag", required=True, help="the release tag, vX.Y.Z")
    args = ap.parse_args(argv)
    found = problems(args.dist, args.tag, package_data())
    for line in found:
        print(f"check_dist: {line}", file=sys.stderr)
    if not found:
        print(f"check_dist: {args.dist} is ready for {args.tag}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
