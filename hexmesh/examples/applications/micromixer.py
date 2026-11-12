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
Micromixer: a T-mixer for lipid nanoparticles, with a twisted mixing
channel, at its real size in micrometres.

    python3 -m hexmesh.examples.applications.micromixer # writes micromixer.msh

The lipid nanoparticles in mRNA vaccines form when a lipid-in-ethanol
stream meets an mRNA-in-water stream and the two mix fast.  Lab work
uses microfluidic mixers, T-junctions among them.  Production uses
T-mixers and impinging-jet mixers.  Scaling between the two by Reynolds
number is an open problem.

**The T is the engulfment benchmark's** (Bothe, Stemich and Warnecke 2006,
`bothe_and_stemich_etal_2006`, and their proceedings paper,
`bothe_and_stemich_etal_2006b`; experiments in Hoffmann, Schlüter and
Räbiger 2006, `hoffmann_and_schluter_etal_2006`):
- two inlets 100 µm wide and 100 µm deep, meeting head-on;
- a mixing channel 200 µm wide and 100 µm deep, leaving at right angles;
- their computational domain: inlets 400 µm long, mixing channel 1.5 mm.

Below a critical Reynolds number the two streams run side by side; above
it they engulf each other and mix.  Bothe et al. put the onset at a mean
velocity of about 1.1 m/s in water: Re ≈ 146 on the mixing channel's
hydraulic diameter (133 µm).

**In hexmesh's terms** the inlet line is the main, a 100 µm square duct.
The mixing channel is a **full-width duct tap** on its side: as deep as
the duct across, and 200 µm along the inlets' axis.  The tap keeps the
main's 8 cells per side, so the mixing channel's cells are 25 × 12.5 µm.

**Not from a source** (modelling choices, stated as such):
- **the twisted channel:** after the benchmark's 1.5 mm, the mixing
  channel twists one full turn over 2 mm (`Straight(twist=360)`), then
  runs straight for 1 mm to the outlet.  Twisted microchannels mix
  passively by swirl (e.g. `sivashankar_and_agambayev_etal_2016`, whose
  twist comes from stacked quarter-circle units rather than a twisted
  duct).  This one is inspired by them, not a copy;
- the counts (8 per side), a resolution for the picture rather than a
  converged mixing study (Bothe et al. used about a million cells).

**Quality:** no `validate()` warning.  The T's turn blocks hold the worst
cells (min scaled Jacobian 0.58, the full-width tap's limit).  The
largest aspect ratio, 12, is in the inlet straights.

Inlets ``lipid_inlet`` and ``aqueous_inlet``; outlet ``outlet``.
"""

from hexmesh import Assembly, PipeSpec, Straight, Tee
from hexmesh.core.shape import RectShape
from hexmesh.units import mm, um

# Bothe, Stemich and Warnecke 2006: the T-mixer.
INLET_W, MIX_W, DEPTH = 100 * um, 200 * um, 100 * um
L_INLET, L_MIX = 0.4 * mm, 1.5 * mm
# Not from a source (see the docstring).
TWIST, L_TWIST, L_OUTLET = 360.0, 2 * mm, 1 * mm

N = 8  # cells per side of every section

#: The inlet line: a square duct, the main of the T.
INLET = PipeSpec(nang_w=N, nang_h=N).core("fluid", half_w=INLET_W / 2, half_h=DEPTH / 2)
#: The mixing channel's section, as the tap leaves the main's face:
#: across the face it is the duct's depth, along the main its width.
MIXING = RectShape(DEPTH / 2, MIX_W / 2, N, N)


def build() -> Assembly:
    asm = Assembly(INLET, direction=[1, 0, 0], up=[0, 1, 0], inlet_name="lipid_inlet")
    end = asm.add(Straight(L_INLET, n_layers=8))
    end, mix = asm.add(end, Tee(branch=MIXING, face="wide", branch_length=0.3 * mm))
    asm.add(end, Straight(L_INLET, n_layers=8), names=["aqueous_inlet"])
    mix = asm.add(mix, Straight(L_MIX - 0.3 * mm, n_layers=24))
    mix = asm.add(mix, Straight(L_TWIST, twist=TWIST, n_layers=48))
    asm.add(mix, Straight(L_OUTLET, n_layers=10), names=["outlet"])
    return asm


def gallery_cutaway() -> dict:
    """The gallery's cut-away: the T and the start of the mixing channel,
    the near half of the depth removed, so the tap's blocks show."""
    def keep(c):
        return (c[:, 1] < 0.45 * mm) & (c[:, 2] > 0)

    return {"keep": keep, "direction": (0.35, -0.45, -1.0), "up": (0, 1, 0)}


def main(output: str = "micromixer.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
