"""
Assembly guards (task 0039).

* An interface is the inlet of at most one fitting and the outlet of at
  most one: a second fitting on the same side is rejected when added.
* Every GMSH-side method needs an open GMSH session, and says so before
  any GMSH call.
* Quality needs a mesh: ``check_quality`` before ``mesh()`` says so.
"""

import gmsh
import pytest

from hexmesh import Session
from hexmesh.assembly import Assembly, AssemblyError, Bend, Straight
from hexmesh.assembly.assembler import Edge
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec


def _pipe():
    return PipeSpec(nang=4).core("fluid", CircleShape(radius=0.1, nang=4), nrad=3)


def _run():
    a = Assembly(_pipe())
    a.add(Straight(0.2, n_layers=2))
    return a


# ---------------------------------------------------------------------------
# Interface degree
# ---------------------------------------------------------------------------

def test_second_fitting_on_inlet_rejected_at_add():
    a = _run()
    with pytest.raises(AssemblyError) as exc:
        a.add(a.inlet, Straight(0.2, n_layers=2))
    msg = str(exc.value)
    assert "inlet" in msg and "#0" in msg
    assert "fitting #0 Straight" in msg            # the fitting already there
    assert msg.count("Straight(") == 2             # and the new one
    assert len(a.edges) == 1 and len(a.interfaces) == 2   # nothing recorded


def test_second_fitting_on_outlet_rejected_at_add():
    a = _run()
    out = a.interfaces[1]
    a.add(out, Straight(0.2, n_layers=2))
    with pytest.raises(AssemblyError, match="already the inlet of fitting #1"):
        a.add(out, Bend(radius=0.3, angle=90, n_layers=4))


def test_branching_from_distinct_outlets_still_allowed():
    a = _run()
    a.add(Straight(0.2, n_layers=2))
    a.validate()


def test_loaded_json_with_overlap_fails():
    d = _run().to_dict()
    d["edges"].append(dict(d["edges"][0], source=0))
    with pytest.raises(AssemblyError, match="already the inlet"):
        Assembly.from_dict(d)


def test_validate_rejects_overlap_built_without_add():
    a = _run()
    out = a._new_interface(a.interfaces[1].frame, a.inlet.spec, None)
    edge = Edge(1, Straight(0.2, n_layers=2), [a.inlet, out])
    a._edges.append(edge)
    a.inlet.edges.append(edge)
    out.edges.append(edge)
    with pytest.raises(AssemblyError, match=r"is the inlet of 2 fittings"):
        a.validate()


def test_prepend_unaffected():
    a = _run()
    a.prepend(Straight(0.1, n_layers=1))
    a.prepend(Straight(0.1, n_layers=1))
    a.validate()


# ---------------------------------------------------------------------------
# Session guard
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("call", [
    lambda a, p: a.write(str(p / "x.msh")),
    lambda a, p: a.write_openfoam(str(p / "x.msh")),
    lambda a, p: a.mesh(),
    lambda a, p: a.build(),
    lambda a, p: a.build_faces(),
    lambda a, p: a.fill(),
    lambda a, p: a.write_physical_groups(),
    lambda a, p: a.check_quality(),
    lambda a, p: a.fitting_volumes(),
    lambda a, p: a.volumes,
], ids=["write", "write_openfoam", "mesh", "build", "build_faces", "fill",
        "write_physical_groups", "check_quality", "fitting_volumes", "volumes"])
def test_outside_session_raises_quietly(call, tmp_path, capfd):
    assert not gmsh.isInitialized()
    a = _run()
    with pytest.raises(AssemblyError, match=r"needs a GMSH session: use `with Session"):
        call(a, tmp_path)
    out, err = capfd.readouterr()
    assert "Gmsh" not in err and "Gmsh" not in out
    assert err == ""


def test_check_quality_before_mesh(tmp_path):
    with Session("guard"):
        a = _run()
        with pytest.raises(AssemblyError, match=r"call mesh\(\) or write\(\) first"):
            a.check_quality()
        with pytest.raises(AssemblyError, match=r"call mesh\(\) first"):
            a.group_roles()
        a.mesh()
        assert a.check_quality().ok
        assert a.group_roles()
