"""
Mitred bends: a single 90° miter joint and a 3-cut segmented elbow.

    python3 -m hexmesh.examples.miter_bend       # writes miter_bend.msh

A ``MiterBend`` has the same ports as the smooth ``Bend`` with equal radius
and angle.  Its cut faces are the exact ellipses where the straight pipe
pieces meet, so wall nodes on a cut lie on both pipes.
"""

from hexmesh import Assembly, MiterBend, PipeSpec, Straight

PIPE = (PipeSpec(nang=6)
        .core("fluid", radius=0.1, nrad=5)
        .shell("pipe_wall", dR=0.01, nrad=2))


def build() -> Assembly:
    asm = Assembly(PIPE, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.4, n_layers=8))
    asm.add(MiterBend(radius=0.25, angle=90, n_cuts=1, n_layers=3))   # single joint
    asm.add(Straight(0.4, n_layers=8))
    asm.add(MiterBend(radius=0.4, angle=90, n_cuts=3, n_layers=3, roll=90))
    asm.add(Straight(0.4, n_layers=8))
    return asm


def main(output: str = "miter_bend.msh"):
    from hexmesh.examples._run import run
    return run(build, output)


if __name__ == "__main__":
    main()
