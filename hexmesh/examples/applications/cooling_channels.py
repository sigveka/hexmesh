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
Cooling channels: a supply pipe split by a wye into two flat rectangular
channels, each returning to a round outlet.

    python3 -m hexmesh.examples.applications.cooling_channels # writes cooling_channels.msh

Each daughter of the 60° wye bends back parallel to the supply, then a
``Transition`` flattens it into a 3:1 channel (0.12 × 0.04), the kind of
passage that cools a plate or a mould.  After the channel a second
``Transition`` rounds it off again.  The circle's ``n_arc`` equals the
channel's ``n_width`` and ``n_height``, so every transition is a plain sweep.
Outlets: ``fluid_left_out``, ``fluid_right_out``.
"""

from hexmesh import Assembly, Bend, PipeSpec, Straight, Transition, Wye

PIPE = PipeSpec(n_arc=6).core("fluid", radius=0.03, n_radial=3)
CHANNEL = PipeSpec(n_width=6, n_height=6).core("fluid", half_w=0.06, half_h=0.02, radial_grading=1.2)


def build() -> Assembly:
    asm = Assembly(PIPE, direction=[1, 0, 0], up=[0, 0, 1])
    supply = asm.add(Straight(0.2, n_layers=6))
    left, right = asm.add(supply, Wye(angle=60, run_length=0.08, branch_length=0.15,
                                      n_run=3, n_branch=3, n_split=4))
    for port, roll, name in ((left, 90, "left_out"), (right, -90, "right_out")):
        end = asm.add(port, Bend(radius=0.1, angle=30, n_layers=4, roll=roll))
        end = asm.add(end, Straight(0.05, n_layers=2))
        end = asm.add(end, Transition(CHANNEL, length=0.08, n_layers=4))
        end = asm.add(end, Straight(0.4, n_layers=16))
        end = asm.add(end, Transition(PIPE, length=0.08, n_layers=4))
        asm.add(end, Straight(0.1, n_layers=3), names=[name])
    return asm


def main(output: str = "cooling_channels.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
