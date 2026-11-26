# 0196 — Volunteer runs under NumPy 2 write `np.float64(…)` into OpenFOAM dictionaries; the bend's run then crashes on an empty history

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

**The root cause, found 2026-11-26 from the user's log.**  The first
pimpleFoam chunk never ran.  Every rank stopped at once with:

```
--> FOAM FATAL IO ERROR: (openfoam-2406)
file: stream/functions/lda/probeLocations at line 0.
    From Foam::Istream& Foam::operator>>(Istream&, doubleScalar&)
```

- `_pimple_control` writes the probes as `f"({x!r} {y!r} {z!r})"` over
  a NumPy array (`validation/turbulent_bend/run.py`).
- Under **NumPy 2**, `repr(np.float64(0.1))` is `np.float64(0.1)`, which
  OpenFOAM can't read.
- The volunteer's venv gets NumPy 2 from pip.  This machine's
  `python3` has NumPy 1.26.4, where the repr is `0.1`, so every local
  run, the local check and 0190's checks passed.  CI has NumPy 2 but no
  OpenFOAM, so it never wrote this dictionary.
- The empty history (below) is the second failure, caused by this one.

The same pattern is elsewhere: `{…!r}` into OpenFOAM text in
`validation/mms/run.py` (the wave numbers `w[i]`),
`validation/helical_pipe/run.py`, `turbulent_pipe`, `square_bend`, and
possibly the library's writers.  It is harmless for Python floats and
broken for NumPy scalars under NumPy 2.

**Do.**
0. **The root cause first:**
   - one number formatter for OpenFOAM text, e.g. `of.num(x)` returning
     `repr(float(x))`, used for every value written into a dictionary;
   - `git grep` for `!r}` and `repr(` in `validation/` and
     `hexmesh/study/`, and fix every place that can see a NumPy scalar;
   - **a test that runs under NumPy 2, in CI:** build each driver's
     dictionaries without OpenFOAM (the writers are plain Python), and
     assert no `np.` and no `float64` in the text.  At least the bend's
     controlDict with probes, MMS's source terms and the helical
     driver's vectors;
   - record the NumPy 1 → 2 repr change, and the fact that this
     machine's `python3` has NumPy 1.26 while users get 2, in
     `docs/integrations/platforms.md`, with versions and date;
   - **the local check** should run in an environment with the pip
     dependencies users get (a venv), or at least report NumPy's
     version, so this class shows up before a tag.  Propose which under
     *Questions for design* if it's more than a few lines.
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
4. **Why the user's first chunk left no rows:** found (above): the
   probes' NumPy 2 repr.  Check after the fix that the same run
   directory gets past the first chunk.
5. **Resume:** say whether a run directory left by the crash can be
   resumed on the fixed code, keeping the steady start (`start.json`),
   and what the user must do, if anything.  `write_transient` is cached
   by `zones.json`, so a resumed directory keeps the broken controlDict
   unless the fix rewrites it.  Make the resume rewrite it, or tell the
   user which two items to delete.  Test it: a run directory
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
- No NumPy scalar reprs in any OpenFOAM text, tested under NumPy 2
  in CI.

**Privacy.**  The user's paste had a local path in it.  No local path
goes into commits, task files or messages (the repository is public).

## Agent notes

- **Steps 1-3** in `validation/turbulent_bend/run.py`: `_history`
  returns `(0, 0)` with no rows (the width isn't known without one);
  `empty_series` names the series with none (`HISTORIES`: `SERIES` was
  taken, the GCI quantities); `histories` returns None while any is empty.
  The loop's top already took None as "no history yet".  After a chunk:
  `SystemExit` "[source] the chunk from t = <t> wrote no pBefore/pAfter/lda
  rows; see transient/log.pimpleFoam.<t>"; the final call alike.
- **Step 4, where the empty series came from:** `write_transient`
  copies only `constant/`, so `postProcessing` was written by a chunk.
  A pimpleFoam that constructs its function objects (they write their
  file headers) and then fails before its first step leaves header-only
  files: likely the user's first chunk.  Waiting for the user's log tail
  (via the design session) to confirm the cause.
- **Step 5, resume:** yes.  The user checks out `volunteer-bend-2` in
  their clone (`git fetch --tags`, `git checkout volunteer-bend-2`) and
  runs the same `python -m validation.volunteer run --np 16 <dir>`:
  `start.json` keeps the steady start (0.28 h), the loop sees no history
  and runs the first chunk.  If that chunk fails again, the new message
  names its log.  Tested with a stand-in solver.
- **Step 7:** both cards that name the tag (the bend's, and the
  Poiseuille try-out's) say `volunteer-bend-2`; the bend's note says not
  to use `-1`.  Nothing under `hexmesh/` changed since `volunteer-bend-1`,
  and in the bend driver only this fix, so the mesh hashes are the same.
- **Step 8:** the helical driver keeps its history in JSON, and the
  junction driver reads logs and fields: neither reads function-object
  series, so neither has the trap.
- **Tests** (`tests/test_bend_history.py`, 7): rows; an empty file, a
  header-only file and a missing series give None; no rows is 2-D; a
  crashed level resumes into its first chunk without redoing the steady
  start; a chunk without rows stops with the message.

## Questions for design

## Outcome
