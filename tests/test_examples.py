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


def test_every_example_is_listed():
    import hexmesh.examples as pkg
    root = Path(pkg.__path__[0])
    found = {f"{p.parent.name}.{p.stem}" for p in root.glob("*/*.py")
             if not p.stem.startswith("_")}
    assert found == set(ALL)
    assert not [p for p in root.glob("*.py") if not p.stem.startswith("_")]
