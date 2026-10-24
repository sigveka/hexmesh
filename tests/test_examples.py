"""
Every example runs, writes its mesh, and meshes exactly as predicted
(docs/tasks/0016).
"""

import importlib

import pytest

EXAMPLES = ["smooth_bend", "miter_bend", "insulated_pipe", "reducer_network",
            "tee", "loop", "spline_pipe", "pipe_network"]


@pytest.mark.parametrize("name", EXAMPLES)
def test_example(name, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    module = importlib.import_module(f"hexmesh.examples.{name}")
    result = module.main()
    assert (tmp_path / f"{name}.msh").stat().st_size > 0
    assert result.meshed == result.predicted
    assert result.quality.ok, str(result.quality)


def test_every_example_is_tested():
    from pathlib import Path
    import hexmesh.examples as pkg
    found = {p.stem for p in Path(pkg.__path__[0]).glob("*.py")
             if not p.stem.startswith("_")}
    assert found == set(EXAMPLES)
