# 0172 — The docs site on the next Essens release: layouts, MathML, no KaTeX

- **Status:** ready (step 1 now; steps 2–7 when a release after v0.1.4
  is out)
- **Decision:** [0049](../decisions/0049-docs-site-from-markdown.md)
  (the site from the Markdown)
- **Depends on:** an Essens release after v0.1.4 (`gh release list
  --repo Essens-lang/essens`).  Step 1 doesn't.
- **Blocks:** 1.0 (decision 0042 note 2026-11-28; the user: "Doc site will be updated").

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `essens describe` on the local build (2026-11-17,
`docs/integrations/essens.md`, the section "The local build after
0.1.4") shows changes that break or obsolete parts of the site build:
- `--template` is refused for `--layout`, so `python3 docs/site.py`
  fails with the local build today;
- HTML math is MathML with no script, which leaves the vendored KaTeX
  unused;
- `--linked` replaces `--pictures linked`, and each page carries
  Essens's own stylesheet;
- `folder-pages` works, fixing v0.1.4's duplicate-id lint failure.
CI pins v0.1.4, so nothing is broken there yet.  The next release
carries these changes.

**Do.**
1. **Now:** CONTRIBUTING's *The docs site* says which Essens builds the
   site: the v0.1.4 release archive (the link and the pin in
   `.github/workflows/docs.yml`), not a newer source build, until this
   task's step 2 lands.  `docs/site.py` checks the version where it can.
   Since a source build also says `0.1.4`, it catches the
   `--template is now --layout` error and exits with a message naming
   the archive, not Essens's raw error.
2. **When the release is out:** read its `essens describe`.  Compare
   `contracts` with the 2026-11-17 values (all 1.0) and re-check the
   integration note's points against the release archive itself, not a
   local build (the lesson of 0137's `folder-pages`).
3. **Layout:** `docs/site/page.html.tmpl` becomes a layout
   (`layouts/site/html.layout` or a file path in `essens.yaml`'s
   `render.html.layout`).  Its `&[textus]` and `&[toc]` stay, and the
   `@@…@@` text `docs/site.py` fills stays.  Then `site.py` drops
   `--template`.
4. **Math:** render RESEARCH and the other pages with equations and
   count `MathNotConverted`.  Fix each equation in the Markdown so that
   it still reads on GitHub, or list it under *Agent notes* if it can't
   be.  Then remove `docs/site/vendor/katex/` and the template's KaTeX
   lines.  Record the size saved.
5. **Styles:** choose between Essens's stylesheet and `render.html.
   essens-style: none` (keeping simple.css and `site.css`).  Compare one
   page both ways, and write which and why under *Agent notes*.  Use
   `--linked` / `render.html.assets: linked` in place of
   `pictures: linked`.
6. **`folder-pages`:** confirm that lint passes on all `README.md` and
   `RESULTS.md` pages with the release.  If the docs workflow ran by hand
   only because of that failure or the private repository, say which
   still holds.
7. **Move the pin** (`ESSENS_VERSION` in the docs workflow), rebuild,
   and compare with the v0.1.4 site: page count, broken links (0), and
   a look at RESEARCH, the GUIDE and a validation page.  Update
   `docs/integrations/essens.md` (the new release's verified behaviour;
   the local-build section becomes history) and CONTRIBUTING.

**Accept.**
- Step 1: CONTRIBUTING names the archive; `site.py` gives a clear
  message with a newer build.
- Steps 2–7: the site builds with the new release, with no KaTeX, no
  `--template` and no error-level diagnostics; every link resolves;
  `MathNotConverted` is 0, or each one is listed; the pin is moved; the
  integration note matches the release.

**Out of scope.**  Changing the site's look beyond what the stylesheet
choice needs; a site theme from Essens; making the docs workflow run on
every push (it depends on Essens's repository being public).

## Agent notes

## Questions for design

## Outcome
