# 0085 — The O-H ↔ H switch, and `Transition` to an H rectangle

- **Status:** ready (after 0084)
- **Decision:** [0036 — Cartesian (H) rectangular section](../decisions/0036-cartesian-rectangular-section.md) (items 5–6, rollout step 2); [0011](../decisions/0011-port-face-signatures-and-switch-strategies.md) (class 1, pillow / unpillow); DESIGN A4, §7.1
- **Depends on:** 0084.  Reuses task 0069's pillowed-dome construction
  (decision 0033 B).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  A rectangular O-H face is an H face with `nrad` ring layers
pillowed in (RESEARCH §7.11).  Going between them means ending those
ring sheets inside one fitting.  Circle ↔ rectangle transitions need it
once the H face is the default, and so do the duct junctions (0086).

**Where.**  New switch builder (in `assembly/`, using `sections`); the
`Switch` fitting; `Transition` in `assembly/fittings.py` (or its own
module, per decision 0037 item 5); tests; RESEARCH input via *Outcome*.

**Do.**
1. **Prototype both constructions** for a straight switch piece, O-H
   rect (`nang_w`, `nang_h`, `nrad`) ↔ H rect (`nang_w`, `nang_h`):
   - **turned out:** each ring sheet flares and ends on the wall along a
     loop, as the duct tap's dome (task 0069);
   - **capped:** each ring sheet closes with a cup across the duct, open
     toward the O-H side (core, four side, one cap and four corner-wedge
     blocks per sheet).
   - Measure each, predicted and meshed: min scaled Jacobian, max
     non-orthogonality, max skewness, and how the switch length must
     scale.  Use a/b = 1, 2, 4 and `nrad` = 1, 3, 6, with the ring
     graded as in typical specs.
2. **Choose.**
   - Prefer the one with the higher meshed min SJ.  If they are within
     0.05, prefer turned out (it reuses 0069's code).
   - If neither meets `limits.py`'s quality limits, stop: write the
     numbers under *Questions for design* and set `blocked`.
3. **`Switch(length=…, n_layers=…)`**: a sweep-like fitting between an
   O-H rectangular port and an H rectangular port with equal counts and
   the same shape.
   - It declares the class-1 strategy (decision 0011 item 3; DESIGN
     §6's `strategies`).  Either direction works.
   - `validate()` checks the counts and the length rule from step 1
     before GMSH.
   - It has an exact cell count.
4. **`Transition` with an H rectangular end**: circle O-H ↔ rect H, in
   either direction.  The transition stays a class-0 blend to an O-H
   rectangle, and the switch is embedded in its rectangular end slab(s)
   (DESIGN §7.1's paragraph on duct junctions; decision 0036 item 5).
   - The user passes only the two specs.
   - Multi-layer transitions (task 0046) keep working when the
     rectangular end is O-H.  With H plus shells, wait for 0086 and
     reject with a named error.
5. **Flow check** (OpenFOAM v2406, laminar, Re 100, the rect duct's
   setup): an O-H run → `Switch` → H run, fully developed.  Report:
   - the f·Re of each run, against the plain runs;
   - the pressure-loss defect over the switch, as a percentage of the
     developed Δp over the switch length;
   - the velocity field just downstream, compared with the series.

   This is a check, not a gate.  Report the numbers.

**Accept.**
- The chosen switch passes the conformance kit in both directions, and
  its signature pair classifies as class 1 and is accepted.
- An O-H ↔ H pair joined directly (no switch) is rejected before GMSH,
  naming class 1 and `Switch` as the fix.
- `Transition` circle ↔ rect H passes the kit, at a/b = 1 and 2.
- *Outcome*: the step 1 table, the choice and why, and the step 5
  numbers, written for RESEARCH §7.11.
- Every existing mesh unchanged (the default is still `"oh"`).
- Full suite: no new failures.

**Out of scope.**  Switches inside junctions (0086); the default flip
(0087); class-2 count changes at the switch (counts must match).

## Agent notes

## Questions for design

## Outcome
