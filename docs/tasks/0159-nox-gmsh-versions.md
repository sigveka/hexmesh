# 0159 — Local test sessions against both gmsh versions (`nox`)

- **Status:** done
- **Decision:** [0052](../decisions/0052-ci-gates-main.md) (measure 3).
- **Depends on:** none.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0145's failure was gmsh 4.15.2 against 4.12.1.  CI runs
both; a change to junction or plate code should be checked against both
before it is pushed, in minutes rather than one CI cycle.

**Do.**
1. **`noxfile.py`**: sessions `tests-gmsh412` (gmsh 4.12.1) and
   `tests-gmsh-latest` (what `pip` installs), each in its own venv,
   taking pytest arguments (`nox -s tests-gmsh412 -- -k tee`).
2. **Disk and CPU** (CLAUDE.md): the venvs go under `.nox/` (git-ignored)
   or a path you choose; record their size.  Their docstring repeats
   CLAUDE.md's rule: check `pgrep -af pytest` before a run.
3. **CONTRIBUTING:** when to run them (changes under `hexmesh/assembly/`
   junction or plate code, `core/` surfaces), and the junction test set
   that 0145 used.
4. **Check:** both sessions pass the junction tests on the current tree;
   times and venv sizes under *Outcome*.

**Accept.**
- Both sessions run and pass the junction tests here.
- CONTRIBUTING says when to use them.

**Out of scope.**  Windows or macOS locally; CI covers them.

## Agent notes

- **nox isn't installed here; `uvx nox` runs it** (uv is), without
  touching the system Python.  CONTRIBUTING gives both `uvx nox` and
  `pip install nox`.  `venv_backend="uv|virtualenv"`: uv when present.
- **Install as CI does:** `pip install -e ".[dev,study]"`, then
  `gmsh==4.12.1` for the reference session (`tests.yml`'s pinned job).
- **The junction test set** wasn't written down anywhere, so I made it
  `JUNCTIONS` in `noxfile.py`: `test_tee`, `test_equal_tee`, `test_wye`,
  `test_duct_tap`, `test_tee_branch_grading`, `test_junction_quality`,
  `test_pcf_junctions`, `test_units` (task 0145's four failures were in
  the last three).  With pytest arguments after `--`, those replace the
  set.
- **`-n 2` first,** so a `-n` given after `--` wins (xdist takes the
  last).  `reuse_existing_virtualenvs = True`: a second run doesn't
  reinstall.

## Questions for design

## Outcome

Done 2026-11-14.

- **Files:** `noxfile.py` (new), `.gitignore` (`.nox/`),
  `CONTRIBUTING.md` (when to run them, the commands, the set).
- **Both sessions pass the junction tests here** (`uvx nox`, one after
  the other, nothing else running):

  | session | gmsh | result | wall time | venv |
  |---|---|---|---|---|
  | `tests-gmsh412` | 4.12.1 | 262 passed | 286 s | 374 MB |
  | `tests-gmsh-latest` | 4.15.2 | 262 passed | 252 s | 121 MB |

  Building both venvs took 25 s (uv, warm cache); `du` counts uv's
  hard-linked files once, so together about 0.5 GB.
- **Disk:** `.nox/` deleted after the check (CLAUDE.md); the next
  `uvx nox` rebuilds it.

