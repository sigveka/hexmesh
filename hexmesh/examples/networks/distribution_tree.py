"""
Two-level distribution tree: a header with two tees, and a second tee on
one of the branches after a reducer.

    python3 -m hexmesh.examples.networks.distribution_tree # writes distribution_tree.msh

A tee's branch outlet carries a smaller spec, so every fitting after it is
sized from the branch.  To tee off a branch, first widen it with a
``Reducer``: a tee needs its branch smaller than the pipe it sits on.
The outlets are named, so each open end becomes its own patch
(``water_branch_a``, …), and the branches use different bend kinds.
"""

from hexmesh import Assembly, Elbow, MiterBend, PipeSpec, Reducer, Straight, Tee


def pipe(radius: float) -> PipeSpec:
    return PipeSpec(nang=6).core("water", radius=radius, nrad=5)


def build() -> Assembly:
    asm = Assembly(pipe(0.1), direction=[1, 0, 0], up=[0, 0, 1])
    header = asm.add(Straight(0.4, n_layers=6))
    header, first = asm.add(header, Tee(run_length=0.2, branch_length=0.25,
                                        branch_radius=0.06))
    header = asm.add(header, Straight(0.6, n_layers=8))
    header, second = asm.add(header, Tee(run_length=0.2, branch_length=0.25,
                                         branch_radius=0.06))
    asm.add(header, MiterBend(radius=0.25, angle=90, n_cuts=2, n_layers=2, roll=90),
            names=["header_end"])

    # First branch: turn back upstream, widen, and split again.
    line = asm.add(first, Elbow(90, schedule="long", n_layers=8, roll=180))
    line = asm.add(line, Reducer(pipe(0.08), length=0.15, n_layers=4))
    line, tap = asm.add(line, Tee(run_length=0.15, branch_length=0.2,
                                  branch_radius=0.04))
    asm.add(line, Straight(0.3, n_layers=4), names=["branch_a"])
    asm.add(tap, Straight(0.2, n_layers=4), names=["branch_a_tap"])

    # Second branch: a single miter joint downstream.
    line = asm.add(second, Straight(0.2, n_layers=4))
    line = asm.add(line, MiterBend(radius=0.15, angle=90, n_cuts=1, n_layers=3))
    asm.add(line, Straight(0.3, n_layers=4), names=["branch_b"])
    return asm


def main(output: str = "distribution_tree.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
