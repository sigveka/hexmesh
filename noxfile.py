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
Local test sessions against both gmsh versions CI runs (decision 0052,
task 0159): the reference gmsh 4.12.1 and what ``pip`` installs.  Each
session has its own venv under ``.nox/`` (git-ignored)::

    nox -s tests-gmsh412                     # the junction tests, gmsh 4.12.1
    nox -s tests-gmsh-latest                 # the same, the latest gmsh
    nox -s tests-gmsh412 -- -k tee           # pytest arguments after --
    nox -s tests-gmsh412 tests-gmsh-latest   # both

Without arguments a session runs ``JUNCTIONS``, the tests whose numbers
moved between the two versions in task 0145.  ``-n 2`` comes first, so
a ``-n`` of yours wins.  No ``nox``?  ``uvx nox …`` runs it without
installing it.

The machine may be shared (CLAUDE.md): check ``pgrep -af pytest`` for
another session's run before starting one, and keep ``-n`` low.
"""

import nox

nox.options.reuse_existing_virtualenvs = True
nox.options.sessions = ["tests-gmsh412", "tests-gmsh-latest"]

#: the junction and plate tests (task 0145's failures were among them)
JUNCTIONS = ["tests/test_tee.py", "tests/test_equal_tee.py", "tests/test_wye.py",
             "tests/test_duct_tap.py", "tests/test_tee_branch_grading.py",
             "tests/test_junction_quality.py", "tests/test_pcf_junctions.py",
             "tests/test_units.py"]


def _tests(session: nox.Session, gmsh: str | None) -> None:
    session.install("-e", ".[dev,study]")
    if gmsh:
        session.install(f"gmsh=={gmsh}")
    session.run("python", "-c", "import gmsh, hexmesh; "
                "print('gmsh', gmsh.__version__, '| hexmesh', hexmesh.__version__)")
    session.run("python", "-m", "pytest", "-q", "-n", "2", "-p", "no:cacheprovider",
                *(session.posargs or JUNCTIONS))


@nox.session(name="tests-gmsh412", venv_backend="uv|virtualenv")
def tests_gmsh412(session: nox.Session) -> None:
    """The tests on gmsh 4.12.1, the reference (CI's pinned job)."""
    _tests(session, "4.12.1")


@nox.session(name="tests-gmsh-latest", venv_backend="uv|virtualenv")
def tests_gmsh_latest(session: nox.Session) -> None:
    """The tests on the gmsh ``pip`` installs today."""
    _tests(session, None)
