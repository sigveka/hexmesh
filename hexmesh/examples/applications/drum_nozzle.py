"""
Line from a drum nozzle: a horizontal drum with a top nozzle, a riser, an
elbow, a tee and CFD extensions on the open ends.

    python3 -m hexmesh.examples.applications.drum_nozzle # writes drum_nozzle.msh

``Drum`` builds no geometry; it gives the nozzle face's pose (decision
0002).  ``Assembly.from_nozzle`` starts the network there, and the inlet
patch is named after the drum and nozzle (``water_D101_N1``).
``extend_open_ends`` adds straight runs after every open outlet, sized in
diameters of each end; the nozzle end is never extended.
"""

from hexmesh import Assembly, Drum, Elbow, Nozzle, OnShell, PipeSpec, Straight, Tee

PIPE = PipeSpec(nang=6).core("water", radius=0.08, nrad=5)

DRUM = Drum("D101", diameter=2.0, length=6.0, head="ellipsoidal_2_1",
            nozzles=[Nozzle("N1", PIPE, OnShell(axial=1.5, angle=0, projection=1.3))])


def build() -> Assembly:
    asm = Assembly.from_nozzle(DRUM, "N1")
    asm.add(Straight(0.4, n_layers=6))                     # riser off the top
    asm.add(Elbow(90, schedule="long", n_layers=10))       # along the drum axis
    main, branch = asm.add(Tee(run_length=0.2, branch_length=0.25, branch_radius=0.05))
    asm.add(main, Straight(0.4, n_layers=6), names=["outlet"])
    asm.add(branch, Elbow(90, schedule="short", n_layers=8), names=["vent"])
    asm.extend_open_ends(downstream=5.0, cells_per_diameter=2.0)
    return asm


def main(output: str = "drum_nozzle.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
