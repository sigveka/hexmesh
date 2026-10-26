"""
Boundary-role manifest and OpenFOAM patch retyping (decision 0013,
docs/tasks/0023).

Text-fixture tests run everywhere; the ``openfoam`` tests convert real
meshes and are opt-in (``-m openfoam``) and skipped without OpenFOAM.
"""

import json
import re
import shutil
import warnings

import gmsh
import pytest

from hexmesh.assembly import Assembly, Straight, Tee
from hexmesh.core.spec import PipeSpec
from hexmesh.io.writers.openfoam_boundary import (
    apply_boundary_roles, apply_boundary_roles_to_regions, read_roles, retype_boundary_text,
    roles_path,
)

from test_openfoam_output import OPENFOAM_RC, _insulated, foam_case, run_foam

HEADER = r"""/*--------------------------------*- C++ -*----------------------------------*\
| =========                 |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       polyBoundaryMesh;
    location    "constant/polyMesh";
    object      boundary;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

"""

# As gmshToFoam v1912 writes it, plus one split-made mappedWall and one
# patch that already has groups.
BOUNDARY = HEADER + """4
(
    fluid_inlet
    {
        type            patch;
        physicalType    patch;
        nFaces          156;
        startFace       21588;
    }
    fluid_wall  // the outer wall
    {
        type            patch;
        physicalType    patch;
        nFaces          1140;
        startFace       21744;
    }
    fluid_to_steel
    {
        type            mappedWall;
        inGroups        1(wall);
        nFaces          864;
        startFace       22884;
        sampleMode      nearestPatchFace;
        sampleRegion    steel;
        samplePatch     steel_to_fluid;
    }
    fluid_wall_Bend2
    {
        type            patch;
        inGroups        1(heated);
        nFaces          288;
        startFace       23748;
    }
)

// ************************************************************************* //
"""

ROLES = {"format": 1, "groups": {
    "fluid": "volume", "fluid_inlet": "open_end", "fluid_wall": "wall",
    "fluid_wall_Bend2": "wall"}, "not_written": []}


def _entry(text, name):
    return re.search(rf"^    {name}\b[^{{]*\{{(.*?)^    \}}", text, re.M | re.S).group(1)


class TestRetypeText:
    def test_walls_retyped_like_openfoam(self):
        new, retyped, unknown = retype_boundary_text(BOUNDARY, ROLES["groups"])
        assert retyped == ["fluid_wall", "fluid_wall_Bend2"] and unknown == []
        assert _entry(new, "fluid_wall") == (
            "\n        type            wall;\n"
            "        inGroups        1(wall);\n"
            "        physicalType    wall;\n"
            "        nFaces          1140;\n"
            "        startFace       21744;\n")

    def test_existing_groups_extended(self):
        new, _, _ = retype_boundary_text(BOUNDARY, ROLES["groups"])
        assert "inGroups        2(heated wall);" in _entry(new, "fluid_wall_Bend2")

    def test_open_end_and_mapped_wall_unchanged(self):
        new, _, _ = retype_boundary_text(BOUNDARY, ROLES["groups"])
        for name in ("fluid_inlet", "fluid_to_steel"):
            assert _entry(new, name) == _entry(BOUNDARY, name)

    def test_everything_else_byte_for_byte(self):
        new, _, _ = retype_boundary_text(BOUNDARY, ROLES["groups"])
        strip = lambda t: re.sub(r"(?m)^\s*(type|physicalType|inGroups)\s.*\n", "", t)
        assert strip(new) == strip(BOUNDARY)
        assert new.startswith(HEADER) and new.endswith(BOUNDARY[-90:])

    def test_idempotent(self):
        once, _, _ = retype_boundary_text(BOUNDARY, ROLES["groups"])
        twice, retyped, _ = retype_boundary_text(once, ROLES["groups"])
        assert twice == once and retyped == []

    def test_unknown_patch_reported(self):
        groups = {k: v for k, v in ROLES["groups"].items() if k != "fluid_inlet"}
        _, _, unknown = retype_boundary_text(BOUNDARY, groups)
        assert unknown == ["fluid_inlet"]          # the mappedWall is not reported


def _case(tmp_path, text=BOUNDARY, region=None):
    d = tmp_path / "constant" / (region or "") / "polyMesh"
    d.mkdir(parents=True)
    (d / "boundary").write_text(text)
    return d / "boundary"


def test_apply_writes_file_and_warns_once(tmp_path):
    path = _case(tmp_path)
    roles = dict(ROLES, groups={k: v for k, v in ROLES["groups"].items()
                                if k not in ("fluid_inlet", "fluid_wall_Bend2")})
    with pytest.warns(UserWarning, match="fluid_inlet, fluid_wall_Bend2") as rec:
        assert apply_boundary_roles(tmp_path, roles) == ["fluid_wall"]
    assert len(rec) == 1
    assert "type            wall;" in _entry(path.read_text(), "fluid_wall")
    assert not list(path.parent.glob(".boundary.*"))      # no temp file left


def test_apply_from_manifest_file_and_regions(tmp_path):
    for region in ("fluid", "steel"):
        _case(tmp_path, region=region)
    manifest = tmp_path / "pipe.roles.json"
    manifest.write_text(json.dumps(ROLES))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        done = apply_boundary_roles_to_regions(tmp_path, manifest)
    assert done == {"fluid": ["fluid_wall", "fluid_wall_Bend2"],
                    "steel": ["fluid_wall", "fluid_wall_Bend2"]}


