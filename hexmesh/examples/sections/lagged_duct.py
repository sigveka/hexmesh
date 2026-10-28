"""
Lagged duct: a rectangular air duct with a steel wall and lagging,
through a reducer and bends both ways.

    python3 -m hexmesh.examples.sections.lagged_duct # writes lagged_duct.msh

``dR`` around a rectangle grows it: half_w and half_h each by ``dR``,
corners kept sharp (decision 0026).  So the wall and the lagging are
rectangles too, and every ring's corner lines run along the diagonals.
The ``Reducer`` shrinks every layer's outline at once; it changes sizes
only.  A change of shape is a ``Transition``
(``sections.insulated_transition``).

Rules: a stack with a rectangle has one count on every side, here 6
(``nang = nang_w = nang_h``).
"""

from hexmesh import Assembly, Bend, PipeSpec, Reducer, Straight
from hexmesh.core.shape import RectShape

NANG = 6


def duct(half_w: float, half_h: float) -> PipeSpec:
    return (PipeSpec(nang=NANG)
            .core("air", RectShape(half_w, half_h, NANG, NANG), nrad=3)
            .shell("steel", dR=0.002, nrad=2)
            .shell("lagging", dR=0.03, nrad=3))


def build() -> Assembly:
    asm = Assembly(duct(0.2, 0.1), direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.6, n_layers=6))
    asm.add(Bend(radius=0.4, angle=90, n_layers=12))             # easy way, toward up
    asm.add(Straight(0.3, n_layers=3))
    asm.add(Reducer(duct(0.14, 0.07), length=0.3, n_layers=4))
    asm.add(Straight(0.3, n_layers=3))
    asm.add(Bend(radius=0.4, angle=90, n_layers=12, roll=90))    # hard way, sideways
    asm.add(Straight(0.6, n_layers=6))
    return asm


def main(output: str = "lagged_duct.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
