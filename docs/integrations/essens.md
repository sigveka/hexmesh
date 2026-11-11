# Essens

Version-specific behaviour of Essens (the `.ess` document tool) as it
concerns hexmesh's docs.  **Role:** it renders the docs site from the
Markdown (decision 0049, task 0137): `docs/site.py`, `essens.yaml`,
`docs/site/`.

## Essens 0.1.4 (2026-11-10)

**One history in a git repository: git's.**  Answered by the Essens
session (essens-ca), checked against its `docs/GIT-HISTORY.ess` and in a
temporary git repository (the files under `.git` unchanged before and
after `init`, `lint`, `log`, `commit`).
- A document's versions (v1, v2, …) are the commits on the default
  branch's first-parent line that change it (§2 `gh-version`).  A plain
  `git commit` makes one; `essens commit` never runs for it.
- Essens never writes the index, refs, tags or `.git` (§1 `gh-owners`).
  - `essens commit` writes nothing: it lints and prints "commit with
    git".
  - `essens milestone` and `baseline` print a `git tag -a
    essens/<doc>/<name> …` command for a person to run (§4).
  - `sign`, `accept` and `reject` write record files in the working tree
    (`essens/signatures/`, `essens/decisions/`), committed with git (§5).
  - `sync` refuses in a person's repository.
- A version is whatever git holds, half-staged hunks included; a
  "published" point is a milestone tag.  Version numbers change if
  history is rewritten: pin a milestone or a content id, not `@v3`.
- **Render-only works without `init`:** `--scratch` (in-memory, writes
  nothing) is the default outside a project.  `init` is only for history
  features (log, blame, show, milestones, version pins).
- **If `init` is run:** it does not edit `.gitignore` (hexmesh's already
  lists `.essens/`, line 23); it writes `AGENTS.md` unless one exists
  (hexmesh has none: it would create one, beside `CLAUDE.md`).
- **CI:** a shallow clone sees only fetched versions; use
  `fetch-depth: 0` for versions and milestone tags.

**Rendering, measured in a scratch project** (two documents, hexmesh's
`references.bib`; lint and render with `--scratch`, 0 diagnostics):
- Citations from `references.bib` render in CSL (chicago-author-date by
  default), with a reference list and DOI links.  One spacing glitch:
  "11 : 1358601" (volume : article number).
- A cross-reference renders with its type: write `[[eq-width]]`, not
  `Equation [[eq-width]]` (that gives "Equation Equation 1").
- HTML loads KaTeX from jsDelivr at `katex@0.16` (a floating minor);
  pages need the network for math.  The default page has no stylesheet.
- Pictures are inlined by default (a one-image page was 666 KB);
  `render.html.pictures: linked` writes them to `assets/`.
- No Markdown output: formats are html, html-fragment, jsonld, latex,
  pdf, revealjs, beamer.

**Rendering hexmesh's own Markdown as a site** (the user's idea,
2026-11-10: Markdown stays the source, Essens renders pages, as MkDocs or
Jekyll would).  A scratch copy of all 233 tracked `.md` files outside
`hexmesh/` and `tests/`, with their images and `references.bib`:
`essens render --scratch --to html --pictures linked --output-dir site/ <files>`.
- 233 pages in 15 s (156 MB peak), 21 MB with `assets/`.  Every `.md`
  link became a page link; all 883 relative links and image paths and
  every anchor resolve (GitHub-style slugs match), except links to
  files that aren't docs (LICENSE, CITATION.cff, `case.json`,
  `references.bib`).  RESEARCH: 189 inline and 14 display equations.
- **Same-named files** (`validation/*/RESULTS.md`) clash as one document
  id.  `folder-pages: [RESULTS]` in `essens.yaml` names each by its
  folder (checked); `[RESULTS.md]`, the form the 0.1.4 hint suggests,
  didn't match in the first 0.1.4 build.  The build installed
  2026-11-10 23:43 (still `0.1.4`) matches both forms (checked), and
  has the history wording in `--help` and `essens explain CODE`.
