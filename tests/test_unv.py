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
The ``.unv`` format test (task 0181): gmsh's I-DEAS universal file,
parsed here without a consumer.  Datasets 2411 (nodes), 2412 (elements:
115 the 8-node hexahedron, 94 the 4-node quadrilateral) and 2477 (the
groups, by name; the task said 2467, gmsh 4.12.1 writes 2477).
code_saturne reads it locally: ``validation/exports/code_saturne/``.
"""

import importlib
from collections import Counter
from pathlib import Path

import pytest

from test_export_formats import check_written

#: I-DEAS element type → hexmesh's cell type name
UNV_TYPES = {11: "line2", 94: "quad4", 115: "hex8"}
#: beam types: an extra record (orientation) before the nodes
BEAMS = {11, 21, 22, 24}
#: a group's entity type for an element
ELEMENT = 8


def datasets(path: Path) -> dict[int, list[str]]:
    """The file's datasets: number → lines, between the ``-1`` markers."""
    out, lines, i = {}, Path(path).read_text(encoding="utf-8").splitlines(), 0
    while i < len(lines):
        if lines[i].strip() == "-1" and i + 1 < len(lines):
            end = next(j for j in range(i + 2, len(lines)) if lines[j].strip() == "-1")
            out[int(lines[i + 1])] = lines[i + 2:end]
            i = end
        i += 1
    return out


def elements(lines: list[str]) -> dict[int, int]:
    """Dataset 2412: element label → I-DEAS type."""
    out, i = {}, 0
    while i < len(lines):
        label, kind, *_, n = (int(v) for v in lines[i].split())
        i += 1 + (kind in BEAMS) + -(-n // 8)
        out[label] = kind
    return out


def groups(lines: list[str]) -> dict[str, list[tuple[int, int]]]:
    """Dataset 2477: group name → (entity type, tag) pairs, two a line."""
    out, i = {}, 0
    while i < len(lines):
        n = int(lines[i].split()[-1])
        name = lines[i + 1].strip()
        f = [int(v) for ln in lines[i + 2:i + 2 + -(-n // 2)] for v in ln.split()]
        out[name] = [(f[j], f[j + 1]) for j in range(0, 4 * n, 4)]
        i += 2 + -(-n // 2)
    return out


def read_unv(path: Path) -> dict[str, dict[str, int]]:
    """A ``.unv`` file's groups: name → {cell type: count}."""
    ds = datasets(path)
    assert {2411, 2412, 2477} <= set(ds), f"datasets {sorted(ds)}"
    kinds = elements(ds[2412])
    out = {}
    for name, members in groups(ds[2477]).items():
        assert {t for t, _ in members} == {ELEMENT}, f"{name}: not elements"
        out[name] = dict(Counter(UNV_TYPES[kinds[tag]] for _, tag in members))
    return out


def _example(name: str):
    return importlib.import_module(f"hexmesh.examples.{name}").build()


@pytest.mark.filterwarnings("ignore::hexmesh.HexmeshWarning")
@pytest.mark.parametrize("name", ["fittings.equal_tee", "sections.insulated_pipe"])
def test_unv_keeps_groups_cell_types_and_counts(tmp_path, name):
    """Every group by name, the hexes type 115, their count cell_count();
    a layered pipe keeps a group per cell zone."""
    asm = _example(name)
    got = check_written(asm, tmp_path / "m.unv", read_unv)
    zones = [g for g, c in got.items() if "hex8" in c]
    assert len(zones) >= (2 if name.startswith("sections.") else 1), zones


@pytest.mark.filterwarnings("ignore::hexmesh.HexmeshWarning")
def test_unv_reads_back_in_gmsh(tmp_path):
    """gmsh.merge of the file gives the nodes and elements written."""
    import gmsh
    from hexmesh import Session
    asm = _example("fittings.equal_tee")
    path = tmp_path / "t.unv"
    with asm.to_mesh() as m:
        m.write(str(path))
    ds = datasets(path)
    nodes, kinds = len(ds[2411]) // 2, elements(ds[2412])
    with Session("unv-read"):
        gmsh.merge(str(path))
        tags, _, _ = gmsh.model.mesh.getNodes()
        _, etags, _ = gmsh.model.mesh.getElements()
        assert len(tags) == nodes
        assert sum(len(t) for t in etags) == len(kinds)
