"""
Branched network built as a graph: a header with two side taps, each
pointing a different way.

    python3 -m hexmesh.examples.networks.pipe_network # writes pipe_network.msh

``add(fitting)`` continues from the tail; ``add(interface, fitting)``
branches from any interface.  ``toward=`` gives absolute directions, so a
tee's branch can leave sideways without an extra elbow.  Fittings are
placed and validated in pure Python first, then filled in any order
(DESIGN.md A6).
"""

from hexmesh import Assembly, Elbow, PipeSpec, Straight, Tee

PIPE = PipeSpec(nang=6).core("water", radius=0.1, nrad=5)


def build() -> Assembly:
    asm = Assembly(PIPE, direction=[1, 0, 0], up=[0, 0, 1])
    header = asm.add(Straight(0.5, n_layers=8))

    for k, side in enumerate([(0, 1, 0), (0, -1, 0)]):   # taps to +y, then -y
        header, branch = asm.add(header, Tee(run_length=0.2, branch_length=0.25,
                                             branch_radius=0.06, toward=side))
        asm.add(branch, Straight(0.3, n_layers=6), names={"outlet": f"tap{k}"})
        header = asm.add(header, Straight(0.4, n_layers=6))
    asm.add(header, Elbow(90, n_layers=10, toward=(0, 0, 1)), names=["header_end"])
    return asm


def main(output: str = "pipe_network.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