- **A `.md` file is read with Essens's syntax** (decided by Essens):
  `[[...]]` in prose is a reference; quote it in a code span.
- `HtmlNotRead` flags `<placeholder>` text that GitHub silently strips:
  it found three in hexmesh's docs.
- **No site navigation or theme:** Essens renders and checks pages;
  ordering, indexes and the site template are the project's own script
  after render (`--fragment` into a generator, or full pages), by its
  design ("The site is the project's", docs/CODE-PROJECTS.ess).  Whether
  Essens ships a site template is an open question there.

## The docs site's build (task 0137, 2026-11-11)

**Pinned and vendored:**
- Essens **0.1.4** (the build installed 2026-11-10 23:43); the CI pin
  is in `.github/workflows/docs.yml`: the release archive
  `essens-v0.1.4-linux-x64.tar.gz` from
  `github.com/Essens-lang/essens/releases` (the `essens` and
  `essens-lsp` binaries at its root; a `.deb` too), per the Essens
  session 2026-11-11.  **The repository is private:** a runner needs an
  `ESSENS_TOKEN` secret or the repository made public (the Essens
  user's decision, asked), so the workflow runs by hand only until then.
- **simple.css 2.3.1** (MIT, Kev Quirk), `docs/site/vendor/simple.css/`:
  classless, no external requests (no `url()` or `@import`), light and
  dark from `prefers-color-scheme`.  Chosen over Pico's classless build
  for size (8.7 kB) and because its variables (`--bg`, `--accent`,
  `--border`, …) were enough for the layout in `site.css`.
- **KaTeX 0.16.11** (MIT, Khan Academy), `docs/site/vendor/katex/`:
  `katex.min.css`, `katex.min.js`, `contrib/auto-render.min.js` and the
  20 `.woff2` fonts only (browsers take woff2 first, so the woff/ttf
  fallbacks the CSS lists are never fetched).  Downloaded from jsDelivr,
  2026-11-11.

**Verified behaviour (0.1.4):**
- **`--template FILE` replaces the whole page**, `<head>` included:
  `&[textus]` is the article, `&[toc]` a `<nav class="essens-toc">`.  So
  the CDN KaTeX links Essens's default page carries are gone without
  post-processing; our template loads the local copy with the same
  auto-render delimiters (`\( \)`, `\[ \]`; Essens wraps them in
  `span.math-inline` / `.math-display`).  Text that isn't a slot
  (`@@TITLE@@`, …) passes through, which `docs/site.py` fills per page.
- **`render.html.template` in `essens.yaml` is read as a name only:**
  `docs/site/page.html.tmpl` and `./docs/site/page.html.tmpl` both give
  `named template … not found [NotFound]`, while the same path works as
  `--template`.  `--help` says a value with a separator or extension is
  a path.  Reported to the Essens session 2026-11-11: a confirmed bug,
  fixed after 0.1.4 (a path is read from `essens.yaml`'s folder and must
  stay inside the project).  `docs/site.py` passes `--template` until the
  pinned release has the fix.
- **The local `essens` isn't the pinned release** (2026-11-11): the
  Essens session reinstalled `~/.local/bin/essens` from its current
  source, with the yaml template fix and `--format json` on more
  commands, and it **still reports `0.1.4`**.  So `essens --version`
  doesn't tell a local build from CI's v0.1.4 archive.  `docs/site.py`
  uses only what v0.1.4 has (`--template`, `lint --format json`), so
  both build the same; check a new feature against the release archive
  before relying on it.
- **`essens lint --format json` writes one JSON array**, pretty-printed
  over many lines (not one object per line).
- **Diagnostics on hexmesh's docs** after task 0137's fixes: one
  warning, `HtmlNotRead` for README's `<sub>` (its text is kept).  Not an
  error, so the build passes.
- 237 pages in about 17 s; 29.8 MB with `assets/` and `_static/`.

