"""
Reducer, bend and expander: a line that narrows, turns and widens again.

    python3 -m hexmesh.examples.reducer_network  # writes reducer_network.msh

A ``Reducer`` may change radii only; the layer stack and every density
parameter must match on both sides, which ``validate`` checks before GMSH.
"""

from hexmesh import Assembly, Bend, PipeSpec, Reducer, Straight


def pipe(radius: float) -> PipeSpec:
    return (PipeSpec(nang=6)
            .core("fluid", radius=radius, nrad=5)
            .shell("pipe_wall", dR=0.01, nrad=2))


def build() -> Assembly:
    asm = Assembly(pipe(0.1), direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.4, n_layers=8))
    asm.add(Reducer(pipe(0.06), length=0.2, n_layers=6))
    asm.add(Bend(radius=0.2, angle=180, n_layers=24))          # hairpin
    asm.add(Straight(0.3, n_layers=6))
    asm.add(Reducer(pipe(0.1), length=0.2, n_layers=6))       # expander
    asm.add(Straight(0.4, n_layers=8))
    return asm


def main(output: str = "reducer_network.msh"):
    from hexmesh.examples._run import run
    return run(build, output)


if __name__ == "__main__":
    main()
