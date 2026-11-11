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
"""Build the docs site: Essens renders the Markdown; this adds the rest.

Decision 0049, task 0137.  Run from anywhere::

    python3 docs/site.py [--out build/site] [--repo-url URL]

1. Lists every tracked ``.md`` outside ``hexmesh/`` and ``tests/``.
2. ``essens lint`` on them: an error-level diagnostic fails the build.
3. ``essens render`` in one call, through ``docs/site/page.html.tmpl``,
   into the output folder (``essens.yaml`` holds the rest of the setup).
4. Fills the template's markers per page: title, the path back to the
   root, the sidebar, the source link and commit.
5. Points links to files that aren't docs (LICENSE, ``.json``, ``.py``,
   folders) at GitHub at the current commit.
6. Copies ``docs/site/`` (stylesheets, KaTeX) to ``_static/`` and the
   README's page to ``index.html``.
7. Checks every relative link and anchor; a broken one fails the build.

Pure Python and Essens; no other dependency.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "docs" / "site"
TEMPLATE = SITE / "page.html.tmpl"
REPO_URL = "https://github.com/sigveka/hexmesh"

#: the sidebar's top level, in this order, with short labels; every other
#: page goes in a group named by its folder (GROUPS), by its own <h1>
TOP = {"README.md": "Home", "docs/GUIDE.md": "User guide", "API.md": "API reference",
       "docs/GALLERY.md": "Examples", "DESIGN.md": "Design", "docs/RESEARCH.md": "Research notes",
       "validation/README.md": "Validation", "CHANGELOG.md": "Changes",
       "CONTRIBUTING.md": "Contributing"}
#: folder → sidebar group title, in this order; unlisted folders go under "More"
GROUPS = {"docs/gallery": "Gallery", "docs/decisions": "Decisions", "docs/tasks": "Tasks",
          "docs/integrations": "Integrations", "validation": "Validation cases"}
#: tracked .md files that aren't pages
SKIP = {"CLAUDE.md"}


# ---------------------------------------------------------------------------
# sources and Essens
# ---------------------------------------------------------------------------

def sources() -> list[str]:
    """Tracked Markdown files to render, repository-relative."""
    out = subprocess.run(["git", "ls-files", "*.md"], cwd=ROOT, check=True,
                         capture_output=True, text=True).stdout.split()
    return sorted(p for p in out
                  if not p.startswith(("hexmesh/", "tests/")) and p not in SKIP)


def essens(*args: str) -> subprocess.CompletedProcess:
    exe = shutil.which("essens")
    if exe is None:
        sys.exit("site: essens is not on PATH (docs/integrations/essens.md)")
    return subprocess.run([exe, *args], cwd=ROOT, capture_output=True, text=True)


def lint(files: list[str]) -> None:
    """Fail on error-level diagnostics; report the rest by kind."""
    r = essens("lint", "--scratch", "--format", "json", *files)
    if r.returncode == 2:
        sys.exit(f"site: essens lint failed:\n{r.stderr}")
    try:
        entries = json.loads(r.stdout) if r.stdout.strip() else []
    except json.JSONDecodeError as e:
        sys.exit(f"site: essens lint wrote no JSON array ({e}):\n{r.stdout[:500]}")
    errors = [e for e in entries if e.get("severity") == "error"]
    kinds: dict[str, int] = {}
    for e in entries:
        k = f"{e.get('severity')} {e.get('kind')}"
        kinds[k] = kinds.get(k, 0) + 1
    for k, n in sorted(kinds.items()):
        print(f"site: lint: {n} × {k}")
    if errors or r.returncode == 1:
        for e in errors[:20]:
            src = e.get("source", {})
            print(f"  {e.get('doc_id')}:{src.get('line', '?')}: {e.get('kind')}: "
                  f"{e.get('message')}", file=sys.stderr)
        sys.exit(f"site: {len(errors)} error-level Essens diagnostic(s)")


def render(files: list[str], out: Path) -> None:
    # --template, not essens.yaml: 0.1.4 reads the yaml key as a name only
    r = essens("render", "--scratch", "--to", "html", "--template", str(TEMPLATE),
               "--output-dir", str(out), *files)
    if r.returncode != 0:
        sys.exit(f"site: essens render failed:\n{r.stderr[-4000:]}")


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------

def page_of(src: str) -> str:
    """The page Essens writes for *src* (``docs/GUIDE.md`` → ``docs/GUIDE.html``)."""
    return src[:-3] + ".html"


class _Scan(HTMLParser):
    """A page's ids, links, first <h1> text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.h1: str | None = None
        self._in_h1 = False
        self._h1_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and a.get("name"):
            self.ids.add(a["name"])
        for k in ("href", "src"):
            if a.get(k):
                self.links.append(a[k])
        if tag == "h1" and self.h1 is None:
            self._in_h1 = True

    def handle_endtag(self, tag):
        if tag == "h1" and self._in_h1:
            self._in_h1 = False
            self.h1 = " ".join("".join(self._h1_text).split())

    def handle_data(self, data):
        if self._in_h1:
            self._h1_text.append(data)


def scan(text: str) -> _Scan:
    s = _Scan()
    s.feed(text)
    return s


