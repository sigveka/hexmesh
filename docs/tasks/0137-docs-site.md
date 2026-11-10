# 0137 — The docs site: Essens pages, our navigation and template, GitHub Pages

- **Status:** ready (the CSS strategy settled 2026-11-10)
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

## Questions for design

## Outcome
