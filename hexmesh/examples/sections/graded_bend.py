"""
CFD-ready bend: wall grading, axial cells clustered at the bend, inlet and
outlet extensions, and one wall patch per fitting.

    python3 -m hexmesh.examples.sections.graded_bend # writes graded_bend.msh

- ``first_cell`` grades the core radially toward the wall.
- ``axial_grading`` is the ratio of consecutive axial cells, inlet to
  outlet: below 1 refines the upstream straight toward the bend, above 1
  refines the downstream straight from it.
- ``extend_open_ends`` adds developing lengths, in diameters.
- ``walls_by_fitting=True`` gives ``fluid_wall_<label>`` per fitting, so
  wall data can be read per fitting in the solver.  The extensions have
  no label, so their walls take the default ``<Type><index>`` names
  (``fluid_wall_Straight3``, …).
"""

from hexmesh import Assembly, Bend, PipeSpec, Straight

PIPE = PipeSpec(nang=6).core("fluid", radius=0.05, nrad=6, first_cell=0.003)


def build() -> Assembly:
    asm = Assembly(PIPE, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.4, n_layers=12, axial_grading=0.9), label="upstream")
    asm.add(Bend(radius=0.15, angle=90, n_layers=16), label="bend")
    asm.add(Straight(0.6, n_layers=16, axial_grading=1.1), label="downstream")
    asm.extend_open_ends(upstream=3.0, downstream=6.0, cells_per_diameter=2.0)
    return asm


def main(output: str = "graded_bend.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, walls_by_fitting=True, **options)


if __name__ == "__main__":
    main()
