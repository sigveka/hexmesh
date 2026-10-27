"""
Insulated route: a three-layer stack carried through a reducer, a miter, a
spline and an elbow.

    python3 -m hexmesh.examples.sections.insulated_route # writes insulated_route.msh

Every sweep fitting takes the whole layer stack, so fluid, steel and
insulation stay separate volumes with conformal ``interface_*`` groups
along the full route.  The reducer shrinks the core and keeps the shell
thicknesses; it may change radii only, never the stack or the densities
(CLAUDE.md, "Parameter separation").  The fluid core is graded from the
wall with ``first_cell``.
"""

from hexmesh import (Assembly, Elbow, MiterBend, PipeSpec, Reducer,
                     SplinePipe, Straight)


def pipe(radius: float) -> PipeSpec:
    return (PipeSpec(nang=6)
            .core("fluid", radius=radius, nrad=6, first_cell=0.1 * radius)
            .shell("steel", dR=0.006, nrad=2)
            .shell("insulation", dR=0.04, nrad=3, mprg=1.2))


def build() -> Assembly:
    asm = Assembly(pipe(0.1), direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.5, n_layers=8))
    asm.add(Reducer(pipe(0.07), length=0.25, n_layers=6))
    asm.add(Straight(0.3, n_layers=4))
    asm.add(MiterBend(radius=0.3, angle=90, n_cuts=1, n_layers=3, roll=90))

    frame = asm.add(Straight(0.3, n_layers=4)).frame
    p, t = frame.position, frame.normal
    asm.add(SplinePipe([p, p + 0.4 * t + 0.2 * frame.up, p + 0.9 * t + 0.3 * frame.up],
                       n_layers=10, end_tangent=t))

    asm.add(Elbow(90, schedule="short", n_layers=8, roll=180))   # turn down
    asm.add(Straight(0.4, n_layers=6))
    return asm


def main(output: str = "insulated_route.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
