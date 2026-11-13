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
- **No bare built-in raise** (decision 0040; task 0106): ``raise
  ValueError``, ``TypeError``, ``RuntimeError``, ``KeyError``,
  ``NotImplementedError`` or ``AttributeError`` in ``hexmesh/`` only from
  the reviewed :data:`BARE_ALLOWED` list, each entry with its reason (see
  :func:`bare_raise_violations`).  A user's error is a coded
  ``HexmeshError``, an internal invariant an ``InternalError``.  The list
  only shrinks: every entry must still be needed.
- **The light commands load neither gmsh nor scipy** (decision 0040,
  amendment 2026-11-07; task 0107): in a fresh interpreter every
  ``hexmesh`` command but ``build`` leaves ``gmsh`` out of
  ``sys.modules``, ``validate`` and ``estimate`` leave ``scipy`` out too,
  and with gmsh unimportable they all still work while ``build`` gives
  ``gmsh_unavailable``.  The manifest's ``needs_gmsh`` must agree.

Each check returns its violations, so the planted-violation tests at the
end run the same code on a synthetic tree.
"""

from __future__ import annotations

import ast
import re
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: capabilities in dependency order (DESIGN §3.1)
ORDER = ("core", "sections", "assembly", "interchange", "study",
         "agent")                     # task 0095: decision 0040's tool layer, on top
#: shared leaves: anyone may import them; they import only leaves
LEAVES = {"hexmesh._occ", "hexmesh.session", "hexmesh.quality_hex",
          "hexmesh.version",            # task 0091: assembly stamps the version
          "hexmesh.errors",             # task 0094: every layer's error classes
          "hexmesh._gmsh",              # task 0107: gmsh, loaded on first use
          "hexmesh.units"}              # task 0128: length constants (decision 0047)
#: the public API ``hexmesh.agent`` may import (task 0097): the package
#: roots, and the documented registries the schema reads
AGENT_IMPORTS = {"hexmesh", "hexmesh.assembly", "hexmesh.interchange", "hexmesh.errors",
                 "hexmesh.units",
                 "hexmesh.assembly.intent", "hexmesh.assembly.limits",   # FITTING_TYPES, LIMITS
                 "hexmesh.core.params", "hexmesh.core.shape",            # UNITS, SHAPES
                 "hexmesh.core.grading"}          # advise: the first-cell solvers
#: which capabilities may import ``io.writers``
WRITERS_USERS = {"assembly", "study"}
#: may import anything
FREE = {"root", "examples"}
#: private names that may cross packages (DESIGN §3.1)
PRIVATE_OK = {"hexmesh._occ", "hexmesh._gmsh"}     # _gmsh: task 0107

#: dependency edges outside the order, each with the task that removes it
ALLOWED_EDGES = {
    # task 0066: the readers are in interchange.importers; io.readers only
    # re-exports them for the public name (test_io_readers_only_re_export)
    ("io.readers", "interchange"): "a re-export of interchange.importers (decision 0037 item 4)",
}
#: module cycles today, each with the task that removes it
ALLOWED_CYCLES: dict[frozenset, str] = {}

#: shape-specific sites outside core/shape.py and sections: 69 at task 0081
#: (RESEARCH §12's cruder grep found 89), 59 at task 0082 (the face
#: dispatch, corner 0 and side counts moved into sections), 15 at task
#: 0083 (the shape protocol; all 15 in tee.py, left for the tee split,
#: task 0060), 7 after it, 0 at task 0151 (the pipe tee's circle reads go
#: through ``sections.circle_radius``; decision 0051).  Keep it at 0.
SHAPE_SITES_CAP = 0
SHAPE_TYPES = {"CircleShape", "RectShape", "BlendShape"}
SHAPE_FIELDS = {"radius", "half_w", "half_h", "nang_w", "nang_h"}
SHAPE_VALUES = {"core_shape", "shape", "branch"}

RULE_ORDER = "DESIGN §3.1, dependency order"
RULE_PRIVATE = "DESIGN §3.1, no private name crosses a package"
RULE_CYCLE = "DESIGN §3.1, no module cycles"
RULE_SHAPES = "DESIGN §3.1, shapes and section layouts own their behaviour"
RULE_ENCODING = "decision 0039, text I/O names its encoding"
RULE_CODES = "decision 0040, every error carries a registered code"
RULE_BARE = "decision 0040, no bare built-in raise"
RULE_POSIX = ("decision 0052, a test that runs a POSIX tool is posix_only "
              "(docs/integrations/platforms.md: WSL's bash)")
RULE_PATH_TEXT = ("decision 0052, no bare path inside compared text "
                  "(docs/integrations/platforms.md: str(path) uses \\, shlex.quote quotes it)")
#: commands a Windows runner lacks, or has as something else (its ``bash``
#: is WSL's, its ``timeout`` waits for a key): a test running one is
#: ``posix_only`` (task 0157)
POSIX_TOOLS = {"bash", "sh", "timeout"}
#: OpenFOAM utilities: a test running one is ``openfoam`` or ``posix_only``
OPENFOAM_TOOLS = {"gmshToFoam", "checkMesh", "splitMeshRegions", "blockMesh", "decomposePar",
                  "reconstructPar", "simpleFoam", "foamRun", "mapFields", "foamDictionary"}
#: markers that keep a test off Windows (``openfoam`` is opt-in, Linux only)
POSIX_MARKERS = {"posix_only", "openfoam"}
#: (test file, function) running a POSIX tool without a marker of its own:
#: the reason it is safe
POSIX_ALLOWED = {
    ("tests/test_openfoam_output.py", "run_foam"):
        "a helper, called only from openfoam-marked tests (test_openfoam_boundary, via _types)",
}
#: (test file, function, line text) comparing text with a bare path: the reason
PATH_TEXT_ALLOWED: dict[tuple[str, str], str] = {}
#: the roots of the coded error and warning classes (``hexmesh/errors.py``)
CODED_ROOTS = {"HexmeshError", "HexmeshWarning", "HexmeshNotice", "InternalError"}
#: built-in exceptions hexmesh code must not raise bare (task 0106)
BARE = {"ValueError", "TypeError", "RuntimeError", "KeyError", "NotImplementedError",
        "AttributeError"}
#: (module, enclosing function, exception) raised bare on purpose: the reason
BARE_ALLOWED = {
    ("hexmesh/interchange/__init__.py", "__getattr__", "AttributeError"):
        "the module __getattr__ protocol: a missing attribute must be an AttributeError",
    ("hexmesh/errors.py", "_Fields._set", "KeyError"):
        "the code registry's own guard: an unregistered code is a programming error, "
        "and the code check (test_every_error_is_coded) finds it statically",
    ("hexmesh/assembly/sweep.py", "Sweep.path", "NotImplementedError"):
        "an abstract method: each sweep fitting overrides it",
    ("hexmesh/core/cross_section.py", "LayeredCrossSection.get", "KeyError"):
        "a lookup by name, in the mapping protocol; internal callers only",
    ("hexmesh/core/region.py", "MaterialGraph.interface_label", "KeyError"):
        "a lookup by name, in the mapping protocol; internal callers only",
}
#: ``X.open(...)`` on these modules is not a text-file open (binary by
#: default, or a dataset or model)
BINARY_OPENERS = {"gzip", "bz2", "lzma", "tarfile", "zipfile", "wave", "dbm", "shelve",
                  "rasterio", "fiona", "gmsh", "Image"}
#: besides ``hexmesh/``, the trees whose text I/O the encoding rule
#: checks: the suite runs them on Windows too (task 0092's CI)
ENCODING_TREES = ("tests", "docs", "validation")         # validation/: task 0093


# --- the module tree -----------------------------------------------------------

_PARSED: dict[tuple, ast.Module] = {}


def _parse(path: Path) -> ast.Module:
    """*path*'s AST, parsed once per run while the file is unchanged: the
    rules walk the same files (task 0158: the hook's time)."""
    st = path.stat()
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key not in _PARSED:
        _PARSED[key] = ast.parse(path.read_text(encoding="utf-8"), str(path))
    return _PARSED[key]


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
        tree = _parse(path)
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
        if tgt == "agent" and src != "agent":           # not even root or examples
            out.append(f"{imp.where(root)}: {imp.module} ({src}) imports {imp.target}: "
                       "nothing in the library imports hexmesh.agent (task 0095)")
            continue
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
        rel = path.relative_to(root).as_posix()           # once per file: 9 s otherwise
        for node in ast.walk(_parse(path)):
            where = f"{rel}:{getattr(node, 'lineno', 0)}"
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
        rel = path.relative_to(root).as_posix()
        for node in ast.walk(_parse(path)):
            if not isinstance(node, ast.Call):
                continue
            f, where = node.func, f"{rel}:{node.lineno}"
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


_SUBPROCESS = {"run", "Popen", "call", "check_call", "check_output"}


def _marks(decorators) -> set[str]:
    """The ``pytest.mark.<name>`` names in *decorators* (bare or called),
    or in a ``pytestmark`` value."""
    out = set()
    for d in decorators:
        for node in ast.walk(d):
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute)
                    and node.value.attr == "mark"):
                out.add(node.attr)
    return out