def nav_html(pages: dict[str, str], current: str) -> str:
    """The sidebar for *current*: TOP, then a folded group per folder."""
    def link(src: str, label: str | None = None) -> str:
        href = posixpath.relpath(page_of(src), posixpath.dirname(current) or ".")
        here = ' aria-current="page"' if page_of(src) == current else ""
        text = html.escape(label or pages[src])
        return f'<li><a href="{html.escape(href)}"{here}>{text}</a></li>'

    out = ["<ul>"] + [link(s, label) for s, label in TOP.items() if s in pages] + ["</ul>"]
    rest = [s for s in pages if s not in TOP]
    groups: dict[str, list[str]] = {}
    for s in rest:
        folder = next((f for f in GROUPS if s.startswith(f + "/")), "")
        groups.setdefault(folder, []).append(s)
    for folder in [*GROUPS, ""]:
        members = groups.get(folder)
        if not members:
            continue
        title = GROUPS.get(folder, "More")
        is_open = " open" if any(page_of(s) == current for s in members) else ""
        out += [f"<details{is_open}><summary>{title} ({len(members)})</summary><ul>",
                *[link(s) for s in sorted(members)], "</ul></details>"]
    return "\n".join(out)


_HREF = re.compile(r'(\b(?:href|src)=")([^"]*)(")')


def rewrite_links(text: str, page: str, out: Path, blob: str) -> str:
    """Relative links to files that aren't pages go to GitHub at *blob*."""
    def fix(m):
        url = m.group(2)
        if not url or url.startswith(("#", "http:", "https:", "mailto:", "data:", "//")):
            return m.group(0)
        path, _, frag = url.partition("#")
        target = posixpath.normpath(posixpath.join(posixpath.dirname(page), path))
        if (out / target).is_file() or target.startswith("_static/"):
            return m.group(0)
        if target.startswith("..") or not (ROOT / target).exists():
            return m.group(0)                    # left for the link check to report
        kind = "tree" if (ROOT / target).is_dir() else "blob"
        new = f"{blob.replace('/blob/', f'/{kind}/')}/{target}" + (f"#{frag}" if frag else "")
        return m.group(1) + html.escape(new) + m.group(3)
    return _HREF.sub(fix, text)


def check_links(out: Path, pages: list[str]) -> list[str]:
    """Broken relative links and anchors, as "page: link" lines."""
    ids: dict[str, set[str]] = {}
    links: dict[str, list[str]] = {}
    for p in pages + ["index.html"]:
        s = scan((out / p).read_text(encoding="utf-8"))
        ids[p], links[p] = s.ids, s.links
    bad = []
    for p, ls in links.items():
        for url in ls:
            url = html.unescape(url)
            if url.startswith(("http:", "https:", "mailto:", "data:", "//")):
                continue
            path, _, frag = url.partition("#")
            target = (posixpath.normpath(posixpath.join(posixpath.dirname(p), path))
                      if path else p)
            if not (out / target).exists():
                bad.append(f"{p}: {url} (no such file)")
            elif frag and target.endswith(".html"):
                if target not in ids:
                    ids[target] = scan((out / target).read_text(encoding="utf-8")).ids
                if frag not in ids[target]:
                    bad.append(f"{p}: {url} (no anchor #{frag})")
    return bad


# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "site")
    ap.add_argument("--repo-url", default=REPO_URL)
    args = ap.parse_args(argv)
    out = args.out.resolve()

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                            capture_output=True, text=True).stdout.strip()
    blob = f"{args.repo_url}/blob/{commit}"
    files = sources()
    print(f"site: {len(files)} pages, commit {commit[:10]}")

    lint(files)
    if out.exists():
        shutil.rmtree(out)
    render(files, out)

    titles = {}
    for src in files:
        s = scan((out / page_of(src)).read_text(encoding="utf-8"))
        titles[src] = s.h1 or Path(src).stem

    for src in files:
        page = page_of(src)
        f = out / page
        text = f.read_text(encoding="utf-8")
        root = posixpath.relpath(".", posixpath.dirname(page) or ".")
        root = "" if root == "." else root + "/"
        text = (text.replace("@@TITLE@@", html.escape(titles[src]))
                    .replace("@@ROOT@@", root)
                    .replace("@@NAV@@", nav_html(titles, page))
                    .replace("@@SOURCE@@", html.escape(f"{blob}/{src}"))
                    .replace("@@SOURCE_PATH@@", html.escape(src))
                    .replace("@@COMMIT@@", commit[:10]))
        f.write_text(rewrite_links(text, page, out, blob), encoding="utf-8")

    shutil.copytree(SITE / "vendor", out / "_static", dirs_exist_ok=True)
    shutil.copy2(SITE / "site.css", out / "_static" / "site.css")
    shutil.copy2(out / "README.html", out / "index.html")
    (out / ".nojekyll").write_text("", encoding="utf-8")    # serve _static/ as is

    bad = check_links(out, [page_of(s) for s in files])
    for b in bad[:50]:
        print(f"  broken: {b}", file=sys.stderr)
    if bad:
        sys.exit(f"site: {len(bad)} broken relative link(s) or anchor(s)")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"site: wrote {out} ({size / 1e6:.1f} MB); links and anchors checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
