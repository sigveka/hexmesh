# 0202 — Validation: the Vattenfall T-junction, stage (b): the LES by a volunteer, and the comparison

- **Status:** ready (after 0120; the LES needs a volunteer or the
  maintainer's hardware)
- **Decision:** [0012](../decisions/0012-openfoam-validation-cases.md);
  [0044](../decisions/0044-volunteer-runs.md);
  [0042](../decisions/0042-road-to-1-0.md) note 2026-11-28 (before 1.0)
- **Depends on:** 0120 (the case, mesh, data, card, and the gates design
  fixes from its *Questions for design*).
- **Blocks:** 1.0.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user (2026-11-28) wants the three new cases with results
before 1.0.  The LES is too heavy for this machine (0120).

**Do.**
1. **Offer the card**, once design has fixed the gates.  List it in
   `VOLUNTEERS.md`, tag `volunteer-vattenfall-1` with the user's OK, and
   tell the user, who may run it on their own hardware.
2. **Check the contribution** with `python3 -m validation.volunteer
   check` (decision 0044): the machine record, the solver time, the
   averaging window against the card's.
3. **The comparison:** mean and RMS velocity and wall temperature
   against the gates fixed in 0120.  Report the report's best LES
   beside ours (Smith et al. 2011).  Store the level with its
   provenance, and write `RESULTS.md`.
4. **The case sheet** (task 0199's form), with the flow picture taken
   from the volunteer's slice if the card asks for one.  Make the card
   ask for one.
5. If the volunteer's run misses a gate, report the miss.  Then put the
   ladder's step 1–2 checks (decision 0058) under *Questions for design*,
   before anything is rerun.

**Accept.**  A checked contribution; the gates reported; RESULTS.md
and the sheet; the case in the validation tables.

## Agent notes

## Questions for design

## Outcome
