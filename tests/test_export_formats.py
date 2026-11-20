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
The export checks' format tests (decision 0057 rule 2, task 0182): an
assembly written to a format, then the file parsed, with no solver.  The
group names, each group's cell types and counts, and the volume cell
count must be what hexmesh meshed.  These run in CI; the consumers run
locally (``validation/exports/<consumer>/``).

A new format adds a reader, ``read(path) -> {group name: {cell type:
count}}`` with hexmesh's cell type names (``Mesh.cells``), and a test
calling :func:`check_written` (tasks 0181 ``.unv``, 0183 ``.su2``).  A
format without cell zones puts its volume cells under ``""``.
"""

import importlib.util
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: gmsh element type → hexmesh's cell type name (``Mesh.cells``)
GMSH_TYPES = {15: "point1", 1: "line2", 8: "line3", 3: "quad4", 16: "quad8", 10: "quad9",
              5: "hex8", 17: "hex20", 12: "hex27"}
VOLUME = ("hex8", "hex20", "hex27")


def check_written(asm, path: Path, read, *, order: int = 1, zones: bool = True) -> dict:
    """Mesh *asm* at *order*, write *path*, parse it with *read*, and assert
    the groups (names, cell types, counts) and the volume cell count are
    what hexmesh meshed.  Without *zones* (a format with no cell zones)
    the volume groups are one, named ``""``.  Returns what *read* found."""
    with asm.to_mesh(order=order) as m:
        want = {name: {t: len(a) for t, a in g.items()} for name, g in m.groups.items()}
        m.write(str(path))
    if not zones:
        merged = Counter()
        for name in [n for n, g in want.items() if set(g) & set(VOLUME)]:
            merged.update(want.pop(name))
        want[""] = dict(merged)
    got = read(path)
    assert set(got) == set(want), f"groups: {sorted(got)} written, {sorted(want)} meshed"
    for name in want:
        assert got[name] == want[name], f"group {name!r}: {got[name]} written, {want[name]} meshed"
    volume = Counter()
    for g in got.values():
        volume.update({t: n for t, n in g.items() if t in VOLUME})
    assert sum(volume.values()) == asm.cell_count()
    assert set(volume) == {"hex8" if order == 1 else "hex27"}
    return got


# --- .msh 4.1 (FEniCSx reads it: validation/exports/fenicsx/) -------------------------

def read_msh41(path: Path) -> dict[str, dict[str, int]]:
    """An ASCII ``.msh`` 4.1 file's physical groups: name → {cell type:
    count}, from ``$PhysicalNames``, ``$Entities`` and ``$Elements``."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()

    def section(name: str) -> list[str]:
        a = lines.index(f"${name}")
        return lines[a + 1:lines.index(f"$End{name}", a)]

    version = section("MeshFormat")[0].split()
    assert version[0] == "4.1" and version[1] == "0", f"not ASCII .msh 4.1: {version}"
    names = {}
    for line in section("PhysicalNames")[1:]:
        dim, tag, name = line.split(maxsplit=2)
        names[(int(dim), int(tag))] = name.strip('"')
    ent = section("Entities")
    counts = [int(n) for n in ent[0].split()]
    physical, i = {}, 1
    for dim, n in enumerate(counts):
        for line in ent[i:i + n]:
            f = line.split()
            at = 4 if dim == 0 else 7                    # a point has x y z, the rest a box
            physical[(dim, int(f[0]))] = [int(t) for t in f[at + 1:at + 1 + int(f[at])]]
        i += n
    el = section("Elements")
    blocks, out, i = int(el[0].split()[0]), {}, 1
    for _ in range(blocks):
        dim, tag, kind, n = (int(v) for v in el[i].split())
        for p in physical.get((dim, tag), []):
            g = out.setdefault(names[(dim, p)], {})
            g[GMSH_TYPES[kind]] = g.get(GMSH_TYPES[kind], 0) + n
        i += 1 + n
    return out


