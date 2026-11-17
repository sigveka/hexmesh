# 0165 — A public `Profile` type; a section kind in the description

- **Status:** done
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

- **Step 1, `Profile` (the choice asked for):** the public class *is*
  `hexmesh.assembly.profile.Profile`, a frozen dataclass value (`kind` and
  its fields; each field an attribute: `p.s0`).  The old evaluator, which
  took a tuple, a length and the inlet radius, is now
  `RadiusProfile(profile, length, r_in)`, internal.  The parameter
  checks moved from the evaluator into the constructors, with the same
  codes and messages; only the venturi's "too short" stays in the
  evaluator, because it needs the length.  New:
  `profile_fields_invalid` (a kind given the wrong fields) and
  `profile_type_invalid` (an `AssemblyTypeError`, so still a
  `TypeError`), whose hint is the call (`profile=Profile.cosine(0.25)`).
  `KINDS` maps each kind to its check; a new kind adds a row, a
  constructor and a form in `RadiusProfile`.
- **`Profile.table(points)`:** the table form existed; the design session
  approved keeping it as the third kind (2026-11-17, noted in decision
  0053).  The bare-list form goes, so it is in the CHANGELOG's
  *Breaking*.
- **Step 2:** a profile saves as `{"kind": …, <fields>}`, a table as
  `{"kind": "table", "points": [[s, r], …]}`.  Version 4;
  `intent.upgrade` turns version 3's tuples into objects (version 2 and 1
  go through 3).  The schema has a `Profile` def, one object per kind.
- **Step 3:** `PipeSpec.to_dict` saves `"kind": "concentric"` first;
  `from_dict` takes a missing kind as concentric and raises
  `section_kind_unsupported` (`SpecError`, naming decision 0035 stage B)
  for any other.  The value is public as `PipeSpec.KIND`, so the agent
  schema reads it through the public API (the architecture test asks
  that).
- **Tests:** `test_reducer.py`: constructors' checks (8 cases), the tuple
  error with its hint (3), the profile as a value; the existing profile
  tests on `Profile`/`RadiusProfile`.  `test_intent.py`: version 3 → 4 for
  each kind (3), a missing kind, an unknown kind.  The version-2 example
  test now goes through two migrations.

## Questions for design

## Outcome

- **Done** (2026-11-17): `hexmesh.Profile` with `cosine`, `venturi` and
  `table`; `Reducer(profile=…)` takes a `Profile` only, and a tuple is
  `profile_type_invalid` with the call as its hint.  Each saved spec
  carries `"kind": "concentric"` (`PipeSpec.KIND`); any other kind is
  `section_kind_unsupported`.  Description version 4, migrating version
  3's profile tuples.
- **Files:** `assembly/profile.py` (`Profile`, `RadiusProfile`),
  `fittings.py`, `intent.py`, `core/spec.py`, `agent/_schema.py`,
  `errors.py` (3 codes), the exports; the two examples with profiles
  (stenosis, rocket injector manifold), two validation drivers, tests;
  API.md (profile table, Versions, `PipeSpec.KIND`, Errors), CHANGELOG,
  the gallery, `support.json`, `docs/api-1.0.json`.
- **Tests:** `test_reducer.py` +13 (constructors' checks 8, the tuple's
  error 3, the profile as a value 1; the existing profile tests on the new
  types), `test_intent.py` +5 (version 3 → 4 per kind, a missing kind, an
  unknown kind).  Full suite on one worker: 4669 passed, 16 skipped, 1
  failed.  The failure was the validation summary that 3814213 regenerated
  while the run was going (it started before); it passes now.
- **Examples:** all 35 byte-identical (meshes, recipe block left out)
  with the worktree at fcb5d42.
