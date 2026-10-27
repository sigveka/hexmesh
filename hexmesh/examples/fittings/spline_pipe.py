"""
Pipe along a 3-D cubic spline through given points.

    python3 -m hexmesh.examples.fittings.spline_pipe # writes spline_pipe.msh

The spline leaves the inlet along its direction; cross-sections follow
rotation-minimising (Bishop) frames, one station per axial layer.
"""

from hexmesh import Assembly, PipeSpec, SplinePipe, Straight

PIPE = (PipeSpec(nang=6)
        .core("fluid", radius=0.05, nrad=4)
        .shell("pipe_wall", dR=0.008, nrad=2))


def build() -> Assembly:
    asm = Assembly(PIPE, direction=[1, 0, 0], up=[0, 0, 1])
    start = asm.add(Straight(0.3, n_layers=6)).frame.position
    points = [start, start + (0.5, 0.2, 0.0), start + (1.0, 0.1, 0.3),
              start + (1.4, 0.5, 0.5)]
    asm.add(SplinePipe(points, n_layers=40, end_tangent=(0, 1, 0)))
    asm.add(Straight(0.3, n_layers=6))
    return asm


def main(output: str = "spline_pipe.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