def _test_functions(tree: ast.Module):
    """``(function, its marks)`` for each top-level function and method,
    with the module's ``pytestmark`` and the class's included."""
    module = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(x, ast.Name) and x.id == "pytestmark"
                                                for x in node.targets):
            module |= _marks([node.value])
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node, module | _marks(node.decorator_list)
        elif isinstance(node, ast.ClassDef):
            cls = module | _marks(node.decorator_list)
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield sub, cls | _marks(sub.decorator_list)


def posix_tool_violations(root: Path, tree: str = "tests") -> list[tuple[str, str, str]]:
    """``(file:line, function, call)`` for each ``subprocess.run``/``Popen``/
    ``call``/``check_call``/``check_output`` in *tree*'s ``.py`` files whose
    argv is a list or tuple literal starting with a POSIX tool or an
    OpenFOAM utility (:data:`POSIX_TOOLS`, :data:`OPENFOAM_TOOLS`), in a
    function without a :data:`POSIX_MARKERS` mark (its own, its class's or
    the module's ``pytestmark``).  Module-level calls count as unmarked
    unless ``pytestmark`` has one."""
    out = []
    for path in sorted((root / tree).rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        parsed = _parse(path)
        owner = {}
        for fn, marks in _test_functions(parsed):
            for node in ast.walk(fn):
                owner.setdefault(id(node), (fn.name, marks))
        for node in ast.walk(parsed):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in _SUBPROCESS and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "subprocess" and node.args
                    and isinstance(node.args[0], (ast.List, ast.Tuple)) and node.args[0].elts
                    and isinstance(node.args[0].elts[0], ast.Constant)
                    and node.args[0].elts[0].value in POSIX_TOOLS | OPENFOAM_TOOLS):
                continue
            name, marks = owner.get(id(node), ("<module>", None))
            if marks is None:
                marks = set()
                for top in parsed.body:
                    if isinstance(top, ast.Assign) and any(
                            isinstance(x, ast.Name) and x.id == "pytestmark" for x in top.targets):
                        marks |= _marks([top.value])
            if not marks & POSIX_MARKERS:
                out.append((f"{rel}:{node.lineno}", name, ast.unparse(node.args[0])))
    return out


