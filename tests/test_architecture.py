"""
Architecture rules of DESIGN §3.1 (decision 0037; task 0081).

AST only: nothing from ``hexmesh`` is imported, and imports inside
functions count the same as module-level ones.

- **Dependency order:** ``core`` → ``sections`` → ``assembly`` →
  ``interchange`` → ``study``; each capability imports only from those to
  its left.  ``io.writers`` is a leaf for ``assembly`` and ``study``;
  ``_occ``, ``session`` and ``quality_hex`` are shared leaves;
  ``hexmesh/__init__.py`` and ``examples`` may import anything.
- **No private name crosses a package** (``_occ`` is the declared
  exception).
- **No module cycles.**  Imports under ``if TYPE_CHECKING:`` don't run,
  so they can't form one; they still count for the other rules.
- **A cap on shape-specific sites** outside ``core/shape.py`` and
  ``sections`` (see :func:`shape_sites`).  The cap only goes down.

Each check returns its violations, so the planted-violation tests at the
end run the same code on a synthetic tree.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: capabilities in dependency order (DESIGN §3.1)
ORDER = ("core", "sections", "assembly", "interchange", "study")
#: shared leaves: anyone may import them; they import only leaves
LEAVES = {"hexmesh._occ", "hexmesh.session", "hexmesh.quality_hex",
          "hexmesh.version"}            # task 0091: assembly stamps the version
#: which capabilities may import ``io.writers``
WRITERS_USERS = {"assembly", "study"}
#: may import anything
FREE = {"root", "examples"}
#: private names that may cross packages (DESIGN §3.1)
PRIVATE_OK = {"hexmesh._occ"}

#: dependency edges outside the order, each with the task that removes it
ALLOWED_EDGES = {
    ("io.readers", "interchange"): "task 0066 moves the readers into interchange.importers",
}
#: module cycles today, each with the task that removes it
ALLOWED_CYCLES: dict[frozenset, str] = {}

#: shape-specific sites outside core/shape.py and sections: 69 at task 0081
#: (RESEARCH §12's cruder grep found 89); task 0083 replaces them with a
#: shape protocol.  Only goes down.
SHAPE_SITES_CAP = 69
SHAPE_TYPES = {"CircleShape", "RectShape", "BlendShape"}
SHAPE_FIELDS = {"radius", "half_w", "half_h", "nang_w", "nang_h"}
SHAPE_VALUES = {"core_shape", "shape", "branch"}

RULE_ORDER = "DESIGN §3.1, dependency order"
RULE_PRIVATE = "DESIGN §3.1, no private name crosses a package"
RULE_CYCLE = "DESIGN §3.1, no module cycles"
RULE_SHAPES = "DESIGN §3.1, shapes and section layouts own their behaviour"


# --- the module tree -----------------------------------------------------------

def modules(root: Path) -> dict[str, Path]:
    """Dotted module name → file, for every ``.py`` under ``root/hexmesh``."""
    out = {}
    for p in sorted((root / "hexmesh").rglob("*.py")):
        parts = list(p.relative_to(root).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        out[".".join(parts)] = p
    return out


def capability(mod: str) -> str:
    """The capability a module belongs to."""
    parts = mod.split(".")
    if len(parts) == 1:
        return "root"
    top = parts[1]
    if mod in LEAVES:
        return "leaf"
    if top in ("faces", "sections"):          # faces counts as sections until task 0082
        return "sections"
    if top == "io":
        return "io.readers" if len(parts) > 2 and parts[2] == "readers" else "io.writers"
    if top in ORDER or top == "examples":
        return top
    raise AssertionError(f"{mod}: not in any capability of DESIGN §3.1; place it in "
                         "tests/test_architecture.py:capability()")


@dataclass(frozen=True)
class Import:
    module: str           # the importing module
    path: Path
    lineno: int
    target: str           # the imported module
    names: tuple          # names taken from it (empty for ``import x``)
    type_only: bool = False   # under ``if TYPE_CHECKING:``

    def where(self, root: Path) -> str:
        return f"{self.path.relative_to(root)}:{self.lineno}"


def _type_checking_nodes(tree: ast.AST) -> set[int]:
    """ids of the nodes inside ``if TYPE_CHECKING:`` bodies."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = node.test
            name = test.id if isinstance(test, ast.Name) else \
                test.attr if isinstance(test, ast.Attribute) else None
            if name == "TYPE_CHECKING":
                out |= {id(n) for stmt in node.body for n in ast.walk(stmt)}
    return out


