"""
Every example runs, writes its mesh, and meshes exactly as predicted
(docs/tasks/0016).
"""

import importlib
from pathlib import Path

import pytest

from hexmesh.examples import ALL


@pytest.mark.parametrize("name", ALL)
def test_example(name, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    module = importlib.import_module(f"hexmesh.examples.{name}")
    result = module.main()
    assert (tmp_path / f"{name.split('.')[-1]}.msh").stat().st_size > 0
    assert result.meshed == result.predicted
    assert result.quality.ok, str(result.quality)
    # what hexmesh changed in gmsh's mesh, every fitting, "none" included
    # (decision 0046 rule 5, task 0123)
    assert result.quality.corrections
    assert all(c["wall_projection"] == "none" or c["wall_projection"]["nodes"] > 0
               for c in result.quality.corrections.values())
    assert not any(c["elements_written"] for c in result.quality.corrections.values())


def test_every_example_is_listed():
    import hexmesh.examples as pkg
    root = Path(pkg.__path__[0])
    found = {f"{p.parent.name}.{p.stem}" for p in root.glob("*/*.py")
             if not p.stem.startswith("_")}
    assert found == set(ALL)
    assert not [p for p in root.glob("*.py") if not p.stem.startswith("_")]


# --- families: the gallery's Features page (decision 0050, task 0142) ---------

ROOT = Path(__file__).resolve().parents[1]


def test_every_feature_example_is_in_one_family():
    from hexmesh.examples import FAMILIES
    listed = [q for f in FAMILIES.values() for q in f["examples"]]
    assert len(listed) == len(set(listed))
    assert set(listed) == {q for q in ALL if not q.startswith("applications.")}


def test_family_tags_and_fittings_exist():
    import json
    import re
    from hexmesh.examples import FAMILIES
    schema = json.loads((ROOT / "validation" / "case.schema.json").read_text(encoding="utf-8"))
    tags = set(schema["properties"]["tags"]["properties"]["features"]["items"]["enum"])
    api = (ROOT / "API.md").read_text(encoding="utf-8")
    for fam, f in FAMILIES.items():
        assert set(f["tags"]) <= tags, fam
        for name in f["fittings"]:
            assert re.search(rf"^### `(Assembly\.)?{name}\(", api, re.M), (fam, name)
    # every tag belongs to some family, so no case is left off the Features page
    assert tags <= {t for f in FAMILIES.values() for t in f["tags"]}


def test_guide_examples_table_matches_the_families():
    from hexmesh.examples import CATEGORIES, FAMILIES
    guide = (ROOT / "docs" / "GUIDE.md").read_text(encoding="utf-8")
    section = guide[guide.index("\n## Examples\n"):guide.index("\n## Current limitations")]
    for f in FAMILIES.values():
        row = next(line for line in section.splitlines() if line.startswith(f"| {f['title']} |"))
        assert row.count("`") // 2 == len(f["examples"]), f["title"]
        assert all(f"`{q}`" in row for q in f["examples"]), f["title"]
    row = next(line for line in section.splitlines() if line.startswith("| Applications |"))
    assert all(f"`applications.{n}`" in row for n in CATEGORIES["applications"])
