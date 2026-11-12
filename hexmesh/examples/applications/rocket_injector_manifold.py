#        _.-------._
#    .-''     |     ''-.
#  .'  \      |      /  '.     _                                         _
# /     +-----+-----+     \   | |__   ___  __  __  _ __ ___   ___  ___  | |__
# |     |     |     |     |   | '_ \ / _ \ \ \/ / | '_ ` _ \ / _ \/ __| | '_ \
# |-----+-----+-----+-----|   | | | |  __/  >  <  | | | | | |  __/\__ \ | | | |
# |     |     |     |     |   |_| |_|\___| /_/\_\ |_| |_| |_|\___||___/ |_| |_|
# \     +-----+-----+     /
#  '.  /      |      \  .'    structured all-hex meshes for pipe networks
#    '-..     |     ..-'
#        '---------'
#
"""
Rocket injector manifold: a liquid-oxygen ring feeding eight injector
legs, supplied by an insulated feed line through a cavitating venturi.

    python3 -m hexmesh.examples.applications.rocket_injector_manifold # writes rocket_injector_manifold.msh

A liquid-rocket engine's oxidiser reaches the injector through a
manifold: a ring around the injector that spreads the flow evenly to its
feeds.  Test stands and pressure-fed engines put a **cavitating venturi**
in the feed line.  Once its throat cavitates, the flow depends only on
the upstream pressure, so it fixes the mass flow and isolates the line
from chamber-pressure oscillations.

**The ring is a closed loop** (`Assembly.close`): nine tees, one for
the feed line and eight for the injector legs, joined by 40° bends, the
last bend closing back onto the ring's start.  The feed line is the
feed tee's branch, built outward to the tank end, ``lox_inlet``.

**Where each number comes from:**
- **The line velocity** is the worked example's in Huzel and Huang,
  NASA SP-125 (`huzel_and_huang_1971`, p. 286): liquid oxygen at 79.4
  ft/s (24.2 m/s) in an 8 in. duct.
- **The venturi's divergent**, 8°, from the 6°–8° of a cavitating
  venturi patent for propellants (`us5647201`), within ISO 5167-4's
  7°–15° that hexmesh's venturi profile takes.

**Not from a source** (modelling choices, stated as such):
- **the engine:** 50 kN thrust, liquid oxygen and RP-1 at a mixture
  ratio of 2.35, specific impulse 280 s: 12.8 kg/s of oxygen
  (1141 kg/m³), 11.2 L/s;
- **the feed line** at the line velocity: 24.3 mm bore;
- **the ring and the injector legs at a third of it** (the ring slow, so
  the legs see the same pressure): a 29.7 mm ring, each half carrying
  half the flow, and 14.9 mm legs, each an eighth;
- the venturi's throat at half the bore (β 0.5), the ring's 60 mm bend
  radius, the tees' 30 mm runs, the lengths of the feed line and legs;
- 1.5 mm steel everywhere, and 20 mm of foam insulation on the feed line
  only, starting two cells out from the ring (a stack change);
- the venturi necks every layer down with the bore, insulation
  included.  A real venturi body is straight outside: a simplification.

**Quality:** each injector tee warns: predicted min scaled Jacobian 0.258
below the 0.3 tier, at a branch ratio r/R of 0.5 ("no run length reaches
it").  Faster legs would be narrower and worse; the warning is the cost
of eight legs off a slow ring.  No cell is inverted.

Inlet ``lox_inlet``; outlets ``injector_1`` … ``injector_8``.  The
ring's start, ``ring_start``, is closed: it isn't an open end.
"""

import math

import numpy as np

from hexmesh import Assembly, Bend, PipeSpec, Reducer, Straight, Tee
from hexmesh.units import mm

# Huzel and Huang, NASA SP-125, p. 286: liquid oxygen, 79.4 ft/s.
V_LINE = 79.4 * 0.3048
# US 5,647,201: a 6°–8° divergent.
VENTURI_DIVERGENT = 8.0
# Not from a source (see the docstring).
THRUST, ISP, MIXTURE_RATIO, LOX_DENSITY, G0 = 50e3, 280.0, 2.35, 1141.0, 9.80665
N_INJECTORS = 8
VENTURI_BETA = 0.5
WALL, INSULATION = 1.5 * mm, 20 * mm
RING_BEND, RUN = 0.06, 0.03

