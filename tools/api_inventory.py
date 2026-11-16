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
The stable surface, generated (task 0150 step 1; decision 0042
criterion 5).  From the repository root::

    python3 tools/api_inventory.py            # write docs/api-1.0.json
    python3 tools/api_inventory.py --check    # compare, exit 1 on a change

What it lists:
- **python:** every module with an ``__all__`` whose dotted path has no
  ``_``-prefixed part; per exported name its kind, and for a function or
  class its signature (each argument's kind and default).  A class also
  lists its public methods and properties.
- **schema:** the saved description's JSON Schema (``agent.schema()``).
- **cli:** the commands, the envelope and the exit codes, from the
  manifest.
- **manifest:** its format, version and top-level keys.
- **codes:** every error, warning and notice code (``errors.CODES``).
- **not_promised:** class members that are importable but not promised
  (``NOT_PROMISED``), left out of the class entries.

``tests/test_api_inventory.py`` runs the comparison: a change to the
surface fails until the file is regenerated on purpose.  The hexmesh
version is left out, so a release doesn't change the file.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import difflib
import enum
import importlib
import importlib.util
import inspect
import json
import pkgutil
import sys
import warnings
from pathlib import Path, PurePath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "docs/api-1.0.json"
FORMAT = "hexmesh.api_inventory"

#: members that are importable but not promised (task 0150, row 10): the
#: shapes' outline protocol, for the face builders, which works in
#: radians.  Listed under "not_promised", left out of the class entries.
_OUTLINE = {"corner", "ring_corner", "corners_from", "side", "side_count", "extent",
            "max_extent", "distance", "grown", "lerp", "period"}
#: Row 11: the block-layout protocol of the junction fittings, which
#: returns internal types; and the constructors of types users get back
#: but never build (their attributes are promised).
_BLOCKS = {"layout", "skeleton", "wall"}
NOT_PROMISED = {"hexmesh.core.shape.CircleShape": _OUTLINE,
                "hexmesh.core.shape.RectShape": _OUTLINE,
                "hexmesh.core.shape.Shape": _OUTLINE,
                "hexmesh.assembly.tee.Tee": _BLOCKS,
                "hexmesh.assembly.wye.Wye": _BLOCKS,
                "hexmesh.assembly.switch.Switch": _BLOCKS,
                "hexmesh.assembly.interface.Interface": {"__init__"},
                "hexmesh.assembly.sweep.FillResult": {"__init__"}}


_PLAIN = (bool, int, float, str, type(None))


def _value(value) -> dict:
    if isinstance(value, enum.Enum):
        return {"enum": f"{type(value).__name__}.{value.name}"}
    if inspect.isclass(value):
        return {"class": f"{value.__module__}.{value.__qualname__}"}
    if isinstance(value, PurePath):                  # the same on every platform
        return {"path": value.as_posix()}
    if isinstance(value, _PLAIN):
        return {"value": value}
    if isinstance(value, (tuple, list)) and all(isinstance(v, _PLAIN) for v in value):
        return {"value": list(value)}
    if isinstance(value, dict) and all(isinstance(v, _PLAIN) for v in value.values()):
        return {"value": {str(k): v for k, v in value.items()}}
    return {"repr": repr(value)}


def _default(value):
    if value is inspect.Parameter.empty:
        return None
    if value is dataclasses.MISSING:
        return None
    return _value(value)


def signature(obj, factories: dict | None = None) -> list[dict] | None:
    """Each parameter's name, kind and default; None where Python can't
    give a signature (some builtins).  *factories*: a dataclass's
    ``default_factory`` per field, whose product is the default."""
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return None
    out = []
    for p in sig.parameters.values():
        row = {"name": p.name, "kind": p.kind.name.lower()}
        d = (_default(factories[p.name]()) if factories and p.name in factories
             else _default(p.default))
        if d is not None:
            row["default"] = d
        out.append(row)
    return out


def _class(cls) -> dict:
    factories = ({f.name: f.default_factory for f in dataclasses.fields(cls)
                  if f.default_factory is not dataclasses.MISSING}
                 if dataclasses.is_dataclass(cls) else None)
    skip = NOT_PROMISED.get(f"{cls.__module__}.{cls.__qualname__}", set())
    members = {}
    for name, attr in sorted(vars(cls).items()):
        if (name.startswith("_") and name != "__init__") or name in skip:
            continue
        if isinstance(attr, property):
            members[name] = {"kind": "property", "settable": attr.fset is not None}
        elif isinstance(attr, (staticmethod, classmethod)):
            members[name] = {"kind": type(attr).__name__,
                             "signature": signature(getattr(cls, name))}
        elif inspect.isfunction(attr):
            members[name] = {"kind": "method",
                             "signature": signature(attr, factories if name == "__init__"
                                                    else None)}
    bases = [f"{b.__module__}.{b.__qualname__}" for b in cls.__bases__
             if b is not object]
    out = {"kind": "class", "bases": bases, "members": members}
    if issubclass(cls, enum.Enum):
        out["kind"] = "enum"
        out["values"] = [m.name for m in cls]
    return out


def describe(obj) -> dict:
    if inspect.isclass(obj):
        return _class(obj)
    if inspect.ismodule(obj):
        return {"kind": "module", "module": obj.__name__}
    if callable(obj):
        return {"kind": "function", "signature": signature(obj)}
    if isinstance(obj, (bool, int, float, str)):
        return {"kind": "constant", "value": obj}
    if isinstance(obj, dict):
        return {"kind": "mapping", "keys": sorted(map(str, obj))}
    if isinstance(obj, (tuple, list, frozenset, set)):
        items = sorted(obj) if isinstance(obj, (set, frozenset)) else list(obj)
        return {"kind": type(obj).__name__, "items": [_value(v) for v in items]}
    return {"kind": type(obj).__name__}


def _has_all(path: str) -> bool:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return any(isinstance(node, (ast.Assign, ast.AnnAssign))
               and any(getattr(t, "id", None) == "__all__"
                       for t in getattr(node, "targets", [getattr(node, "target", None)]))
               for node in tree.body)


def public_modules() -> list[str]:
    """Modules with an ``__all__``, found from their source: importing a
    module only to look would change what its package exports (a
    submodule replaces a package attribute of the same name)."""
    import hexmesh
    names = ["hexmesh"] if _has_all(hexmesh.__file__) else []
    for info in pkgutil.walk_packages(hexmesh.__path__, "hexmesh."):
        if any(part.startswith("_") for part in info.name.split(".")):
            continue
        spec = importlib.util.find_spec(info.name)
        if spec and spec.origin and spec.origin.endswith(".py") and _has_all(spec.origin):
            names.append(info.name)
    return sorted(names)


def python() -> dict:
    """Each module's exports as a plain ``import`` gives them: a package is
    described before its submodules are imported (sorted order)."""
    out = {}
    for name in public_modules():
        mod = importlib.import_module(name)
        out[name] = {n: describe(getattr(mod, n)) for n in sorted(mod.__all__)}
    return out


def inventory() -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)   # a deprecated module's import
        from hexmesh import agent
        from hexmesh.agent._schema import schema   # python() imports the submodule
        from hexmesh.errors import CODES             # of the same name (task 0150 step 3)
        man = agent.manifest()
        return {
            "format": FORMAT,
            "python": python(),
            "schema": schema(),
            "cli": {"commands": man["commands"], "envelope": man["envelope"],
                    "invocation": man["invocation"]},
            "manifest": {"format": man["format"], "manifest_version": man["manifest_version"],
                         "keys": sorted(man)},
            "codes": sorted(CODES),
            "not_promised": {cls: sorted(names) for cls, names in sorted(NOT_PROMISED.items())},
        }


def dumps(data: dict) -> str:
    return json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def diff(path: Path = OUT) -> str:
    """The unified diff from the committed file to the code's surface;
    empty when they match."""
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    new = dumps(inventory())
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                        str(path.relative_to(ROOT)), "the code"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="compare with the committed file; exit 1 and print the diff on a change")
    args = ap.parse_args(argv)
    if args.check:
        d = diff()
        sys.stdout.write(d)
        return 1 if d else 0
    OUT.write_text(dumps(inventory()), encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
