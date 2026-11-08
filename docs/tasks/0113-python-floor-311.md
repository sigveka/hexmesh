# 0113 — Python 3.11 is the oldest supported; CI green again

- **Status:** ready
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
