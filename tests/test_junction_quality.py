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
"""Junctions predict non-orthogonality in validate() (task 0104)."""

import warnings

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import AssemblyError, limits
from hexmesh.assembly import junction_quality
from hexmesh.assembly.blocks import BlockLayout
from hexmesh.quality_hex import max_non_orthogonality

from test_fitting_conformance import CASES, _session, _tee
from test_wye import _wye_asm


def _fitting(asm):
    e = next(x for x in asm._edges if type(x.fitting).__name__ in ("Tee", "Wye"))
    return e, [p.frame for p in e.ports], e.ports[0].spec


def _layout(asm):
    e, frames, spec = _fitting(asm)
    return e.fitting.layout(frames, spec)


def _nonorth(asm):
    asm.validate()
    return [w for w in asm.warnings if "predicted non-orthogonality" in w]


class TestCells:
    def test_unit_cube(self):
        """One cube block: 2 × 3 × 4 cells, orthogonal, volume 1."""
        lay = BlockLayout()
        for v, p in enumerate([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                               (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]):
            lay.vertex(v, p)
        lay.block(list(range(8)), "fluid")
        lay.edge(0, 1, divisions=2)
        lay.edge(0, 3, divisions=3)
        lay.edge(0, 4, divisions=4)
        verts, conn, block = lay.cells()
        assert len(verts) == 24 and (block == 0).all()
        assert len(np.unique(conn)) == 3 * 4 * 5
        assert lay.predicted_nonorth() == (pytest.approx(0.0, abs=1e-9), 0)

    def test_the_cell_count_matches(self):
        lay = _layout(CASES["tee-0.5"]())
        assert len(lay.cells()[0]) == lay.cell_count()

    @pytest.mark.parametrize("case, tol", [("tee-0.5", 0.5), ("wye-60", 1.0),
                                           ("tee-duct-rect-2-wide", 0.1)])
    def test_predicted_against_meshed(self, case, tol):
        """Within the benchmark's error on these (benchmarks/junction_nonorth.py)."""
        asm = CASES[case]()
        e, frames, spec = _fitting(asm)
        predicted, _ = e.fitting.layout(frames, spec).predicted_nonorth()
        _session()
        try:
            asm.mesh()
            meshed = 0.0
            ntag, nx, _ = gmsh.model.mesh.getNodes()
            pos = np.empty((int(ntag.max()) + 1, 3))
            pos[ntag.astype(int)] = nx.reshape(-1, 3)
            for vol in asm._fitting_volumes[e.index]:
                _, _, enodes = gmsh.model.mesh.getElements(3, vol)
                conn = np.asarray(enodes[0], dtype=int).reshape(-1, 8)
                meshed = max(meshed, max_non_orthogonality(pos[conn], conn))
        finally:
            gmsh.finalize()
        assert predicted == pytest.approx(meshed, abs=tol)


class TestTiers:
    def test_small_ratio_tee_warns(self):
        """r/R 0.3 predicts ~73°: a warning naming the block and the cure."""
        found = _nonorth(_tee(0.3))
        assert len(found) == 1
        assert "OUTLINE_NONORTH_WARN" in found[0]
        assert "turn block" in found[0] and "larger branch ratio" in found[0]

    def test_quiet_below_the_warning(self):
        assert not _nonorth(_tee(0.9))

    def test_above_the_maximum_raises(self, monkeypatch):
        monkeypatch.setattr(limits, "OUTLINE_NONORTH_MAX", 60.0)
        monkeypatch.setattr(limits, "OUTLINE_NONORTH_WARN", 50.0)
        with pytest.raises(AssemblyError) as err:
            _tee(0.5).validate()
        assert err.value.code == "predicted_nonorth_above_maximum"
        assert err.value.value > 60.0

    def test_the_wye_only_warns_above_the_maximum(self):
        """Like its scaled-Jacobian tier, until its layout redesign."""
        asm, _, _ = _wye_asm(30, run=0.4, branch=0.7)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            found = _nonorth(asm)
        assert len(found) == 1 and "OUTLINE_NONORTH_MAX" in found[0]
        assert "the ring at the crotch" in found[0]

    def test_narrow_face_duct_tap_warns(self):
        found = _nonorth(CASES["tee-duct-rect-2-narrow"]())
        assert len(found) == 1 and "wide face" in found[0]

    def test_cached_by_value(self, monkeypatch):
        """A second validate() of an equal junction reuses the prediction."""
        _tee(0.3).validate()
        calls = []
        real = BlockLayout.predicted_nonorth
        monkeypatch.setattr(BlockLayout, "predicted_nonorth",
                            lambda self: calls.append(1) or real(self))
        _tee(0.3).validate()
        assert not calls
        _tee(0.31).validate()
        assert calls
