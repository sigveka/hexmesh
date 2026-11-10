# 0049 — A docs site rendered from the Markdown by Essens

- **Status:** accepted (2026-11-10, the user: "I am thinking we use
  hexmesh markdown files and render pages using essens similar to MkDocs
  and Jekyll", then "yes, but hold until we have a strategy for css";
  the CSS strategy: "yes that sounds good")
- **Date:** 2026-11-10
- **Tasks:** 0137

## Context

hexmesh's docs are Markdown that GitHub renders: README, GUIDE, API,
DESIGN, RESEARCH, the gallery, decisions, tasks, validation READMEs and
RESULTS (233 tracked files).  Tests read some of them
(`tests/test_readme.py` runs the README's code and checks links in
README, WHY and GUIDE; `test_errors.py` and `test_agent_schema.py` check
API.md), and the gallery builder writes GALLERY.md and README blocks.
Decision 0042 lists "the docs site" as not needed for 1.0.

A first idea, writing docs as `.ess`, was set aside (the user, "not
yet"): Essens has no Markdown output, so GitHub couldn't render them,
and every doc test would need porting.  Essens reads Markdown, though,
and a scratch render of all 233 files (`docs/integrations/essens.md`)
gave a site in 15 s with every link and anchor resolved.

## Options

### A. Markdown stays the source; Essens renders the site (chosen)
GitHub, the tests and the gallery builder keep the `.md` files as they
are.  Essens renders them to HTML pages, checking links, anchors and
citations as it goes.  Essens leaves navigation and the page template to
the project (its design: "the site is the project's"), so a short script
of ours adds them.

### B. MkDocs or Jekyll on the Markdown
Mature themes, navigation and search.  No link or citation checking of
the kind Essens gives, no `references.bib` citations, and a second
toolchain beside Essens (which hexmesh's author also maintains).

### C. Docs as `.ess`
Set aside (above).

## Decision (accepted: A)

1. **The Markdown files stay the source of truth**, GitHub-renderable.
   No Essens-only syntax in them (`[[…]]`, `{ NOTE }`): Essens reads a
   `.md` file with its own syntax, so Essens syntax quoted in prose goes
   in a code span.
2. **Essens renders the pages**, all docs in one call
   (`--output-dir`, `--pictures linked`), with `folder-pages:
   [RESULTS]` in an `essens.yaml` at the repository root.  Essens's
   diagnostics are part of the check: the build fails on an error-level
   one.
3. **A project script** (`docs/site.py`) wraps the pages: one page
   template, the site navigation (from the doc tree, ordered by a short
   hand-kept list for the top level), and links to files that aren't
   docs (LICENSE, `case.json`, `references.bib`) pointed at GitHub.
4. **Publishing:** GitHub Pages from a workflow that pins an Essens
   release archive.  The site is built, never committed.
5. **The CSS strategy** (settled 2026-11-10).  The options were a
   classless stylesheet, our own stylesheet, or a theme's CSS reused (its
   markup assumptions don't match Essens's output).  Chosen, in layers:
   - **a classless base stylesheet, vendored** (copied into the
     repository with its licence and version): simple.css preferred,
     Pico's classless build if simple.css's centred layout fights the
     sidebar.  Both are MIT; the task checks the licence and records the
     version.  It gives typography, tables, code and light/dark mode
     without class names;
   - **a short stylesheet of our own** on top: the sidebar layout, wide
     tables scrolling sideways (GALLERY, API.md), images at GitHub's
     `width=` percentages, print, and Essens's classes (`essens-ref`,
     `essens-admonition-*`, `math-display`, `essens-bibliography`,
     figures);
   - **KaTeX vendored** too, so pages work offline; the template points
     Essens's KaTeX links at the local copy, with an exact version.
   No CDN at view time.

## Consequences

- **Repository:** `essens.yaml` and `.essens/` in `.gitignore` (already
  there); `docs/site.py`; the vendored base stylesheet and KaTeX (with
  their licences) and our stylesheet under `docs/site/`; a workflow.  No change to any
  `.md` file's syntax, apart from fixing the three `<placeholder>`s
  GitHub strips (found by the scratch render).
- **1.0:** not a criterion (decision 0042); additive.
- **Future expansions:** 0019/0040 (agents): none, though the site
  could later host the manifest's docs; 0018, 0021, 0030, 0035: none.

## Verified vs. assumed

- **Verified** (scratch render, 2026-11-10, `docs/integrations/essens.md`):
  233 pages, links and anchors, math, tables, images; `folder-pages`
  in the installed build.
- **Assumed:** that a navigation script stays short (a few hundred
  lines); that GitHub Pages' limits (1 GB, 100 GB/month) are ample for
  a ~21 MB site.
