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
The README and the guides (task 0078): the README's first code block
builds the network the gallery measures, with the cell count its metrics
table quotes; every relative link and image in ``README.md``,
``docs/WHY.md`` and ``docs/GUIDE.md`` resolves, anchors included; and
``CITATION.cff`` carries ``pyproject.toml``'s version.
"""

import re
from collections import Counter
from pathlib import Path

import pytest

from hexmesh.examples.sections import insulated_tee

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DOCS = [README, ROOT / "docs" / "WHY.md", ROOT / "docs" / "GUIDE.md"]


def first_python_block(text: str) -> str:
    return re.search(r"^```python\n(.*?)^```", text, re.M | re.S).group(1)


def metrics_cells(text: str) -> int:
    """The cells the README's ``readme:metrics`` table quotes."""
    block = text.split("<!-- readme:metrics:start -->")[1].split("<!-- readme:metrics:end -->")[0]
    row = [l for l in block.splitlines() if re.match(r"^\| [\d\s ]+ = ", l)][0]
    predicted, meshed = (int(re.sub(r"\D", "", x)) for x in row.split("|")[1].split("="))
    assert predicted == meshed
    return predicted


def _run_block(tmp_path, monkeypatch, *, mesh: bool) -> dict:
    code = first_python_block(README.read_text(encoding="utf-8"))
    if not mesh:
        code = "\n".join(l for l in code.splitlines() if "asm.write" not in l)
    monkeypatch.chdir(tmp_path)
    ns: dict = {}
    exec(compile(code, "README.md", "exec"), ns)              # noqa: S102
    return ns


def _same_network(asm):
    ref = insulated_tee.build()
    assert asm.cell_count() == ref.cell_count()
    assert [type(e.fitting).__name__ for e in asm.edges] == \
        [type(e.fitting).__name__ for e in ref.edges]
    assert asm.cell_count() == metrics_cells(README.read_text(encoding="utf-8"))


def test_the_readme_block_builds_the_measured_network(tmp_path, monkeypatch):
    """Everything but the write, which meshes (see the slow test)."""
    _same_network(_run_block(tmp_path, monkeypatch, mesh=False)["asm"])


@pytest.mark.slow
def test_the_readme_block_runs_as_written(tmp_path, monkeypatch):
    ns = _run_block(tmp_path, monkeypatch, mesh=True)
    _same_network(ns["asm"])
    assert (tmp_path / "insulated_tee.msh").stat().st_size > 0


# --- links ---------------------------------------------------------------------

def _strip_code(text: str) -> str:
    text = re.sub(r"^```.*?^```", "", text, flags=re.M | re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def slugs(path: Path) -> set[str]:
    """GitHub's anchors for *path*'s headings, and explicit ids."""
    text = re.sub(r"^```.*?^```", "", path.read_text(encoding="utf-8"), flags=re.M | re.S)
    out, seen = set(), Counter()
    for h in re.findall(r"^#{1,6} +(.+?) *#*$", text, re.M):
        s = re.sub(r"[^\w\- ]", "", h.lower().replace("`", "")).replace(" ", "-")
        out.add(s if not seen[s] else f"{s}-{seen[s]}")
        seen[s] += 1
    out |= set(re.findall(r'<a (?:id|name)="([^"]+)"', text))
    return out


def links(path: Path) -> list[str]:
    text = _strip_code(path.read_text(encoding="utf-8"))
    found = re.findall(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", text)
    found += re.findall(r'<img[^>]*\bsrc="([^"]+)"', text)
    found += re.findall(r'<a[^>]*\bhref="([^"]+)"', text)
    return [u for u in found if not re.match(r"^[a-z]+:", u)]   # http:, mailto:, ...


def broken(path: Path) -> list[str]:
    bad = []
    for link in links(path):
        target, _, anchor = link.partition("#")
        dest = path if not target else (path.parent / target).resolve()
        if not dest.exists():
            bad.append(f"{link}: no such file")
        elif anchor and dest.suffix == ".md" and anchor not in slugs(dest):
            where = dest.relative_to(ROOT) if dest.is_relative_to(ROOT) else dest.name
            bad.append(f"{link}: no heading #{anchor} in {where}")
    return bad


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_relative_link_resolves(doc):
    assert links(doc), f"{doc.name}: no links found: is the pattern wrong?"
    assert broken(doc) == []


def test_a_planted_broken_link_and_anchor(tmp_path):
    (tmp_path / "a.md").write_text("# Top\n\n## Two words\n", encoding="utf-8")
    doc = tmp_path / "doc.md"
    doc.write_text("[ok](a.md#two-words) [self](#here) [gone](b.md) [bad](a.md#nope) "
                   '<img src="c.png"> `[code](x.md)` [web](https://example.com)\n\n'
                   "## Here\n", encoding="utf-8")
    assert sorted(broken(doc)) == ["a.md#nope: no heading #nope in a.md",
                                   "b.md: no such file", "c.png: no such file"]


# --- versions --------------------------------------------------------------------

def test_citation_version_is_the_package_s():
    def version(name, pattern):              # tomllib is Python 3.11+; we support 3.10
        m = re.search(pattern, (ROOT / name).read_text(encoding="utf-8"), re.M)
        return m.group(1).strip("'\"")
    assert version("CITATION.cff", r"^version: *(\S+)") == \
        version("pyproject.toml", r'^version *= *("[^"]+")'), \
        "bump CITATION.cff's version with pyproject.toml's"
