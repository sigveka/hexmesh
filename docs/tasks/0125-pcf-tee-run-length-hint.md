# 0125 — PCF tees too short for their run: a hint a PCF user can act on

- **Status:** done
- **Decision:** [0042 — The road to 1.0](../decisions/0042-road-to-1-0.md) (every user-facing error coded, with a hint a user can act on; task 0106's rules)
- **Depends on:** 0122 (done).  Step 1 for equal tees is done in 0122's follow-up (the
  coding session, at the user's request, 2026-11-10); extend it to the
  other cases here.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0122: a PCF equal tee under thick insulation fails with
`run_length_too_short`, and the hint is the Python one: "run_length >
X, or run_length=None to resolve it".  A PCF user has no `run_length`;
they have a TEE component with end points in a file.  The same holds for
reduced tees and duct taps read from PCF.

**Where.**  `hexmesh/interchange/build.py` (where a PCF part's
`AssemblyError` reaches the user), `tests/test_pcf_*.py`, GUIDE's PCF
section if it quotes the error.

**Do.**
1. When a fitting built from a PCF component raises
   `run_length_too_short` (or `branch_length_too_short`), re-raise with
   the same code and a PCF hint: the component (as the importer already
   names it, e.g. its line or ID), the run (or branch) it has and the one
   it needs, in metres, and what to change in the file ("a TEE with
   END-POINTs at least X m from its CENTRE-POINT", or less insulation).
   The Python hint stays for Python callers.
2. Check every other error a PCF build can pass through for a hint
   naming a Python field; list them in *Agent notes* and fix the ones a
   PCF user can hit, the same way.

**Accept.**
- A PCF equal tee with 0.5 R insulation fails with a hint naming the
  component and the lengths in the file's terms (test).
- No hint reaching a PCF user names a Python-only field (test over the
  codes found in step 2).
- Meshes unchanged; full suite: no new failures.

**Out of scope.**  Lengthening tees automatically (changing the plant's
geometry is the user's call).

## Agent notes

- **Step 1.**  Task 0122's follow-up (ecf16cc) already rewrote the two
  length hints for every junction a PCF build checks (reduced tees, duct
  taps, equal tees, Y pieces), but in generic words ("the file's
  component measures … from its centre to each run end"), which was also
  wrong for a Y piece (its run is the stem, which the importer sizes
  itself).  Now the hint names the component's own points, by junction
  kind: a TEE's END-POINTs or BRANCH1-POINT, a Y piece's BRANCH1- and
  BRANCH2-POINTs; how far they are from its CENTRE-POINT; how far the
  junction needs them; and "a longer <PCF type>, or thinner insulation".
  The component and its line were already in the message ("component 1
  (TEE TEE_1 at …, net.pcf:7)").  The Python hint is unchanged.
- **Which forms reach the length codes** (probed): a TEE (run and
  branch), a set-on's branch (its run is sized by the importer:
  `seton_host_too_short` already speaks of the host pipe), a Y piece's
  branches (its stem: `ypiece_stem_too_short`, already in file terms).
- **Step 2, every hint a PCF build can pass through** (`grep` of every
  `hint=` in `hexmesh/assembly`, `core`, `interchange`, then each one
  traced):
  - fixed here: `run_length_too_short`, `branch_length_too_short`;
  - `interchange/` itself: no hint names a Python field
    (`tee_branch_angled` names `to_assembly(inlet=…)`, the call a PCF user
    makes);
  - spec hints (`nrad=`, `mprg=`, `nang=`, `.core(…)`): reached only
    through the `PipeSpec` the user passes to `to_assembly`, i.e. from
    Python: left as they are;
  - `n_layers` hints (`twist_per_layer_above_maximum`,
    `profile_chords_too_coarse`, `switch_too_short`): a PCF build leaves
    `n_layers` to the assembly, and builds no profile or H transition:
    not reachable;
  - `Tee(branch=, face=)` / `face=, roll=` (duct-tap hints): need a
    rectangular spec, from Python;
  - **not fixed: after the build.**  `validate()` and `mesh()` run on the
    built assembly, outside `build.py`'s wrapper, so the reduced tee's
    predicted-SJ tier reaches a PCF user in Python's terms: probed, a
    TEE with a 50 mm branch on a 100 mm main warns "no run_length reaches
    it: the branch ratio r/R 0.5 limits the junction core", and below
    `PREDICTED_SJ_MIN` it is `predicted_sj_below_minimum` with the hint
    "run_length X or more reaches it (now Y)".  Question 1.
- The error *messages* still name the field ("run_length must exceed
  …"), as `where["field"]` does; the task asks for hints only, so they
  stay.
- Tests (`tests/test_pcf_robustness.py`): the insulated equal tee (0.5 R
  insulation, run and branch: the acceptance case) and the step-2 codes
  on a reduced tee's run and branch and a Y piece's branches; the
  0122-follow-up test updated to the new wording.  The PCF test files
  pass (73 passed, 1 skipped); the full suite waits for the Re 3000
  run.

## Questions for design

1. **The predicted-SJ hints after the build.**  A reduced tee's
   `validate()` tier (a warning, or `predicted_sj_below_minimum`) names
   `run_length` (`tee.py` `_quality`), and reaches a PCF user after
   `to_assembly`.  `build.py` can't rewrite it: it isn't raised there.
   Options:
   - **(a) Neutral words in `tee.py`** (recommended, the simplest): "no run
     length reaches it" and "a run of X m or more each side of the centre
     reaches it (now Y)".  Both audiences can act on it; the Python hint
     loses the literal field name (three tests' regexes change).
   - (b) The edge built from a file carries its source already
     (`origin`); the assembler could rewrite the hint of a fitting built
     from a file, through a translation table in `interchange`.  More
     machinery, for one tier today.
   - (c) Leave it: a warning a PCF user reads with the GUIDE's help.
   Everything else in the task is done; 0125 waits only on this.

## Design answer (2026-11-10, the user: "yes")

Q1: option (a).  Plain words in `tee.py` for everyone: "no run length
reaches it" and "a run of X m or more each side of the centre reaches it
(now Y)".  Codes unchanged; the tests' regexes and CHANGELOG follow.

## Outcome

**Status:** done.

- **Step 1:** a PCF junction too short for its layout hints with the
  component's own points: a TEE's END-POINTs or BRANCH1-POINT, a Y
  piece's BRANCH1- and BRANCH2-POINTs; how far they are from its
  CENTRE-POINT, how far the junction needs them, and "a longer <PCF
  type>, or thinner insulation if it is insulated"
  (`hexmesh/interchange/build.py` `_file_length_hint`).  The message
  already named the component and its line.
- **Step 2:** the survey is in *Agent notes*.  Fixed at build: the two
  length codes.  Fixed for everyone (design's answer): the reduced tee's
  predicted-SJ tier, the one hint reaching a PCF user after the build
  (`tee.py` `_quality`).  Error messages and `where["field"]` still name
  the field, as the task asks for hints only.
- **Tests:** `tests/test_pcf_robustness.py`: the insulated equal tee
  (0.5 R, run and branch) and the step-2 codes on a reduced tee's run
  and branch and a Y piece's branches; five regexes in `test_tee.py` and
  `test_io_readers.py` follow the wording.  The full suite is in task
  0123's run (the two were committed together).
- **Files:** `hexmesh/interchange/build.py`, `hexmesh/assembly/tee.py`,
  the tests above, `docs/GUIDE.md` (PCF section), `CHANGELOG.md`.
- **Meshes:** unchanged (hints only).
