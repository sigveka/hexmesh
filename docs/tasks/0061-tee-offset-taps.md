# 0061 — General branches, stage 2: `Tee(offset=…)`, tangential and offset taps

- **Status:** ready (after 0060)
- **Decision:** [0031 — General branch junctions](../decisions/0031-general-branch-junctions.md) (stage 2); PCF mapping from [0023](../decisions/0023-pcf-branched-networks-insulation-equipment.md)
- **Depends on:** 0060.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Offset and tangential set-ons are real plant fittings (PCF
SKEYs TOSO/TORF and TTSO/TTRF, `docs/integrations/pcf.md`), rejected by
the PCF reader today.

**Where.**  `hexmesh/assembly/tee.py`, `projection.py`, `limits.py`,
`hexmesh/io/readers/pcf.py`, kit, `API.md`, `docs/integrations/pcf.md`.

**Do.**
1. **Field** `offset` (length, default 0): the distance h between the
   branch axis and the main axis, along the main's local `right` after
   the roll.  Valid for |h| + r < R (RESEARCH §3.1), with a margin set
   by measurement.
2. **Geometry:** the full P(φ) of RESEARCH §3.1 with h ≠ 0 (and any α
   from 0060).  Tips move by arcsin(h/R) around the main axis (§3.2).
   Decide how the junction's block corners follow: they stay on the
   branch diagonals; record how the main's ring blocks absorb the
   asymmetry.  Shells and projection as 0060.
3. **Measure:** predicted corner SJ and non-orthogonality over
   h/R ∈ {0, 0.2, 0.4, 0.6} with r/R ∈ {0.3, 0.5}, at α 90° and 45°.
   Propose the margin on |h| + r under *Questions for design*.
4. **PCF:** map TOSO/TORF (offset) and TTSO/TTRF (tangential: the
   largest offset the margin allows, or reject naming the margin) to
   `offset`.  Update the reader's rejection tests and `pcf.md`.

**Accept.**
- `offset=0` meshes identically to before (to 1e-12).
- Kit cases at h/R 0.3 (α 90° and 45°): all-hex, meshed = predicted,
  class-0 ports, walls exact on the final mesh, quality ok.
- A PCF fixture with an offset set-on builds and meshes.
- The quality table and the proposed margin.
- Full suite: no new failures.

**Out of scope.**  Twist (0062), ducts (0063).

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