def _bare_path(value: ast.expr) -> str | None:
    """*value*'s path name if it's ``tmp_path`` or a ``*path``/``*dir``
    name, bare or as ``str(...)``; ``None`` otherwise."""
    if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
            and value.func.id == "str" and len(value.args) == 1):
        value = value.args[0]
    if isinstance(value, ast.Name) and re.search(r"(^|_)(path|dir)$", value.id):
        return value.id
    return None


def _path_fstrings(node: ast.expr) -> list[str]:
    """The bare path names interpolated into the f-strings in *node*."""
    return [name for sub in ast.walk(node) if isinstance(sub, ast.JoinedStr)
            for part in sub.values if isinstance(part, ast.FormattedValue)
            for name in [_bare_path(part.value)] if name]


def path_text_violations(root: Path, tree: str = "tests") -> list[tuple[str, str, str]]:
    """``(file:line, function, name)`` for each ``assert`` in *tree* that
    compares text (``==``, ``!=``, ``in``, ``not in``, ``.startswith``,
    ``.endswith``) with an f-string interpolating a bare path
    (:func:`_bare_path`): ``f"{tmp_path}/x"``, ``f"{str(out_dir)}"``.
    ``.name``, ``.as_posix()`` and ``shlex.quote(...)`` are safe, as is
    anything not in an ``assert``."""
    out = []
    for path in sorted((root / tree).rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        parsed = _parse(path)
        owner = {}
        for fn, _ in _test_functions(parsed):
            for node in ast.walk(fn):
                owner.setdefault(id(node), fn.name)
        for node in ast.walk(parsed):
            if not isinstance(node, ast.Assert):
                continue
            for sub in ast.walk(node.test):
                operands = []
                if isinstance(sub, ast.Compare) and all(
                        isinstance(op, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)) for op in sub.ops):
                    operands = [sub.left, *sub.comparators]
                elif (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                      and sub.func.attr in ("startswith", "endswith")):
                    operands = [sub.func.value, *sub.args]
                for name in (n for o in operands for n in _path_fstrings(o)):
                    out.append((f"{rel}:{sub.lineno}", owner.get(id(node), "<module>"), name))
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
    code itself (``PreflightFailed``, or ``InternalError`` through
    ``_set``) is constructed without one."""
    trees = {p: _parse(p)
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
                if isinstance(n, ast.Call) and _base_name(n.func) in ("__init__", "_set"):
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

def bare_raises(root: Path) -> list[tuple[tuple[str, str, str], int]]:
    """Every ``raise`` of a :data:`BARE` exception in ``hexmesh/``, as
    ((module, enclosing qualified name, exception), line)."""
    out = []
    for path in modules(root).values():
        rel = path.relative_to(root).as_posix()

        def visit(node, scope):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    visit(child, scope + (child.name,))
                    continue
                if isinstance(child, ast.Raise) and child.exc is not None:
                    exc = child.exc.func if isinstance(child.exc, ast.Call) else child.exc
                    name = _base_name(exc)
                    if name in BARE:
                        out.append(((rel, ".".join(scope), name), child.lineno))
                visit(child, scope)
        visit(_parse(path), ())
    return out


def bare_raise_violations(root: Path, allowed=None) -> list[str]:
    """Bare built-in raises not in *allowed* (default :data:`BARE_ALLOWED`)."""
    allowed = BARE_ALLOWED if allowed is None else allowed
    return [f"{rel}:{line}: raise {exc} in {scope or 'the module'}"
            for (rel, scope, exc), line in bare_raises(root) if (rel, scope, exc) not in allowed]


def agent_violations(root: Path) -> list[str]:
    """Imports by ``hexmesh.agent`` of anything but :data:`AGENT_IMPORTS`
    and itself."""
    return [f"{imp.where(root)}: {imp.module} imports {imp.target}, not the public API"
            for imp in imports(root)
            if imp.module.startswith("hexmesh.agent")
            and not imp.target.startswith("hexmesh.agent") and imp.target not in AGENT_IMPORTS]


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


def test_io_readers_only_re_export():
    """The io.readers → interchange edge is a re-export only (task 0066):
    each module holds a docstring, imports, ``__all__`` and the
    ``sys.modules`` alias, and no code of its own; the package also warns
    that it is deprecated (task 0148)."""
    for path in sorted((ROOT / "hexmesh/io/readers").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue                                     # the docstring
            if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                    and ast.unparse(node.value.func) == "warnings.warn"
                    and "DeprecationWarning" in ast.unparse(node.value)):
                continue                                     # the deprecation (task 0148)
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                tgt = node.targets[0]
                if isinstance(tgt, ast.Name) and tgt.id == "__all__":
                    continue
                if isinstance(tgt, ast.Subscript) and ast.unparse(tgt) == "sys.modules[__name__]":
                    continue
            raise AssertionError(f"{path.relative_to(ROOT)}:{node.lineno}: io.readers only "
                                 f"re-exports interchange.importers (task 0066)")


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



def test_no_bare_builtin_raise():
    bad = bare_raise_violations(ROOT)
    assert not bad, (f"{RULE_BARE}; a user's error is a coded HexmeshError subclass (keep the "
                     "built-in in its bases, as SpecTypeError does), an internal invariant an "
                     "InternalError:\n  " + "\n  ".join(bad))


def test_bare_allow_list_still_needed():
    found = {key for key, _ in bare_raises(ROOT)}
    stale = sorted(set(BARE_ALLOWED) - found)
    assert not stale, f"BARE_ALLOWED entries no longer raised (remove them): {stale}"


def test_posix_tools_are_marked():
    bad = [f"{where} in {fn}: {argv}" for where, fn, argv in posix_tool_violations(ROOT)
           if (where.split(":")[0], fn) not in POSIX_ALLOWED]
    assert not bad, (f"{RULE_POSIX}; add @pytest.mark.posix_only (or openfoam) to the test, "
                     "or pytestmark to its module:\n  " + "\n  ".join(bad))


@pytest.mark.parametrize("platform, skipped", [("win32", True), ("linux", False),
                                               ("darwin", False)])
def test_posix_only_is_skipped_on_windows_only(monkeypatch, platform, skipped):
    """``conftest.py``'s hook (task 0157), with fake items."""
    import conftest

    class Item:
        def __init__(self, marked):
            self.marked, self.added = marked, []

        def get_closest_marker(self, name):
            return object() if self.marked and name == "posix_only" else None

        def add_marker(self, mark):
            self.added.append(mark)

    items = [Item(True), Item(False)]
    monkeypatch.setattr(conftest.sys, "platform", platform)
    conftest.pytest_collection_modifyitems(None, items)
    assert [bool(i.added) for i in items] == [skipped, False]
    if skipped:
        assert "WSL's bash" in items[0].added[0].kwargs["reason"]


