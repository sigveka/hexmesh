# 0125 — PCF tees too short for their run: a hint a PCF user can act on

- **Status:** ready
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

## Questions for design

## Outcome
