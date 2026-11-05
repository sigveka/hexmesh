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
Rectangular duct: a 2:1 duct with an easy-way and a hard-way bend.

    python3 -m hexmesh.examples.sections.rect_duct # writes rect_duct.msh

The width runs along the frame's ``right`` and the height along ``up``.
A bend with ``roll=0`` turns toward ``up``, across the short side: the
"easy way" for a flat duct.  ``roll=90`` turns toward ``right``, across the
long side: the "hard way", which needs the larger bend radius (it is
checked against the half-width).  The open ends become ``air_inlet`` and
``air_outlet``.

The section is an H face, one Cartesian patch (the default for a
rectangle since 0.4.0).  ``first_cell`` grades its walls: the end cell of
every side, here 4 mm against a uniform cell of 12.5 mm.  ``layout="oh"`` with ``nrad=`` gives the O-H
face instead.
(Limits: no elbow for ducts yet; duct tees are single-layer.  A duct with a wall and lagging:
``sections.lagged_duct``.)
"""

from hexmesh import Assembly, Bend, PipeSpec, Straight

# walls graded to a 4 mm first cell (a uniform cell is 12.5 mm)
DUCT = PipeSpec(nang_w=16, nang_h=8).core("air", half_w=0.1, half_h=0.05, first_cell=0.004)


def build() -> Assembly:
    asm = Assembly(DUCT, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.4, n_layers=8))
    asm.add(Bend(radius=0.15, angle=90, n_layers=10))             # easy way
    asm.add(Straight(0.3, n_layers=6))
    asm.add(Bend(radius=0.25, angle=90, n_layers=12, roll=90))    # hard way
    asm.add(Straight(0.4, n_layers=8), names=["outlet"])
    return asm


def main(output: str = "rect_duct.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
