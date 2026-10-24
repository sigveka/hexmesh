"""
Branched network built as a graph: a header with two tees, each branch
continued with its own fittings.

    python3 -m hexmesh.examples.pipe_network     # writes pipe_network.msh

``add(fitting)`` continues from the tail; ``add(interface, fitting)``
branches from any interface.  Fittings are placed and validated in pure
Python first, then filled in any order (DESIGN.md A6).
"""

from hexmesh import Assembly, Elbow, PipeSpec, Straight, Tee

PIPE = PipeSpec(nang=6).core("water", radius=0.1, nrad=5)


def build() -> Assembly:
    asm = Assembly(PIPE, direction=[1, 0, 0], up=[0, 0, 1])
    header = asm.add(Straight(0.5, n_layers=8))

    branches = []
    for _ in range(2):                             # header with two side taps
        header, branch = asm.add(header, Tee(run_length=0.2, branch_length=0.25,
                                             branch_radius=0.06))
        branches.append(branch)
        header = asm.add(header, Straight(0.4, n_layers=6))
    asm.add(header, Elbow(90, n_layers=10, roll=90), names=["header_end"])

    for k, branch in enumerate(branches):          # turn the taps opposite ways
        turned = asm.add(branch, Elbow(90, schedule="short", n_layers=8,
                                       roll=90 + 180 * k))
        asm.add(turned, Straight(0.3, n_layers=6), names=[f"tap{k}"])
    return asm


def main(output: str = "pipe_network.msh"):
    from hexmesh.examples._run import run
    return run(build, output)


if __name__ == "__main__":
    main()