def test_posix_allow_list_still_needed():
    found = {(where.split(":")[0], fn) for where, fn, _ in posix_tool_violations(ROOT)}
    stale = sorted(set(POSIX_ALLOWED) - found)
    assert not stale, f"POSIX_ALLOWED entries no longer needed (remove them): {stale}"


def test_no_bare_path_in_compared_text():
    bad = [f"{where} in {fn}: {name}" for where, fn, name in path_text_violations(ROOT)
           if (where.split(":")[0], fn) not in PATH_TEXT_ALLOWED]
    assert not bad, (f"{RULE_PATH_TEXT}; compare with path.as_posix(), path.name or "
                     "shlex.quote(str(path)), or the text read back as a Path:\n  "
                     + "\n  ".join(bad))


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


@pytest.mark.parametrize("rel", ["hexmesh/__init__.py", "hexmesh/examples/fittings/tee.py",
                                 "hexmesh/study/run.py"])
def test_planted_import_of_agent(tmp_path, rel):
    root = _tree(tmp_path, {rel: "from hexmesh.agent import schema\n",
                            "hexmesh/agent/__init__.py": "",
                            "hexmesh/agent/schema.py": "from hexmesh import Session\n"})
    bad = order_violations(root)
    assert len(bad) == 1 and rel in bad[0] and "hexmesh.agent" in bad[0]


