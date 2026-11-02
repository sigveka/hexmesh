"""
Branched ventilation supply: a fan's round outlet, a flat main duct with
three taps, and a bend at the end of the run.

    python3 -m hexmesh.examples.applications.hvac_branched # writes hvac_branched.msh

- A ``Transition`` takes the round fan outlet (Ø 0.3) to a 0.5 × 0.25
  duct.  Every section has ``N`` cells per side, which the duct taps need
  too: a tap keeps the main's counts, so its port is class 0.
- Three duct taps (decision 0033): a rectangular tap on the top (wide)
  face and a round tap on the bottom, each pillowed into its face
  (``add()`` resolves the layout's tunables and the run length), and a
  full-width tap on the side (narrow) face, as tall as the duct, whose
  walls are all planes.  A pillowed tap on the narrow face of a 2:1 duct
  predicts a corner scaled Jacobian below 0.3 at any size and warns.
- The main turns sideways, away from the side tap, with a hard-way bend
  (its radius is checked against the half-width), and ends at ``main_end``.
  Axial cells come from ``axial_cell``; the taps' branches are named
  ``supply_up``, ``supply_down`` and ``supply_side``.

Limits: single-layer ducts only (no lagging through a tap); taps are
perpendicular.

Patches: ``air_inlet``, ``air_main_end``, ``air_supply_up``,
``air_supply_down``, ``air_supply_side``, ``air_wall``.
"""

from hexmesh import Assembly, Bend, CircleShape, PipeSpec, Straight, Tee, Transition
from hexmesh.core.shape import RectShape

N = 8      # cells per side, shared by every section and tap
HALF_W, HALF_H = 0.25, 0.125

FAN = PipeSpec(nang=N).core("air", radius=0.15, nrad=4)
DUCT = PipeSpec(nang_w=N, nang_h=N).core("air", half_w=HALF_W, half_h=HALF_H, nrad=4)


def build() -> Assembly:
    asm = Assembly(FAN, direction=[1, 0, 0], up=[0, 0, 1], axial_cell=0.08)
    asm.add(Straight(0.4))
    asm.add(Transition(DUCT, length=0.6))
    asm.add(Straight(0.6))
    # on the top face, half_w runs across the duct and half_h along it
    main, up = asm.add(Tee(branch=RectShape(0.15, 0.1, N, N), branch_length=0.4))
    asm.add(up, Straight(0.4), names=["supply_up"])
    main = asm.add(main, Straight(0.4))
    main, down = asm.add(main, Tee(branch=CircleShape(0.1, N), branch_length=0.4, roll=180))
    asm.add(down, Straight(0.4), names=["supply_down"])
    main = asm.add(main, Straight(0.4))
    # on the side face, half_w runs along the duct and half_h across it:
    # the duct's full half-height, a full-width tap
    main, side = asm.add(main, Tee(branch=RectShape(0.1, HALF_H, N, N), face="narrow",
                                   branch_length=0.4))
    asm.add(side, Straight(0.4), names=["supply_side"])
    main = asm.add(main, Straight(0.4))
    # sideways: the hard way (across the width), away from the side tap
    main = asm.add(main, Bend(radius=0.5, angle=90, roll=-90))
    asm.add(main, Straight(0.6), names=["main_end"])
    return asm


def main(output: str = "hvac_branched.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
