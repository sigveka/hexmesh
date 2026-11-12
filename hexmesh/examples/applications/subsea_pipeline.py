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
Subsea pipeline: an insulated flowline laid over a field of sand waves,
read from a seabed survey, rising at its end into a riser.

    python3 -m hexmesh.examples.applications.subsea_pipeline # writes subsea_pipeline.msh

The example shows the **bathymetry reader**.  `read_bathymetry` takes a
seabed surface (here an XYZ point file) and a route of waypoints in plan,
drapes the route on the seabed, and returns a network model.
`to_assembly(spec, kinks="spline")` turns it into one `SplinePipe` that
follows the terrain.  The riser is then added to the imported network
like any other fitting: an imported assembly is an ordinary one.

**The seabed is generated, not downloaded:** the example writes a small
XYZ file to a temporary folder.  For real data, public bathymetry such
as GEBCO's grids reads the same way (`surface_format="geotiff"` or
`"netcdf"`).  The surface is a gentle slope with straight-crested sand
waves crossing the route at an angle.  Sand waves are a real concern for
subsea lines: they migrate, and can leave a pipeline spanning between
their crests.  From Dronkers 2024 (`dronkers_2024`, the Coastal Wiki
review):
- crest spacing "most often between 200 and 700 m": **300 m** here;
- mean height H ≈ 0.07 λ^0.8 (Flemming 2000, as cited there): **6.7 m**
  at λ = 300 m.

**Not from a source** (modelling choices, stated as such):
- the water depth (80 m at the start, 1 m deeper per 100 m), the crests'
  angle to the route (17°) and the route (three waypoints over 700 m,
  turning once);
- **the section, typical values for a wet-insulated flowline:** a
  10-inch line (273.1 mm outer diameter, 15.9 mm steel wall), a 3 mm
  anti-corrosion coating and 50 mm of polypropylene insulation;
- the riser: a bend of 5 m radius at the route's end, then 70 m straight
  up, stopping short of the surface (``riser_top``).  A real riser here
  would often be a flexible pipe with a different wall.  That needs a
  layer that changes material along the line (decision 0021's note of
  2026-11-12), so this riser keeps the flowline's section;
- 1.5 m axial cells: a pipeline-scale mesh.  The coating's cells are
  3 mm thick, so the aspect ratio reaches about 1000 and SICN is small.
  A flow case near the riser base would refine there.

**What the reader did:** the route was split into segments of at most
10 m (``max_segment_length``) so the spline follows the sand waves.  The
build's join tolerance came out relative to the network's size
(``model.report["tol_source"] == "relative"``, task 0138).

Ends ``flowline_start`` and ``riser_top``.
"""

import os
import tempfile

import numpy as np

from hexmesh import Bend, PipeSpec, Straight
from hexmesh.interchange import read_bathymetry
from hexmesh.units import mm

# Dronkers 2024 (Coastal Wiki), with Flemming's height relation.
WAVELENGTH = 300.0
HEIGHT = 0.07 * WAVELENGTH ** 0.8
# Not from a source (see the docstring).
DEPTH, SLOPE, CREST_ANGLE = 80.0, 0.01, 17.0
ROUTE = [(0.0, 0.0), (350.0, 60.0), (700.0, 0.0)]
OD, WALL, COATING, INSULATION = 273.1 * mm, 15.9 * mm, 3 * mm, 50 * mm
RISER_BEND, RISER_HEIGHT = 5.0, 70.0
AXIAL_CELL = 1.5

#: The gallery's colours (``docs/gallery/build.py``).
GALLERY_COLOURS = {"oil": ("#3b2a1e", "dark brown"), "steel": ("#8e979f", "grey"),
                   "coating": ("#2e75b6", "blue"), "insulation": ("#e8833a", "orange")}

#: The flowline's section: oil, steel, coating, insulation.
SPEC = (PipeSpec(nang=8).core("oil", radius=OD / 2 - WALL, nrad=4)
        .shell("steel", dR=WALL, nrad=2)
        .shell("coating", dR=COATING, nrad=1)
        .shell("insulation", dR=INSULATION, nrad=2))


def seabed(x, y):
    """The seabed's elevation (negative, metres) at plan position (x, y)."""
    a = np.radians(CREST_ANGLE)
    along = x * np.cos(a) + y * np.sin(a)
    return -DEPTH - SLOPE * x + HEIGHT / 2 * np.sin(2 * np.pi * along / WAVELENGTH)


def write_seabed(path: str) -> None:
    """The survey: seabed points every 5 m around the route, as X Y Z text."""
    x, y = np.meshgrid(np.arange(-50.0, 751.0, 5.0), np.arange(-100.0, 161.0, 5.0))
    np.savetxt(path, np.column_stack([x.ravel(), y.ravel(), seabed(x, y).ravel()]),
               fmt="%.3f")


def build():
    with tempfile.TemporaryDirectory() as tmp:
        survey = os.path.join(tmp, "seabed.xyz")
        write_seabed(survey)
        model = read_bathymetry(survey, ROUTE, max_segment_length=10.0)
    asm = model.to_assembly(SPEC, kinks="spline", axial_cell=AXIAL_CELL)
    end = max(asm.open_interfaces(), key=lambda i: i.frame.position[0])
    # The riser: turn from the route's last heading to straight up.
    heading = np.asarray(end.frame.normal)
    angle = float(np.degrees(np.arccos(np.clip(heading[2], -1.0, 1.0))))
    top = asm.add(end, Bend(radius=RISER_BEND, angle=angle, toward=(0, 0, 1), n_layers=12))
    asm.add(top, Straight(RISER_HEIGHT, n_layers=35), names=["riser_top"])
    return asm


def gallery_cutaway() -> dict:
    """The gallery's cut-away: where the flowline turns up into the riser,
    cut along the vertical plane through the route's last leg and coloured
    by material, so the four layers show."""
    (x0, y0), (x1, y1) = ROUTE[-2], ROUTE[-1]
    end = np.array([x1, y1, seabed(x1, y1)])
    leg = np.array([x1 - x0, y1 - y0, 0.0]) / np.hypot(x1 - x0, y1 - y0)
    side = np.array([-leg[1], leg[0], 0.0])           # horizontal, across the leg

    def keep(c):
        d = c - end
        along = d @ leg
        return (along > -1.5) & (along < 4.5) & (d[:, 2] < 4.0) & (d @ side > 0)

    view = -side + 0.5 * leg + 0.45 * np.array([0.0, 0.0, 1.0])
    return {"keep": keep, "direction": tuple(view), "up": (0, 0, 1), "by_material": True}


def main(output: str = "subsea_pipeline.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
