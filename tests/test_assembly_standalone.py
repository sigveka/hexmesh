"""
The assembly does not depend on the legacy API (docs/tasks/0011).

Run in a subprocess so the legacy modules can be blocked before anything
imports them.
"""

import subprocess
import sys
import textwrap

SCRIPT = textwrap.dedent("""
    import sys
    for name in ("hexmesh.connectors", "hexmesh.network", "hexmesh.model",
                 "hexmesh.core.cursor"):
        sys.modules[name] = None          # any import of these now raises

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "hexmesh", "hexmesh/__init__.py",
        submodule_search_locations=["hexmesh"])
    pkg = importlib.util.module_from_spec(spec)
    sys.modules["hexmesh"] = pkg          # skip the legacy package __init__

    import gmsh
    from hexmesh.assembly import Assembly, Straight
    from hexmesh.core.shape import CircleShape
    from hexmesh.core.spec import PipeSpec

    spec = PipeSpec(nang=4).core("fluid", CircleShape(radius=0.1, nang=4), nrad=3)
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add("standalone")
    asm = Assembly(spec, lc=0.1)
    asm.add(Straight(0.3, n_layers=3))
    asm.mesh()
    assert asm.check_quality().ok
    gmsh.finalize()
    print("ok")
""")


def test_assembly_runs_without_legacy_modules():
    root = __file__.rsplit("/tests/", 1)[0]
    r = subprocess.run([sys.executable, "-c", SCRIPT], cwd=root,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().endswith("ok")
