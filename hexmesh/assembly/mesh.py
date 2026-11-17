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
A mesh as a value: ``Assembly.to_mesh()`` meshes without a ``Session``
(task 0167, decision 0053).

Each :class:`Mesh` owns a gmsh model of its own, in the gmsh that a
``Session`` or the caller started, or that hexmesh starts on first use
and finalizes at exit.  The assembly is copied before it is built, so it
stays unmeshed, and every call leaves the caller's current model and
gmsh's options as they were (``docs/integrations/gmsh.md``, task 0167).
"""

from __future__ import annotations

import itertools
import weakref

import numpy as np

from .. import _gmsh, _occ
from .._gmsh import gmsh
from ..errors import InternalError
from .errors import AssemblyError
from .quality import QualityReport
from . import _checks, _output, _realise

#: gmsh element type number → the name ``Mesh.cells`` and ``Mesh.groups``
#: key it by: the shape and its node count.  A new type is an addition.
ELEMENT_TYPES: dict[int, str] = {
    15: "point1",
    1: "line2", 8: "line3",
    2: "tri3", 9: "tri6",
    3: "quad4", 16: "quad8", 10: "quad9",
    4: "tet4", 11: "tet10",
    5: "hex8", 17: "hex20", 12: "hex27",
    6: "prism6", 18: "prism15", 13: "prism18",
    7: "pyramid5", 19: "pyramid13", 14: "pyramid14",
}

_names = itertools.count(1)


def to_mesh(asm, dim: int, order: int, incomplete: bool) -> "Mesh":
    """``Assembly.to_mesh``: a copy of *asm*, built and meshed in a new
    model; the caller's model current again after it."""
    _gmsh.start()
    try:
        description = asm.to_dict()
    except TypeError:                   # an assembly no description can hold
        description = None
    built = _realise.unbuilt_copy(asm)
    name = f"hexmesh-mesh-{next(_names)}"
    previous = gmsh.model.getCurrent()
    gmsh.model.add(name)
    gmsh.model.setCurrent(previous)
    try:
        with _gmsh.model(name), _occ.saved():
            built.mesh(dim, order=order, incomplete=incomplete)
    except BaseException:
        _gmsh.release(name)
        raise
    return Mesh(built, name, description=description, dim=dim, order=order,
                incomplete=incomplete)


