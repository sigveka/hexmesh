# 0140 — Example: a liquid-rocket propellant feed line and ring injector manifold

- **Status:** ready
- **Decision:** none new: a showcase within today's fittings, as task
  0121's aorta.  DESIGN §8 (closed loops, `Assembly.close`).
- **Depends on:** 0141 (done 2026-11-11: a tee placed by trigonometry
  along −x failed to fill; OCC's plate is now retried).  0142 (done):
  the gallery's new layout, so the example goes in
  `CATEGORIES["applications"]` and the GUIDE's *Examples* table (a test
  checks both).  Not alongside 0139, which also regenerates the gallery.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user (2026-11-11) wanted an aerospace example in the
spirit of the idealised aorta, and chose a liquid-rocket feed system
over an S-duct inlet and an aircraft bleed-air network.  It shows what
no example shows at this scale: a **closed ring** (`Assembly.close`)
carrying **many tees**, with an insulated cryogenic feed line and a
cavitating venturi, in fluid,
steel and insulation regions (the conjugate-heat-transfer story), and a
cut-away of the ring for the gallery.

**Where.**  `hexmesh/examples/applications/rocket_injector_manifold.py`
(new), the gallery (`docs/gallery/build.py`: the entry and its
cut-away), the example registry, `docs/GALLERY.md`,
`docs/references.bib`, `tests/` (the examples' tests pick it up; add it
to `test_second_order.py`'s exclusions only if it holds an equal tee or
wye there).

**How it has to be built** (the design session checked this,
2026-11-11).  Every fitting has one inlet, and `close(source, target)`
joins an outlet to an *inlet*; in a tree the only free inlet is the
assembly's.  So **the ring is the root**: start at a point on the ring,
go round it through the tees and the bends between them, and close the
last outlet back into the assembly's inlet (a `Closure`, or a `Bend`
that fits exactly).  The **feed line is a tee branch**, built outward
from the ring to the tank, and named as the inlet (`lox_inlet`): the
mesh has no flow direction, only patch names.  So the drum-nozzle start
(`Assembly.from_nozzle`) can't be used for the tank; the feed line ends
at an open patch.

**The design session's prototype** (2026-11-11, scratch, R 0.02 with
a 0.003 steel shell, `nang` 6): rings of 8 and 12 tees, `roll=90` (the
branches along the ring's axis), `Bend`s of 360°/N between them and a
`Closure` into the inlet, **validate**.  Two things to plan for:
- **Branch ratio:** the predicted-SJ tiers, the same at `nang` 6, 8 and
  12: r/R < 0.2 is rejected (SJ < 0.1); 0.2 to 0.55 builds with a
  warning (SJ 0.12 at 0.25, 0.15 at 0.3, 0.20 at 0.4, 0.26 at 0.5);
  0.6 and up are clean.  Injector feeds are naturally small next to
  the ring, so either choose r/R ≥ 0.6 (a manifold "feed passage"
  rather than the orifice) or accept and report the warning; say which.
- **Meshing** at r/R 0.6 failed at the sixth tee: task 0141.
- The ring's size comes from the tee runs and the bends; choose the
  bend radius so the tee centres lie on the stated ring circle, and let
  the `Closure` take only the rounding.
- **The venturi** validates on the insulated line (r 0.012, steel 0.003,
  insulation 0.01, `nang` 6, 40 layers): `beta` 0.5 and 0.4, 7°
  divergent, length 0.3.  Shorter is rejected with the length needed
  (`profile_too_short`: 0.142 at `beta` 0.5, 7°).  Not meshed.

**Do.**
1. **Sizes from stated design rules, not one engine's drawings.**
   Choose an engine size class (thrust, mixture ratio, specific impulse)
   and derive the oxidiser mass flow; size the feed line and the ring
   from recommended line velocities, and the injector feed ports from
   their count.  Take the rules from an open source, e.g. NASA SP-125
   (Huzel and Huang, *Design of Liquid Propellant Rocket Engines*), and
   cite each in the module's docstring and `docs/references.bib`.  Where
   a value is a modelling choice (ring diameter, number of ports, line
   route), say so, as task 0121 did for the aorta's lengths.  Wall and
   insulation thicknesses: typical values, stated as such.
2. **Build it from fittings:**
   - **the ring:** `N` tees (8 to 12) evenly around a circle, with
     `Bend`s of 360°/N between them (or the tees' runs and short bends),
     closed back into the inlet; the tees' branches point along the
     engine axis, into the injector face (`roll`);
   - **the injector feeds:** a short `Straight` on each branch, named
     `injector_1` … `injector_N`;
   - **the feed tee:** one more tee on the ring whose branch is the feed
     line: a `Straight`, a `Bend` or two out to the tank, and a
     `Reducer` if the sizes call for one, ending at `lox_inlet`.  Its
     branch ratio within `TEE_MAX_RATIO` (0.95), or an equal tee if the
     sizes make it one (square and centred only);
   - **a cavitating venturi** in the feed line, upstream of the feed
     tee (the user, 2026-11-11): `Reducer(spec, length, n_layers,
     profile=("venturi", beta, divergent))`.  Rocket feed lines and test
     stands use one to fix the propellant mass flow and isolate the line
     from chamber-pressure oscillations: once the throat cavitates, the
     flow depends on the upstream pressure only.  Take `beta` and the
     divergent angle from a cited source on cavitating venturis (or state
     them as choices); the throat is where the mesh needs to show the
     contraction.  Name nothing new: it is a stretch of the feed line.
     The profile scales every layer, so the steel and insulation neck
     down with the bore (a real venturi body is straight outside): say
     so in the docstring, as a modelling simplification;
   - **layers:** fluid and a steel wall everywhere; insulation on the
     feed line (cryogenic), ending before the ring if
     `Straight(stack_changes=…)` can end it there; if it can't, insulate
     the whole network and say why under *Agent notes*.
3. **Mesh and report** as the other examples: cell count before meshing
   (and equal to the meshed count), min SJ, non-orthogonality, every
   `validate()` warning and what it names.  If the small injector tees
   warn on predicted SJ (the aorta's arch tees did, at r/R 0.5), report
   the numbers and the hint, and choose sizes that pass without new
   limits where the sources allow.
4. **The gallery:** the network image, a section image, and a
   **cut-away of the ring** at the feed tee (the aorta's `gallery_cutaway()`
   hook): the junction cores visible.

**Accept.**
- `python3 -m hexmesh.examples.applications.rocket_injector_manifold`
  writes the mesh; the gallery shows it with its numbers and the
  cut-away.
- Every derived size traceable to a cited rule or a stated choice.
- No new fitting or limit; anything the model needs that hexmesh lacks
  goes under *Questions for design*.
- Full suite: no new failures; the gallery's other meshes unchanged.

**Out of scope.**  The fuel side (a second ring as a second assembly:
a follow-up if this one works); cooling channels; any CFD run; the drum
start for the tank (see *How it has to be built*).

## Agent notes

## Questions for design

## Outcome
