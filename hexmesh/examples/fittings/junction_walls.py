"""
Exact junction walls: a tee and a narrow 30° wye, their wall nodes moved
onto the analytic walls after surface meshing.

    python3 -m hexmesh.examples.fittings.junction_walls # writes junction_walls.msh

A junction's wall is not one smooth surface: the tee's is the union of two
cylinders, the wye's the union of three tubes with a sharp crease at the
crotch.  The OCC surfaces between the layout's exact wall curves are
fillings: within 0.03 % of the radius for the tee (plates through wall
points), but 16 % for a 60° wye and 77 % for this 30° one.  So
``Assembly.mesh()`` meshes the surfaces, moves every junction wall node
onto the analytic wall (``hexmesh.assembly.projection.TubeUnion``), then
meshes the volumes from the moved nodes (decision 0029, task 0051).

Near the crotch the nodes move along a smoothed normal, not to the nearest
point, so rows of nodes stay in order across the crease and no cell folds,
down to 30°.  ``Assembly.projection_report`` gives each fitting's largest
move.  The OCC geometry itself stays approximate: export the mesh, not
the CAD.
"""

from hexmesh import Assembly, PipeSpec, Straight, Tee, Wye

PIPE = PipeSpec(nang=8).core("fluid", radius=0.1, nrad=3)


def build() -> Assembly:
    asm = Assembly(PIPE, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.3, n_layers=4))
    main, branch = asm.add(Tee(branch_length=0.3, branch_radius=0.07),
                           names=["main", "branch"])
    asm.add(branch, Straight(0.3, n_layers=4), names=["branch_end"])
    run = asm.add(main, Straight(0.3, n_layers=4))
    left, right = asm.add(run, Wye(30, run_length=0.4, branch_length=0.7))
    asm.add(left, Straight(0.4, n_layers=6), names=["left_end"])
    asm.add(right, Straight(0.4, n_layers=6), names=["right_end"])
    return asm


def report(asm: Assembly) -> None:
    for name, r in asm.projection_report.items():
        print(f"  {name}: wall nodes moved up to {r['move'] / 0.1:.2%} of the radius")


def main(output: str = "junction_walls.msh", **options):
    from hexmesh.examples._run import run
    options.setdefault("inspect", report)
    return run(build, output, **options)


if __name__ == "__main__":
    main()
