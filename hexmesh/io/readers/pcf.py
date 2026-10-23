"""
PCF (Piping Component File) reader.

Parses an Isogen PCF file and returns a NetworkSpec — a declarative
description of the pipe network that can be converted to a Network via
``NetworkSpec.to_network()``.

PCF format summary
------------------
ASCII text, one record per component.  Each record starts with a
component-type keyword (PIPE, ELBOW, REDUCER-CONCENTRIC, …) followed by
attribute lines.  Coordinates appear on END-POINT and CENTRE-POINT lines.

Supported component types
--------------------------
PIPE                     → ComponentSpec(kind="pipe")
ELBOW                    → ComponentSpec(kind="elbow")
REDUCER-CONCENTRIC       → ComponentSpec(kind="reducer")
FLANGE, VALVE, INSTRUMENT→ ComponentSpec(kind="fitting") — modelled as
                            short straight segments; set ignored=True to
                            skip them entirely.

Unsupported types (TEE, CROSS, …) are collected in ``NetworkSpec.skipped``
with a warning rather than raising an exception.

References
----------
Isogen PCF format specification:
    AVEVA Plant (formerly CADMATIC / Intergraph I-Configure) documentation.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import numpy as np


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ComponentSpec:
    """One piping component parsed from a PCF file.

    Attributes
    ----------
    kind : str
        Normalised type: "pipe", "elbow", "reducer", "fitting".
    start : ndarray, shape (3,)
        Start end-point coordinates (mm in PCF, converted to metres).
    end : ndarray, shape (3,)
        End end-point coordinates.
    centre : ndarray or None
        Centre point (present for elbows).
    bore : float
        Nominal bore (metres).
    end_bore : float or None
        Outlet bore for reducers (metres).
    ignored : bool
        True for component types that are parsed but not meshed.
    raw : dict
        All raw attribute key→value pairs from the PCF record.
    """

    kind:     str
    start:    np.ndarray
    end:      np.ndarray
    centre:   np.ndarray | None = None
    bore:     float = 0.0
    end_bore: float | None = None
    ignored:  bool = False
    raw:      dict = field(default_factory=dict)


@dataclass
class NetworkSpec:
    """Declarative description of a pipe network parsed from an external file.

    Attributes
    ----------
    components : list[ComponentSpec]
        Ordered list of components (topologically sorted by connectivity).
    skipped : list[tuple[str, dict]]
        Component records that could not be mapped to a supported type.
    source : str
        Path or description of the source file.
    """

    components: list[ComponentSpec] = field(default_factory=list)
    skipped:    list[tuple[str, dict]] = field(default_factory=list)
    source:     str = ""

    def to_network(self, pipe_spec, **kwargs):
        """Convert this NetworkSpec to a hexmesh Network.

        Parameters
        ----------
        pipe_spec : PipeSpec
            Cross-section specification applied to every pipe component.
        **kwargs
            Passed to Network.__init__ (e.g. lc=0.05).

        Returns
        -------
        Network
        """
        from ...network import Network
        from ...connectors import Straight, Bend, Reducer
        from ...core.cursor import Cursor

        sorted_comps = _sort_by_connectivity(self.components)
        if not sorted_comps:
            raise ValueError("NetworkSpec has no components to build.")

        first = sorted_comps[0]
        cursor = Cursor(
            position  = first.start,
            direction = _unit(first.end - first.start),
            up        = _perpendicular(_unit(first.end - first.start)),
        )
        net = Network(pipe_spec, cursor=cursor, **kwargs)

        for comp in sorted_comps:
            if comp.ignored:
                continue
            if comp.kind == "pipe":
                length = float(np.linalg.norm(comp.end - comp.start))
                net.add(Straight(length=length, n_layers=max(1, int(length / 0.1))))
            elif comp.kind == "elbow":
                radius, angle = _elbow_params(comp)
                net.add(Bend(radius=radius, angle=angle, n_layers=8))
            # reducers require outlet PipeSpec — skipped here, user handles manually
        return net


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def read_pcf(
    path:          str | Path,
    unit_scale:    float = 1e-3,   # PCF coordinates in mm → metres
    ignore_types:  set[str] | None = None,
) -> NetworkSpec:
    """Parse a PCF file and return a NetworkSpec.

    Parameters
    ----------
    path : str or Path
        Path to the ``.pcf`` file.
    unit_scale : float
        Multiply all coordinates by this factor.  Default 1e-3 converts
        millimetres (PCF default) to metres.
    ignore_types : set[str], optional
        Component-type keywords to silently ignore (e.g. {"SUPPORT", "WELD"}).
        Defaults to a standard set of non-geometric types.

    Returns
    -------
    NetworkSpec
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PCF file not found: {path}")

    if ignore_types is None:
        ignore_types = {
            "SUPPORT", "WELD", "GASKET", "BOLT", "INSTRUMENT-COMPONENT",
            "PIPE-DIRECTION-BREAK",
        }

    spec = NetworkSpec(source=str(path))

    for record_type, attrs in _iter_records(path):
        kind = _classify(record_type)
        if record_type in ignore_types:
            continue
        if kind is None:
            spec.skipped.append((record_type, attrs))
            warnings.warn(
                f"Unsupported PCF component type '{record_type}' — skipped.",
                stacklevel=2,
            )
            continue

        endpoints = attrs.get("END-POINT", [])
        if len(endpoints) < 2:
            warnings.warn(
                f"Component {record_type} has < 2 END-POINTs — skipped.",
                stacklevel=2,
            )
            continue

        start  = np.array(endpoints[0][:3], dtype=float) * unit_scale
        end    = np.array(endpoints[1][:3], dtype=float) * unit_scale
        bore   = float(endpoints[0][3]) * unit_scale if len(endpoints[0]) > 3 else 0.0

        centre = None
        if "CENTRE-POINT" in attrs:
            cp = attrs["CENTRE-POINT"]
            centre = np.array(cp[:3], dtype=float) * unit_scale

        end_bore = None
        if kind == "reducer" and len(endpoints) >= 2 and len(endpoints[1]) > 3:
            end_bore = float(endpoints[1][3]) * unit_scale

        ignored = kind == "fitting"

        spec.components.append(ComponentSpec(
            kind=kind, start=start, end=end,
            centre=centre, bore=bore, end_bore=end_bore,
            ignored=ignored, raw=attrs,
        ))

    return spec


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_COMPONENT_MAP = {
    "PIPE":                  "pipe",
    "ELBOW":                 "elbow",
    "BEND":                  "elbow",
    "REDUCER-CONCENTRIC":    "reducer",
    "REDUCER-ECCENTRIC":     "reducer",
    "FLANGE":                "fitting",
    "VALVE":                 "fitting",
    "TEE":                   None,    # not yet supported
    "CROSS":                 None,
    "CAP":                   "fitting",
    "OLET":                  None,
    "INSTRUMENT-COMPONENT":  "fitting",
}


