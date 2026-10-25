"""
OpenFOAM-compatible output (docs/tasks/0005).

The CI tests parse the written ``.msh``; the last test runs OpenFOAM
(``gmshToFoam``, ``splitMeshRegions``, ``checkMesh``) and is skipped where
it is not installed.
"""

import pathlib
import re
import shutil
import subprocess

import gmsh
import pytest

from hexmesh.assembly import Assembly, Straight
from hexmesh.core.spec import PipeSpec

OPENFOAM_RC = pathlib.Path("/usr/share/openfoam/etc/bashrc")


def _insulated():
    spec = (PipeSpec(nang=4).core("fluid", radius=0.1, nrad=3)
            .shell("steel", dR=0.01, nrad=1).shell("insulation", dR=0.03, nrad=2))
    asm = Assembly(spec)
    asm.add(Straight(0.3, n_layers=4))
    return asm


def _mesh_format(path):
    lines = pathlib.Path(path).read_text().splitlines()
    assert lines[0] == "$MeshFormat"
    version, binary, size = lines[1].split()
    return version, binary, size


def _physical_names(path):
    text = pathlib.Path(path).read_text()
    block = text.split("$PhysicalNames")[1].split("$EndPhysicalNames")[0]
    return sorted(re.findall(r'"([^"]+)"', block))


def test_header_is_msh22_ascii(gmsh_session, tmp_path):
    out = tmp_path / "pipe.msh"
    _insulated().write_openfoam(out)
    assert _mesh_format(out) == ("2.2", "0", "8")


def test_options_restored(gmsh_session, tmp_path):
    gmsh.option.setNumber("Mesh.MshFileVersion", 4.1)
    gmsh.option.setNumber("Mesh.Binary", 1)
    _insulated().write_openfoam(tmp_path / "pipe.msh")
    assert gmsh.option.getNumber("Mesh.MshFileVersion") == 4.1
    assert gmsh.option.getNumber("Mesh.Binary") == 1


def test_interface_groups_left_out_of_file_only(gmsh_session, tmp_path):
    out = tmp_path / "pipe.msh"
    asm = _insulated()
    asm.write_openfoam(out)
    names = _physical_names(out)
    assert names == sorted([
        "fluid", "steel", "insulation",
        "fluid_inlet", "steel_inlet", "insulation_inlet",
        "fluid_outlet", "steel_outlet", "insulation_outlet",
        "insulation_wall",
    ])
    in_model = {gmsh.model.getPhysicalName(d, t) for d, t in gmsh.model.getPhysicalGroups()}
    assert {"fluid_to_steel", "steel_to_insulation"} <= in_model


def test_interface_groups_kept_on_request(gmsh_session, tmp_path):
    out = tmp_path / "pipe.msh"
    _insulated().write_openfoam(out, interfaces=True)
    assert {"fluid_to_steel", "steel_to_insulation"} <= set(_physical_names(out))


def test_rejects_other_extensions(gmsh_session, tmp_path):
    with pytest.raises(ValueError, match=".msh"):
        _insulated().write_openfoam(tmp_path / "pipe.vtk")


@pytest.mark.skipif(not OPENFOAM_RC.exists() or shutil.which("bash") is None,
                    reason="OpenFOAM not installed")
def test_openfoam_cht_split(gmsh_session, tmp_path):
    """gmshToFoam → splitMeshRegions -cellZones gives mappedWall pairs."""
    msh = tmp_path / "pipe.msh"
    _insulated().write_openfoam(msh)
    case = tmp_path / "case"
    (case / "system").mkdir(parents=True)
    (case / "system" / "controlDict").write_text(
        "FoamFile { version 2.0; format ascii; class dictionary; object controlDict; }\n"
        "application none; startFrom startTime; startTime 0; stopAt endTime;\n"
        "endTime 1; deltaT 1; writeControl timeStep; writeInterval 1;\n")
    header = "FoamFile { version 2.0; format ascii; class dictionary; object %s; }\n"
    (case / "system" / "fvSchemes").write_text(
        header % "fvSchemes" +
        "ddtSchemes { default steadyState; } gradSchemes { default Gauss linear; }\n"
        "divSchemes { default none; } laplacianSchemes { default Gauss linear corrected; }\n"
        "interpolationSchemes { default linear; } snGradSchemes { default corrected; }\n")
    (case / "system" / "fvSolution").write_text(header % "fvSolution")
    script = (f"source {OPENFOAM_RC} >/dev/null 2>&1; set -e; "
              f"gmshToFoam -case {case} {msh}; "
              f"splitMeshRegions -case {case} -cellZones -overwrite; "
              f"for r in fluid steel insulation; do checkMesh -case {case} -region $r; done")
    run = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    assert run.stdout.count("Mesh OK.") == 3

    def patches(region):
        text = (case / "constant" / region / "polyMesh" / "boundary").read_text()
        return {m[0]: (m[1], int(m[2])) for m in re.findall(
            r"(\w+)\s*\{\s*type\s+(\w+);[^}]*?nFaces\s+(\d+);", text)}

    fluid, steel, insulation = (patches(r) for r in ("fluid", "steel", "insulation"))
    n = fluid["fluid_to_steel"][1]
    assert fluid["fluid_to_steel"] == ("mappedWall", n)
    assert steel["steel_to_fluid"] == ("mappedWall", n)
    assert steel["steel_to_insulation"][0] == "mappedWall"
    assert insulation["insulation_to_steel"] == steel["steel_to_insulation"]
    assert insulation["insulation_wall"][0] == "patch"
