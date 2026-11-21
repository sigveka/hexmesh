# 0187 — The tee's miss, diagnosed: setup, a second code (code_saturne SST), a second model

- **Status:** ready (after 0186, which is the ladder's step 1)
- **Decision:** [0058](../decisions/0058-diagnosis-ladder-and-user-hints.md)
  rules 1–2
- **Depends on:** 0186 (the fixed-wall levels: this task runs at its
  mid level); 0181 (code_saturne set-up).
- **Blocks:** 1.0 (decision 0058 rule 4).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The tee (`junction_loss`, Div a, q 0.6) misses ξ_PG by about
0.1 with SST and with k–ε.  The user wants the cause found before 1.0,
by changing one thing at a time (decision 0058).

**Do.**  Use the level 0186 settles on as "the mid level" (k = 2 of
the fixed-wall family, unless 0186 says otherwise).  Each run records
ξ_PG and ξ_MGb with both pressure methods, y⁺, `wall_s` and `cores`.
1. **Step 2, setup:** one run per change, beside the base:
   - **inlet profile:** the precursor's developed profile vs. a uniform
     inlet.  The paper's set-up is in RESEARCH §7.2: say which it used;
   - **inlet length:** double the upstream run;
   - **outlet length:** double the downstream runs;
   - **outlet condition:** if the base fixes p at both outlets, the
     alternative the paper used (or a flow split held by a
     `flowRateOutletVelocity`), whichever is set out in RESEARCH §7.2.
   Report each change's shift in ξ_PG.  A change worth over 0.03 (the
   gate's width) "explains part"; under 0.01 "rules it out".
2. **Step 3, solver:** the base case in code_saturne, with the same mesh
   through `.unv` and k–ω SST.
   - Match the inlet (map the profile), outlets, fluid and Re.
   - **Wall functions:** code_saturne's are two-scale log laws, not
     Spalding.  Pick the nearest, and record the choice in
     `docs/integrations/code_saturne.md`.
   - Compute ξ the same way: use the same post-processing on its
     exported wall pressures and sections, or write an adapter, and say
     which.
   - A ξ_PG within 0.02 of OpenFOAM's "rules out" the solver.  A gap of
     0.05 or more "explains part".
3. **Step 4, model:** 0162 has realizable k–ε at refined(k)'s k = 2.
   Rerun it on the fixed-wall mid level so the comparison is like for
   like.  LES: write a volunteer card only if the case's card exists
   (0179); otherwise list it as a follow-up.
4. **Write** `validation/junction_loss/RESULTS.md` § *Why it misses*,
   one line per step: explains it / part of it / rules it out, with the
   numbers.  Then a summary sentence for the README row.  RESEARCH §7.2
   is the design session's.
5. **Lessons for 0188:** list under *Outcome* each finding a user could
   repeat, in one sentence, with its evidence.
6. **Stop rule:** if code_saturne's SST run can't be set up in about a
   day, stop and write it under *Questions for design*.

**Accept.**
- Steps 2–4 reported, with the verdict per step.
- *Why it misses* written.
- Gates and the verdict unchanged (decision 0058: the ladder explains,
  never passes).
- Lessons listed for 0188.

**Out of scope.**  The 19 other points of 0162's sweep; LES runs on
this machine; step 5 (only if steps 1–4 leave the mesh suspected; then
ask design).

## Agent notes

## Questions for design

## Outcome
