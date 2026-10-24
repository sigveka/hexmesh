"""
Three-layer insulated pipe: fluid, steel wall, insulation.

    python3 -m hexmesh.examples.insulated_pipe   # writes insulated_pipe.msh

Each layer is its own physical volume, and the layers meet at conformal
material interfaces (``fluid_to_steel``, …) for conjugate heat transfer.
``Elbow`` takes its radius from the pipe: 1.5 D for a long-radius elbow.
"""

from hexmesh import Assembly, Elbow, PipeSpec, Straight

PIPE = (PipeSpec(nang=6)
        .core("fluid", radius=0.1, nrad=5)
        .shell("steel", dR=0.008, nrad=2)
        .shell("insulation", dR=0.05, nrad=4, mprg=1.2))


def build() -> Assembly:
    asm = Assembly(PIPE, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.8, n_layers=12))
    asm.add(Elbow(90, schedule="long", n_layers=12))
    asm.add(Straight(0.8, n_layers=12))
    return asm


def main(output: str = "insulated_pipe.msh"):
    from hexmesh.examples._run import run
    return run(build, output)


if __name__ == "__main__":
    main()
