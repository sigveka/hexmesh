#        _.-------._
#    .-''     |     ''-.
#  .'  \      |      /  '.     _                                         _
# /     +-----+-----+     \   | |__   ___  __  __  _ __ ___   ___  ___  | |__
# |     |     |     |     |   | '_ \ / _ \ \ \/ / | '_ ` _ \ / _ \/ __| | '_ \
# |-----+-----+-----+-----|   | | | |  __/  >  <  | | | | | |  __/\__ \ | | | |
# |     |     |     |     |   |_| |_|\___| /_/\_\ |_| |_| |_|\___||___/ |_| |_|
# \     +-----+-----+     /
#  '.  /      |      \  .'    structured all-hex meshes for pipe networks
#    '-..     |     ..-'
#        '---------'
#
"""
District heating: a buried pre-insulated pipe, its soil meshed with it,
turning a street corner.

    python3 -m hexmesh.examples.applications.district_heating # writes district_heating.msh

A district-heating main is a steel service pipe, insulated with
polyurethane foam (PUR) inside a polyethylene casing, all bonded together
and buried (the single pipes of EN 253).  Heat lost to the ground is what
a model of it is usually for, so the soil is part of the mesh:
- a **square of near soil** around the casing, finely meshed, where the
  temperature changes fastest;
- a **rectangle of far soil** around that, to the domain's boundary, its
  cells growing outward (radial grading, ``mprg``).

Every layer is a region of its own, with an interface to the next, so a
conjugate heat-transfer case can give each its conductivity.

**Typical values, not checked against the standard's table** (EN 253's
dimension table is not open): a DN 100 service pipe, 114.3 mm × 3.6 mm
steel, in a 200 mm casing (a manufacturer's insulation series 1) with a
3.2 mm wall.

**Not from a source** (modelling choices, stated as such):
- the near soil 0.6 m square, the far soil 3.0 m wide and 2.4 m deep;
- **the pipe is centred in the soil.**  A buried pipe sits about a metre
  down, nearer the surface than the bottom of a heat-loss domain.  An
  off-centre pipe in a rectangle isn't a hexmesh section today;
- the run: 3 m, a 90° bend of 3 m radius, 3 m.

**The pair waits for a design.**  Real networks lay a supply and a
return pipe side by side, hot and cold.  Two pipes in one block of soil
is a section with two cores, decision 0035 stage B, whose first case
this is (the user, 2026-11-12): each pipe in its square of near soil,
the two squares side by side, and the far soil around both.  The far
layer then also carries the depth: thinner above the pair than below.

**Colours** mean something here: water red, steel grey, PUR yellow,
casing black, near soil light brown, far soil dark brown.

Ends ``supply`` and ``house_side``.
"""

from hexmesh import Assembly, Bend, PipeSpec, Straight
from hexmesh.core.shape import RectShape
from hexmesh.units import mm

# Typical DN 100 single pipe, insulation series 1 (see the docstring).
STEEL_OD, STEEL_WALL, CASING_OD, CASING_WALL = 114.3 * mm, 3.6 * mm, 200 * mm, 3.2 * mm
# Not from a source (see the docstring).
NEAR_SOIL, FAR_W, FAR_H = 0.6, 3.0, 2.4
L_RUN, BEND_RADIUS = 3.0, 3.0

N = 8  # cells per 90° of every ring, and per side of every rectangle

SPEC = (PipeSpec(nang=N).core("water", radius=STEEL_OD / 2 - STEEL_WALL, nrad=4)
        .shell("steel", dR=STEEL_WALL, nrad=1)
        .shell("pur", dR=CASING_OD / 2 - CASING_WALL - STEEL_OD / 2, nrad=3)
        .shell("casing", dR=CASING_WALL, nrad=1)
        .shell("near_soil", outer=RectShape(NEAR_SOIL / 2, NEAR_SOIL / 2, N, N), nrad=4,
               mprg=1.2)
        .shell("far_soil", outer=RectShape(FAR_W / 2, FAR_H / 2, N, N), nrad=5, mprg=1.3))

#: The gallery's colours (``docs/gallery/build.py``).
GALLERY_COLOURS = {"water": ("#c0392b", "red"), "steel": ("#8e979f", "grey"),
                   "pur": ("#e8c547", "yellow"), "casing": ("#2b2b2b", "black"),
                   "near_soil": ("#c49a6c", "light brown"), "far_soil": ("#7a5230", "dark brown")}


def build() -> Assembly:
    asm = Assembly(SPEC, direction=[1, 0, 0], up=[0, 0, 1], inlet_name="supply")
    end = asm.add(Straight(L_RUN, n_layers=12))
    end = asm.add(end, Bend(radius=BEND_RADIUS, angle=90, toward=(0, 1, 0), n_layers=12))
    asm.add(end, Straight(L_RUN, n_layers=12), names=["house_side"])
    return asm


def gallery_cutaway() -> dict:
    """The gallery's cut-away: the first metre of the run, inside the near
    soil, cut along the vertical plane through the pipe's axis and
    coloured by material, so every layer shows."""
    def keep(c):
        return (c[:, 0] < 1.0) & (abs(c[:, 1]) < NEAR_SOIL / 2) & \
               (abs(c[:, 2]) < NEAR_SOIL / 2) & (c[:, 1] > 0)

    return {"keep": keep, "direction": (-0.8, -1.0, 0.55), "up": (0, 0, 1), "by_material": True}


def main(output: str = "district_heating.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
