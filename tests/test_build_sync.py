"""
Build without per-entity synchronizes (decision 0020, docs/tasks/0036).

hexmesh records the start/end points and kind of every curve it creates
(``hexmesh._occ``), so nothing reads the model back during a build; the
whole assembly synchronizes a fixed number of times, whatever its size.
"""

import gmsh
import pytest

import test_fitting_conformance as kit
from hexmesh import Assembly, Bend, PipeSpec, Straight, _occ

SPEC = PipeSpec(nang=4).core("fluid", radius=0.05, nrad=2)


@pytest.fixture
def syncs(monkeypatch):
    calls = []
    orig = gmsh.model.occ.synchronize
    monkeypatch.setattr(gmsh.model.occ, "synchronize", lambda: (calls.append(1), orig())[1])
    return calls


def _serpentine(pairs):
    asm = Assembly(SPEC, direction=[1, 0, 0], up=[0, 0, 1])
    for k in range(pairs):
        asm.add(Straight(0.2, n_layers=2))
        asm.add(Bend(radius=0.1, angle=180, n_layers=3, roll=0 if k % 2 else 180))
    return asm


@pytest.mark.parametrize("pairs", [1, 4])
def test_synchronize_count_independent_of_size(gmsh_session, syncs, pairs):
    """Four per assembly: after the faces, at the end of fill, after
    removing construction points, and before the mesh constraints."""
    fallbacks = _occ.fallbacks
    asm = _serpentine(pairs)
    asm.mesh()
    assert len(syncs) == 4
    assert _occ.fallbacks == fallbacks
    assert sum(len(t) for t in gmsh.model.mesh.getElements(3)[1]) == asm.cell_count()


@pytest.mark.parametrize("case", sorted(kit.CASES))
def test_records_match_model(gmsh_session, case):
    """Every recorded curve has the end points and kind the synchronized
    model reports, and no build needed a fallback query."""
    fallbacks = _occ.fallbacks
    kit.CASES[case]().mesh()
    assert _occ.fallbacks == fallbacks
    curves = {t for _, t in gmsh.model.getEntities(1)}
    recorded = [t for t in _occ._ends if t in curves]
    assert recorded
    for t in recorded:
        assert _occ._ends[t] == _occ._model_endpoints(t), t
        assert _occ._kind[t] == gmsh.model.getType(1, t), t


def test_unrecorded_curve_falls_back(gmsh_session):
    """A curve hexmesh did not create is read from the model."""
    a = gmsh.model.occ.addPoint(0, 0, 0)
    b = gmsh.model.occ.addPoint(1, 0, 0)
    c = gmsh.model.occ.addLine(b, a)
    _occ._ends.pop(c, None), _occ._kind.pop(c, None)
    fallbacks = _occ.fallbacks
    with _occ.building():
        assert _occ.endpoints(c) == (b, a)
        assert _occ.kind(c) == "Line"
    assert _occ.fallbacks == fallbacks + 2


def test_records_ignored_outside_a_build(gmsh_session):
    """A stale record (say, from an earlier model with the same tags) is
    never used outside a build: the model is asked."""
    a = gmsh.model.occ.addPoint(0, 0, 0)
    b = gmsh.model.occ.addPoint(1, 0, 0)
    c = gmsh.model.occ.addLine(a, b)
    _occ._ends[c], _occ._kind[c] = (b, a), "Circle"
    assert _occ.endpoints(c) == (a, b)
    assert _occ.kind(c) == "Line"


def test_build_resets_records(gmsh_session):
    _occ._ends[10**6] = (1, 2)
    asm = Assembly(SPEC)
    asm.add(Straight(0.1, n_layers=1))
    asm.build_faces()
    assert 10**6 not in _occ._ends
