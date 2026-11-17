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
``Assembly.add`` returns a named tuple for a fitting with several outlets
(decision 0053 rule 3, task 0164): it unpacks as before and reads by
port name.
"""

import json

import numpy as np
import pytest

from hexmesh import (Assembly, Interface, PipeSpec, Straight, Tee, TeeOutlets, Wye,
                     WyeOutlets)
from hexmesh.agent import describe


def _asm():
    return Assembly(PipeSpec(n_arc=6).core("fluid", radius=0.1, n_radial=4),
                    direction=[1, 0, 0], up=[0, 0, 1])


def test_a_tee_returns_its_run_and_branch_by_name():
    asm = _asm()
    asm.add(Straight(0.5, n_layers=4))
    out = asm.add(Tee(branch_length=0.3, branch_radius=0.06))
    assert isinstance(out, TeeOutlets) and out._fields == ("run", "branch")
    run, branch = out                                   # unpacks as before
    assert run is out.run and branch is out.branch
    assert isinstance(run, Interface) and isinstance(branch, Interface)
    # the run continues along the inlet; the branch leaves it at 90°
    assert np.allclose(run.frame.normal, [1, 0, 0])
    assert abs(np.dot(branch.frame.normal, [1, 0, 0])) < 1e-9
    nxt = asm.add(Straight(0.5, n_layers=4))            # the tail follows the run
    assert np.allclose(nxt.frame.position, run.frame.position + [0.5, 0, 0])


def test_a_wye_returns_left_and_right_by_name():
    asm = _asm()
    out = asm.add(Wye(angle=60, run_length=0.3, branch_length=0.5))
    assert isinstance(out, WyeOutlets) and out._fields == ("left", "right")
    left, right = out
    assert left is out.left and right is out.right
    # right turns toward the inlet's right: -y for direction +x, up +z
    assert right.frame.normal[1] < 0 < left.frame.normal[1]


def test_names_are_keyed_by_the_same_port_names():
    asm = _asm()
    out = asm.add(Tee(branch_length=0.3, branch_radius=0.06),
                  names={"run": "main_out", "branch": "tap"})
    assert (out.run.name, out.branch.name) == ("main_out", "tap")


def test_a_single_outlet_fitting_still_returns_the_interface():
    asm = _asm()
    assert isinstance(asm.add(Straight(0.5, n_layers=4)), Interface)


def test_describe_is_unchanged_by_the_tuple():
    """The tuple is only what add returns: the description holds interfaces."""
    a, b = _asm(), _asm()
    a.add(Tee(branch_length=0.3, branch_radius=0.06))
    run, branch = b.add(Tee(branch_length=0.3, branch_radius=0.06))
    assert json.dumps(describe(a), sort_keys=True) == json.dumps(describe(b), sort_keys=True)
    assert "Outlets" not in json.dumps(describe(a))
