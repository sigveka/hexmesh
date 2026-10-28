"""
Layer outlines: a round conductor in a square filler in a round sheath.

    python3 -m hexmesh.examples.sections.layer_outlines # writes layer_outlines.msh

A shell's outline need not be a circle (decision 0026).  ``.shell(name,
outer=…)`` gives a layer its own outline, ``CircleShape`` or
``RectShape``; ``dR`` grows the previous one.  Here the copper's circle
sits in a square filler, and the filler in a round sheath, so the stack
has a circle inside a rectangle and a rectangle inside a circle.  Every
layer goes through the bends as a separate volume, with conformal
``interface_*`` groups between them.

Rules: a stack with a rectangle has one count on every side (``nang``
equals each rectangle's ``nang_w`` and ``nang_h``), and each outline lies
inside the next all round.  Quality falls as the rectangles flatten;
task 0047 measured it.
"""

from hexmesh import Assembly, Bend, PipeSpec, Straight
from hexmesh.core.shape import CircleShape, RectShape

NANG = 6

CABLE = (PipeSpec(nang=NANG)
         .core("copper", radius=0.01, nrad=4)
         .shell("filler", outer=RectShape(0.015, 0.015, NANG, NANG), nrad=3)
         .shell("sheath", outer=CircleShape(0.026, NANG), nrad=3))


def build() -> Assembly:
    asm = Assembly(CABLE, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.1, n_layers=6))
    asm.add(Bend(radius=0.08, angle=90, n_layers=12))            # turn up
    asm.add(Straight(0.06, n_layers=4))
    asm.add(Bend(radius=0.08, angle=-90, n_layers=12, roll=90))  # then sideways
    asm.add(Straight(0.1, n_layers=6))
    return asm


def main(output: str = "layer_outlines.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
