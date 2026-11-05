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
The HVAC examples and ``lagged_duct`` built with ``layout="h"`` (task
0086 step 6; the examples themselves stay O-H until task 0087).  Each H
build meshes all-hex at the predicted count, with the min corner SJ of
task 0086's table.
"""

import pytest

from hexmesh import PipeSpec, Reducer, Session, Transition
from hexmesh.core.shape import RectShape
from hexmesh.examples.applications import hvac_branched, hvac_supply
from hexmesh.examples.sections import lagged_duct
from hexmesh.quality_hex import hex_vertices, min_scaled_jacobians


def _h(half_w, half_h, n, **kw):
    return PipeSpec(nang_w=n, nang_h=n).core("air", RectShape(half_w, half_h, n, n),
                                             layout="h", **kw)


def _supply(monkeypatch, **kw):
    """The terminal's rectangle → rectangle change is a ``Reducer`` on H
    faces (a ``Transition`` with H at both ends points there)."""
    n = hvac_supply.N
    term = _h(0.15, 0.15, n, **kw)
    monkeypatch.setattr(hvac_supply, "DUCT", _h(0.25, 0.125, n, **kw))
    monkeypatch.setattr(hvac_supply, "TERMINAL", term)
    monkeypatch.setattr(hvac_supply, "Transition", lambda outlet, length, n_layers: (
        Reducer(outlet, length, n_layers=n_layers) if outlet is term
        else Transition(outlet, length=length, n_layers=n_layers)))
    return hvac_supply.build()


def _branched(monkeypatch, **kw):
    monkeypatch.setattr(hvac_branched, "DUCT", _h(hvac_branched.HALF_W, hvac_branched.HALF_H,
                                                  hvac_branched.N, **kw))
    return hvac_branched.build()


def _lagged(monkeypatch, **kw):
    n = lagged_duct.NANG
    monkeypatch.setattr(lagged_duct, "duct", lambda half_w, half_h: (
        PipeSpec(nang=n).core("air", RectShape(half_w, half_h, n, n), layout="h", **kw)
        .shell("steel", dR=0.002, nrad=2).shell("lagging", dR=0.03, nrad=3)))
    return lagged_duct.build()


# (build, H kwargs, cells, min SJ): task 0086's table; O-H 15360, 33472, 10488
@pytest.mark.parametrize("build, kw, cells, sj", [
    (_supply, {}, 6912, 0.577),
    (_supply, {"first_cell": 0.005}, 6912, 0.566),
    (_branched, {}, 24704, 0.421),
    (_branched, {"first_cell": 0.01}, 24704, 0.421),
    (_lagged, {}, 7176, 0.690),
    (_lagged, {"first_cell": 0.004}, 7176, 0.690),
])
def test_h_build_meshes(monkeypatch, build, kw, cells, sj):
    with Session("h-example"):
        asm = build(monkeypatch, **kw)
        assert asm.cell_count() == cells
        asm.mesh()
        vols = sum(asm.fitting_volumes().values(), [])
        _, xyz = hex_vertices(vols)
        assert len(xyz) == cells
        assert float(min_scaled_jacobians(xyz).min()) == pytest.approx(sj, abs=1e-3)
        assert asm.warnings == []
