# 0137 — The docs site: Essens pages, our navigation and template, GitHub Pages

- **Status:** in progress (the design session, at the user's request, 2026-11-11): done but for an Essens release with `folder-pages` (v0.1.4 predates it; CI can reach the releases since 2026-11-11, `ESSENS_TOKEN`) and the README link once the site is live
- **Decision:** [0049 — A docs site rendered from the Markdown by Essens](../decisions/0049-docs-site-from-markdown.md)
- **Depends on:** none.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Decision 0049: the Markdown stays the source; Essens renders
it; a script of ours adds navigation and a template; GitHub Pages
publishes it.

**Where.**  `essens.yaml` (new, repository root), `docs/site.py` (new),
`docs/site/` (the vendored base stylesheet and KaTeX with their
licences, and `site.css`, ours), `.github/workflows/docs.yml`
(new), `docs/integrations/essens.md`, the three files with
`<placeholder>`s, `CONTRIBUTING.md` (how to build the site).

**Do.**
1. **Fix what GitHub strips today:** the `<fitting>` (task 0129),
   `<pcf>` (task 0125) and `<level>` (VOLUNTEERS.md, from its generator)
   placeholders: write them so GitHub shows them (e.g. in a code span or
   *FITTING*).  Fix the generator, not only its output.
2. **`essens.yaml`:** `folder-pages: [RESULTS]`, the bibliography
   (`docs/references.bib`), `render.html.pictures: linked`.
3. **`docs/site.py`:** render every tracked `.md` outside `hexmesh/` and
   `tests/` in one Essens call into a build folder; wrap each page in
   the template (site title, a sidebar from the doc tree with a short
   hand-kept order for the top level, the page's own headings, the
   stylesheet); point links to files that aren't docs at their GitHub
   URL for the current commit; fail on an error-level Essens diagnostic
   and on a broken relative link or anchor (the check the scratch render
   used).  Pure Python, no new dependency.
4. **Styles** (decision 0049, item 5): vendor simple.css (or Pico's
   classless build, saying why under *Agent notes*) and KaTeX at exact
   versions, with their licences and the versions in
   `docs/integrations/essens.md`; `site.css` for the sidebar, wide
   tables, `width=` images, print and Essens's classes; the template
   replaces Essens's KaTeX CDN links with the local copy.  Check a page
   in light and dark mode, at phone width, and in print preview.
5. **Workflow:** on push to `main`, pin an Essens release archive
   (record the version in `docs/integrations/essens.md`), run
   `docs/site.py`, deploy to GitHub Pages.  Full history isn't needed
   (no Essens history features).
6. **Docs:** CONTRIBUTING says how to build and preview the site
   locally; README links it once it's live.

**Accept.**
- The site builds locally and in CI with no error-level diagnostics and
  no broken relative link or anchor; no request leaves the site at view
  time (no CDN); light, dark, phone width and print checked.
- No `.md` file needs Essens-only syntax; the doc tests pass unchanged.

**For Essens** (its session asked, 2026-11-10: Essens ships no site
template for now and will revisit from what a project needs): *Outcome*
lists what `docs/site.py` ends up doing beyond Essens's render (nav,
template, link rewriting, KaTeX swap, checks), each with its line count;
the design session passes it on.

**Out of scope.**  `.ess` sources; Essens history features; search (a
follow-up if wanted).

## Agent notes

- **Template instead of wrapping.**  Essens 0.1.4's `--template FILE`
  replaces the whole page, `<head>` included (`&[textus]`, `&[toc]`), so
  `docs/site/page.html.tmpl` loads our CSS and KaTeX directly: there is no
  KaTeX swap step.  The template's `@@TITLE@@`, `@@ROOT@@`, `@@NAV@@`,
  `@@SOURCE@@`, `@@SOURCE_PATH@@` and `@@COMMIT@@` pass through Essens and
  `docs/site.py` fills them per page.
- **`--template` on the command line**, not in `essens.yaml`: 0.1.4
  reads the yaml key as a template name only (`essens.md`; reported to
  the Essens session).
- **simple.css, not Pico:** 8.7 kB, no external requests, and its
  variables were enough (`essens.md`).  `site.css` undoes two of its
  element styles: `<article>` as a card, `<aside>` floated at 30 %.
- **The placeholders (step 1):** task 0125 had two `<PCF type>`, one
  across a line break that a line `grep` misses (Essens's lint found it);
  task 0129 one `<fitting>`; VOLUNTEERS.md's `<level>` came from
  `validation/helical_pipe/volunteer.json`.  The generator
  (`validation/volunteer.py` `render`) now refuses a raw `<word>` outside
  code and HTML comments (`_raw_placeholders`, tested); it caught nothing
  else.  Also fixed: `docs/integrations/essens.md`'s unquoted
  `[[eq-width]]` (a `DanglingReference` warning).
- **Lint is read as one JSON array.**  The first version parsed it line
  by line and silently missed two of three warnings; it now fails if the
  output isn't JSON.
- **The sidebar:** a hand-kept top level with short labels (`TOP` in
  `site.py`), then one folded group per folder (Decisions, Tasks,
  Integrations, Validation cases, More), titled by each page's `<h1>`.
  `CLAUDE.md` is left out (agent instructions, not docs).
- **Checks (step 4):** Chromium headless, served from
  `python3 -m http.server`: RESEARCH (KaTeX inline and display maths) at
  1400 px light and dark, GUIDE at 390 px (phone) dark, RESEARCH printed
  to PDF, GALLERY at 1400 px.  Fixed after the first look: the contents
  column squeezed by simple.css's `aside`; the nav filling a phone's
  first screen (now a wrapped row); the header printed; long citation
  keys overflowing the contents column.  No page references a CDN
  (`grep` for `cdn.`, `jsdelivr`, `googleapis` in the build: none).

## Questions for design

## Design answer (2026-11-11, the user: "Wait for a release")

The v0.1.4 release predates `folder-pages`, and Essens has no newer
release for now (its CI billing comes first; no date).  Options were:
wait; `id:` front matter in the 34 same-named files (shown by GitHub,
against decision 0049's plain Markdown); or publishing a locally built
site to a `gh-pages` branch.  **Wait:** the workflow, Pages ("GitHub
Actions" source) and `ESSENS_TOKEN` are in place, and the site goes live
with `ESSENS_VERSION` bumped to the first release that has
`folder-pages`, then the push and pull-request triggers and the README
link.  The Essens session says when a release exists.

## Outcome
