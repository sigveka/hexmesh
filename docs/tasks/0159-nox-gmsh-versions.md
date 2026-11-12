# 0159 — Local test sessions against both gmsh versions (`nox`)

- **Status:** ready
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

## Questions for design

## Outcome
