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
Bathymetry reader — pipeline route on a surveyed seabed surface.

Takes a bathymetric surface (XYZ point cloud or DEM raster) and a 2-D
pipeline route (list of waypoints or a Shapefile), projects the route
onto the surface, and returns a network model (decision 0032) holding one
``Polyline`` part: the 3-D centreline of the pipe through the projected
waypoints.  Build it with ``model.to_assembly(pipe_spec, kinks="spline")``:
the route bends at its vertices without fittings, so its segments are
joined into a spline.

Supported input formats
-----------------------
Surface:
    ``"xyz"``     — whitespace/comma-separated X Y Z text file
    ``"geotiff"`` — GeoTIFF DEM (requires ``rasterio``)
    ``"netcdf"``  — NetCDF grid (requires ``netCDF4`` or ``xarray``)

Route:
    list of (x, y) tuples / ndarray of shape (N, 2)
    ``"csv"``     — two-column CSV (x, y)
    ``"shp"``     — Shapefile LineString (requires ``shapely`` + ``fiona``)
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

from ...errors import ReaderError
from ..model import NetworkModel, Polyline, Provenance
from ..operations import import_entry


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def read_bathymetry(
    surface_path:   str | Path,
    route:          str | Path | np.ndarray | Sequence,
    burial_depth:   float = 0.0,
    surface_format: str = "xyz",
    route_format:   str | None = None,
    unit_scale:     float = 1.0,
    max_segment_length: float | None = None,
) -> NetworkModel:
    """A network model of a pipeline route projected onto bathymetry.

    The pipe centreline is placed at depth ``burial_depth`` below the
    interpolated seabed surface (positive = deeper).  For an exposed
    pipeline set ``burial_depth=0``.

    Parameters
    ----------
    surface_path : str or Path
        Path to the bathymetric surface file.
    route : array-like or path
        2-D pipeline waypoints in the same coordinate system as the surface.
        Shape (N, 2) with columns [x, y].
    burial_depth : float
        Depth below seabed surface (metres, positive downward).
    surface_format : str
        Surface file format: ``"xyz"``, ``"geotiff"``, or ``"netcdf"``.
    route_format : str or None
        Route file format: ``"csv"`` or ``"shp"``.  Inferred from extension
        if None.
    unit_scale : float
        Multiply all coordinates by this factor.
    max_segment_length : float or None
        If set, split long segments so no segment exceeds this length.
        Useful for routes with sparse waypoints.

    Returns
    -------
    NetworkModel
        One ``Polyline`` (named ``PIPE``; its segments label as ``PIPE_1``,
        ``PIPE_2``, …) through the projected waypoints; no sizes (the
        spec sets them).
    """
    surface_path = Path(surface_path)

    # --- Load and interpolate surface ---
    x_grid, y_grid, z_grid = _load_surface(surface_path, surface_format)
    interp = _make_interpolator(x_grid, y_grid, z_grid)

    # --- Load route ---
    xy = _load_route(route, route_format)
    if unit_scale != 1.0:
        xy = xy * unit_scale

    # --- Project route onto surface ---
    z_surface = interp(xy[:, 0], xy[:, 1])
    xyz = np.column_stack([xy, z_surface - burial_depth])

    # --- Optionally subdivide long segments ---
    if max_segment_length is not None:
        xyz = _subdivide_route(xyz, max_segment_length, interp, burial_depth)

    # --- The model: one polyline through the waypoints ---
    model = NetworkModel()
    model.add_part(Polyline, [p.copy() for p in xyz], id="route", name="PIPE",
                   type="PIPE", provenance=Provenance(source=str(surface_path),
                                                      format="bathymetry", record="route"))
    import_entry(model, "bathymetry",
                 [str(surface_path)] + ([str(route)] if isinstance(route, (str, Path)) else []),
                 {"burial_depth": burial_depth, "surface_format": surface_format,
                  "route_format": route_format, "unit_scale": unit_scale,
                  "max_segment_length": max_segment_length})
    return model


# ---------------------------------------------------------------------------
# Surface loaders
# ---------------------------------------------------------------------------

