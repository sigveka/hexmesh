"""
Insulated network: a three-layer header with a tee and a wye, the steel and
the insulation running through both junctions, and one branch left bare.

    python3 -m hexmesh.examples.sections.insulated_network # writes insulated_network.msh

Junctions carry the whole layer stack (decision 0028): the tee's branch
copies the header's shells, and the wye's daughters keep the header's
spec, so every ``interface_*`` group is one conformal sheet through the
network.  The tee's branch is bare beyond its first cell: its straight's
``stack_changes`` drops the insulation, and the annulus where it stops is
``insulation_end`` (decision 0006).  That is where the PCF reader places a
bare leg's switch too (task 0054).

Junction shells have limits, checked before GMSH (``API.md``): a wye with
shells needs 40° or more, and its total shell thickness at most
R · min(0.65 tan(angle/2), 0.55), 0.375 R at 60°; here 0.31 R.
"""

from hexmesh import Assembly, PipeSpec, Straight, Tee, Wye


def pipe(radius: float, insulated: bool = True) -> PipeSpec:
    spec = (PipeSpec(nang=6)
            .core("fluid", radius=radius, nrad=5, mprg=0.85)
            .shell("steel", dR=0.006, nrad=2))
    return spec.shell("insulation", dR=0.025, nrad=2) if insulated else spec


def build() -> Assembly:
    asm = Assembly(pipe(0.1), direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.4, n_layers=6))
    main, branch = asm.add(Tee(branch_length=0.3, branch_radius=0.06))
    asm.add(branch, Straight(0.4, n_layers=6,
                             stack_changes=((1, pipe(0.06, insulated=False)),)),
            names=["tap"])
    header = asm.add(main, Straight(0.4, n_layers=6))
    left, right = asm.add(header, Wye(60, run_length=0.15, branch_length=0.4))
    asm.add(left, Straight(0.3, n_layers=4), names=["left"])
    asm.add(right, Straight(0.3, n_layers=4), names=["right"])
    return asm


def report(asm: Assembly) -> None:
    tee = next(e.fitting for e in asm.edges if isinstance(e.fitting, Tee))
    print(f"  tee run_length resolved to {tee.run_length:.4g}")
    for msg in asm.warnings:
        print(f"  warning: {msg.split(': ', 1)[1]}")


def main(output: str = "insulated_network.msh", **options):
    from hexmesh.examples._run import run
    options.setdefault("inspect", report)
    return run(build, output, **options)


if __name__ == "__main__":
    main()