LOX_FLOW = THRUST / (ISP * G0) * MIXTURE_RATIO / (1 + MIXTURE_RATIO) / LOX_DENSITY  # m³/s
D_FEED = math.sqrt(4 * LOX_FLOW / (math.pi * V_LINE))
D_RING = math.sqrt(4 * (LOX_FLOW / 2) / (math.pi * V_LINE / 3))
D_LEG = math.sqrt(4 * (LOX_FLOW / N_INJECTORS) / (math.pi * V_LINE / 3))

NANG = 8


def pipe(diameter: float) -> PipeSpec:
    """Liquid oxygen in a steel tube of bore *diameter*."""
    return (PipeSpec(nang=NANG).core("lox", radius=diameter / 2, nrad=4)
            .shell("steel", dR=WALL, nrad=2))


#: The gallery's colours (``docs/gallery/build.py``).
GALLERY_COLOURS = {"lox": ("#6fa8dc", "light blue"), "steel": ("#8e979f", "grey"),
                   "insulation": ("#e8c547", "yellow")}


def build() -> Assembly:
    asm = Assembly(pipe(D_RING), direction=[1, 0, 0], up=[0, 0, 1], inlet_name="ring_start")
    n = N_INJECTORS + 1
    end, feed = asm.inlet, None
    for k in range(n):
        if k == 0:     # the feed tee: its branch points out of the ring
            out = tuple(np.cross(end.frame.normal, (0, 0, 1)))
            end, feed = asm.add(end, Tee(run_length=RUN, branch_radius=D_FEED / 2,
                                         branch_length=3 * D_FEED, toward=out))
        else:          # an injector tee: its branch points down, at the injector face
            end, leg = asm.add(end, Tee(run_length=RUN, branch_radius=D_LEG / 2,
                                        branch_length=2 * D_RING, toward=(0, 0, -1)))
            asm.add(leg, Straight(4 * D_LEG, n_layers=4), names=[f"injector_{k}"])
        left = tuple(np.cross((0, 0, 1), end.frame.normal))
        bend = Bend(radius=RING_BEND, angle=360 / n, toward=left, n_layers=6)
        if k < n - 1:
            end = asm.add(end, bend)
        else:          # the last bend closes the ring
            asm.close(end, asm.inlet, bend)
    # The feed line: insulated from two cells out, then up toward the tank
    # through the venturi.
    insulated = pipe(D_FEED).shell("insulation", dR=INSULATION, nrad=2)
    end = asm.add(feed, Straight(0.12, n_layers=8, stack_changes=((2, insulated),)))
    end = asm.add(end, Bend(radius=0.08, angle=90, toward=(0, 0, 1), n_layers=8))
    end = asm.add(end, Straight(0.15, n_layers=6))
    end = asm.add(end, Reducer(insulated, length=0.3, n_layers=30,
                               profile=("venturi", VENTURI_BETA, VENTURI_DIVERGENT)))
    asm.add(end, Straight(0.2, n_layers=6), names=["lox_inlet"])
    return asm


def gallery_cutaway() -> dict:
    """The gallery's cut-away: the feed tee, its branch and the half-bends
    either side of it, the upper half removed and coloured by material, so the
    junction's core shows.

    The ring's centre is at (RUN, a), a = RUN / tan(φ/2) + RING_BEND for a
    turn φ per sector.  By symmetry each bend's middle station lies on a
    radial plane at ±φ/2 from the feed tee, so cutting there is clean."""
    half = math.radians(360 / (N_INJECTORS + 1)) / 2
    a = RUN / math.tan(half) + RING_BEND

    def keep(c):
        angle = np.arctan2(c[:, 0] - RUN, a - c[:, 1])   # 0 at the feed tee
        out = np.hypot(c[:, 0] - RUN, a - c[:, 1]) - a      # beyond the feed tee's run
        return (c[:, 2] < 0) & (np.abs(angle) < half) & (out < 3 * D_FEED)

    return {"keep": keep, "direction": (0.25, -0.5, 1.0), "up": (0, 1, 0), "by_material": True}


def main(output: str = "rocket_injector_manifold.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
