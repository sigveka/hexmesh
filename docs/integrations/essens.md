# Essens

Version-specific behaviour of Essens (the `.ess` document tool) as it
concerns hexmesh's docs.  Context: a proposed render-only proof of
concept (the design session, 2026-11-10).

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
  "Equation [[eq-width]]" (that gives "Equation Equation 1").
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
