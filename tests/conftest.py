"""
Shared pytest fixtures for hexmesh tests.

GMSH is a process-level singleton; each test that touches the geo/mesh kernel
must run in its own initialize/finalize session.  The ``gmsh_session`` fixture
handles that lifecycle automatically.

Pipe-spec fixtures use the smallest practical nang (4) and nrad (3) to keep
meshing fast while still exercising all code paths.
"""

import pytest
import gmsh

from hexmesh.core.spec import PipeSpec
from hexmesh.core.shape import CircleShape, RectShape


# ---------------------------------------------------------------------------
# GMSH session lifecycle
# ---------------------------------------------------------------------------

@pytest.fixture
def gmsh_session():
    """Fresh GMSH session for one test — initialize, add model, finalize."""
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add("test")
    yield
    gmsh.finalize()


# ---------------------------------------------------------------------------
# Pipe-spec fixtures (no GMSH needed — pure Python)
# ---------------------------------------------------------------------------

@pytest.fixture
def circle_pipe():
    """Single-layer circular pipe (fluid only)."""
    return (
        PipeSpec(nang=4)
        .core("fluid", shape=CircleShape(radius=0.1, nang=4), nrad=3)
    )


@pytest.fixture
def two_layer_pipe():
    """Two-layer circular pipe (fluid + wall)."""
    return (
        PipeSpec(nang=4)
        .core("fluid",    shape=CircleShape(radius=0.1, nang=4), nrad=3)
        .shell("wall",    dR=0.025, nrad=2)
    )


@pytest.fixture
def rect_pipe():
    """Single-layer rectangular (duct) pipe."""
    return (
        PipeSpec(nang_w=3, nang_h=2)
        .core("air", shape=RectShape(half_w=0.08, half_h=0.05, nang_w=3, nang_h=2),
              nrad=3)
    )


@pytest.fixture
def rect_shell_pipe():
    """Circular core + circular shell + square outer shell (bundle cell)."""
    return (
        PipeSpec(nang=4)
        .core("fluid",  shape=CircleShape(radius=0.08, nang=4), nrad=3)
        .shell("wall",  dR=0.02, nrad=2)
        .shell("shell", outer=RectShape(0.15, 0.15, 4, 4), nrad=2)
    )