def test_agent_imports_only_the_public_api():
    assert agent_violations(ROOT) == []


def test_planted_agent_import(tmp_path):
    root = _tree(tmp_path, {"hexmesh/agent/__init__.py": "from hexmesh import Assembly\n"
                                                         "from ._x import f\n",
                            "hexmesh/agent/_x.py": "from hexmesh.assembly.tee import Tee\n",
                            "hexmesh/assembly/tee.py": ""})
    bad = agent_violations(root)
    assert len(bad) == 1 and "hexmesh.assembly.tee" in bad[0]


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


@pytest.mark.parametrize("text, n", [
    ("def test_a():\n    subprocess.run(['bash', '-n', p])\n", 1),
    ("def test_a():\n    subprocess.check_output(('sh', '-c', s))\n", 1),
    ("def test_a():\n    subprocess.run(['timeout', '8', exe])\n", 1),
    ("def test_a():\n    subprocess.Popen(['checkMesh', '-case', c])\n", 1),
    ("def helper():\n    return subprocess.run(['bash', '-c', s])\n", 1),      # helpers too
    ("x = subprocess.run(['bash', '-c', s])\n", 1),                             # module level
    ("@pytest.mark.posix_only\ndef test_a():\n    subprocess.run(['bash', '-n', p])\n", 0),
    ("@pytest.mark.openfoam\ndef test_a():\n    subprocess.run(['bash', '-c', s])\n", 0),
    ("pytestmark = [pytest.mark.openfoam]\n"
     "def test_a():\n    subprocess.run(['gmshToFoam', m])\n", 0),
    ("@pytest.mark.posix_only\nclass TestA:\n"
     "    def test_a(self):\n        subprocess.run(['bash', '-n', p])\n", 0),
    ("def test_a():\n    subprocess.run([sys.executable, '-c', s])\n", 0),        # not a tool
    ("def test_a():\n    subprocess.run(['docker', 'ps'])\n", 0),                 # on Windows too
    ("def test_a():\n    subprocess.run(argv)\n", 0),                             # not a literal
])
def test_planted_posix_tools(tmp_path, text, n):
    root = _tree(tmp_path, {"tests/test_x.py": text})
    assert len(posix_tool_violations(root)) == n


