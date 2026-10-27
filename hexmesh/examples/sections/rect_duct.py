"""
Rectangular duct: a 2:1 duct with an easy-way and a hard-way bend.

    python3 -m hexmesh.examples.sections.rect_duct # writes rect_duct.msh

The width runs along the frame's ``right`` and the height along ``up``.
A bend with ``roll=0`` turns toward ``up``, across the short side: the
"easy way" for a flat duct.  ``roll=90`` turns toward ``right``, across the
long side: the "hard way", which needs the larger bend radius (it is
checked against the half-width).  The open ends become ``air_inlet`` and
``air_outlet``.
(Limits: single-layer ducts; no reducer, tee or elbow for ducts yet.)
"""

from hexmesh import Assembly, Bend, PipeSpec, Straight

DUCT = PipeSpec(nang_w=8, nang_h=4).core("air", half_w=0.1, half_h=0.05, nrad=3)


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
