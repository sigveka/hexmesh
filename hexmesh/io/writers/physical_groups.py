"""
Standalone write_physical_groups utility.

Provides a functional alternative to ``Network.write_physical_groups``
for cases where the caller manages regions/interfaces manually rather
than through a Network instance.
"""

from __future__ import annotations
from collections import defaultdict
from typing import Callable

import gmsh

from ...faces._gmsh_helpers import add_physical_group
from ...core.region import RegionSet


def write_physical_groups(
    regions:               dict[str, RegionSet],
    interfaces:            dict[str, list[int]] | None = None,
    outer_wall_classifier: Callable[[int], str] | None = None,
    inlet_classifier:      Callable[[int], str] | None = None,
    outlet_classifier:     Callable[[int], str] | None = None,
    synchronize:           bool = True,
) -> None:
    """Write Physical Volume and Physical Surface groups to the GMSH model.

    Parameters
    ----------
    regions : dict[str, RegionSet]
        Per-material accumulated entity tags.  Keys are material names
        (used directly as Physical group names for volumes).
    interfaces : dict[str, list[int]], optional
        Conformal interface surfaces keyed by label.
    outer_wall_classifier : callable, optional
        ``f(surface_tag) -> str`` — assigns outer wall surfaces to named
        Physical Surface groups.  If None, all outer walls of each material
        go to ``"{material}_wall"``.

        Example — split a half-buried pipe by ground plane::

            def by_ground(tag, z0=0.0):
                z = gmsh.model.mesh.getCenterOfMass(2, tag)[2]
                return "soil_contact" if z < z0 else "air_contact"

    inlet_classifier : callable, optional
        As ``outer_wall_classifier`` but for inlet faces.
    outlet_classifier : callable, optional
        As ``outer_wall_classifier`` but for outlet faces.
    synchronize : bool
        Call ``gmsh.model.occ.synchronize()`` before writing.  Set to
        False if the model has already been synchronised.
    """
    if synchronize:
        gmsh.model.occ.synchronize()

    # --- Volumes ------------------------------------------------------------
    for name, rset in regions.items():
        if rset.volumes:
            add_physical_group(3, rset.volumes, name)

    # --- Inlets / outlets ---------------------------------------------------
    for name, rset in regions.items():
        _write_classified(2, rset.inlets,  inlet_classifier,
                          default_name=f"{name}_inlet")
        _write_classified(2, rset.outlets, outlet_classifier,
                          default_name=f"{name}_outlet")

    # --- Outer walls --------------------------------------------------------
    for name, rset in regions.items():
        _write_classified(2, rset.walls, outer_wall_classifier,
                          default_name=f"{name}_wall")

    # --- Interfaces ---------------------------------------------------------
    if interfaces:
        for label, tags in interfaces.items():
            if tags:
                add_physical_group(2, tags,label)


def _write_classified(
    dim:          int,
    tags:         list[int],
    classifier:   Callable[[int], str] | None,
    default_name: str,
) -> None:
    if not tags:
        return
    if classifier is None:
        add_physical_group(dim, tags, name=default_name)
        return
    groups: dict[str, list[int]] = defaultdict(list)
    for tag in tags:
        groups[classifier(tag)].append(tag)
    for label, group_tags in groups.items():
        add_physical_group(dim, group_tags, name=label)