class Mesh:
    """A meshed assembly, as a value (``Assembly.to_mesh()``).

    It owns a gmsh model until :meth:`close`; use it as a context manager,
    or let it go: the model is removed when the ``Mesh`` is collected, and
    when the ``Session`` it was made in ends.  After ``close()``,
    :attr:`description` still works and every other member raises
    ``AssemblyError`` (``mesh_closed``).

    Not thread-safe (gmsh isn't): build in parallel with a process pool,
    one build per worker, each returning what it wrote or its arrays.  A
    ``Mesh`` can't be pickled (``mesh_not_picklable``).

    The arrays are read-only:

    - ``nodes``: ``(N, 3)`` floats, in the unit the assembly was built in;
    - ``cells``: element type name (:data:`ELEMENT_TYPES`) →
      ``(M, k)`` ints, the 0-based rows of each element's nodes in
      ``nodes``, in gmsh's node order for the type, for every dimension
      the mesh has (``"hex8"``, ``"quad4"``, ``"line2"``, ``"point1"``);
    - ``groups``: physical group name → {type name → row indices into
      ``cells[type]``}, for volumes and boundaries alike, as
      :meth:`write` writes them with ``walls_by_fitting=False``.
    """

    def __init__(self, assembly, model: str, *, description: dict | None,
                 dim: int, order: int, incomplete: bool) -> None:
        self._assembly = assembly
        self._model = model
        self._description = description
        self._options = {"dim": dim, "order": order, "incomplete": incomplete}
        self._session = _gmsh.sessions[-1] if _gmsh.sessions else None
        self._arrays: tuple | None = None
        self._closed = False
        self._finalizer = weakref.finalize(self, _gmsh.release, model)
        _gmsh.open_meshes.add(self)

    # --- lifetime --------------------------------------------------------

    def close(self) -> None:
        """Remove the gmsh model.  Closing again does nothing."""
        if not self._closed:
            self._closed = True
            _gmsh.open_meshes.discard(self)
            self._assembly = self._arrays = None
            self._finalizer()

    def _forget(self) -> None:
        """Closed because gmsh was finalized: no gmsh call."""
        self._finalizer.detach()
        self._closed = True
        self._assembly = self._arrays = None
        _gmsh.open_meshes.discard(self)

    @property
    def closed(self) -> bool:
        return self._closed

    def __enter__(self) -> "Mesh":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False

    def __reduce_ex__(self, protocol):
        raise AssemblyError(
            "a Mesh can't be pickled: it holds a gmsh model of this process",
            code="mesh_not_picklable",
            hint="return what the worker wrote (mesh.write(path)), or the arrays "
                 "(mesh.nodes, mesh.cells, mesh.groups), or the assembly's description")

    def __repr__(self) -> str:
        if self._closed:
            return "Mesh(closed)"
        o = self._options
        return f"Mesh(dim={o['dim']}, order={o['order']}, cells={self.cell_count})"

    def _check_open(self) -> None:
        if not self._closed and self._model not in _gmsh.models():
            self._forget()              # gmsh finalized under it (by the caller)
        if self._closed:
            raise AssemblyError("the mesh is closed: its gmsh model was removed",
                                code="mesh_closed",
                                hint="call assembly.to_mesh() again; a Mesh closes with "
                                     "close(), at the end of its `with` block, or when "
                                     "the Session it was made in ends")

    def _open(self):
        """Its model current inside the block."""
        self._check_open()
        return _gmsh.model(self._model)

    # --- what it is --------------------------------------------------------

    @property
    def description(self) -> dict | None:
        """The assembly's ``to_dict()`` it was meshed from, or ``None`` for
        an assembly no description can hold."""
        return self._description

    @property
    def dim(self) -> int:
        self._check_open()
        return self._options["dim"]

    @property
    def order(self) -> int:
        self._check_open()
        return self._options["order"]

    @property
    def nodes(self) -> np.ndarray:
        return self._read()[0]

    @property
    def cells(self) -> dict[str, np.ndarray]:
        return dict(self._read()[1])

    @property
    def groups(self) -> dict[str, dict[str, np.ndarray]]:
        return {k: dict(v) for k, v in self._read()[2].items()}

    @property
    def cell_count(self) -> int:
        """The number of volume elements."""
        return sum(len(c) for t, c in self._read()[1].items()
                   if t.startswith(("hex", "tet", "prism", "pyramid")))

    def check_quality(self, quality_name: str = "minSICN", *, threshold: float | None = None,
                      by: str = "material") -> QualityReport:
        """As ``Assembly.check_quality``, on this mesh."""
        with self._open():
            return _checks.check_quality(self._assembly, quality_name, threshold, by)

    # --- writing -----------------------------------------------------------

    def write(self, path: str, *, walls_by_fitting: bool = False, provenance: bool = True,
              scale: float = 1.0) -> None:
        """Write *path* in the format its extension names: the bytes
        ``Assembly.write`` writes in a ``Session`` with the same options."""
        o = self._options
        with self._open():
            _output.write(self._assembly, path, o["dim"], order=o["order"],
                          incomplete=o["incomplete"], walls_by_fitting=walls_by_fitting,
                          provenance=provenance, scale=scale)

    def write_openfoam(self, path: str, *, interfaces: bool = False,
                       walls_by_fitting: bool = False, provenance: bool = True,
                       scale: float = 1.0) -> None:
        """Write a ``.msh`` for ``gmshToFoam`` and its roles manifest, as
        ``Assembly.write_openfoam`` does.  A first-order volume mesh only."""
        with self._open():
            _output.write_openfoam(self._assembly, path, interfaces=interfaces,
                                   walls_by_fitting=walls_by_fitting, provenance=provenance,
                                   order=self._options["order"], scale=scale)

    # --- the arrays ----------------------------------------------------------

    def _read(self) -> tuple:
        with self._open():
            if self._arrays is None:
                o = self._options
                # the groups as written by default, whatever was written last
                self._assembly.mesh(o["dim"], order=o["order"], incomplete=o["incomplete"])
                self._arrays = _arrays()
        return self._arrays


def _type_name(t: int) -> str:
    try:
        return ELEMENT_TYPES[t]
    except KeyError:
        raise InternalError(f"gmsh element type {t} has no name in ELEMENT_TYPES",
                            value=t) from None


def _frozen(a: np.ndarray) -> np.ndarray:
    a.setflags(write=False)
    return a


def _arrays() -> tuple:
    """(nodes, cells, groups) of the current model."""
    msh = gmsh.model.mesh
    tags, x, _ = msh.getNodes()
    order = np.argsort(tags)
    sorted_tags = tags[order]

    def rows(node_tags):
        return order[np.searchsorted(sorted_tags, node_tags)]

    cells, element_rows = {}, {}
    for dim in range(4):
        for t in msh.getElementTypes(dim):
            name = _type_name(int(t))
            etags, ntags = msh.getElementsByType(int(t))
            k = msh.getElementProperties(int(t))[3]
            cells[name] = _frozen(rows(ntags).reshape(-1, k).astype(np.int64))
            by = np.argsort(etags)
            element_rows[name] = (etags[by], by)
    groups: dict[str, dict[str, np.ndarray]] = {}
    for dim, tag in gmsh.model.getPhysicalGroups():
        found: dict[str, list] = {}
        for ent in gmsh.model.getEntitiesForPhysicalGroup(dim, tag):
            for t, etags, _ in zip(*msh.getElements(dim, int(ent))):
                found.setdefault(_type_name(int(t)), []).append(etags)
        group = groups.setdefault(gmsh.model.getPhysicalName(dim, tag), {})
        for name, parts in found.items():
            sorted_etags, by = element_rows[name]
            group[name] = _frozen(by[np.searchsorted(sorted_etags, np.concatenate(parts))]
                                  .astype(np.int64))
    nodes = _frozen(x.reshape(-1, 3).copy())
    return nodes, cells, groups
