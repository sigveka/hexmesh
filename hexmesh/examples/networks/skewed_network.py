"""
Off-axis network: a drum on a skewed axis, a nozzle at 35° from vertical,
and fittings at arbitrary angles and rolls.

    python3 -m hexmesh.examples.networks.skewed_network # writes skewed_network.msh

Nothing in hexmesh is tied to the coordinate axes.  Every interface is a
``Frame`` (position, normal, up) in absolute coordinates, so a drum axis,
a start direction, a bend angle and a ``roll`` can all take any value.
Here no pipe runs along x, y or z, and no bend lies in a coordinate plane.
"""

from hexmesh import (Assembly, Bend, Drum, Elbow, MiterBend, Nozzle, OnShell,
                     PipeSpec, Straight, Tee)

PIPE = PipeSpec(nang=6).core("water", radius=0.08, nrad=5)

DRUM = Drum("D201", diameter=1.6, length=4.0, axis=(1, 0.5, 0), up=(0, 0, 1),
            nozzles=[Nozzle("N1", PIPE, OnShell(axial=1.2, angle=35, projection=1.1))])


def build() -> Assembly:
    asm = Assembly.from_nozzle(DRUM, "N1")
    asm.add(Straight(0.3, n_layers=5))
    asm.add(Bend(radius=0.3, angle=50, n_layers=8, roll=30))
    main, branch = asm.add(Tee(run_length=0.2, branch_length=0.25, branch_radius=0.05))

    main = asm.add(main, Straight(0.3, n_layers=5))
    main = asm.add(main, MiterBend(radius=0.3, angle=60, n_cuts=2, n_layers=2, roll=-45))
    asm.add(main, Straight(0.4, n_layers=6), names=["outlet"])

    branch = asm.add(branch, Elbow(75, schedule="long", n_layers=8, roll=135))
    asm.add(branch, Straight(0.3, n_layers=5), names=["branch"])
    return asm


def main(output: str = "skewed_network.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
