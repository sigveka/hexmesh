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
The package version, a shared leaf: ``hexmesh.__version__`` re-exports it,
and ``assembly`` stamps it into the meshes it writes (task 0091) without
importing the root package.
"""

from __future__ import annotations


def _version() -> str:
    """``pyproject.toml``'s version in a source checkout, else the
    installed distribution's (an editable install's metadata is only as
    fresh as its last install)."""
    import re
    from pathlib import Path
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8")
        if re.search(r'^name\s*=\s*"hexmesh"', text, re.M):
            return re.search(r'^version\s*=\s*"([^"]+)"', text, re.M).group(1)
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version("hexmesh")
    except PackageNotFoundError:
        return "unknown"


__version__ = _version()