def test_manifest_format_checked():
    with pytest.raises(ValueError, match="format"):
        read_roles({"format": 2, "groups": {}})


# ---------------------------------------------------------------------------
# The manifest written by write_openfoam
# ---------------------------------------------------------------------------

def test_manifest_from_the_graph(gmsh_session, tmp_path):
    out = tmp_path / "pipe.msh"
    _insulated().write_openfoam(out)
    m = read_roles(roles_path(out))
    assert roles_path(out).name == "pipe.roles.json"
    assert m["groups"] == {
        "fluid": "volume", "steel": "volume", "insulation": "volume",
        "fluid_inlet": "open_end", "steel_inlet": "open_end", "insulation_inlet": "open_end",
        "fluid_outlet": "open_end", "steel_outlet": "open_end", "insulation_outlet": "open_end",
        "insulation_wall": "wall",
        "interface_fluid_steel": "interface", "interface_steel_insulation": "interface",
    }
    assert m["not_written"] == ["interface_fluid_steel", "interface_steel_insulation"]


def test_manifest_with_interfaces_and_fitting_walls(gmsh_session, tmp_path):
    out = tmp_path / "pipe.msh"
    asm = _insulated()
    asm.write_openfoam(out, interfaces=True, walls_by_fitting=True)
    m = read_roles(roles_path(out))
    assert m["not_written"] == []
    walls = sorted(g for g, r in m["groups"].items() if r == "wall")
    assert walls == ["insulation_wall_Straight0"]


# ---------------------------------------------------------------------------
# Through OpenFOAM
# ---------------------------------------------------------------------------

needs_openfoam = pytest.mark.skipif(not OPENFOAM_RC.exists() or shutil.which("bash") is None,
                                    reason="OpenFOAM not installed")


def _types(case, region=None):
    """patch → type, as foamDictionary reads it."""
    boundary = case / "constant" / (region or "") / "polyMesh" / "boundary"
    names = re.findall(r"^    (\w+)\s*\n\s*\{", boundary.read_text(), re.M)
    script = "; ".join(
        f"echo {n} $(foamDictionary {boundary} -entry entry0/{n}/type -value)" for n in names)
    run = run_foam(script)
    assert run.returncode == 0, run.stderr[-2000:]
    return dict(line.split() for line in run.stdout.strip().splitlines())


def _tee():
    asm = Assembly(PipeSpec(nang=4).core("fluid", radius=0.1, nrad=3),
                   up=[0, 0, 1], lc=0.05)
    asm.add(Straight(0.2, n_layers=2))
    main, branch = asm.add(Tee(0.2, 0.25, 0.05), names=["main", "branch"])
    asm.add(main, Straight(0.2, n_layers=2))
    asm.add(branch, Straight(0.2, n_layers=2))
    return asm


@pytest.mark.openfoam
@needs_openfoam
@pytest.mark.parametrize("walls_by_fitting", [False, True])
@pytest.mark.usefixtures("gmsh_session")
def test_openfoam_single_material_tee(tmp_path, walls_by_fitting):
    msh = tmp_path / "tee.msh"
    _tee().write_openfoam(msh, walls_by_fitting=walls_by_fitting)
    case = foam_case(tmp_path / "case")
    run = run_foam(f"gmshToFoam -case {case} {msh}")
    assert run.returncode == 0, run.stdout[-2000:]
    retyped = apply_boundary_roles(case, roles_path(msh))
    run = run_foam(f"checkMesh -case {case}")
    assert run.returncode == 0 and "Mesh OK." in run.stdout, run.stdout[-2000:]

    roles = read_roles(roles_path(msh))["groups"]
    types = _types(case)
    walls = sorted(p for p in types if roles[p] == "wall")
    ends = sorted(p for p in types if roles[p] == "open_end")
    assert sorted(retyped) == walls
    assert len(walls) == (4 if walls_by_fitting else 1)     # one per fitting
    assert len(ends) == 3                                   # inlet and two outlets
    assert {types[w] for w in walls} == {"wall"}
    assert {types[e] for e in ends} == {"patch"}


@pytest.mark.openfoam
@needs_openfoam
@pytest.mark.usefixtures("gmsh_session")
def test_openfoam_cht_regions(tmp_path):
    msh = tmp_path / "pipe.msh"
    _insulated().write_openfoam(msh)
    case = foam_case(tmp_path / "case")
    run = run_foam(f"gmshToFoam -case {case} {msh}; "
                   f"splitMeshRegions -case {case} -cellZones -overwrite")
    assert run.returncode == 0, run.stdout[-2000:]
    done = apply_boundary_roles_to_regions(case, roles_path(msh))
    assert done == {"fluid": [], "insulation": ["insulation_wall"], "steel": []}
    run = run_foam("; ".join(f"checkMesh -case {case} -region {r}"
                             for r in ("fluid", "steel", "insulation")))
    assert run.returncode == 0 and run.stdout.count("Mesh OK.") == 3

    fluid, steel, insulation = (_types(case, r) for r in ("fluid", "steel", "insulation"))
    assert insulation["insulation_wall"] == "wall"
    assert fluid["fluid_to_steel"] == steel["steel_to_fluid"] == "mappedWall"
    assert steel["steel_to_insulation"] == insulation["insulation_to_steel"] == "mappedWall"
    for t, r in ((fluid, "fluid"), (steel, "steel"), (insulation, "insulation")):
        assert t[f"{r}_inlet"] == t[f"{r}_outlet"] == "patch"
