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
Shared pytest fixtures for hexmesh tests.

GMSH is a process-level singleton; each test that touches the geo/mesh kernel
must run in its own initialize/finalize session.  The ``gmsh_session`` fixture
handles that lifecycle automatically.

Pipe-spec fixtures use the smallest practical n_arc (4) and n_radial (3) to keep
meshing fast while still exercising all code paths.
"""

import sys

import pytest
import gmsh

from hexmesh.core.spec import PipeSpec
from hexmesh.core.shape import CircleShape, RectShape


# ---------------------------------------------------------------------------
# Platforms (decision 0052; task 0157)
# ---------------------------------------------------------------------------

def pytest_collection_modifyitems(config, items):
    """``posix_only`` tests are skipped on Windows (the architecture test
    ``test_posix_tools_are_marked`` finds the tests that need it)."""
    if sys.platform != "win32":
        return
    skip = pytest.mark.skip(reason="needs a POSIX shell (platforms.md: WSL's bash)")
    for item in items:
        if item.get_closest_marker("posix_only"):
            item.add_marker(skip)


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
        PipeSpec(n_arc=4)
        .core("fluid", shape=CircleShape(radius=0.1, n_arc=4), n_radial=3)
    )


@pytest.fixture
def two_layer_pipe():
    """Two-layer circular pipe (fluid + wall)."""
    return (
        PipeSpec(n_arc=4)
        .core("fluid",    shape=CircleShape(radius=0.1, n_arc=4), n_radial=3)
        .shell("wall",    dR=0.025, n_radial=2)
    )


@pytest.fixture
def rect_pipe():
    """Single-layer rectangular (duct) pipe."""
    return (
        PipeSpec(n_width=3, n_height=2)
        .core("air", shape=RectShape(half_w=0.08, half_h=0.05, n_width=3, n_height=2),
              n_radial=3, layout="oh")
    )


@pytest.fixture
def rect_shell_pipe():
    """Circular core + circular shell + square outer shell (bundle cell)."""
    return (
        PipeSpec(n_arc=4)
        .core("fluid",  shape=CircleShape(radius=0.08, n_arc=4), n_radial=3)
        .shell("wall",  dR=0.02, n_radial=2)
        .shell("shell", outer=RectShape(0.15, 0.15, n_width=4, n_height=4), n_radial=2)
    )
