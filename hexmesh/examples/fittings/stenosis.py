"""
Stenosis: a smooth cosine constriction in a straight pipe, the benchmark
geometry of Varghese et al. (RESEARCH §7.3).

    python3 -m hexmesh.examples.fittings.stenosis # writes stenosis.msh

A profiled ``Reducer`` with ``profile=("cosine", s0)`` narrows the pipe to
a throat of radius ``(1 − 2·s0)·R`` and widens it back over ``length``.
The defaults are the benchmark: ``s0 = 0.25`` (75 % area reduction),
``length = 2 D``, 3 D of pipe upstream and 16 D downstream of the throat.
Every wall node at a station lies on the profile, and ``validate`` rejects
a chord further than ``chord_tol`` from it, naming the layers needed.

``s0 < 0`` makes a bulge instead (an aneurysm, an expansion chamber), of
largest radius ``(1 − 2·s0)·R``; ``s0 = 0`` is a plain pipe.

The counts are fixed, not derived from the geometry, so every
``build(s0, length_d)`` with ``−1 ≤ s0 ≤ 0.25`` and ``length_d ≥ 1`` has
the same mesh connectivity: node *i* is the same point of the network in
every variant, only moved.  That is what a parameter study or a surrogate
model over shapes needs, from constriction through plain pipe to bulge.
The counts are sized for the variant needing the most layers: the bulge
``s0 = −1`` needs 71 to keep every wall chord within ``chord_tol`` of the
profile (a constriction of 0.25 needs 36).

Fittings are labelled, so with ``walls_by_fitting=True`` the constriction's
wall is its own patch (``fluid_wall_stenosis``), e.g. for wall shear
stress.  Open ends: ``fluid_inlet``, ``fluid_outlet``.
"""

from hexmesh import Assembly, PipeSpec, Reducer, Straight

D = 0.02                                  # pipe diameter
UPSTREAM, DOWNSTREAM = 3.0, 16.0          # diameters from the throat
N_UP, N_STENOSIS, N_DOWN = 10, 71, 48     # fixed counts: aligned variants

PIPE = PipeSpec(nang=6).core("fluid", radius=D / 2, nrad=6, first_cell=D / 40)


def build(s0: float = 0.25, length_d: float = 2.0) -> Assembly:
    """The constriction of severity *s0* and length *length_d* diameters."""
    length = length_d * D
    asm = Assembly(PIPE, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(UPSTREAM * D - length / 2, n_layers=N_UP), label="upstream")
    asm.add(Reducer(PIPE, length, n_layers=N_STENOSIS, profile=("cosine", s0)),
            label="stenosis")
    asm.add(Straight(DOWNSTREAM * D - length / 2, n_layers=N_DOWN,
                     axial_grading=1.03), label="downstream", names=["outlet"])
    return asm


def main(output: str = "stenosis.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, walls_by_fitting=True, **options)


if __name__ == "__main__":
    main()
