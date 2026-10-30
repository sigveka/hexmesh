# 0069 — Prototype: duct tap with a pillowed ring (hole on the wall)

- **Status:** ready
- **Decision:** [0033 — Junction layout for duct taps](../decisions/0033-duct-tap-topology.md) (option B, accepted for prototyping)
- **Depends on:** —  (the duct sections of tasks 0028/0029; the tee's
  block-layout machinery and predicted-quality tiers from 0052)

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  A duct tap narrower than its face, and a round tap on a duct,
can't use the pipe tee's layout: the duct's creases would cross block
faces (task 0057, decision 0027's amendment).  The user chose to go
straight for a general layout.  This task prototypes it and measures
it; the layout is chosen on the numbers.

**The idea** (decision 0033, B).
- The hole is a patch of the main duct's own top-wall cells; its
  outline lies on mesh lines of the main's top face.
- The branch's O-grid ring layer continues into the main as a
  **pillow** sheet: a dome of cells under the hole patch whose boundary
  is a loop on the top wall around the hole.  The sheet ends on the wall
  (as pillowing does, RESEARCH §9.5, [`borden_and_benzley_etal_2000`]),
  not at a cap.
- The main's blocks are unchanged away from the dome, so the port faces
  stay the standard O-H face.
- The branch's own section joins the hole patch and the dome's rim.

**Where.**  A prototype first: `hexmesh/assembly/` (a new layout module,
e.g. `duct_tap.py`, on `BlockLayout`), behind `Tee` only once it
works.  Scripts and measurements in this session's scratchpad until
then.

**Do.**
1. **Rectangular tap inside the face** (q < a with a margin, p within the
   room), on a single-layer rectangular main, branch rectangular with
   the main's counts per side.  Work out:
   - which main cells the hole occupies (its outline on mesh lines);
   - the dome's extent (how many cells beyond the hole on the wall, how
     deep);
   - the blocks that realise it with `BlockLayout`.

   Write the layout down (a sketch in *Agent notes*) before coding.
2. **The sizing rule:** the hole's edges must fall on the main's mesh
   lines, so the tap size is tied to the main's counts.  State the rule,
   and what a user does when their tap size doesn't fit: the nearest
   valid size, or the counts that make it fit.  Give it as a hint.
3. **Round tap:** the same construction with a circular branch: the
   hole patch's outline approximates a circle on the wall (the branch's
   O-H corners at its diagonals), walls by node projection (decision
   0029) where needed.
4. **Full-width taps (q = a):** does the construction cover them (the
   dome's wall loop then meets the creases)?  If yes, say how; if no,
   say why.  This decides whether task 0057 returns.
5. **Measure** for each variant: predicted and meshed min corner SJ, max
   non-orthogonality, cell count against the main alone.  Over tap/face
   ratio 0.3 / 0.6 / 0.9, duct aspect 1 / 2 / 3, wide and narrow face,
   `nang` 4 and 8.  All-hex and conformal, with meshed = predicted.
6. **Report** under *Questions for design*: the layout, the sizing rule,
   the quality table, the full-width answer, and whether the collar
   (decision 0033, A) still needs prototyping.

**Accept** (for a prototype).
- A rectangular inside-the-face tap and a round tap mesh all-hex, with
  meshed = predicted, standard port faces and walls exact.  On a 2:1
  duct, wide face, ratio 0.6.
- The quality table and the sizing rule.
- The full-width question answered.
- Nothing merged into `Tee` yet (that is the follow-up task once design
  chooses).

**Out of scope.**  Shells; angled taps (decision 0031); merging into
`Tee`.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