def _load_surface(path: Path, fmt: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (x, y, z) arrays for the bathymetric surface."""
    if fmt == "xyz":
        return _load_xyz(path)
    elif fmt == "geotiff":
        return _load_geotiff(path)
    elif fmt == "netcdf":
        return _load_netcdf(path)
    else:
        raise ReaderError(f"Unknown surface format '{fmt}'. "
                          "Use 'xyz', 'geotiff', or 'netcdf'.",
                          code="option_invalid", where={"field": "format"}, value=fmt,
                          limit=["xyz", "geotiff", "netcdf"])


def _load_xyz(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load a whitespace/comma-separated XYZ point cloud."""
    data = np.loadtxt(path, delimiter=None, comments=["#", "//"])
    if data.ndim != 2 or data.shape[1] < 3:
        raise ReaderError(f"XYZ file must have >= 3 columns, got shape {data.shape}.",
                          code="reader_format_invalid", where={"source": {"file": str(path)}})
    return data[:, 0], data[:, 1], data[:, 2]


def _load_geotiff(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load a GeoTIFF DEM (requires rasterio)."""
    try:
        import rasterio
        from rasterio.transform import xy as rio_xy
    except ImportError:
        raise ImportError(
            "rasterio is required for GeoTIFF bathymetry input. "
            "Install with: pip install rasterio"
        )
    with rasterio.open(path) as src:
        z = src.read(1).astype(float)
        rows, cols = np.meshgrid(np.arange(z.shape[0]), np.arange(z.shape[1]),
                                 indexing="ij")
        xs, ys = rio_xy(src.transform, rows.ravel(), cols.ravel())
        return np.array(xs), np.array(ys), z.ravel()


def _load_netcdf(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load a NetCDF bathymetry grid (requires xarray)."""
    try:
        import xarray as xr
    except ImportError:
        raise ImportError(
            "xarray is required for NetCDF bathymetry input. "
            "Install with: pip install xarray"
        )
    ds = xr.open_dataset(path)
    # Try common variable name conventions
    for zvar in ("z", "depth", "elevation", "topo", "bed_elevation"):
        if zvar in ds:
            z  = ds[zvar].values
            # Try common coordinate names
            for xvar in ("x", "lon", "longitude", "easting"):
                for yvar in ("y", "lat", "latitude", "northing"):
                    if xvar in ds.coords and yvar in ds.coords:
                        xg, yg = np.meshgrid(ds[xvar].values, ds[yvar].values)
                        return xg.ravel(), yg.ravel(), z.ravel()
    raise ReaderError(
        "Could not identify x/y/z variables in NetCDF file.  "
        "Please rename coordinates to 'x','y','z' or 'lon','lat','depth'.",
        code="reader_format_invalid", where={"source": {"file": str(path)}}
    )


# ---------------------------------------------------------------------------
# Interpolator
# ---------------------------------------------------------------------------

def _make_interpolator(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
):
    """Build a 2-D scatter interpolator for the bathymetric surface."""
    try:
        from scipy.interpolate import LinearNDInterpolator
        return LinearNDInterpolator(np.column_stack([x, y]), z)
    except ImportError:
        raise ImportError(
            "scipy is required for bathymetry interpolation. "
            "Install with: pip install scipy"
        )


# ---------------------------------------------------------------------------
# Route loaders
# ---------------------------------------------------------------------------

def _load_route(
    route:  str | Path | np.ndarray | Sequence,
    fmt:    str | None,
) -> np.ndarray:
    """Return route as ndarray of shape (N, 2)."""
    if isinstance(route, np.ndarray):
        return route.reshape(-1, 2)
    if isinstance(route, (list, tuple)):
        return np.array(route, dtype=float).reshape(-1, 2)

    path = Path(route)
    if fmt is None:
        fmt = path.suffix.lower().lstrip(".")

    if fmt == "csv":
        return np.loadtxt(path, delimiter=",", comments="#")[:, :2]
    elif fmt in ("shp", "shapefile"):
        return _load_shapefile(path)
    else:
        raise ReaderError(f"Unknown route format '{fmt}'. Use 'csv' or 'shp'.",
                          code="option_invalid", where={"field": "format"}, value=fmt,
                          limit=["csv", "shp"])


def _load_shapefile(path: Path) -> np.ndarray:
    """Extract the first LineString geometry from a Shapefile."""
    try:
        import fiona
        from shapely.geometry import shape
    except ImportError:
        raise ImportError(
            "fiona and shapely are required for Shapefile route input. "
            "Install with: pip install fiona shapely"
        )
    with fiona.open(path) as src:
        for feature in src:
            geom = shape(feature["geometry"])
            coords = np.array(geom.coords)[:, :2]
            return coords
    raise ReaderError(f"No features found in Shapefile: {path}",
                      code="reader_format_invalid", where={"source": {"file": str(path)}})


# ---------------------------------------------------------------------------
# Route subdivision
# ---------------------------------------------------------------------------

def _subdivide_route(
    xyz:          np.ndarray,
    max_length:   float,
    interp,
    burial_depth: float,
) -> np.ndarray:
    """Insert intermediate points so no segment exceeds max_length."""
    result = [xyz[0]]
    for i in range(len(xyz) - 1):
        p0, p1   = xyz[i], xyz[i + 1]
        seg_len  = float(np.linalg.norm(p1 - p0))
        n_splits = max(1, int(np.ceil(seg_len / max_length)))
        for k in range(1, n_splits + 1):
            t   = k / n_splits
            pt  = p0 + t * (p1 - p0)
            z_s = interp(pt[0:1], pt[1:2])
            result.append(np.array([pt[0], pt[1], float(z_s) - burial_depth]))
    return np.array(result)
