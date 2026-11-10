"""
Equal tee: a branch as wide as the main.

    python3 -m hexmesh.examples.fittings.equal_tee # writes equal_tee.msh

A ``Tee`` whose ``branch_radius`` is the main's builds its junction
around an oriented cube, square to all three pipes: a centre hex, a
five-block column to each pipe, and one block on each of the other
three sides, whose outer face is projected onto the wall.
``run_length`` is left out, so the tee resolves the length the cube
needs.  (Limits: circular layers, square and centred, first order only.
The crease where branch and main meet crosses the cube's faces beside
the branch, so its chord error falls as ``nang`` rises: 3.7 % of the
radius at ``nang`` 8.)
"""

from hexmesh import Assembly, PipeSpec, Straight, Tee

PIPE = PipeSpec(nang=8).core("fluid", radius=0.1, nrad=4)


def build() -> Assembly:
    asm = Assembly(PIPE, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.4, n_layers=8))
    main, branch = asm.add(Tee(branch_length=0.4, branch_radius=0.1))
    asm.add(main, Straight(0.3, n_layers=6), names=["main_end"])
    asm.add(branch, Straight(0.3, n_layers=6), names=["branch_end"])
    return asm


def main(output: str = "equal_tee.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