@pytest.mark.parametrize("text, n", [
    ('assert out.endswith(f"run {tmp_path}")\n', 1),        # the 4473cb1 failure, as it was
    ('assert f"{tmp_path}/a.msh" in text\n', 1),
    ('assert text == f"wrote {str(out_dir)}"\n', 1),
    ('assert line.startswith(f"{case_path}: ")\n', 1),
    ('assert ok and f"{tmp_path}" != text\n', 1),
    ('assert out.endswith(f"run {shlex.quote(str(tmp_path))}")\n', 0),
    ('assert f"{tmp_path.name}/a" in text\n', 0),
    ('assert f"{tmp_path.as_posix()}/a" in text\n', 0),
    ('assert Path(text) == tmp_path / "a"\n', 0),            # compared as paths
    ('msg = f"{tmp_path}"\n', 0),                               # not in an assert
    ('assert f"{n} cells" in text\n', 0),                       # not a path name
    ('assert len(f"{tmp_path}") > 3\n', 0),                     # not a text comparison
])
def test_planted_path_text(tmp_path, text, n):
    root = _tree(tmp_path, {"tests/test_x.py": "def test_a(tmp_path):\n    " + text})
    assert len(path_text_violations(root)) == n


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


@pytest.mark.parametrize("text, n", [
    ("def f():\n    raise ValueError('x')\n", 1),
    ("class C:\n    def m(self):\n        raise KeyError\n", 1),          # a bare name too
    ("raise NotImplementedError('module level')\n", 1),
    ("def f():\n    raise InternalError('x')\n", 0),
    ("def f():\n    raise AssertionError('unreachable')\n", 0),             # an invariant
    ("def f():\n    raise FileNotFoundError('p')\n", 0),
    ("def allowed():\n    raise TypeError('x')\n", 0),                     # on the list
])
def test_planted_bare_raise(tmp_path, text, n):
    root = _tree(tmp_path, {"hexmesh/assembly/x.py": text})
    bad = bare_raise_violations(root, {("hexmesh/assembly/x.py", "allowed", "TypeError"): "test"})
    assert len(bad) == n, bad


# --- the light commands (task 0107) -------------------------------------------

