"""
Ventilation supply run: a fan's round outlet, a flat duct through the
building, and a square terminal.

    python3 -m hexmesh.examples.applications.hvac_supply # writes hvac_supply.msh

- A ``Transition`` takes the round fan outlet (Ø 0.3) to a 0.5 × 0.25
  duct.  Counts per side match (``nang`` = ``nang_w`` = ``nang_h``), so the
  two faces have the same mesh connectivity.
- The duct rises with an easy-way bend (``roll=0``: across the height),
  turns along the ceiling with a two-cut mitred hard-way bend
  (``roll=90``: across the width, so its radius is checked against the
  half-width), and jogs sideways with a spline offset.
- A second ``Transition`` (rectangle → rectangle) ends at a 0.3 × 0.3
  square terminal, named ``terminal``.

Patches: ``air_inlet``, ``air_terminal``, ``air_wall``.
"""

from hexmesh import (
    Assembly, Bend, MiterBend, PipeSpec, SplinePipe, Straight, Transition,
)

N = 8      # cells per side, shared by every section so transitions are class 0

FAN = PipeSpec(nang=N).core("air", radius=0.15, nrad=4)
DUCT = PipeSpec(nang_w=N, nang_h=N).core("air", half_w=0.25, half_h=0.125, nrad=4)
TERMINAL = PipeSpec(nang_w=N, nang_h=N).core("air", half_w=0.15, half_h=0.15, nrad=4)


def build() -> Assembly:
    asm = Assembly(FAN, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.4, n_layers=6))
    asm.add(Transition(DUCT, length=0.6, n_layers=6))
    asm.add(Straight(1.0, n_layers=8))
    asm.add(Bend(radius=0.35, angle=90, n_layers=8))             # up: easy way
    asm.add(Straight(1.2, n_layers=12))
    asm.add(MiterBend(radius=0.6, angle=90, n_cuts=2, n_layers=2,
                      roll=90))                                   # sideways: hard way
    run = asm.add(Straight(0.8, n_layers=8))
    # sideways jog of 0.6 over 2.0, leaving and arriving along the duct axis
    p, d, side = run.frame.position, run.frame.normal, -run.frame.right
    asm.add(SplinePipe((tuple(p), tuple(p + 1.0 * d + 0.3 * side),
                        tuple(p + 2.0 * d + 0.6 * side)),
                       n_layers=16, end_tangent=tuple(d)))
    asm.add(Transition(TERMINAL, length=0.4, n_layers=4))
    asm.add(Straight(0.3, n_layers=4), names=["terminal"])
    return asm


def main(output: str = "hvac_supply.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
