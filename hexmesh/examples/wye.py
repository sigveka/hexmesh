"""
Symmetric wye: straight inlet, a 60° Y-junction, a straight on each daughter.

    python3 -m hexmesh.examples.wye              # writes wye.msh

The wye is a block layout around a hub: the inlet core continues into the
hub, each daughter's core leaves one side of it, and the O-grid ring layer
covers the whole junction.  The daughters split in the inlet's (normal,
right) plane.  Ports are named, and the open ends become the patches
``fluid_inlet``, ``fluid_left_end`` and ``fluid_right_end``.
(Prototype limits: single-layer spec, equal daughters, angle 30°–120°.)
"""

from hexmesh import Assembly, PipeSpec, Straight, Wye

PIPE = PipeSpec(nang=6).core("fluid", radius=0.1, nrad=3)


def build() -> Assembly:
    asm = Assembly(PIPE, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.4, n_layers=8))
    left, right = asm.add(Wye(60, run_length=0.3, branch_length=0.5,
                              n_run=4, n_branch=4, n_split=6))
    asm.add(left, Straight(0.4, n_layers=8), names=["left_end"])
    asm.add(right, Straight(0.4, n_layers=8), names=["right_end"])
    return asm


def main(output: str = "wye.msh"):
    from hexmesh.examples._run import run
    return run(build, output)


if __name__ == "__main__":
    main()
