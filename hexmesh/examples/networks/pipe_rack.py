"""
3-D pipe route mixing every sweep fitting: elbow, riser, segmented miter,
spline offset, reducer and a rolled bend.

    python3 -m hexmesh.examples.networks.pipe_rack # writes pipe_rack.msh

Every fitting starts where the previous one ended, so the route is just a
sequence of ``add`` calls.  ``toward=`` turns a bend toward an absolute
direction, which is how a planar fitting leaves the plane.  The assembly's
``axial_cell`` sets every fitting's axial layers from its length, so no
fitting gives ``n_layers`` (``Elbow`` and ``MiterBend`` have their own
default, so they say ``n_layers=None``).  Fittings of different kinds
share one cross-section, so they join conformally whatever their order
(DESIGN.md P1).
"""

from hexmesh import (Assembly, Bend, Elbow, MiterBend, PipeSpec, Reducer,
                     SplinePipe, Straight)


def pipe(radius: float) -> PipeSpec:
    return (PipeSpec(nang=6)
            .core("fluid", radius=radius, nrad=5)
            .shell("pipe_wall", dR=0.008, nrad=2))


def build() -> Assembly:
    asm = Assembly(pipe(0.08), direction=[1, 0, 0], up=[0, 0, 1], axial_cell=0.07)
    asm.add(Straight(0.5))
    asm.add(Elbow(90, schedule="long", n_layers=None, toward=(0, 0, 1)))   # a riser
    asm.add(Straight(0.6))
    asm.add(MiterBend(radius=0.3, angle=90, n_cuts=3, n_layers=None,
                      toward=(0, -1, 0)))                       # over, sideways

    # Spline jog: shift the line sideways and down while keeping its heading.
    frame = asm.add(Straight(0.3)).frame
    p, t, side = frame.position, frame.normal, frame.right
    asm.add(SplinePipe([p, p + 0.5 * t + 0.15 * side - 0.1 * frame.up,
                        p + 1.0 * t + 0.3 * side - 0.2 * frame.up], end_tangent=t))

    asm.add(Reducer(pipe(0.05), length=0.2))
    asm.add(Bend(radius=0.2, angle=60, toward=(0, 0, 1)))       # up again
    asm.add(Straight(0.4))
    return asm


def main(output: str = "pipe_rack.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
