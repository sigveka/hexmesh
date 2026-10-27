"""
Closed loop: three bends, a straight, and a ``Closure`` that joins the end
back to the start.

    python3 -m hexmesh.examples.fittings.loop # writes loop.msh

``Assembly.close`` joins two existing open interfaces.  The closure follows
a smooth curve, absorbs any roll mismatch modulo the cross-section symmetry,
and gives an assembly with no open ends (DESIGN.md §8).
"""

from hexmesh import Assembly, Bend, Closure, PipeSpec, Straight

PIPE = (PipeSpec(nang=6)
        .core("fluid", radius=0.1, nrad=5)
        .shell("pipe_wall", dR=0.01, nrad=2))


def build() -> Assembly:
    asm = Assembly(PIPE, direction=[1, 0, 0], up=[0, 0, 1])
    for roll in (0, 20, 0):                        # rolled middle bend: not planar
        asm.add(Straight(0.6, n_layers=6))
        asm.add(Bend(radius=0.3, angle=90, n_layers=8, roll=roll))
    asm.add(Straight(0.6, n_layers=6))
    # validate() rejects a closure that would turn tighter than the pipe
    # radius, so the closing curve needs room: here a 0.6 m run before it.
    asm.close(asm.interfaces[-1], asm.inlet, Closure(n_layers=24))
    return asm


def main(output: str = "loop.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
