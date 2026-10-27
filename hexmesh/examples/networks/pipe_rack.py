"""
3-D pipe route mixing every sweep fitting: elbow, riser, segmented miter,
spline offset, reducer and a rolled bend.

    python3 -m hexmesh.examples.networks.pipe_rack # writes pipe_rack.msh

Every fitting starts where the previous one ended, so the route is just a
sequence of ``add`` calls.  ``roll`` turns a bend about the pipe axis
(0 toward ``up``, 90 toward ``right``), which is how a planar fitting
leaves the plane.  Fittings of different kinds share one cross-section,
so they join conformally whatever their order (DESIGN.md P1).
"""

from hexmesh import (Assembly, Bend, Elbow, MiterBend, PipeSpec, Reducer,
                     SplinePipe, Straight)


def pipe(radius: float) -> PipeSpec:
    return (PipeSpec(nang=6)
            .core("fluid", radius=radius, nrad=5)
            .shell("pipe_wall", dR=0.008, nrad=2))


def build() -> Assembly:
    asm = Assembly(pipe(0.08), direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.5, n_layers=8))
    asm.add(Elbow(90, schedule="long", n_layers=8))            # up: a riser
    asm.add(Straight(0.6, n_layers=8))
    asm.add(MiterBend(radius=0.3, angle=90, n_cuts=3, n_layers=2,
                      roll=90))                                 # over, sideways

    # Spline jog: shift the line sideways and down while keeping its heading.
    frame = asm.add(Straight(0.3, n_layers=4)).frame
    p, t, side = frame.position, frame.normal, frame.right
    asm.add(SplinePipe([p, p + 0.5 * t + 0.15 * side - 0.1 * frame.up,
                        p + 1.0 * t + 0.3 * side - 0.2 * frame.up],
                       n_layers=12, end_tangent=t))

    asm.add(Reducer(pipe(0.05), length=0.2, n_layers=6))
    asm.add(Bend(radius=0.2, angle=60, n_layers=6, roll=-90))
    asm.add(Straight(0.4, n_layers=6))
    return asm


def main(output: str = "pipe_rack.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
