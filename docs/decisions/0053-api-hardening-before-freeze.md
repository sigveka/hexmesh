# 0053 — Three API changes before the freeze

- **Status:** accepted (2026-11-16, by the user: "yes")
- **Date:** 2026-11-16
- **Tasks:** 0164

## Context

Task 0150 reviewed the public surface name by name and froze it in
`docs/api-1.0.json`.  Asked to steelman the API and question its future
weaknesses, the design session found three that the name review didn't
cover, because they are about *how* names are called, not which names
exist.  Each becomes permanent at 1.0 (decision 0042's promise 1: 1.x
never removes or renames), and each is cheap now.  There are no users
yet (the user, 2026-11-16), so no deprecation period is needed.

1. **Positional arguments.**  97 public callables take four or more
   arguments that may be passed by position; `Tee.__init__` takes 21,
   the interchange `Bend` 13, `CrossSection` 13, `Study` 12 (counted from
   `docs/api-1.0.json`).  Under the freeze, their order is frozen too: a
   new argument can only be appended, and `Tee(0.1, 0.3, 0.02, 3, 3, 2,
   0, None, 45)` must keep working.
2. **`PipeSpec` mutates.**  `core()` and `shell()` append to `self` and
   return it (`hexmesh/core/spec.py`, `return self`).  Checked:
   ```python
   base = PipeSpec(nang=8).core("fluid", radius=0.05, nrad=4).shell("steel", dR=0.003, nrad=2)
   ins = base.shell("insulation", dR=0.02, nrad=2)   # ins is base: base is insulated too
   ```
   The fluent style reads as if each call makes a new spec.  A network
   insulated in places, the common plant case, is where this bites.
   After 1.0 someone may rely on the mutation, and fixing it would break.
3. **`Assembly.add` returns one `Interface`, or a bare tuple** for a
   fitting with several outlets (`_graph.add`: `outlets[0] if
   len(outlets) == 1 else outlets`).  The tuple's order is the only name
   its members have.  Crosses (asked about in 1.x, decision 0042) and
   branching networks (decision 0018) add fittings with more outlets.

Also unclear: whether README *Stability* promises the quality limits'
values and levels (error or warning).  Loosening one is harmless;
tightening one, or turning a warning into an error, breaks scripts.

## Options

### A. Change all three now, in 0.8
Breaking for positional callers, mutating callers and nobody else
(tuples still unpack).  One task of moderate size; the examples and
tests are the main call sites.

### B. Freeze as is; document
No work.  The positional order and the mutation become promises for
all of 1.x; new multi-outlet fittings extend an unnamed convention.

### C. Fix in 2.0
The same as B for the whole 1.x line.

## Decision

**A**, with these rules:

1. **Keyword-only after the obvious.**  A public callable keeps as
   positional only the arguments a reader understands without their
   name, **at most two**; everything after them is keyword-only (`*`).
   The defaults:
   - fittings: `Straight(length)`, `Bend(radius, angle)`,
     `MiterBend(…)` and `Elbow(…)` likewise, `Reducer(outlet)`,
     `Transition(outlet)`; `Tee`, `Wye`, `Switch`, `Closure`,
     `SplinePipe`: none positional (every argument is a choice among
     equals);
   - `PipeSpec(*, …)`; `.core(name, …)`, `.shell(name, …)`;
   - `Assembly(spec, …)`; `Assembly.add(source, fitting, …)`;
     `Assembly.close(a, b, fitting, …)` as now;
   - writers: `write(path, …)`;
   - dataclasses that users only read (`QualityReport`,
     `RegionQuality`, `HexVolumeQuality`, `FillResult`, `NetworkSpec`
     and the interchange parts): `kw_only=True` where users build them,
     unchanged where they don't.
   The task lists every exception it makes to these defaults in a table
   for the design session; it doesn't stop to ask for each.
2. **`PipeSpec` is copy-on-write.**  `core()`, `shell()` (and any other
   public method that changes a spec) return a new spec and leave `self`
   unchanged.  Equality and `to_dict()` are unaffected.  A spec is
   therefore safe to share between fittings and between assemblies.
3. **Multi-outlet `add` returns a named tuple** per fitting (`Tee` →
   `(run, branch)`, `Wye` and `Switch` with their port names as the
   fittings already call them).  It unpacks as before, so existing code
   keeps working, and `ports.branch` reads by name.  A single-outlet
   fitting still returns the `Interface` itself.
4. **README *Stability*:** limit values and their levels may change in
   1.x as measurements justify.  Loosening one is not noted; tightening
   one, or turning a warning into an error, is noted in the CHANGELOG
   under *Behaviour*, with the measurement.  Codes are only added.

## Consequences