#: Runs every ``hexmesh`` command in one fresh interpreter and prints, per
#: command, its envelope and the heavy modules loaded so far.  Arguments:
#: block (gmsh unimportable), plant (a module to run ``import gmsh`` in),
#: the work directory.
_RUN_COMMANDS = r"""
import io, json, sys
from pathlib import Path
block, plant, work = sys.argv[1] == "1", sys.argv[2], Path(sys.argv[3])
if block:
    sys.modules["gmsh"] = None
import hexmesh.agent
if plant:
    exec("import gmsh", __import__(plant, fromlist=["_"]).__dict__)
from hexmesh.agent import _commands, cli
net, inputs = str(work / "net.json"), str(work / "inputs.json")
args = {"validate": [net], "estimate": [net], "describe": [net],
        "preview": [net, "--out", str(work / "view.png")],
        "advise": [net, "--inputs", inputs], "apply": [net, "--table", str(work / "table.json")],
        "build": [net, "--out", str(work / "mesh.msh")]}
class Out:
    def __init__(self): self.buffer = io.BytesIO()
    def flush(self): pass
out, real = {}, sys.stdout
for c in _commands.COMMANDS:
    if c == "build" and not block:
        continue                                   # it meshes: not a light command
    sys.stdout = Out()
    cli.main([c, *args.get(c, [])])
    env, sys.stdout = json.loads(sys.stdout.buffer.getvalue()), real
    if c == "advise" and env["ok"]:
        (work / "table.json").write_text(json.dumps(env["result"]["table"]), encoding="utf-8")
    out[c] = {"envelope": {k: env.get(k) for k in ("ok", "error")},
              "heavy": sorted({m.split(".")[0] for m in sys.modules
                               if m.split(".")[0] in ("gmsh", "scipy") and sys.modules[m]})}
print(json.dumps(out))
"""


def run_commands(work: Path, *, block: bool = False, plant: str = "") -> dict:
    """{command: {envelope, heavy}} from a fresh interpreter (see
    :data:`_RUN_COMMANDS`)."""
    if not (work / "net.json").exists():
        from hexmesh import Assembly, Bend, PipeSpec, Straight, Tee
        a = Assembly(PipeSpec(nang=4).core("fluid", radius=0.05, nrad=3)
                     .shell("steel", dR=0.005, nrad=1), direction=[1, 0, 0], up=[0, 0, 1])
        a.add(Straight(0.3, n_layers=3))
        main, branch = a.add(Tee(branch_length=0.2, branch_radius=0.03), names=["main", "branch"])
        a.add(main, Bend(0.2, 90, n_layers=4))
        a.add(branch, Straight(0.2, n_layers=2))
        a.save(work / "net.json")
        (work / "inputs.json").write_text(json.dumps(
            {"fluid": "water", "flow": {"velocity": 0.005}, "accuracy": "coarse"}),
            encoding="utf-8")
    p = subprocess.run([sys.executable, "-c", _RUN_COMMANDS, "1" if block else "0", plant,
                        str(work)], cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def light_violations(runs: dict) -> list[str]:
    """Light commands that loaded gmsh, or (validate, estimate) scipy."""
    from hexmesh.agent._commands import NEEDS_GMSH
    bad = []
    for c, r in runs.items():
        if c not in NEEDS_GMSH and "gmsh" in r["heavy"]:
            bad.append(f"{c}: gmsh loaded")
        if c in ("validate", "estimate") and "scipy" in r["heavy"]:
            bad.append(f"{c}: scipy loaded")
    return bad


@pytest.mark.subprocess
def test_the_light_commands_load_neither_gmsh_nor_scipy(tmp_path):
    runs = run_commands(tmp_path)
    assert all(r["envelope"]["ok"] for r in runs.values()), runs
    assert light_violations(runs) == []


@pytest.mark.subprocess
def test_planted_top_level_gmsh_import(tmp_path):
    """``import gmsh`` run in a light module, as a top-level import would."""
    bad = light_violations(run_commands(tmp_path, plant="hexmesh.agent._commands"))
    assert "validate: gmsh loaded" in bad and "estimate: gmsh loaded" in bad, bad


@pytest.mark.subprocess
def test_without_gmsh_only_build_fails_and_the_manifest_says_so(tmp_path):
    from hexmesh.agent import manifest
    runs = run_commands(tmp_path, block=True)
    needs = {c: d["needs_gmsh"] for c, d in manifest()["commands"].items()}
    assert set(runs) == set(needs)
    for c, r in runs.items():
        env = r["envelope"]
        if needs[c]:
            assert env["ok"] is False and env["error"]["code"] == "gmsh_unavailable", (c, env)
            assert "pip install gmsh" in env["error"]["hint"]
        else:
            assert env["ok"] is True, (c, env)
