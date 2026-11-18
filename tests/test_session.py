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
hexmesh's start of gmsh keeps ``PATH``: ``gmsh.initialize()`` replaces
the native ``PATH`` on Windows (task 0173; ``docs/integrations/gmsh.md``).
Every start goes through ``_gmsh.initialize`` (``Session`` and
``to_mesh``'s ``_gmsh.start``).
"""

import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from hexmesh import Session, _gmsh


def _child_path() -> str:
    """The PATH a program started now inherits (the native environment)."""
    return subprocess.run([sys.executable, "-c", "import os; print(os.environ['PATH'])"],
                          capture_output=True, text=True, check=True).stdout.strip()


def test_initialize_restores_a_path_gmsh_replaced(monkeypatch):
    """A stand-in gmsh replaces the native PATH only (``os.putenv``), as
    gmsh 4.15.2 does on Windows; a program started afterwards still gets
    ``os.environ``'s PATH."""
    path = os.environ["PATH"]
    monkeypatch.setenv("PATH", path)                 # restored after the test
    fake = SimpleNamespace(initialize=lambda: os.putenv("PATH", "clobbered-by-gmsh"))
    monkeypatch.setattr(_gmsh, "load", lambda: fake)
    _gmsh.initialize()
    assert os.environ["PATH"] == path
    assert _child_path() == path


def test_every_start_goes_through_the_helper():
    """``Session`` and ``_gmsh.start`` call ``_gmsh.initialize``, not
    gmsh's own (a new start must too)."""
    import inspect

    import hexmesh.session as session
    assert "_gmsh.initialize()" in inspect.getsource(session.Session.__enter__)
    assert "module.initialize()" not in inspect.getsource(_gmsh.start)
    assert "initialize()" in inspect.getsource(_gmsh.start)


def _native() -> str:
    import ctypes
    buf = ctypes.create_unicode_buffer(32767)
    ctypes.windll.kernel32.GetEnvironmentVariableW("PATH", buf, len(buf))
    return buf.value


@pytest.mark.skipif(sys.platform != "win32", reason="gmsh replaces PATH on Windows only")
def test_native_path_survives_a_session_on_windows():
    with Session("t"):
        assert _native() == os.environ["PATH"]


@pytest.mark.skipif(sys.platform != "win32", reason="gmsh replaces PATH on Windows only")
def test_native_path_survives_to_mesh_on_windows():
    from hexmesh import Assembly, PipeSpec, Straight
    asm = Assembly(PipeSpec(n_arc=4).core("fluid", radius=0.01, n_radial=1))
    asm.add(Straight(0.05, n_layers=2))
    with asm.to_mesh():
        assert _native() == os.environ["PATH"]
