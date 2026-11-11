"""Junctions and bends at directions placed by trigonometry (task 0141):
``[cos a, 0, -sin a]`` is 1e-16 off an axis at 180°, where OCC's plate
filling of one tee face failed at gmsh's default tolerance
(``blocks.BlockLayout._plate`` retries it at a relative one)."""
import math
import warnings

import pytest

from hexmesh import Assembly, PipeSpec, Session, Tee
from hexmesh.assembly import Bend, Straight, Wye

SPEC = lambda: (PipeSpec(nang=6).core("lox", radius=0.02, nrad=4)
                .shell("steel", dR=0.003, nrad=2))
ANGLES = range(0, 360, 45)


def _meshed(asm):
    with Session("dir"), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        asm.mesh()


@pytest.mark.parametrize("dz", [0.0, -1.2246e-16, 1.2246e-16, -1e-12, -1e-9, -1e-6])
def test_the_reported_tee(dz):
    asm = Assembly(SPEC(), direction=[-1, 0, dz], up=[0, -1, 0])
    asm.add(Tee(branch_length=0.05, branch_radius=0.012))
    _meshed(asm)


def _ring_direction(a):
    a = math.radians(a)
    return [math.cos(a), 0.0, -math.sin(a)]


@pytest.mark.parametrize("a", ANGLES)
def test_a_tee_at_each_ring_direction(a):
    asm = Assembly(SPEC(), direction=_ring_direction(a), up=[0, -1, 0])
    asm.add(Tee(branch_length=0.05, branch_radius=0.012, roll=90))
    _meshed(asm)


@pytest.mark.parametrize("a", ANGLES)
def test_a_wye_at_each_ring_direction(a):
    asm = Assembly(SPEC(), direction=_ring_direction(a), up=[0, -1, 0])
    asm.add(Wye(60, run_length=0.08, branch_length=0.08))
    _meshed(asm)


@pytest.mark.parametrize("a", ANGLES)
def test_a_bend_at_each_ring_direction(a):
    asm = Assembly(SPEC(), direction=_ring_direction(a), up=[0, -1, 0])
    asm.add(Straight(0.05, n_layers=1))
    asm.add(Bend(0.06, 45, n_layers=3))
    _meshed(asm)