def imports(root: Path, mods: dict[str, Path] | None = None) -> list[Import]:
    """Every import of a ``hexmesh`` module, at any depth in the file.

    ``from pkg import name`` where *name* is a submodule counts as an
    import of that submodule; otherwise it is an import of *pkg*."""
    mods = modules(root) if mods is None else mods
    out = []
    for mod, path in mods.items():
        is_pkg = path.name == "__init__.py"
        tree = ast.parse(path.read_text(), str(path))
        typing_only = _type_checking_nodes(tree)
        for node in ast.walk(tree):
            tc = id(node) in typing_only
            if isinstance(node, ast.Import):
                out += [Import(mod, path, node.lineno, a.name, (), tc)
                        for a in node.names if a.name.split(".")[0] == "hexmesh"]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = mod.split(".") if is_pkg else mod.split(".")[:-1]
                    base = base[: len(base) - node.level + 1]
                    target = ".".join(base + ([node.module] if node.module else []))
                else:
                    target = node.module or ""
                if target.split(".")[0] != "hexmesh":
                    continue
                plain = []
                for a in node.names:
                    sub = f"{target}.{a.name}"
                    if sub in mods:
                        out.append(Import(mod, path, node.lineno, sub, (), tc))
                    else:
                        plain.append(a.name)
                if plain:
                    out.append(Import(mod, path, node.lineno, target, tuple(plain), tc))
    return out


# --- the rules -----------------------------------------------------------------

def _rank(cap: str) -> int:
    # importing the root package pulls in assembly (hexmesh/__init__.py)
    return ORDER.index("assembly") if cap == "root" else ORDER.index(cap)


def order_violations(root: Path) -> list[str]:
    out = []
    for imp in imports(root):
        src, tgt = capability(imp.module), capability(imp.target)
        if src == tgt or src in FREE:
            continue
        if (src, tgt) in ALLOWED_EDGES:
            continue
        if tgt == "leaf" or (tgt == "io.writers" and src in WRITERS_USERS):
            continue
        if src in ("leaf", "io.writers", "io.readers") or tgt in ("io.writers", "io.readers", "examples"):
            ok = False
        else:
            ok = _rank(src) > _rank(tgt)
        if not ok:
            out.append(f"{imp.where(root)}: {imp.module} ({src}) imports {imp.target} ({tgt})")
    return out


def private_violations(root: Path) -> list[str]:
    out = []
    for imp in imports(root):
        if capability(imp.module) == capability(imp.target) or imp.target in PRIVATE_OK:
            continue
        private_module = any(p.startswith("_") for p in imp.target.split("."))
        names = [n for n in imp.names                      # dunders are public
                 if n.startswith("_") and not (n.startswith("__") and n.endswith("__"))]
        if private_module or names:
            what = ", ".join(names) if names else "the module"
            out.append(f"{imp.where(root)}: {imp.module} imports {what} from {imp.target}")
    return out


def cycles(root: Path) -> list[frozenset]:
    """Strongly connected components with more than one module (or a
    module importing itself), function-level imports included and
    ``TYPE_CHECKING`` ones not."""
    mods = modules(root)
    graph: dict[str, set] = {m: set() for m in mods}
    for imp in imports(root, mods):
        if imp.target in mods and not imp.type_only:
            graph[imp.module].add(imp.target)
    index, low, stack, on, out = {}, {}, [], set(), []

    def visit(v):                                   # Tarjan
        index[v] = low[v] = len(index)
        stack.append(v)
        on.add(v)
        for w in graph[v]:
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = set()
            while True:
                w = stack.pop()
                on.discard(w)
                comp.add(w)
                if w == v:
                    break
            if len(comp) > 1 or v in graph[v]:
                out.append(frozenset(comp))

    for v in sorted(graph):
        if v not in index:
            visit(v)
    return out


def _cycle_text(root: Path, comp: frozenset) -> str:
    edges = sorted({f"{imp.where(root)}: {imp.module} → {imp.target}"
                    for imp in imports(root)
                    if imp.module in comp and imp.target in comp and not imp.type_only})
    return f"{', '.join(sorted(comp))}:\n    " + "\n    ".join(edges)


def _shape_checked(mod: str) -> bool:
    cap = capability(mod)
    return mod != "hexmesh.core.shape" and cap not in ("sections", "examples")


