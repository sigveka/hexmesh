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
An assembly's output: physical groups, patch names, .msh and OpenFOAM
files (task 0136).
"""

from __future__ import annotations

from .._gmsh import gmsh
from .errors import AssemblyError
from ..sections import add_physical_group
from ..io.writers import msh_comments
from ..io.writers.openfoam_boundary import roles_path, write_roles
from ..version import __version__
from .interface import Interface
from ._checks import _require_session


def write_physical_groups(asm, walls_by_fitting: bool = False) -> None:
    asm.build()
    fill = asm._fill
    asm._group_roles = {}

    def group(dim, tags, name, role):
        add_physical_group(dim, tags, name)
        asm._group_roles[name] = role

    for name, vols in fill.volumes.items():
        group(3, vols, name, "volume")
    for iface in asm.open_interfaces():
        patch = asm.patch_name(iface)
        for name, cs in iface.face.layers:
            group(2, list(cs.surfaces), f"{name}_{patch}", "open_end")
    if walls_by_fitting:
        names = [e.name for e in asm._edges]
        if len(set(names)) != len(names):
            raise AssemblyError(f"fitting names are not unique: {names}",
                                code="fitting_names_not_unique", value=names)
        for e in asm._edges:
            for base, tags in asm._fitting_walls[e.index].items():
                group(2, tags, f"{base}_{e.name}", "wall")
    else:
        merged: dict[str, list[int]] = {}
        for e in asm._edges:
            for base, tags in asm._fitting_walls[e.index].items():
                merged.setdefault(base, []).extend(tags)
        for base, tags in merged.items():
            group(2, tags, base, "wall")
    for label, tags in fill.interfaces.items():
        group(2, tags, label, "interface")


def patch_name(asm, iface: Interface) -> str:
    if iface.name:
        return iface.name
    ends = [i for i in asm.open_interfaces() if i is not asm.inlet]
    if len(ends) == 1 and iface is ends[0]:
        return "outlet"
    return f"port{iface.index}"


def write(asm, path: str, dim: int = 3, *, order: int = 1, incomplete: bool = False,
          walls_by_fitting: bool = False, provenance: bool = True) -> None:
    asm.mesh(dim, order=order, incomplete=incomplete, walls_by_fitting=walls_by_fitting)
    gmsh.write(path)
    if str(path).endswith(".msh"):
        msh_comments.to_lf(path)
        if provenance:
            hi = "" if order == 1 else f" order={order} incomplete={incomplete}"
            _stamp(asm, path, f"write dim={dim}{hi} walls_by_fitting={walls_by_fitting}")


def _stamp(asm, path, write: str) -> None:
    """Insert the ``$Comments`` block (decision 0038): logo, versions,
    *write* options and :meth:`to_dict`, or why there is none."""
    try:
        recipe, error = asm.to_dict(), None
    except TypeError as e:
        recipe, error = None, str(e)
    msh_comments.insert(path, msh_comments.block(
        f"hexmesh {__version__}", write, recipe, tool=f"gmsh {gmsh.__version__}",
        msh=msh_comments.msh_format(path), error=error))


def write_openfoam(asm, path: str, *, interfaces: bool = False,
                   walls_by_fitting: bool = False, provenance: bool = True,
                   order: int = 1) -> None:
    if order != 1:
        raise AssemblyError(f"write_openfoam writes first-order meshes only, got "
                            f"order={order!r}: gmshToFoam reads no second-order elements",
                            code="openfoam_needs_order_1", where={"field": "order"},
                            value=order, limit=1, hint="use write(..., order=2) for "
                            "other solvers")
    if not str(path).endswith(".msh"):
        raise AssemblyError(f"write_openfoam writes a .msh file, got {path!r}",
                            code="write_openfoam_needs_msh", where={"field": "path"},
                            value=str(path))
    _require_session()
    asm.mesh(walls_by_fitting=walls_by_fitting)
    dropped = []
    if not interfaces:
        labels = set(asm._fill.interfaces)
        for d, t in gmsh.model.getPhysicalGroups(2):
            name = gmsh.model.getPhysicalName(d, t)
            if name in labels:
                dropped.append((d, t, name,
                                list(gmsh.model.getEntitiesForPhysicalGroup(d, t))))
        if dropped:   # an empty list would remove every group
            gmsh.model.removePhysicalGroups([(d, t) for d, t, _, _ in dropped])
    write_roles(roles_path(path), asm.group_roles(),
                not_written=[name for _, _, name, _ in dropped])
    options = {k: gmsh.option.getNumber(k) for k in ("Mesh.MshFileVersion", "Mesh.Binary")}
    try:
        gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
        gmsh.option.setNumber("Mesh.Binary", 0)
        gmsh.write(str(path))
        msh_comments.to_lf(path)
        if provenance:
            _stamp(asm, path, f"write_openfoam dim=3 interfaces={interfaces} "
                              f"walls_by_fitting={walls_by_fitting}")
    finally:
        for k, v in options.items():
            gmsh.option.setNumber(k, v)
        for d, t, name, ents in dropped:
            gmsh.model.addPhysicalGroup(d, ents, t)
            gmsh.model.setPhysicalName(d, t, name)
