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
Where each case lives (decision 0057, task 0182): a validation case in
``validation/<case>/``, named by its directory; an export check in
``validation/exports/<consumer>/``, named by its ``case.json``'s
``name``::

    cases = _load("cases", "validation/tools/cases.py")   # validation/ is no package
    cases.path("fenicsx_second_order")     # ROOT / "validation/exports/fenicsx"
    cases.names("export")                  # ["fenicsx_second_order"]
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "validation"
EXPORTS = VALIDATION / "exports"
KINDS = ("validation", "export")


def _meta(d: Path) -> dict:
    return json.loads((d / "case.json").read_text(encoding="utf-8"))


def found(root: Path = ROOT) -> dict[str, Path]:
    """Case name → directory: every directory with a ``case.json`` or a
    ``run.py``, validation cases first, each kind by name."""
    val, exp = root / "validation", root / "validation" / "exports"
    out = {d.name: d for d in sorted({p.parent for pat in ("*/case.json", "*/run.py")
                                      for p in val.glob(pat)}) if d != exp}
    for d in sorted({p.parent for pat in ("*/case.json", "*/run.py") for p in exp.glob(pat)}):
        out[_meta(d).get("name", d.name) if (d / "case.json").exists() else d.name] = d
    return out


def path(name: str, root: Path = ROOT) -> Path:
    """The directory of case *name*; ``validation/<name>`` if there is none
    (so a missing file is named where a validation case would have it)."""
    return found(root).get(name, root / "validation" / name)


def rel(name: str, root: Path = ROOT) -> str:
    """``validation/<name>`` or ``validation/exports/<consumer>``."""
    return path(name, root).relative_to(root).as_posix()


def kind(name: str, root: Path = ROOT) -> str:
    """``"export"`` for an export check, else ``"validation"``."""
    d = path(name, root)
    return _meta(d).get("kind", "validation") if (d / "case.json").exists() else "validation"


def names(of: str | None = None, root: Path = ROOT) -> list[str]:
    """Every case's name, or those of one kind (validation first)."""
    return [n for n in found(root) if of is None or kind(n, root) == of]
