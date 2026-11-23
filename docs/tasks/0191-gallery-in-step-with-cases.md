# 0191 — The gallery in step with the cases: regenerate, fix the printed path, and a test that catches drift

- **Status:** ready
- **Decision:** none needed (keeps decision 0057 rule 4's tables true)
- **Depends on:** 0178 (done).
- **Blocks:** none.  Worth doing before 1.0: the gallery is the public
  face of validation.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0178 found the gallery behind the cases.
`docs/gallery/VALIDATION.md` counts 13 cases and 1 export check, but
there are 14 and 3.  `build.py --validation <case>` prints FEniCSx's old
path, though it writes the right file.  Nothing tests that the gallery
matches `validation/`, so it drifted silently, as the agent file did
before its stale test.

**Do.**
1. **Regenerate** the gallery's pages with `docs/gallery/build.py`.
   Pass whatever flags keep renders that haven't changed (say which).
   Check the landing page's counts, VALIDATION's two tables, and
   FEATURES' *Validated by*.
2. **The printed path:** `build.py` prints the path it writes, through
   `validation/tools/cases.py`, for both kinds.
3. **A stale test, cheap** (no meshing, no renders):
   - the case and export-check names and statuses, as the gallery
     pages state them, match `validation/*/case.json` and
     `validation/exports/*/case.json`;
   - so do the counts on the landing page.
   If `build.py` can produce the text without renders, compare against
   that.  Otherwise parse the pages.  It must fail on today's stale
   pages, so show that before regenerating.
4. **The local check:** if regeneration is cheap enough, add "gallery
   current" to `tools/local_check.py`; otherwise only the test.
5. CHANGELOG *Unreleased* (Docs): one line.

**Accept.**
- The pages match the cases.
- The test fails on the stale pages and passes on the new ones.
- The printed path is right.

**Out of scope.**  Redesigning the gallery.

## Agent notes

## Questions for design

## Outcome
