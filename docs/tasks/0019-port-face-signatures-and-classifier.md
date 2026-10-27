# 0019 — Port-face signatures and the topology-switch classifier

- **Status:** done
- **Decision:** [0011 — Port-face signatures and topology-switch strategies](../decisions/0011-port-face-signatures-and-switch-strategies.md)
- **Depends on:** —  (do it before 0018 if possible; 0018 then declares
  class 1)

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  DESIGN A4 (as amended by decision 0011) lets a fitting's two
ports differ only in ways covered by a strategy the fitting declares.
Today each fitting checks its own port pair ad hoc: the reducer uses
`fittings._density` and `_DENSITY_FIELDS` to name the first differing
field.  This task adds the shared mechanism: a mesh signature per face, a
class per port pair, a `strategies` declaration per fitting, and the
validation and kit checks.  **No new geometry and no new strategies.**

**Where.**
- `hexmesh/assembly/interface.py`: `port_type` (exact interface key;
  leave it as is).
- `hexmesh/assembly/fittings.py`: `_density`, `_DENSITY_FIELDS`, and
  their use in `Reducer.validate`; the fittings `Straight`, `Bend`,
  `MiterBend`, `Elbow`, `Reducer`, `SplinePipe`, `Closure`.
- `hexmesh/assembly/tee.py`: `Tee`.
- `hexmesh/assembly/sweep.py`: `Sweep.validate`.
- `tests/test_fitting_conformance.py`: `CASES` and the kit tests.

