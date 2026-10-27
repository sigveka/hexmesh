"""
Side-branch tee: straight run, tee, then a bend on the main line.

    python3 -m hexmesh.examples.fittings.tee # writes tee.msh

The tee is a block layout: its O-grid ring layer turns continuously from
the main pipe into the branch, so the junction is all-hex with no merged
nodes.  Ports are named, and the open ends become the patches
``fluid_inlet``, ``fluid_main_end`` and ``fluid_branch_end``.
(Prototype limits: single-layer spec, branch radius below the main radius.)
"""

from hexmesh import Assembly, Bend, PipeSpec, Straight, Tee

PIPE = PipeSpec(nang=6).core("fluid", radius=0.1, nrad=5)


def build() -> Assembly:
    asm = Assembly(PIPE, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.4, n_layers=8))
    main, branch = asm.add(Tee(run_length=0.2, branch_length=0.25, branch_radius=0.06))
    # add(interface, fitting) branches from that interface; it returns the
    # new outlet, which is where the next fitting on that line attaches.
    bend = asm.add(main, Bend(radius=0.3, angle=90, n_layers=12, roll=90))
    asm.add(bend, Straight(0.3, n_layers=6), names=["main_end"])
    asm.add(branch, Straight(0.3, n_layers=6), names=["branch_end"])
    return asm


def main(output: str = "tee.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
