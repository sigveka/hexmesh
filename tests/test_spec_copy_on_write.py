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
``PipeSpec`` is copy-on-write (decision 0053 rule 2, task 0164):
``core()`` and ``shell()`` return a new spec and leave their own
unchanged, so a spec is safe to share.
"""

import pytest

from hexmesh import PipeSpec
from hexmesh.core import CircleShape, RectShape


def _base():
    return PipeSpec(nang=8).core("fluid", radius=0.05, nrad=4).shell("steel", dR=0.003, nrad=2)


def test_shell_leaves_the_spec_it_was_called_on():
    base = _base()
    before = base.to_dict()
    ins = base.shell("insulation", dR=0.02, nrad=2)
    assert ins is not base
    assert base.layer_names == ["fluid", "steel"]
    assert ins.layer_names == ["fluid", "steel", "insulation"]
    assert base.to_dict() == before


def test_core_leaves_the_spec_it_was_called_on():
    empty = PipeSpec(nang=8)
    a = empty.core("fluid", radius=0.05, nrad=4)
    b = empty.core("gas", radius=0.04, nrad=3)
    assert empty.layer_names == []
    assert a.layer_names == ["fluid"] and b.layer_names == ["gas"]
    assert a.core_shape.radius == 0.05


def test_counts_a_shape_sets_stay_on_the_new_spec():
    """A shape's counts fill the spec's unset nang_w/nang_h on the copy only."""
    empty = PipeSpec()
    duct = empty.core("air", shape=RectShape(0.1, 0.05, nang_w=6, nang_h=4), nrad=0, layout="h")
    assert (duct.nang_w, duct.nang_h) == (6, 4)
    assert (empty.nang_w, empty.nang_h) == (None, None)
    circle = empty.core("fluid", shape=CircleShape(0.05, nang=8), nrad=3)
    assert circle.nang == 8 and empty.nang is None


def test_two_branches_from_one_spec_are_independent():
    base = _base()
    bare = base.shell("paint", dR=0.001, nrad=1)
    lagged = base.shell("insulation", dR=0.02, nrad=2)
    assert bare.layer_names[-1] == "paint" and lagged.layer_names[-1] == "insulation"
    assert len(base.shells) == 1


def test_the_saved_form_is_unchanged():
    assert _base().to_dict() == PipeSpec.from_dict(_base().to_dict()).to_dict()


def test_a_refused_shell_leaves_the_spec_unchanged():
    base = _base()
    with pytest.raises(Exception):
        base.shell("insulation", dR=-0.01, nrad=2)    # a negative thickness
    assert base.layer_names == ["fluid", "steel"]
