"""
Insulated tee: a three-layer header with a side branch, the steel and the
insulation running through the junction into the branch.

    python3 -m hexmesh.examples.sections.insulated_tee # writes insulated_tee.msh

The branch copies the header's shells (same names, thicknesses and
densities), so ``interface_fluid_steel`` and ``interface_steel_insulation``
each run as one conformal sheet from the header through the tee into the
branch (decision 0028).  Wall and shell-boundary nodes lie exactly on their
offset cylinders: ``mesh()`` projects them onto the analytic surfaces
(decision 0029).

The tee's ``run_length`` is left out: ``add()`` picks one that keeps the
shells' slabs well shaped (``r + T + R/2``, T the total shell thickness).
A run chosen too short is rejected before GMSH, naming the shortest run
that would do.  A branch below about 0.57 of the header radius also warns
at any run: the junction core's quality is set by the branch ratio
(``Assembly.warnings``; task 0052).
"""

from hexmesh import Assembly, Bend, PipeSpec, Straight, Tee

PIPE = (PipeSpec(nang=6)
        .core("fluid", radius=0.1, nrad=5, first_cell=0.01)
        .shell("steel", dR=0.008, nrad=2)
        .shell("insulation", dR=0.04, nrad=3))


def build() -> Assembly:
    asm = Assembly(PIPE, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.5, n_layers=8))
    main, branch = asm.add(Tee(branch_length=0.3, branch_radius=0.06))
    asm.add(main, Straight(0.5, n_layers=8), names=["main_end"])
    bend = asm.add(branch, Bend(radius=0.3, angle=90, n_layers=10))
    asm.add(bend, Straight(0.3, n_layers=6), names=["branch_end"])
    return asm


def report(asm: Assembly) -> None:
    tee = asm.edges[1].fitting
    print(f"  tee run_length resolved to {tee.run_length:.4g}")
    for msg in asm.warnings:
        print(f"  warning: {msg.split(': ', 1)[1]}")


def main(output: str = "insulated_tee.msh", **options):
    from hexmesh.examples._run import run
    options.setdefault("inspect", report)
    return run(build, output, **options)


if __name__ == "__main__":
    main()