def _classify(record_type: str) -> str | None:
    return _COMPONENT_MAP.get(record_type.upper())


def _iter_records(path: Path) -> Iterator[tuple[str, dict]]:
    """Yield (record_type, attrs_dict) for each PCF component record."""
    current_type: str | None = None
    current_attrs: dict = {}
    endpoints: list[list[float]] = []

    def _flush():
        if current_type is not None:
            attrs = dict(current_attrs)
            if endpoints:
                attrs["END-POINT"] = list(endpoints)
            yield current_type, attrs

    with path.open() as fh:
        for raw_line in fh:
            line = raw_line.rstrip()
            if not line or line.startswith(";"):
                continue

            # Component-type lines start at column 0 with no leading whitespace
            if not line[0].isspace() and not line[0].isdigit():
                yield from _flush()
                current_type   = line.strip().split()[0]
                current_attrs  = {}
                endpoints      = []
            elif "END-POINT" in line:
                nums = [float(x) for x in re.findall(r"[-\d.]+", line)]
                endpoints.append(nums)
            elif "CENTRE-POINT" in line:
                nums = [float(x) for x in re.findall(r"[-\d.]+", line)]
                current_attrs["CENTRE-POINT"] = nums
            else:
                # Generic attribute line
                parts = line.split(None, 1)
                if len(parts) == 2:
                    current_attrs[parts[0].strip()] = parts[1].strip()

    yield from _flush()


def _sort_by_connectivity(comps: list[ComponentSpec]) -> list[ComponentSpec]:
    """Topological sort: order components by endpoint connectivity."""
    if not comps:
        return []
    # Simple greedy chain: start from the first component, follow end-points
    tol    = 1e-4
    result = [comps[0]]
    remaining = list(comps[1:])

    while remaining:
        tail = result[-1].end
        found = False
        for i, c in enumerate(remaining):
            if np.linalg.norm(c.start - tail) < tol:
                result.append(remaining.pop(i))
                found = True
                break
            elif np.linalg.norm(c.end - tail) < tol:
                # Reversed orientation — flip
                c.start, c.end = c.end.copy(), c.start.copy()
                result.append(remaining.pop(i))
                found = True
                break
        if not found:
            # Disconnected component — append as-is
            result.append(remaining.pop(0))

    return result


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def _perpendicular(v: np.ndarray) -> np.ndarray:
    candidate = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(v, candidate)) > 0.9:
        candidate = np.array([0.0, 1.0, 0.0])
    return _unit(np.cross(v, candidate))


def _elbow_params(comp: ComponentSpec) -> tuple[float, float]:
    """Estimate bend radius and angle from an elbow ComponentSpec."""
    if comp.centre is None:
        length = float(np.linalg.norm(comp.end - comp.start))
        return length * 0.5, 90.0   # fallback

    v1 = _unit(comp.start  - comp.centre)
    v2 = _unit(comp.end    - comp.centre)
    radius = float(np.linalg.norm(comp.start - comp.centre))
    cos_a  = float(np.clip(np.dot(v1, v2), -1.0, 1.0))
    import math
    angle  = math.degrees(math.acos(cos_a))
    return radius, angle
