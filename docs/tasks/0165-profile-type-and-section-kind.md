# 0165 — A public `Profile` type; a section kind in the description

- **Status:** ready (after 0166)
- **Decision:** [0053](../decisions/0053-api-hardening-before-freeze.md), amendment items 4 and 6
- **Depends on:** 0166 (the renames).
- **Blocks:** the 0.8.0 tag.

Ground rules for all tasks: [README](README.md#ground-rules).

**Do.**
1. **`Profile`**, exported from `hexmesh`: `Profile.cosine(s0)`,
   `Profile.venturi(beta, divergent)`, with the limits and coded errors
   the tuples have now.  `Reducer(profile=…)` takes a `Profile` only;
   a tuple is a coded error whose hint shows the `Profile` call.  The
   internal `profile.Profile` either becomes this class or sits behind
   it: your choice, say which.
2. **The description:** a profile saves as `{"kind": "cosine", "s0":
   …}` / `{"kind": "venturi", "beta": …, "divergent": …}`; the schema
   says so; old descriptions with tuples migrate on load (a version
   bump, `intent.VERSION`, with its migration test).
3. **Section kind:** each saved `PipeSpec` carries `"kind":
   "concentric"`; missing loads as concentric; another value is a coded
   error (`section_kind_unsupported`) naming decision 0035.  Schema and
   migration as in step 2.
4. Docs (API.md's profile table, GUIDE), examples (byte-identical
   meshes), the inventory, CHANGELOG *Breaking*.

**Accept.**  Tests for both constructors, the tuple's error, both
migrations and the unknown kind; examples byte-identical; full suite
and CI green.

## Agent notes

## Questions for design

## Outcome
