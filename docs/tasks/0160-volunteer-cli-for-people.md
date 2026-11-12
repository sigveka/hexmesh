# 0160 — The volunteer command line, for people: names checked first, a readable `list`, help with the commands

- **Status:** ready
- **Decision:** none new; [0044](../decisions/0044-volunteer-runs.md)
  (volunteer runs).  The user, 2026-11-13: a volunteer run "did not
  recognize the documented case name. The output from the 'list' option
  and '-h' is not user friendly still".
- **Depends on:** none.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Found by the design session, 2026-11-13, on `main`, the same
on the tag `volunteer-helical-1`:

| typed | got |
|---|---|
| `prepare helical_pipe re3000 --dir run/` | the runner is looked for first; then a traceback, `ValueError: helical_pipe has no level 're3000': re<1800\|2400\|3000>_n<8\|12\|16\|24>`, which lists levels the card doesn't offer (only `re3000_n24`) |
| the same, no OpenFOAM found | a `StudyError` traceback about the runner; the level is never checked |
| `run helical_pipe re3000_n24` | `unrecognized arguments`: `run` takes the run directory, but the help lists it beside `prepare` with no hint |
| `-h` | the description stops at "From the repository root::" (the reST literal block is dropped) |
| `list` | Markdown tables, each row a paragraph of evidence: unreadable in a terminal |

And `VOLUNTEERS.md` says both "`git clone --branch <tag>`" and, in the
card, "git checkout volunteer-helical-1 before prepare".

**Do.**
1. **Names first.**  `prepare` (and `check`, wherever a case or level is
   named) checks the case and the level against the **card** before
   anything else: before the runner, OpenFOAM or gmsh.  A wrong name
   prints one line and exits 2, no traceback:
   `unknown level 're3000' for helical_pipe; did you mean 're3000_n24'? Levels: re3000_n24.  See: python3 -m validation.volunteer list`
   (`difflib.get_close_matches`).  The same for the case.
2. **No tracebacks for a person's mistake.**  `StudyError` and the name
   errors become one-line messages with exit 2 at the CLI's top level.
   A real bug still shows its traceback.
3. **`list` for a terminal:** per case, its title and, per level, one
   line each: cores, wall time, memory, disk, cells, and the exact
   `prepare` command to copy.  At most 100 columns.  The evidence moves
   to **`info <case> [<level>]`** (new), which prints today's detail as
   wrapped text, not Markdown tables.  `VOLUNTEERS.md` keeps its tables.
4. **`-h`:** the five commands as an epilog
   (`RawDescriptionHelpFormatter`), as `VOLUNTEERS.md` gives them.  Each
   subcommand's help says what it takes: `run DIR` "the directory
   `prepare --dir` made; job.sh calls this", `collect DIR`, `check FILE`.
5. **One instruction for the version:** the card's `note` and the
   generated "five commands" agree: `git clone --branch <the card's
   tag>`, nothing else.  Regenerate `VOLUNTEERS.md`.
6. **Reach the volunteers.**  A volunteer checks out the card's tag, so
   fixes on `main` don't reach them.  After 1–5:
   - `prepare helical_pipe re3000_n24 --mesh-only` on the fixed tree
     gives the same mesh hash as the card's.  If it doesn't, stop:
     *Questions for design*;
   - propose a new tag (`volunteer-helical-2`) at the fixed commit, and
     the card's `tag` updated to it.  **Making and pushing the tag needs
     the user's OK**; ask under *Outcome*.
7. **Tests** (`tests/test_volunteer.py`): each row of the table above
   gives a one-line message naming the fix, exit 2, no traceback, and
   none of them touches a runner (no OpenFOAM, no Docker needed); `list`
   lines are at most 100 columns; `-h` contains `prepare <case> <level>`.

**Accept.**
- The five mistakes above give the messages of steps 1–4 (shown under
  *Outcome*), and the tests pass on all CI jobs.
- `list` and `info` shown under *Outcome* as they print.
- The mesh hash matches, and the new tag is proposed to the user.

**Out of scope.**  The per-case `run.py` drivers (their `--help` is
fine) and a single `python3 -m validation` entry point; the design
session may propose one separately.
