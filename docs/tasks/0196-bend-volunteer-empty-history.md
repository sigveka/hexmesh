# 0196 — The bend's volunteer run crashes when a history series has no rows

- **Status:** ready (the user to place it against 0186; the design
  session suggests first)
- **Decision:** [0044](../decisions/0044-volunteer-runs.md) (volunteer
  runs), [0055](../decisions/0055-cards-for-every-case-ci-without-openfoam.md)
- **Depends on:** none.
- **Blocks:** the bend's volunteer card (0190) in practice: the tag
  `volunteer-bend-1` crashes on this path.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user ran the bend's card on Windows (2026-11-26, tag
`volunteer-bend-1`, `python -m validation.volunteer run --np 16 <dir>`).
The source level's steady start completed: 2000 steps, K 0.2595,
f +0.0077, 0.28 h.  Then `transient_run` crashed in `histories`
(`validation/turbulent_bend/run.py`, line 779 at the tag):
`IndexError: too many indices for array: array is 1-dimensional, but 2
were indexed`.

**The cause** (the design and coding sessions, confirmed in the code):
- `_history` returns `np.array([])`, a 1-D array, when a series has no
  rows.  `p1[:n, 0]` then fails even with `n == 0`.
- `histories` has three call sites in `transient_run`:
  - the loop's top (line 941 at the tag), guarded only by
    `postProcessing` existing;
  - after each pimpleFoam chunk (961), where `steadiness(h)` and
    `h["k_bend"][-1]` are unguarded;
  - the final call (970).
- `postProcessing` can exist with an empty series before the first
  chunk has written a row: after a chunk that crashed or was
  interrupted, on a resume, or if a copied directory carries it.

**Do.**
1. **`_history`** returns a 2-D array, `(0, k)`, when there are no rows.
2. **`histories`** returns `None` when any of pBefore, pAfter or lda has
   no rows (`n == 0`).
3. **The call sites:**
   - **the loop's top:** `None` means "no history yet": run the next
     chunk.
   - **after a chunk, and the final call:** `None` is a clear error,
     not a silent loop.  The message names the chunk's start time,
     which series wrote no rows, and the log to read, for example:
     "the chunk from t = … wrote no pBefore/pAfter/lda rows; see
     log.pimpleFoam.<t>".  A chunk that ran yet wrote nothing is the
     real fault, and the message should point the user at it.
4. **Find why the user's first chunk left no rows**, from what they send:
   the listing of `source/transient/postProcessing` and the tail of the
   `log.pimpleFoam.*` files.  The design session forwards them.  If it's
   a Windows/Docker cause, record it in `docs/integrations/platforms.md`
   or `openfoam.md`.
5. **Resume:** say whether a run directory left by the crash can be
   resumed on the fixed code, keeping the steady start (`start.json`),
   and what the user must do, if anything.  Test it: a run directory
   with `start.json` and an empty `postProcessing` resumes into the
   first chunk.
6. **Tests** (no OpenFOAM):
   - an empty `volFieldValue.dat`;
   - a missing `lda` series;
   - a header-only file;
   - the error path after a chunk.
7. **The tag:** `volunteer-bend-2` on a `main` commit with the fix,
   with the user's OK.  `VOLUNTEERS.md` and the card point to it.
   `volunteer-bend-1` stays, as tags are fixed, but the docs say to use
   `-2`.
8. **Other drivers:** check the helical and junction drivers' history
   readers for the same 1-D trap, and fix them alike if present.
9. CHANGELOG *Unreleased* (Fixed): one line.

**Accept.**
- The tests pass, and a resumed run directory starts its first chunk.
- A chunk without rows fails with the message.
- The tag is pushed with the user's OK.
- The cause of the user's empty first chunk recorded, or "not
  reproduced", with what was checked.

**Privacy.**  The user's paste had a local path in it.  No local path
goes into commits, task files or messages (the repository is public).

## Agent notes

## Questions for design

## Outcome