def _ends_in_shape_value(node: ast.expr) -> bool:
    """``shape``, ``x.core_shape``, ``x.branch``, ``x.shape()`` …"""
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Name):
        return node.id in SHAPE_VALUES
    if isinstance(node, ast.Attribute):
        return node.attr in SHAPE_VALUES
    return False


def _names_shape_type(node: ast.expr) -> bool:
    elts = node.elts if isinstance(node, ast.Tuple) else [node]
    for e in elts:
        name = e.id if isinstance(e, ast.Name) else e.attr if isinstance(e, ast.Attribute) else None
        if name in SHAPE_TYPES:
            return True
    return False


def shape_sites(root: Path) -> list[str]:
    """Shape-specific sites outside ``core/shape.py``, ``sections`` (and
    ``faces``) and ``examples``.  A site is:

    - a call ``isinstance(x, T)`` or ``issubclass(x, T)`` whose *T* names
      ``CircleShape``, ``RectShape`` or ``BlendShape`` (alone or in a
      tuple; as a bare name or an attribute), or ``type(x) is T`` /
      ``type(x) == T``;
    - a read of ``.radius``, ``.half_w``, ``.half_h``, ``.nang_w`` or
      ``.nang_h`` on an expression ending in ``core_shape``, ``shape`` or
      ``branch`` (a name, an attribute, or a call of one).

    One line can hold several sites."""
    out = []
    for mod, path in modules(root).items():
        if not _shape_checked(mod):
            continue
        for node in ast.walk(ast.parse(path.read_text(), str(path))):
            where = f"{path.relative_to(root)}:{getattr(node, 'lineno', 0)}"
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ("isinstance", "issubclass") and len(node.args) == 2
                    and _names_shape_type(node.args[1])):
                out.append(f"{where}: {ast.unparse(node)}")
            elif (isinstance(node, ast.Compare) and isinstance(node.left, ast.Call)
                  and isinstance(node.left.func, ast.Name) and node.left.func.id == "type"
                  and any(isinstance(op, (ast.Is, ast.Eq)) for op in node.ops)
                  and any(_names_shape_type(c) for c in node.comparators)):
                out.append(f"{where}: {ast.unparse(node)}")
            elif (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)
                  and node.attr in SHAPE_FIELDS and _ends_in_shape_value(node.value)):
                out.append(f"{where}: {ast.unparse(node)}")
    return out


# --- the real tree -------------------------------------------------------------

def test_every_module_has_a_capability():
    for mod in modules(ROOT):
        capability(mod)


def test_dependency_order():
    bad = order_violations(ROOT)
    assert not bad, f"{RULE_ORDER} ({' → '.join(ORDER)}):\n  " + "\n  ".join(bad)


def test_no_private_name_crosses_a_package():
    bad = private_violations(ROOT)
    assert not bad, (f"{RULE_PRIVATE}; make it public in its owner:\n  " + "\n  ".join(bad))


def test_no_module_cycles():
    found = cycles(ROOT)
    new = [c for c in found if c not in ALLOWED_CYCLES]
    assert not new, f"{RULE_CYCLE}:\n  " + "\n  ".join(_cycle_text(ROOT, c) for c in new)
    gone = [c for c in ALLOWED_CYCLES if c not in found]
    assert not gone, ("cycle(s) removed; delete them from ALLOWED_CYCLES:\n  "
                      + "\n  ".join(", ".join(sorted(c)) for c in gone))


def test_allowed_edges_still_needed():
    used = {(capability(i.module), capability(i.target)) for i in imports(ROOT)}
    gone = [e for e in ALLOWED_EDGES if e not in used]
    assert not gone, f"no longer needed; delete from ALLOWED_EDGES: {gone}"


def test_shape_sites_cap():
    sites = shape_sites(ROOT)
    assert len(sites) <= SHAPE_SITES_CAP, (
        f"{RULE_SHAPES}: {len(sites)} shape-specific sites, cap {SHAPE_SITES_CAP}; "
        "ask the shape instead of switching on its type or fields:\n  " + "\n  ".join(sites))
    assert len(sites) == SHAPE_SITES_CAP, (
        f"{len(sites)} shape-specific sites: lower SHAPE_SITES_CAP to {len(sites)} "
        "(the cap only goes down)")


# --- planted violations: the same checks on a synthetic tree --------------------

