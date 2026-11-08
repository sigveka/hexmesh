# 0111 — Hints for equipment and study errors; the layout errors reviewed

- **Status:** ready (after 0110)
- **Decision:** [0040 — Agents for users](../decisions/0040-user-agents-network-design-and-resolution.md); follow-up of task 0106
- **Depends on:** 0106 (done).  Not needed before the launch.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0106 raised the share of coded errors with a hint from
13 % to 29 % in the modules it listed.  It found three places it didn't
list:
- `assembly/equipment.py`: 0 of 23 with a hint;
- `study/definition.py`: 0 of 18;
- `assembly/blocks.py`'s layout errors: 0 of 13, mostly invariants of
  the fittings' own layouts.

**Do.**
1. **Hints** in `equipment.py` and `study/definition.py`, on 0106's rule:
   a hint says what to change, with the number when there is one; no hint
   is better than a vague one.
2. **Review `blocks.py`'s 13** on 0106's split: a user-reachable error
   keeps its code and gains a hint; an invariant becomes `InternalError`.
   Put the table under *Agent notes*.
3. Report the hint share per module, before and after.

**Accept.**
- The table and the shares are in *Outcome*.
- Existing messages unchanged except where a hint is added or an error
  becomes `InternalError` (listed).
- The architecture rule still passes; full suite: no new failures.