- **Task 0164** applies the four points, before the 0.8.0 tag; task
  0150's release prep (2f54ce9, on `next`) is redone after it: the
  CHANGELOG's 0.8.0 entry gains a *Breaking* section listing them.
- `docs/api-1.0.json` changes on purpose (argument kinds, return
  types); its test is what proves the change is complete.
- **DESIGN.md:** no change; these are conventions of the surface, not
  assembly rules.  §3.1 (one name per concept) is unaffected.
- **Harder:** positional calls in docs and examples must be rewritten;
  a spec built step by step needs the result of each call kept
  (`spec = spec.shell(…)`).
- **Future expansions:** 0018 (vascular networks) and 1.x crosses gain
  named outlets; 0035 (multi-core sections) gains specs that can be
  shared safely; 0019 (agent SDK) gains keyword calls that read the
  same as the description's fields.  None is constrained.
- **Deferred to 1.x, additive** (recorded here, no task):
  - a public `Profile` type for `Reducer(profile=…)`, keeping the tuple
    form, for decision 0021's restrictions;
  - a section-kind field in the description, defaulting to the
    concentric section, for decision 0035 stage B;
  - a stateless build-to-mesh call beside `Session`, for decisions 0019
    and 0030.
- **Not changed:** the mesh-jargon names (`mbmp`, `mprg`, `lc`, `nang`,
  `nrad`).  Renaming now costs every doc and example; aliases later
  would give one concept two names (DESIGN §3.1).  They stay, as
  documented.

## Verified vs. assumed

- **Checked (2026-11-16):** the counts of positional arguments, from
  `docs/api-1.0.json` at 683db4b; `PipeSpec.shell` returning `self` and
  changing the base spec (the snippet above, run); `_graph.add`'s
  return; the schema's `$defs` (no section-kind field).
- **Assumed:** that the work is moderate (the call sites weren't
  counted); that no example depends on `PipeSpec`'s mutation.  The task
  measures both.

## Amendment (2026-11-16): the four deferred items before 1.0

The user: "I also want 4-7 done before 1.0", the four items this
decision deferred or left unchanged (the design session's review,
numbered 4 to 7).  They replace *Deferred to 1.x* and *Not changed*
above.  All four land **before the 0.8.0 tag**, so 0.8 is the surface
1.0 freezes; no users, so no shims (old saved descriptions still
migrate on load, decision 0042's promise 3).

4. **A public `Profile` for `Reducer(profile=…)`** (task 0165).  One
   form, not two: `Profile.cosine(s0)`, `Profile.venturi(beta,
   divergent)`, and a constructor for new kinds that decision 0021's
   restrictions (orifices, valves, nozzles) add with named parameters.
   The tuple form is removed from the API; the description stores the
   profile as an object with a `kind` and named fields.
5. **The jargon names are renamed** (task 0166), into the `n_*`
   convention the counts already use (`n_layers`, `n_outer`, `n_run`)
   and the `*_grading` one (`axial_grading`):

   | now | 1.0 | meaning |
   |---|---|---|
   | `nang` | `n_arc` | cells per 90° arc |
   | `nang_w`, `nang_h` | `n_width`, `n_height` | cells along a rectangle's width and height |
   | `nrad` | `n_radial` | cells across a layer |
   | `mprg` | `radial_grading` | a layer's radial progression ratio |
   | `mbmp` | `arc_bump` | the arcs' bump factor (1 = uniform) |
   | `lc` | removed | gmsh's characteristic length: it doesn't affect the structured mesh (API.md) |

   Everywhere: arguments, properties, the description's fields, the
   schema, error-code *fields* and messages, limits, the CLI's JSON,
   docs, examples, CLAUDE.md (by the design session).  The error
   *codes* that contain an old name are renamed too (no users), listed
   in the CHANGELOG.  §3.1's one name per concept holds: no aliases.
6. **A section-kind field in the description** (task 0165): each
   `PipeSpec` saves `"kind": "concentric"`; a description without one
   loads as concentric.  Decision 0035 stage B adds kinds; until then
   any other value is a coded error.
7. **A build call that doesn't depend on `Session`** (task 0167): the
   assembly meshed into a self-contained result (nodes, cells, groups,
   quality) that writes itself, so a script, the agent SDK (0019) or the
   simulation suite (0030) can mesh many assemblies without managing
   gmsh's global state.  The task starts with a spike on how gmsh allows
   it (a model per call in one gmsh instance, or a process per call),
   recorded in `docs/integrations/gmsh.md`, and comes back to design
   with the result before fixing the API.

**Order:** 0164 (in progress) → 0166 (the renames touch every call
site; best done right after 0164's rewrite) → 0165 → 0167 → the 0.8.0
release prep redone.  The validation runs (0162, 0050) continue beside
them.

**Future expansions:** 0021 gains its profile type; 0035 its section
kind; 0019 and 0030 their build call.  None is constrained.
