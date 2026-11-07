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
gmsh, loaded when first used (task 0107).

Only building and meshing need gmsh, and importing it costs about 0.13 s
and fails where its shared libraries can't load (decision 0039).  The
modules that call gmsh import it from here::

    from ._gmsh import gmsh

and keep their ``gmsh.model…`` calls.  The first attribute read imports
the real module; :class:`~hexmesh.Session` does that when it starts, so
meshing behaves as before.  When the import fails, :func:`load` raises
:class:`~hexmesh.errors.GmshUnavailable` with the reason and the fix.
"""

from __future__ import annotations

import sys

from .errors import GmshUnavailable

#: the commands that work without gmsh: hexmesh.agent._commands.NEEDS_GMSH
#: lists the rest
WITHOUT_GMSH = "schema, manifest, validate, estimate, describe, preview, advise and apply"

_module = None


def load():
    """The real gmsh module, imported on the first call."""
    global _module
    if _module is None:
        try:
            import gmsh as module
        except (ImportError, OSError) as e:          # OSError: a shared library missing
            fix = "pip install gmsh"
            if sys.platform.startswith("linux"):
                fix += ("; on Linux gmsh also needs libglu1-mesa, libxrender1, libxcursor1, "
                        "libxft2 and libxinerama1 (as in .github/workflows/tests.yml)")
            raise GmshUnavailable(
                f"gmsh could not be imported ({type(e).__name__}: {e}); building and meshing "
                f"need it, but {WITHOUT_GMSH} work without it",
                code="gmsh_unavailable", value=f"{type(e).__name__}: {e}", hint=fix) from e
        _module = module
    return _module


class _Lazy:
    """Stands in for the gmsh module: every attribute is the real module's."""

    __slots__ = ()

    def __getattr__(self, name):
        return getattr(load(), name)

    def __repr__(self) -> str:
        return "<gmsh, loaded on first use>" if _module is None else repr(_module)


gmsh = _Lazy()
