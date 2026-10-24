"""
Smooth 90° bend between two straight runs.

    python3 -m hexmesh.examples.smooth_bend      # writes smooth_bend.msh

The bend places a station at every axial layer and joins them with exact
circular arcs, so every wall node lies on the torus.
"""

from hexmesh import Assembly, Bend, PipeSpec, Straight

PIPE = (PipeSpec(nang=6)
        .core("fluid", radius=0.1, nrad=5)
        .shell("pipe_wall", dR=0.01, nrad=2))


def build() -> Assembly:
    asm = Assembly(PIPE, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.5, n_layers=10))
    asm.add(Bend(radius=0.3, angle=90, n_layers=12))
    asm.add(Straight(0.5, n_layers=10))
    return asm


def main(output: str = "smooth_bend.msh"):
    from hexmesh.examples._run import run
    return run(build, output)


if __name__ == "__main__":
    main()
