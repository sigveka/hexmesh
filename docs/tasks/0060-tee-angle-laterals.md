# 0060 — General branches, stage 1: `Tee(angle=…)`, laterals

- **Status:** ready (after the junction-shell work: 0056, 0053, 0054)
- **Decision:** [0031 — General branch junctions](../decisions/0031-general-branch-junctions.md) (stage 1)
- **Depends on:** the tee as of task 0052 (shells, predicted-quality
  limit) and 0051 (node projection).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  45° laterals are common in plant piping, and the Štigler
lateral benchmark covers 30°–90° (RESEARCH §7.2).  `Tee` is
perpendicular only.

**Where.**  `hexmesh/assembly/tee.py`, `projection.py` (`TubeUnion`
with a branch ray at angle α), `blocks.py`, `limits.py`, kit, `API.md`,
DESIGN §7.1 (design applies the wording).

**Do.**
1. **Field** `angle` (degrees, default 90): the angle between the run's
   downstream direction and the branch axis.  `toward=` resolves the
   roll as today; `angle` sets the lean in the branch plane.
2. **Geometry:** saddle points from RESEARCH §3.1 with h = 0, P(φ) for
   the given α (sampled splines, as today).  Station positions along the
   run become asymmetric (s(0) ≠ s(π)); turn faces follow.  The branch
   port frame leans by α.  Shells: the same formula at R + T_l and
   r + T_l (decision 0028); walls and shell boundaries by node
   projection (`TubeUnion` with the branch as a ray at α).
3. **Room checks:** the branch clears the run's ends at the acute side,
   and the turning station clears the main's outer shell, along the
   leaning axis.  Name the limit.
4. **Measure:** predicted corner SJ and max non-orthogonality over
   α ∈ {30, 45, 60, 75, 90}° × r/R ∈ {0.3, 0.6, 0.9} × 0 / 2 shells,
   `nang` 4 and 8.  Locate the worst cell (acute crotch, obtuse side,
   core).
5. **The tee's ratio cut-off τ** (decision 0031's amendment): extend the
   quality table to r/R ∈ {0.9, 0.95, 0.97, 0.99} at 90° and 45°, and
   set `TEE_MAX_RATIO` in `limits.py` where the predicted quality stops
   being acceptable (about 0.95 expected).  `Tee` rejects
   τ < r/R < 1 with the hint "an equal tee, or a branch radius ≤ τ·R",
   and r = R with "equal tees are planned through the wye-family
   layout".
6. **Limit:** the two tiers of 0052 (reject < 0.1, warn < 0.3, with the
   shortest `run_length` hint) apply unchanged.  Propose a lower bound
   on α under *Questions for design* if the tiers alone don't make a
   clean rule.

**Accept.**
- `angle=90` meshes identically to today's tee (node coordinates to
  1e-12).
- Kit cases at 45° and 60° (single-layer and with two shells): all-hex,
  meshed = predicted, class-0 ports, every wall and interface node on
  its analytic surface (1e-6 R), quality ok.
- The branch outlet's frame matches the analytic axis (to 1e-9).
- The quality table and, if needed, a proposed α bound.
- Full suite: no new failures.

**Out of scope.**  Offsets (0061), twist (0062), ducts (0063), equal
tees, crosses.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