def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    base = {"hexmesh/__init__.py": "", "hexmesh/_occ.py": "",
            "hexmesh/core/__init__.py": "", "hexmesh/core/shape.py": "",
            "hexmesh/sections/__init__.py": "", "hexmesh/assembly/__init__.py": "",
            "hexmesh/interchange/__init__.py": "", "hexmesh/study/__init__.py": "",
            "hexmesh/io/__init__.py": "", "hexmesh/io/writers/__init__.py": ""}
    for rel, text in {**base, **files}.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return tmp_path


@pytest.mark.parametrize("rel, text", [
    ("hexmesh/core/spec.py", "def f():\n    from ..assembly import wye\n"),       # inside a function
    ("hexmesh/assembly/wye.py", "from hexmesh.interchange import model\n"),
    ("hexmesh/sections/oh.py", "import hexmesh.study\n"),
    ("hexmesh/core/grading.py", "from ..io.writers import openfoam\n"),           # writers: assembly, study only
])
def test_planted_order_violation(tmp_path, rel, text):
    root = _tree(tmp_path, {rel: text, "hexmesh/assembly/wye.py": "",
                            "hexmesh/interchange/model.py": "",
                            "hexmesh/io/writers/openfoam.py": ""} | {rel: text})
    bad = order_violations(root)
    assert len(bad) == 1 and rel in bad[0]


def test_planted_order_allows_the_order(tmp_path):
    root = _tree(tmp_path, {
        "hexmesh/assembly/wye.py": "from ..core import shape\nfrom hexmesh import _occ\n"
                                   "from ..io.writers import openfoam\n",
        "hexmesh/study/run.py": "from hexmesh import Session\nfrom ..assembly import wye\n",
        "hexmesh/io/writers/openfoam.py": ""})
    assert order_violations(root) == []


@pytest.mark.parametrize("text", [
    "from hexmesh.assembly.wye import _IN_MARGIN\n",
    "def f():\n    from ..assembly.fittings import _with_radii\n",
    "from ..assembly._helpers import public_name\n",
])
def test_planted_private_name(tmp_path, text):
    root = _tree(tmp_path, {"hexmesh/interchange/build.py": text,
                            "hexmesh/assembly/wye.py": "", "hexmesh/assembly/fittings.py": "",
                            "hexmesh/assembly/_helpers.py": ""})
    bad = private_violations(root)
    assert len(bad) == 1 and "interchange/build.py" in bad[0]


def test_planted_private_inside_a_package_is_fine(tmp_path):
    root = _tree(tmp_path, {"hexmesh/assembly/wye.py": "from .fittings import _with_radii\n"
                                                       "from hexmesh import _occ\n"
                                                       "from hexmesh.version import __version__\n",
                            "hexmesh/assembly/fittings.py": "", "hexmesh/version.py": ""})
    assert private_violations(root) == []


def test_planted_type_checking_import_is_no_cycle(tmp_path):
    root = _tree(tmp_path, {"hexmesh/assembly/a.py": "from . import b\n",
                            "hexmesh/assembly/b.py": "from typing import TYPE_CHECKING\n"
                                                     "if TYPE_CHECKING:\n    from .a import X\n"})
    assert cycles(root) == []


def test_planted_cycle_through_a_function(tmp_path):
    root = _tree(tmp_path, {"hexmesh/assembly/a.py": "from . import b\n",
                            "hexmesh/assembly/b.py": "def f():\n    from .a import x\n",
                            "hexmesh/assembly/c.py": "from . import a\n"})
    assert cycles(root) == [frozenset({"hexmesh.assembly.a", "hexmesh.assembly.b"})]


@pytest.mark.parametrize("text, n", [
    ("isinstance(s, CircleShape)\n", 1),
    ("isinstance(s, (shape.RectShape, int))\n", 1),
    ("type(s) is BlendShape\n", 1),
    ("spec.core_shape.radius + shape.half_w + self.branch.nang_h\n", 3),
    ("spec.core_shape().half_h\n", 1),
    ("pipe.radius + isinstance(s, Straight)\n", 0),               # not a shape value / type
    ("core_shape.radius = 1\n", 0),                               # a write, not a read
])
def test_planted_shape_sites(tmp_path, text, n):
    root = _tree(tmp_path, {"hexmesh/assembly/x.py": text,
                            "hexmesh/core/shape.py": text,       # the owner: not counted
                            "hexmesh/sections/oh.py": text})
    assert len(shape_sites(root)) == n
