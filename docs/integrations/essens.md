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
