"""
Insulated transition: an insulated round pipe becomes an insulated duct,
turns, and the insulation stops.

    python3 -m hexmesh.examples.sections.insulated_transition # writes insulated_transition.msh

``Transition`` changes the shape of every layer together (task 0046):
each station blends each layer's two end outlines, so the steel and the
insulation turn from circles into rectangles alongside the air, and stay
nested.  The two ends have the same layers, counts per side and radial
gradings.  ``Reducer`` changes sizes, ``Transition`` changes shapes.

Past the duct bend, ``stack_changes`` ends the insulation part-way along
the last straight.  Its end face becomes the ``insulation_end`` wall, and
the bare duct runs on.
"""

from hexmesh import Assembly, Bend, PipeSpec, Straight, Transition
from hexmesh.core.shape import CircleShape, RectShape

NANG = 6


def pipe() -> PipeSpec:
    return (PipeSpec(nang=NANG)
            .core("air", CircleShape(0.1, NANG), nrad=4)
            .shell("steel", dR=0.003, nrad=2)
            .shell("insulation", dR=0.04, nrad=3))


def duct(insulated: bool = True) -> PipeSpec:
    spec = (PipeSpec(nang=NANG)
            .core("air", RectShape(0.15, 0.075, NANG, NANG), nrad=4)
            .shell("steel", dR=0.003, nrad=2))
    return spec.shell("insulation", dR=0.04, nrad=3) if insulated else spec


def build() -> Assembly:
    asm = Assembly(pipe(), direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.4, n_layers=6))
    asm.add(Transition(duct(), length=0.4, n_layers=8))
    asm.add(Straight(0.2, n_layers=3))
    asm.add(Bend(radius=0.35, angle=90, n_layers=12))            # easy way, toward up
    asm.add(Straight(0.6, n_layers=8, stack_changes=((4, duct(insulated=False)),)))
    return asm


def main(output: str = "insulated_transition.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
