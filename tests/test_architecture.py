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
- **Text I/O names its encoding** (decision 0039; task 0092): every text
  ``open``, ``read_text`` and ``write_text`` in ``hexmesh/`` passes
  ``encoding=`` (see :func:`encoding_violations`).
- **Every error is coded** (decision 0040; task 0094): each construction
  of a ``HexmeshError`` or ``HexmeshWarning`` class passes ``code=`` as a
  string literal registered in ``hexmesh.errors.CODES``, and every
  registered code is used (see :func:`code_violations`).

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
          "hexmesh.version",            # task 0091: assembly stamps the version
          "hexmesh.errors"}             # task 0094: every layer's error classes
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
#: (RESEARCH §12's cruder grep found 89), 59 at task 0082 (the face
#: dispatch, corner 0 and side counts moved into sections), 15 at task
#: 0083 (the shape protocol; all 15 in tee.py, left for the tee split,
#: task 0060).  Only goes down.
SHAPE_SITES_CAP = 7
SHAPE_TYPES = {"CircleShape", "RectShape", "BlendShape"}
SHAPE_FIELDS = {"radius", "half_w", "half_h", "nang_w", "nang_h"}
SHAPE_VALUES = {"core_shape", "shape", "branch"}

RULE_ORDER = "DESIGN §3.1, dependency order"
RULE_PRIVATE = "DESIGN §3.1, no private name crosses a package"
RULE_CYCLE = "DESIGN §3.1, no module cycles"
RULE_SHAPES = "DESIGN §3.1, shapes and section layouts own their behaviour"
RULE_ENCODING = "decision 0039, text I/O names its encoding"
RULE_CODES = "decision 0040, every error carries a registered code"
#: the roots of the coded error and warning classes (``hexmesh/errors.py``)
CODED_ROOTS = {"HexmeshError", "HexmeshWarning"}
#: ``X.open(...)`` on these modules is not a text-file open (binary by
#: default, or a dataset or model)
BINARY_OPENERS = {"gzip", "bz2", "lzma", "tarfile", "zipfile", "wave", "dbm", "shelve",
                  "rasterio", "fiona", "gmsh", "Image"}
