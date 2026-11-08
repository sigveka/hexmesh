# 0113 — Python 3.11 is the oldest supported; CI green again

- **Status:** in progress (all but CI on main, which needs the push)
- **Decision:** [0039 — Platform support](../decisions/0039-platform-support.md), amendment 2026-11-08 (the Python floor)
- **Depends on:** none.  Before the launch post; first in the queue.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Python 3.10 reached its end of life in October 2026, and the
user has dropped it.  The last two CI runs (42466812439, 42468603272)
failed on `windows-latest, Python 3.10` in `actions/setup-python`, so
CI is red on main while the repository is public.

**Where.**  `pyproject.toml`; `.github/workflows/tests.yml`;
`README.md` (badge, install); `docs/GUIDE.md`;
`docs/integrations/README.md`, `docs/integrations/platforms.md`;
`tests/test_readme.py`; `CITATION.cff` if it names Python;
`CHANGELOG.md`.

**Do.**
1. **Read the failing step's log** (`gh run view 42468603272 --log-failed`,
   or the job log through `gh api`) and record why setup-python failed in
   `docs/integrations/platforms.md`, with the date.  If it isn't 3.10
   being unavailable, say so under *Questions for design*: the drop
   stands either way, but the CI cause matters.
2. **The floor:** `requires-python = ">=3.11"`; the CI matrix
   `["3.11", "3.x"]`, with the comment updated.
3. **3.10-only code:** remove what exists only for 3.10 (e.g. the
   `tomllib` workaround in `tests/test_readme.py:143`).  Search for
   others (`sys.version_info`, `tomli`, `typing_extensions` for
   3.11 features) and list what you removed.
4. **Docs:** every "Python ≥ 3.10" and "Python 3.10 and 3.x" in user
   docs and the integrations notes becomes 3.11 (the badge in README.md
   included).  Historical records (decisions, tasks, CHANGELOG entries
   already released, `gmsh.md`'s dated measurements) stay as written.
5. **CHANGELOG:** under *Unreleased*, "**Breaking:** Python 3.10 is no
   longer supported (end of life, October 2026); 3.11 is the oldest."

**Accept.**
- The `tests` workflow passes on all six jobs plus OpenFOAM Docker, on
  main.
- `grep -rn "3\\.10"` over user docs, `pyproject.toml` and the workflow
  finds nothing but historical records (list them).
- The cause of the setup-python failure is recorded.
- Full suite: no new failures.

## Agent notes

- **Step 1, the setup-python failure:** a 504 from GitHub's Python
  download, not a missing 3.10.  Both runs (42466812439 and
  42468603272) failed the same way.
  - 3.10 wasn't in the Windows runner's tool cache, so `setup-python`
    downloaded `python-3.10.11-win32-x64.zip` and got `Unexpected HTTP
    response: 504` three times.
  - The macOS and Linux jobs at 3.10 set it up and passed.
  - Recorded in `docs/integrations/platforms.md`.  The drop stands (the
    user's call, end of life); see *Questions for design*.
- **CI was also red for another reason**, mine: every job of runs
  42476909094 (0108) and 42478255352 failed
  `test_would_invert_reads_the_written_msh`.
  - My test wrote `.msh` coordinates with `{x!r}`, which NumPy 2 (what
    CI installs) prints as `np.float64(0.0)`.  This machine has NumPy
    1.26, so it passed here.
  - Fixed: `float(x)` on `.tolist()` values.  Also in `platforms.md`.
- **And a flaky old test:**
  `test_interchange_operations.py::test_two_sheets_merged_and_joined_build_as_one_read`
  (task 0066) failed on ubuntu 3.x in run 42478255352.
  - Its `_canonical` drops the log's times, but an import's provenance,
    inside its arguments, carries a `time` too.  So the test fails when
    the two reads straddle a second.
  - Fixed: `_timeless` drops `time` at any depth.
- **3.10-only code:** one site, `tests/test_readme.py`'s regex read of
  `pyproject.toml`, now `tomllib`.  Searched for `sys.version_info`,
  `tomli`, `typing_extensions` and 3.11-only features worked around:
  nothing else.
- **What `grep -rn "3\.10"` still finds** (user docs, `pyproject.toml`,
  the workflow and the integrations notes; all historical, or about
  dropping it):
  - `CHANGELOG.md:5`, the new breaking-change line;
  - `docs/integrations/platforms.md:21`, the cp1252 finding on the
    runners "(Python 3.10 and 3.15)", task 0092's dated measurement;
  - `docs/integrations/platforms.md`, the new setup-python entry;
  - `docs/integrations/gmsh.md:422`, task 0092's dated failure counts;
  - and outside the grep's scope, decisions 0039 and the tasks.

## Questions for design

1. **Decision 0039's amendment assumes** "that the runner image no
   longer provides 3.10" (marked *assumed, not verified*).  The log says
   otherwise: 3.10 was available, and its download hit a 504.  The drop
   stands as the user's decision, but the amendment's context may want
   that sentence corrected.  I haven't touched it (decisions are
   design's).
   - **Answered (design, 2026-11-08, ccb3775):** the amendment now gives
     the logged cause (the 504) and the NumPy 2 bug, and the drop rests
     on end of life alone.  Closed.

## Outcome

- **Files:**
  - the floor: `pyproject.toml` (`>=3.11`), `.github/workflows/tests.yml`
    (`["3.11", "3.x"]`);
  - the docs: `README.md` (badge, install line), `docs/GUIDE.md`,
    `docs/integrations/README.md`, `docs/integrations/platforms.md` (the
    versions, and the two CI causes);
  - `CHANGELOG.md`;
  - tests: `tests/test_readme.py` (`tomllib`), `tests/test_openfoam_runner.py`
    (the NumPy 2 fix), `tests/test_interchange_operations.py` (the flaky
    comparison).
- **Tests:** the five affected files, 184 passed; the full suite 3736
  passed, 15 skipped (2026-11-08).
- **CI green on main:** pending the push.
