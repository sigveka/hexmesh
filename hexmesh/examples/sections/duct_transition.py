"""
Duct transition: a circular pipe into a 2:1 duct, a duct bend, and back.

    python3 -m hexmesh.examples.sections.duct_transition # writes duct_transition.msh

``Transition`` joins a circle and a rectangle with the same counts per
side: the circle's ``nang`` equals the duct's ``nang_w`` and ``nang_h``.
Then the two faces have the same mesh connectivity (switch class 0), and
every station between them blends the two outlines.  The open ends
become ``air_inlet`` and ``air_outlet``.
(Limits: equal counts per side.  A layer stack changes shape the same way:
``sections.insulated_transition``.)
"""

from hexmesh import Assembly, Bend, PipeSpec, Straight, Transition

PIPE = PipeSpec(nang=6).core("air", radius=0.1, nrad=3)
DUCT = PipeSpec(nang_w=6, nang_h=6).core("air", half_w=0.14, half_h=0.07, nrad=3)


def build() -> Assembly:
    asm = Assembly(PIPE, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.4, n_layers=8))
    asm.add(Transition(DUCT, length=0.3, n_layers=8))
    asm.add(Straight(0.2, n_layers=4))
    asm.add(Bend(radius=0.25, angle=90, n_layers=12))       # easy way, toward up
    asm.add(Straight(0.2, n_layers=4))
    asm.add(Transition(PIPE, length=0.3, n_layers=8))
    asm.add(Straight(0.4, n_layers=8), names=["outlet"])
    return asm


def main(output: str = "duct_transition.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