def _fenicsx_cases():
    spec = importlib.util.spec_from_file_location("fenicsx_run",
                                                  ROOT / "validation/exports/fenicsx/run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CASES


@pytest.mark.filterwarnings("ignore::hexmesh.HexmeshWarning")
@pytest.mark.parametrize("order", [1, 2])
@pytest.mark.parametrize("case", ["straight", "bend", "tee"])
def test_msh41_keeps_groups_cell_types_and_counts(tmp_path, case, order):
    """What FEniCSx reads (Hex8 and Hex27), parsed here without it."""
    asm = _fenicsx_cases()[case]()
    got = check_written(asm, tmp_path / f"{case}.msh", read_msh41, order=order)
    assert any(name.endswith("_wall") for name in got)          # the Neumann variant's wall


def test_the_msh41_reader_sees_a_lost_group(tmp_path):
    """The check fails when the file and the mesh disagree."""
    asm = _fenicsx_cases()["straight"]()

    def drop_wall(path):
        return {k: v for k, v in read_msh41(path).items() if not k.endswith("_wall")}

    with pytest.raises(AssertionError, match="groups"):
        check_written(asm, tmp_path / "s.msh", drop_wall)


# --- .su2 (SU2 reads it: validation/exports/su2/, task 0183) --------------------------

#: VTK cell type → hexmesh's cell type name
VTK_TYPES = {3: "line2", 5: "tri3", 9: "quad4", 12: "hex8", 23: "quad8", 25: "hex20",
             28: "quad9", 29: "hex27"}


def read_su2(path: Path) -> dict[str, dict[str, int]]:
    """A ``.su2`` file's markers: name → {cell type: count}, and its
    volume cells under ``""`` (SU2 has no cell zones: gmsh writes the
    volume groups' cells together, without their names)."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    out, i = {}, 0
    while i < len(lines):
        key, _, value = lines[i].partition("=")
        if key == "NELEM":
            n = int(value)
            kinds = Counter(VTK_TYPES[int(ln.split()[0])] for ln in lines[i + 1:i + 1 + n])
            out[""] = dict(kinds)
            i += n
        elif key == "MARKER_TAG":
            name = value.strip()
            n = int(lines[i + 1].partition("=")[2])
            out[name] = dict(Counter(VTK_TYPES[int(ln.split()[0])]
                                     for ln in lines[i + 2:i + 2 + n]))
            i += 1 + n
        i += 1
    return out


@pytest.mark.filterwarnings("ignore::hexmesh.HexmeshWarning")
@pytest.mark.parametrize("case", ["straight", "tee"])
def test_su2_keeps_markers_cell_types_and_counts(tmp_path, case):
    """Every boundary group a marker by name, the hexes VTK type 12, their
    count cell_count(); the volume group's name isn't in the file."""
    asm = _fenicsx_cases()[case]()
    got = check_written(asm, tmp_path / f"{case}.su2", read_su2, zones=False)
    text = (tmp_path / f"{case}.su2").read_text(encoding="utf-8")
    assert text.startswith("NDIME= 3\n") and "body" not in got


# --- .cgns (task 0181: the pip gmsh 4.15.2 writes it; 4.12.1 builds may not) ---------

def read_cgns(path: Path) -> dict[str, dict[str, int]]:
    """A ``.cgns`` file's groups, read back by gmsh: name → {cell type:
    count}.  gmsh writes a family per entity, named for its group, and
    reads the families back as groups."""
    import gmsh
    from hexmesh import Session
    out = {}
    with Session("cgns-read"):
        gmsh.merge(str(path))
        for dim, tag in gmsh.model.getPhysicalGroups():
            g = out.setdefault(gmsh.model.getPhysicalName(dim, tag), Counter())
            for e in gmsh.model.getEntitiesForPhysicalGroup(dim, tag):
                for kind, tags in zip(*gmsh.model.mesh.getElements(dim, e)[:2]):
                    g[GMSH_TYPES[int(kind)]] += len(tags)
    return {name: dict(c) for name, c in out.items()}


@pytest.mark.filterwarnings("ignore::hexmesh.HexmeshWarning")
def test_cgns_keeps_groups_cell_types_and_counts(tmp_path):
    """Where gmsh has CGNS: the tee's groups, by name, after a read-back."""
    asm = _fenicsx_cases()["tee"]()
    try:
        check_written(asm, tmp_path / "tee.cgns", read_cgns)
    except Exception as e:                       # noqa: BLE001: the build's message
        if "CGNS" in str(e) and not isinstance(e, AssertionError):
            pytest.skip(f"this gmsh writes no CGNS: {e}")
        raise