#: besides ``hexmesh/``, the trees whose text I/O the encoding rule
#: checks: the suite runs them on Windows too (task 0092's CI)
ENCODING_TREES = ("tests", "docs", "validation")         # validation/: task 0093


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
    if top == "sections":
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
        return f"{self.path.relative_to(root).as_posix()}:{self.lineno}"


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
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
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
    """Shape-specific sites outside ``core/shape.py``, ``sections`` and
    ``examples``.  A site is:

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
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), str(path))):
            where = f"{path.relative_to(root).as_posix()}:{getattr(node, 'lineno', 0)}"
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


def _mode(node: ast.Call, position: int) -> ast.expr | None:
    for kw in node.keywords:
        if kw.arg == "mode":
            return kw.value
    return node.args[position] if len(node.args) > position else None


def encoding_violations(root: Path, trees: tuple[str, ...] = ()) -> list[str]:
    """Text I/O without ``encoding=`` anywhere in ``hexmesh/``, and in the
    ``.py`` files under each of *trees*:

    - ``open(...)`` / ``io.open(...)`` / ``os.fdopen(...)`` /
      ``X.open(...)`` (a ``Path``) whose mode is not a string constant
      containing ``b``;
    - ``X.read_text(...)`` / ``X.write_text(...)``.

    ``encoding`` counts by keyword, or as ``read_text``'s first positional
    argument and ``write_text``'s second.  ``X.open`` on ``gzip``,
    ``tarfile`` and the like is skipped (binary by default)."""
    out = []
    paths = [*modules(root).values(),
             *(p for tree in trees for p in sorted((root / tree).rglob("*.py")))]
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), str(path))):
            if not isinstance(node, ast.Call):
                continue
            f, where = node.func, f"{path.relative_to(root).as_posix()}:{node.lineno}"
            has = any(kw.arg == "encoding" for kw in node.keywords)
            if isinstance(f, ast.Attribute) and f.attr in ("read_text", "write_text"):
                has = has or len(node.args) > (0 if f.attr == "read_text" else 1)
            elif ((isinstance(f, ast.Name) and f.id == "open")
                  or (isinstance(f, ast.Attribute) and f.attr == "open"
                      and not (isinstance(f.value, ast.Name) and f.value.id in BINARY_OPENERS))
                  or (isinstance(f, ast.Attribute) and f.attr == "fdopen")):
                position = 1 if isinstance(f, ast.Name) or (
                    isinstance(f.value, ast.Name) and f.value.id in ("io", "os")) else 0
                mode = _mode(node, position)
                if (isinstance(mode, ast.Constant) and isinstance(mode.value, str)
                        and "b" in mode.value):
                    continue
                has = has or len(node.args) > position + 2          # open(f, m, buffering, enc)
            else:
                continue
            if not has:
                out.append(f"{where}: {ast.unparse(node)}")
    return out


def registered_codes(root: Path) -> set[str]:
    """The keys of ``CODES`` in ``hexmesh/errors.py``, read from its AST."""
    tree = ast.parse((root / "hexmesh" / "errors.py").read_text(encoding="utf-8"))
    for node in tree.body:
        target = node.target if isinstance(node, ast.AnnAssign) else (
            node.targets[0] if isinstance(node, ast.Assign) else None)
        if isinstance(target, ast.Name) and target.id == "CODES":
            return {k.value for k in node.value.keys}
    raise AssertionError("hexmesh/errors.py defines no CODES")


def _base_name(node: ast.expr) -> str:
    return node.attr if isinstance(node, ast.Attribute) else getattr(node, "id", "")


def code_violations(root: Path) -> list[str]:
    """Constructions of a coded error or warning class (a subclass of
    :data:`CODED_ROOTS`, by class name across ``hexmesh/``) or of its
    ``wrap`` without a ``code=`` string literal in ``CODES``, or in a module
    that neither imports nor defines the class; and codes in
    ``CODES`` that nothing uses.  A class whose ``__init__`` passes the
    code itself (``PreflightFailed``) is constructed without one."""
    trees = {p: ast.parse(p.read_text(encoding="utf-8"), str(p))
             for p in modules(root).values()}
    bases = {n.name: {_base_name(b) for b in n.bases}
             for tree in trees.values() for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    coded = set(CODED_ROOTS)
    while True:
        more = {c for c, bs in bases.items() if c not in coded and bs & coded}
        if not more:
            break
        coded |= more
    known, used, out = registered_codes(root), set(), []
    self_coded = set()
    for tree in trees.values():
        for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name in coded):
            for n in ast.walk(cls):
                if isinstance(n, ast.Call) and _base_name(n.func) == "__init__":
                    code = next((kw.value for kw in n.keywords if kw.arg == "code"), None)
                    if isinstance(code, ast.Constant):
                        self_coded.add(cls.name)
                        used.add(code.value)
    for path, tree in trees.items():
        bound = ({a.asname or a.name.split(".")[0] for n in ast.walk(tree)
                  if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
                 | {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)})
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == "wrap":
                name = _base_name(f.value)
            else:
                name = _base_name(f)
            if name not in coded or name in self_coded and not (
                    isinstance(f, ast.Attribute) and f.attr == "wrap"):
                continue
            where = f"{path.relative_to(root).as_posix()}:{node.lineno}"
            code = next((kw.value for kw in node.keywords if kw.arg == "code"), None)
            if isinstance(f, ast.Name) or isinstance(f.value, ast.Name):
                bare = f.id if isinstance(f, ast.Name) else f.value.id
                if bare not in bound:
                    out.append(f"{where}: {bare} is neither imported nor defined here")
            if not (isinstance(code, ast.Constant) and isinstance(code.value, str)):
                out.append(f"{where}: {name}(…) without a code= string literal")
            elif code.value not in known:
                out.append(f"{where}: code {code.value!r} is not in CODES")
            else:
                used.add(code.value)
    out += [f"hexmesh/errors.py: code {c!r} is registered but never used"
            for c in sorted(known - used)]
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



def test_text_io_names_its_encoding():
    bad = encoding_violations(ROOT, ENCODING_TREES)
    assert not bad, (f"{RULE_ENCODING}; pass encoding=\"utf-8\" (and newline=\"\\n\" for "
                     "files OpenFOAM or a shell reads):\n  " + "\n  ".join(bad))



def test_every_error_is_coded():
    bad = code_violations(ROOT)
    assert not bad, (f"{RULE_CODES}; pass code=\"…\" and register it, with a one-line "
                     "description, in hexmesh/errors.py CODES:\n  " + "\n  ".join(bad))


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
        p.write_text(text, encoding="utf-8")
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


@pytest.mark.parametrize("text, n", [
    ("open(p)\n", 1),
    ("open(p, 'w')\n", 1),
    ("open(p, mode='a')\n", 1),
    ("p.open()\n", 1),
    ("p.read_text()\n", 1),
    ("p.write_text(s)\n", 1),
    ("os.fdopen(fd, 'w')\n", 1),
    ("open(p, 'rb')\n", 0),                                      # binary
    ("p.open(mode='wb')\n", 0),
    ("open(p, 'w', encoding='utf-8')\n", 0),
    ("p.read_text('utf-8') + p.write_text(s, 'utf-8')\n", 0),    # positional encoding
    ("gzip.open(p) and gmsh.open(p) and rasterio.open(p)\n", 0),  # not text-file opens
    ("Image.open(p)\n", 0),                                       # PIL: binary
    ("p.read_bytes() and p.write_bytes(b)\n", 0),
])
def test_planted_encoding(tmp_path, text, n):
    root = _tree(tmp_path, {"hexmesh/study/x.py": text, "tests/test_x.py": text})
    bad = encoding_violations(root, ("tests",))
    assert len(bad) == 2 * n, bad
    assert sorted(bad) == sorted(b for f in ("hexmesh/study/x.py", "tests/test_x.py")
                                 for b in bad if b.startswith(f"{f}:1: "))


_ERRORS = ("class HexmeshError(ValueError): pass\n"
           "class HexmeshWarning(UserWarning): pass\n"
           "CODES = {'size_not_positive': 'a size', 'self_coded': 'its own'}\n")


@pytest.mark.parametrize("text, n", [
    ("raise AssemblyError('x', code='size_not_positive')\n", 0),
    ("raise AssemblyError('x')\n", 1),                                  # no code
    ("raise AssemblyError('x', code=name)\n", 1),                       # not a literal
    ("raise AssemblyError('x', code='size_negative')\n", 1),            # not registered
    ("raise AssemblyError.wrap(e, 'x', code='size_not_positive')\n", 0),
    ("raise AssemblyError.wrap(e, 'x')\n", 1),
    ("warnings.warn(HexmeshWarning('x'))\n", 1),
    ("raise Failed(rows)\n", 0),                                        # codes itself
    ("raise ValueError('internal')\n", 0),                              # not a coded class
    ("raise ReaderError('x', code='size_not_positive')\n", 1),          # never imported
])
def test_planted_error_codes(tmp_path, text, n):
    root = _tree(tmp_path, {
        "hexmesh/assembly/errors.py": (
            "from ..errors import HexmeshError\n"
            "class AssemblyError(HexmeshError): pass\n"
            "class Failed(AssemblyError):\n"
            "    def __init__(self, rows):\n"
            "        super().__init__('f', code='self_coded')\n"),
        "hexmesh/errors.py": _ERRORS + "class ReaderError(HexmeshError): pass\n",
        "hexmesh/assembly/x.py": ("from .errors import AssemblyError, Failed\n"
                                  "import warnings\nfrom ..errors import HexmeshWarning\n"
                                  "AssemblyError('y', code='size_not_positive')\n" + text)})
    bad = code_violations(root)
    assert len(bad) == n, bad
    assert all(b.startswith("hexmesh/assembly/x.py:5: ") for b in bad), bad


def test_planted_unused_code(tmp_path):
    root = _tree(tmp_path, {"hexmesh/errors.py": _ERRORS})
    assert code_violations(root) == [
        "hexmesh/errors.py: code 'self_coded' is registered but never used",
        "hexmesh/errors.py: code 'size_not_positive' is registered but never used"]
