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
A plant line from a PCF isometric: the network comes from the file, not
from Python.

    python3 -m hexmesh.examples.applications.pcf_line   # writes pcf_line.msh

``SAMPLE`` (``pcf_line.pcf``, shipped with the package, written for
hexmesh) is one insulated 100 mm line, A-100.  It leaves vessel V-101's
nozzle N1, passes a reducing tee to a 50 mm branch, then an elbow and a
concentric reducer to 80 mm.  Last come a bare flanged valve and a pipe.
``read_pcf`` turns each component into a fitting, and ``pipe`` gives
each nominal bore its section.  With ``insulation=True`` the file's 50 mm
insulation is a third layer.  The valve is bare, so the insulation
stops one cell inside it from each side (``insulation_end``).
Patches: ``*_V_101_N1`` at the nozzle; the tee's branch and the line's
end are open ends named by the file.
"""

from pathlib import Path

from hexmesh import Assembly, PipeSpec
from hexmesh.interchange import read_pcf

SAMPLE = Path(__file__).with_name("pcf_line.pcf")


def pipe(bore: float) -> PipeSpec:
    """The section for a nominal *bore* in metres (the file's sizes)."""
    return (PipeSpec(nang=8)
            .core("fluid", radius=bore / 2, nrad=4)
            .shell("steel", dR=0.004, nrad=2))


def build() -> Assembly:
    return read_pcf(SAMPLE).to_assembly(pipe, insulation=True)


def main(output: str = "pcf_line.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
