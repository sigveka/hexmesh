# 0160 — The volunteer command line, for people: names checked first, a readable `list`, help with the commands

- **Status:** done
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

## Agent notes

- **The task file had no *Agent notes*, *Questions for design* or
  *Outcome* headings;** added here, as the template has them.
- **Step 1, refined: a level the driver builds but the card doesn't
  offer still prepares,** with today's note ("it has no stated
  requirements").  `check` needs it: a contribution may be a stored level
  (the tests use `re1800_n12`), whose mesh hash comes from the driver.
  So a level is checked against the card first, then against the driver
  (a new hook, `check_level(level)` in `helical_pipe/run.py`, raising
  `ValueError`; no gmsh, no OpenFOAM).  Only a level neither knows is the
  step 1 error, and it lists the **card's** levels, with the suggestion.
- **The error type:** `VolunteerError`, in `validation/volunteer.py`.
  `main` catches it and `StudyError` (with its hint after `;`): one line,
  `<prog> <command>: error: …`, exit 2.  The tool's own `SystemExit`
  messages (no OpenFOAM found, already prepared, not a prepared
  directory) became `VolunteerError` too, so every person's mistake exits
  2 the same way.  Anything else still shows its traceback.
- **`run` and `collect` given names** (row 3): they take a hidden
  `extra` positional, so `run helical_pipe re3000_n24` reaches the tool,
  which says what `run` takes and how to get the directory.  A bare case
  name as the directory, with no run state in it, gets the same message.
- **`check FILE` with no such file** was a `FileNotFoundError` traceback:
  now the one-line error.
- **`list`:** one line of cost per level (`~` marks an estimate), the
  `prepare` line to copy, and the card's `git clone --branch <tag>` line.
  **`info <case> [<level>]`:** the card as wrapped text, 100 columns at
  most, Markdown backticks and TeX `$` removed.
- **`-h`:** the commands come from the module docstring's block (one
  source), as an epilog; the description drops "(decision 0044; task
  0119)", which says nothing to a volunteer.
- **Step 5:** the card's note no longer says "git checkout": "clone this
  tag with git clone --branch, as in the five commands".  It doesn't name
  the tag (the card's `tag` field does), so a new tag won't need the note
  changed.  `VOLUNTEERS.md` regenerated: also the `list` comment, and a
  pointer to `info`.

## Questions for design

## Outcome

Done 2026-11-13.

- **Files:** `validation/volunteer.py` (`VolunteerError`,
  `offered_level`, `list_lines`, `info_lines`, `info`, the help, the
  top-level handler); `validation/helical_pipe/run.py` (`check_level`);
  `validation/helical_pipe/volunteer.json` (the note);
  `validation/VOLUNTEERS.md` (regenerated); `CHANGELOG.md`.
- **Tests:** `tests/test_volunteer.py` 26 → 38: each mistake one line,
  exit 2, no traceback, the runner never touched (7 cases); a runner's
  `StudyError` one line; a driver-only level still allowed; `list` and
  `info` at most 100 columns, no Markdown tables or TeX; `-h` and `run -h`;
  the card's note and the five commands agree.  Validation, volunteer,
  docs and architecture tests: 258 passed, 1 skipped.
- **The mistakes, as they print** (the task's second row, no OpenFOAM,
  gives the first message: names come first):

```text
$ python3 -m validation.volunteer prepare helical_pipe re3000 --dir run/
python3 -m validation.volunteer prepare: error: unknown level 're3000' for helical_pipe; did you mean 're3000_n24'? Levels: re3000_n24.  See: python3 -m validation.volunteer list
(exit 2)
$ python3 -m validation.volunteer prepare helical re3000_n24 --dir run/
python3 -m validation.volunteer prepare: error: unknown case 'helical'; did you mean 'helical_pipe'? Cases: helical_pipe.  See: python3 -m validation.volunteer list
(exit 2)
$ python3 -m validation.volunteer run helical_pipe re3000_n24
python3 -m validation.volunteer run: error: run takes the directory `prepare --dir` made, not 'helical_pipe re3000_n24': python3 -m validation.volunteer prepare <case> <level> --dir run/ makes it, and bash run/job.sh (or sbatch) runs it
(exit 2)
```

  `collect helical_pipe`, `run <missing dir>` and `check <missing file>`
  likewise; `-h` ends with the commands (`prepare <case> <level> --dir
  run/` …), and `run -h` says "the directory `prepare --dir` made; job.sh
  calls this".
- **`list`** (84 columns):

```text
helical_pipe: Laminar flow in a helical pipe
  hexmesh: git clone --branch volunteer-helical-1 https://github.com/sigveka/hexmesh
  re3000_n24: 4 cores, ~12 h, 3.6 GB memory, 2.4 GB disk, 2,711,232 cells
    python3 -m validation.volunteer prepare helical_pipe re3000_n24 --dir run/
  more: python3 -m validation.volunteer info helical_pipe

~ estimated, not measured.  Everything else: validation/VOLUNTEERS.md
```

  **`info helical_pipe`** prints the summary, the versions, each
  requirement with its basis and source, the gates and what is sent back,
  wrapped at 100 columns.
- **The mesh hash** (`prepare helical_pipe re3000_n24 --mesh-only`, gmsh
  4.12.1, one at a time, about 6.5 min and 3.4–3.6 GB each):
  `0a420c64bffbae7d5adcf17e447125943a85cc91defb2b7969b893984c60a1d9` at
  `volunteer-helical-1` (de1d477), at 33fb4c4, and at the fixed 58cb459.
  The same, so a new tag pins the same mesh.
- **The new tag:** CI green on eca7352 (run 43387708118, all 8 jobs,
  including 58cb459).  07b12bd sets the card's `tag` to
  `volunteer-helical-2` (`VOLUNTEERS.md` regenerated), and the annotated
  tag `volunteer-helical-2` is on it, both pushed 2026-11-13 at the
  user's "yes".  `volunteer-helical-1` is unchanged, for anyone already
  on it.
- **Checked from GitHub:** `git clone --depth 1 --branch
  volunteer-helical-2` gives 07b12bd; its `list` prints the
  `volunteer-helical-2` clone line, and `prepare helical_pipe re3000`
  gives the one-line error, exit 2.  The clone was deleted.

