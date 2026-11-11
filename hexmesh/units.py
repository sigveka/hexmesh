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
"""Length units (decision 0047): metres per unit, as plain floats.

hexmesh takes every length in metres.  Multiply a number in another unit
by its constant here to get metres::

    from hexmesh.units import mm
    pipe = PipeSpec(nang=8).core("blood", radius=13.25 * mm, nrad=6)

They are plain numbers, not quantity types: nothing checks or converts a
length, and an output is in metres.  Not re-exported from ``hexmesh``.
"""

#: one metre
m = 1.0
#: one centimetre
cm = 0.01
#: one millimetre
mm = 1e-3
#: one micrometre
um = 1e-6
#: one inch (exact, by the 1959 international yard)
inch = 0.0254
#: one foot
ft = 12 * inch

__all__ = ["m", "cm", "mm", "um", "inch", "ft"]