**Do.**
1. **`signature(spec) -> Signature`**: pure Python, no GMSH, frozen and
   hashable.  Per layer, in order:
   - layer name;
   - layout kind: `"oh_core"` for the 5-patch O-grid core, `"annulus"`
     for a shell ring.  Add others only when a builder exists in the
     assembly;
   - chord-family counts: `nang` (around), core grid counts, `nrad`.
   Plus section-level fields that fix mesh connectivity: `n_outer`
   (partition), and the section symmetry period P (decision 0010).
   **Exclude geometry:** radii, shape dimensions, `rot` angle values used
   only for placement.  Check whether `rot` changes connectivity or only
   placement, and record the finding.
   **Grading (`mprg`, `mbmp`): keep it in the signature for now**
   (today's reducer behaviour).  Then investigate decision 0011 question
   3: can station faces with different gradings be joined by a sweep
   without conflicting curve constraints?  Report under *Questions for
   design*; don't change the default.
2. **`classify(a, b) -> SwitchClass`** (0, 1, 2 or 3), with a
   structured difference that names what differs:
   - **0:** signatures equal;
   - **1:** they differ only by whole outermost layers present on one
     side.  Record whether the ring would end on a wall (layer
     termination) or cap inside the fitting.  That is decision 0011
     question 2; report what you find;
   - **2:** same layers and layouts, different counts in at least one
     chord family;
   - **3:** anything else.
3. **`strategies` on every fitting**: a class attribute, e.g.
   `strategies = frozenset({0})`, declared for every existing fitting:
   `Straight`, `Bend`, `MiterBend`, `Elbow`, `Reducer`, `SplinePipe`,
   `Closure`: `{0}`.  `Tee`: `{0}` for each of its port pairs (main in →
   main out; main in → branch).  Decide how a multi-port fitting lists
   pairs, and record the choice.  Task 0018 will add `1` to sweeps that
   allow layer termination.
4. **Validation.**
   - `Sweep.validate` (and `Tee.validate`) computes the class of each
     port pair before GMSH.  If the class is not in `strategies`, raise.
     The message must name the fitting, the class, **what differs** (for
     example, "layer `insulation` present only at the inlet", or
     "`nang` 8 → 16"), and which strategy would bridge it.
   - Replace `Reducer`'s `_density` check with this.  Its existing
     field-naming error tests must still pass, reworded only if needed.
     Delete `_density`/`_DENSITY_FIELDS` if nothing else uses them.
5. **Conformance kit.**  For every case in `CASES`, assert that every
   port pair's class is in the fitting's `strategies`.  Add negative
   cases (no GMSH needed):
   - a `Reducer` whose outlet changes `nang` (class 2, rejected);
   - a `Straight` whose outlet drops a layer (class 1, rejected until
     0018);
   - a `Straight` joined to a different layer stack (class 3, rejected).

**Accept.**
- Unit tests for `signature` and `classify`: equal specs → 0; radius-only
  change → 0; outermost layer removed → 1; `nang` or `nrad` change → 2;
  layer renamed or reordered → 3.
- All existing `CASES` pass the new kit check.  The three negative cases
  are rejected before GMSH with messages naming the difference.
- Reducer behaviour unchanged (its tests pass).
- Full suite: no new failures.

**Out of scope.**  Implementing any class-1, 2 or 3 strategy (0018 adds
class 1 for layer termination; the rest wait for decisions 0003 and
0009).  Changing `port_type` or interface matching.  Removing grading
from the signature.

## Agent notes

- **Module:** `hexmesh/assembly/signature.py`, holding `LayerSig`,
  `Signature`, `Difference`, `SwitchClass`, `signature`, `classify`,
  `strategies_for`, `check_port_pairs` and `BRIDGES` (class → what would
  bridge it, for messages).
- **Signature contents:**
  - per layer: name, kind (`oh_core` for a circular core, `annulus` for
    a circular shell), `nrad`, `mprg`;
  - per section: `n_outer`, period P = 360°/`n_outer` (decision 0010),
    `nang` and `mbmp`.

  `nang` is kept once, at section level, because every layer shares it.
  The OH core's grid counts follow from `nang` and `nrad`.  Rect cores and
  square shells raise: no assembly builder exists for them
  (`check_supported` rejects them first anyway).
- **`rot` is placement, not connectivity (finding).**  The face built
  with `rot = 0.3` has the same entity, quad and node counts (17/20/9
  entities, 144 quads, 158 nodes).  Its nodes equal the `rot = 0` nodes
  rotated by −0.3 rad about the face normal, to 2.8e-16.  So `rot` is
  not in the signature.  The reducer keeps an explicit `rot` check, with
  the same message as before, because its cone needs equal placement.
  For a sweep, `rot` acts like a roll: its correspondence is decision
  0010's.
- **Class rules:**
  - section fields (`n_outer`, P) differ → 3;
  - a layer renamed or of another kind, at any common index → 3;
  - extra outermost layers on one side with equal common layers → 1;
    with count changes as well → 3;
  - same layers, but count or grading (`nang`, `mbmp`, `nrad`, `mprg`)
    differs → 2.  Grading-only is class 2, not 3: it is a node
    distribution, not a topology.
- **Strategies.**  Every fitting class declares
  `strategies = frozenset({0})` explicitly; there is no base-class
  default, so a new fitting must declare (tested).  **Multi-port
  choice:** one frozenset applies to every pair (inlet → outlet *k*); a
  tuple of frozensets gives one per outlet.  The tee uses the single
  frozenset for both main-out and branch.
- **Where it's checked:**
  - `Sweep.validate` and `Tee.validate` check the pairs the fitting
    declares itself (`ports()`);
  - `Assembly.validate` checks the pairs as actually connected, so
    `close()` and hand-edited port specs are covered.

  `Assembly.validate` now runs each fitting's own `validate` first, so
  its specific reason comes first.  (The tee's "single-layer specs only"
  would otherwise surface as class 1, because its branch spec has no
  shells.)  Then come the class check and the exact A4 `port_type` check.
- **Reducer:** `_density` and `_DENSITY_FIELDS` are deleted (nothing else
  used them).  Its five field-naming tests pass unchanged: messages
  still contain "differs from the inlet in core nrad / nang / rot /
  shells".
- **Changed test:** `test_assembly.py::test_port_type_mismatch_rejected`
  (a closure onto an `nang` 6 interface) is now caught by the class
  check, so its regex became `nang \(4 vs 6\).*class 2`.  A new test
  keeps the exact A4 check covered: a radius-only mismatch is class 0
  but still not the declared type.
- **Kit:** `TestConformance.test_switch_classes_declared` passes for all
  25 cases.  The three negative cases are in `tests/test_signature.py`,
  rejected before GMSH:
  - a Reducer changing `nang` (class 2);
  - a Straight whose outlet drops `wall` (class 1);
  - a Straight joined to `steel` instead of `wall` (class 3).

## Questions for design

*Answered 2026-10-26 by [decision 0016](../decisions/0016-class-1-granularity-and-grading-changes.md):
(1) no subclass, kind changes stay class 3; (2) grading stays in the
signature, and sweeps may bridge grading-only class 2 with per-station
interpolation (task 0027).*

1. **Decision 0011 Q2: class-1 granularity.**  From signatures alone, a
   *whole outermost layer present on one side* can only mean the ring's
   end face is exposed, so it **ends on a wall**.  The classifier
   records that as `ends="wall"`.  "Capping inside the fitting" (an
   O-ring replaced by something else, e.g. the square-duct follow-up of
   0009) changes the outermost layer's *kind*, which is class 3 under
   these rules.  So one class 1 is enough for layer termination.
   - **Question:** if the duct follow-up should be class 1 rather than
     3, the rule needs a kind-change subclass (1a: termination on a
     wall; 1b: outer ring replaced).  Should it?
2. **Decision 0011 Q3: grading in the signature.**  Measured with a
   reducer subclass declaring `{0, 2}`; core + shell, `nrad` 6 / 4,
   inlet `mprg` → outlet `mprg`:

   | `mprg` in → out | Mesh | min SICN |
   |---|---|---|
   | 1.0 → 1.0 | all-hex, predicted count | 0.193 |
   | 1.0 → 1.3 | all-hex, predicted count | 0.094 |
   | 1.3 → 0.77 | all-hex, predicted count | 0.097 |
   | 1.0 → 2.0 | all-hex, predicted count | 0.019 |

   - **Joining works mechanically.**  There were no conflicting
     transfinite constraints: each station has its own radial curves,
     and axial curves only need matching node counts.  Worst scaled
     Jacobian stayed 0.826 throughout.
   - **But the quality cost is large**, because today's intermediate
     stations copy the *inlet* grading (`_with_radii`), so the whole
     change happens in the last slab.  If grading leaves the signature,
     the sweep should interpolate it per station, like radii.
   - **Default unchanged:** grading stays in the signature.  Should it
     move out, with interpolation?

## Outcome

- **Files:**
  - new `hexmesh/assembly/signature.py`;
  - `strategies` on all 8 fittings;
  - `fittings.py`: `_density` removed, and an explicit `rot` check in
    `Reducer`;
  - `sweep.py`, `tee.py`: port-pair checks;
  - `assembler.py`: the class check, and the validation order;
  - tests: new `tests/test_signature.py` (19), the kit check in
    `test_fitting_conformance.py` (+25), and `test_assembly.py`
    (1 regex, +1 test);
  - docs: `API.md`.
- **Accept:**
  - the signature and classify unit tests pass (equal → 0, radius → 0,
    outermost layer → 1, `nang` / `nrad` → 2, renamed / reordered → 3);
  - every `CASES` entry passes the kit check;
  - the three negative cases are rejected before GMSH, naming the
    difference;
  - the reducer tests pass unchanged.
- **Tests:** 600 passed (default run) + 5 passed (`-m openfoam`), 0 failed.  The two *Questions for design* are the investigations the task asked for (decision 0011 Q2, Q3); they do not block anything, so the task is done, not blocked.
