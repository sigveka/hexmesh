"""
Study runner (decision 0025, task 0042): study file, sampling, preflight,
mesh stage, manifest, topology key and aligned export.
"""

import csv
import dataclasses
import json
import time

import numpy as np
import pytest

from hexmesh import Assembly, Bend, PipeSpec, Straight
from hexmesh.study import (
    PreflightFailed, StudyError, canonical, load_study, mesh, preflight, run, status,
    topology_key, variant_hash, variants,
)
from hexmesh.study.__main__ import main
from hexmesh.study.manifest import export, read_mesh
from hexmesh.study.stages import variant_dir

TEMPLATE = '''
from hexmesh import Assembly, Bend, PipeSpec, Straight

def build(p):
    spec = PipeSpec(nang=4).core("fluid", radius=0.05, nrad=2)
    asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(p.get("length", 0.2), n_layers=p.get("n", 3)))
    asm.add(Bend(radius=p["radius"], angle=p["angle"], n_layers=p.get("n_bend", 6)))
    return asm
'''


def _study(tmp_path, name="study.json", **fields):
    (tmp_path / "bends.py").write_text(TEMPLATE)
    body = {"template": {"python": "bends:build"}, "output": "out"}
    body.update(fields)
    path = tmp_path / name
    path.write_text(json.dumps(body))
    return load_study(path)


GRID = {"grid": {"radius": [0.15, 0.2, 0.3], "angle": [45, 60, 90]}}


@pytest.fixture(scope="module")
def grid(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("grid")
    study = _study(tmp, sampling=GRID, jobs=3)
    t0 = time.perf_counter()
    checked = run(study, "preflight")
    preflight_time = time.perf_counter() - t0
    rows = run(study)
    return study, checked, rows, preflight_time


class TestGrid:
    def test_preflight_is_fast_and_meshes_nothing(self, grid):
        study, checked, _, seconds = grid
        assert seconds < 2.0
        assert [r["status"] for r in checked] == ["checked"] * 9

    def test_meshed_equals_predicted(self, grid):
        _, _, rows, _ = grid
        assert [r["status"] for r in rows] == ["meshed"] * 9
        for r in rows:
            assert r["cells_meshed"] == r["cells"] == 432 and r["all_hex"]
            assert r["min_sj_fitting"] and r["min_sj"] > 0.5 and r["min_sicn"] > 0

    def test_one_topology_key_and_aligned_export(self, grid):
        study, _, rows, _ = grid
        keys = {r["topology"] for r in rows}
        assert len(keys) == 1
        (key, path), = export(study).items()
        data = np.load(path)
        assert list(data["variants"]) == [r["hash"] for r in rows]
        assert data["coords"].shape[0] == 9
        for i, r in enumerate(rows):
            tags, x, hexes = read_mesh(variant_dir(study, r["hash"]) / "mesh.msh")
            assert np.array_equal(hexes, data["hexes"])
            assert np.array_equal(tags, data["node_tags"])
            np.testing.assert_array_equal(x, data["coords"][i])
        assert not np.allclose(data["coords"][0], data["coords"][-1])

    def test_manifest(self, grid):
        study, _, rows, _ = grid
        with open(study.output / "study.csv") as f:
            table = list(csv.DictReader(f))
        assert [t["hash"] for t in table] == [r["hash"] for r in rows]
        assert table[0]["radius"] == "0.15" and table[0]["angle"] == "45"
        assert {t["topology"] for t in table} == {rows[0]["topology"]}
        data = json.loads((study.output / "study.json").read_text())
        assert data["study"]["sampling"] == GRID
        assert set(data["versions"]) == {"hexmesh", "gmsh", "python"}
        assert status(study) == {"meshed": 9}

    def test_rerun_meshes_nothing_and_adding_a_row_meshes_it(self, grid, tmp_path):
        study, _, rows, _ = grid
        mtimes = {r["hash"]: (variant_dir(study, r["hash"]) / "mesh.msh").stat().st_mtime_ns
                  for r in rows}
        again = run(study)
        assert [(r["hash"], r["topology"], r["cells"]) for r in again] == \
               [(r["hash"], r["topology"], r["cells"]) for r in rows]
        assert all((variant_dir(study, h) / "mesh.msh").stat().st_mtime_ns == t
                   for h, t in mtimes.items())
        # the same study as a table, plus one row
        table = [r["params"] for r in rows] + [{"radius": 0.4, "angle": 30}]
        bigger = dataclasses.replace(study, sampling={"table": {"rows": table}})
        rows2 = preflight(bigger)
        assert mesh(bigger, rows2) == [variant_hash({"radius": 0.4, "angle": 30})]


class TestTopologyKey:
    def test_equal_keys_iff_identical_connectivity(self, tmp_path):
        rows = [{"radius": 0.2, "angle": 90}, {"radius": 0.3, "angle": 45, "length": 0.5},
                {"radius": 0.2, "angle": 90, "n": 4}, {"radius": 0.25, "angle": 60, "n": 4},
                {"radius": 0.2, "angle": 90, "n_bend": 8}]
        study = _study(tmp_path, sampling={"table": {"rows": rows}}, jobs=3)
        out = run(study)
        meshes = [read_mesh(variant_dir(study, r["hash"]) / "mesh.msh") for r in out]
        for a, ma in zip(out, meshes):
            for b, mb in zip(out, meshes):
                same = (np.array_equal(ma[0], mb[0]) and ma[2].shape == mb[2].shape
                        and np.array_equal(ma[2], mb[2]))
                assert (a["topology"] == b["topology"]) == same, (a["params"], b["params"])
        assert len({r["topology"] for r in out}) == 3

    def test_key_ignores_geometry_and_grading(self):
        def asm(radius, angle, mprg=1.0):
            spec = PipeSpec(nang=4).core("fluid", radius=radius, nrad=2, mprg=mprg)
            a = Assembly(spec)
            a.add(Bend(radius=0.3, angle=angle, n_layers=6))
            return a
        assert topology_key(asm(0.05, 90)) == topology_key(asm(0.07, 30.0)) \
            == topology_key(asm(0.05, 90, mprg=1.2))
        a = Assembly(PipeSpec(nang=8).core("fluid", radius=0.05, nrad=2))
        a.add(Bend(radius=0.3, angle=90, n_layers=6))
        assert topology_key(a) != topology_key(asm(0.05, 90))


class TestPreflight:
    def test_a_failing_variant_stops_before_meshing(self, tmp_path):
        rows = [{"radius": 0.2, "angle": 90}, {"radius": 0.04, "angle": 90}]
        study = _study(tmp_path, sampling={"table": {"rows": rows}})
        with pytest.raises(PreflightFailed) as e:
            run(study)
        bad = variant_hash(rows[1])
        assert bad in str(e.value) and "fitting #1 Bend" in str(e.value)
        assert "tighter than the pipe outer radius" in str(e.value)
        assert not (study.output / "variants").exists()
        assert status(study) == {"checked": 1, "preflight_failed": 1}

    def test_keep_going_meshes_the_rest(self, tmp_path):
        rows = [{"radius": 0.2, "angle": 90}, {"radius": 0.04, "angle": 90}]
        study = _study(tmp_path, sampling={"table": {"rows": rows}})
        out = run(study, keep_going=True)
        assert [r["status"] for r in out] == ["meshed", "preflight_failed"]

    def test_budgets(self, tmp_path):
        study = _study(tmp_path, sampling=GRID, budget={"max_cells_variant": 400})
        rows = preflight(study)
        assert all(r["status"] == "preflight_failed" and "budget of 400" in r["error"]
                   for r in rows)
        study = _study(tmp_path, sampling=GRID, budget={"max_cells_total": 1000})
        with pytest.raises(StudyError, match="3888 cells, over max_cells_total 1000"):
            preflight(study)

    def test_quality_warnings_are_recorded(self, tmp_path):
        (tmp_path / "block.py").write_text('''
from hexmesh import Assembly, PipeSpec, Straight
from hexmesh.core.shape import CircleShape, RectShape

def build(p):
    spec = (PipeSpec(nang=4).core("core", CircleShape(0.1, 4), nrad=3)
            .shell("block", outer=RectShape(p["w"], 0.13, 4, 4), nrad=3))
    asm = Assembly(spec)
    asm.add(Straight(0.3, n_layers=2))
    return asm
''')
        (tmp_path / "s.json").write_text(json.dumps({
            "template": {"python": "block:build"},
            "sampling": {"grid": {"w": [0.15, 0.26]}}}))
        rows = preflight(load_study(tmp_path / "s.json"))
        assert rows[0]["warnings"] == []
        assert rows[1]["status"] == "checked" and "OUTLINE_SJ_WARN" in rows[1]["warnings"][0]


class TestJsonTemplate:
    def _network(self, tmp_path):
        spec = PipeSpec(nang=4).core("fluid", radius=0.05, nrad=2)
        a = Assembly(spec)
        a.add(Straight(0.2, n_layers=3))
        a.add(Bend(radius=0.3, angle=90, n_layers=6))
        d = a.to_dict()
        d["edges"][1]["fitting"]["radius"] = "$radius"
        d["edges"][1]["fitting"]["angle"] = "$angle"
        (tmp_path / "net.json").write_text(json.dumps(d))

    def test_substitutes_whole_values(self, tmp_path):
        self._network(tmp_path)
        study = _study(tmp_path, template={"json": "net.json"},
                       sampling={"grid": {"radius": [0.2, 0.3]}}, parameters={"angle": 60})
        rows = preflight(study)
        assert [r["network"]["edges"][1]["fitting"]["radius"] for r in rows] == [0.2, 0.3]
        assert rows[0]["network"]["edges"][1]["fitting"]["angle"] == 60
        assert len({r["topology"] for r in rows}) == 1

    @pytest.mark.parametrize("params, message", [
        ({"radius": 0.2}, r"unknown placeholder\(s\): \$angle"),
        ({"radius": 0.2, "angle": 90, "roll": 5}, r"unused parameter\(s\): roll"),
    ])
    def test_placeholder_errors(self, tmp_path, params, message):
        self._network(tmp_path)
        study = _study(tmp_path, template={"json": "net.json"}, parameters=params)
        with pytest.raises(StudyError, match=message):
            preflight(study)


class TestJobs:
    def test_two_jobs_give_the_same_manifest(self, tmp_path):
        sampling = {"grid": {"radius": [0.15, 0.3], "angle": [45, 90]}}
        timing = ("preflight_time", "mesh_time")
        results = []
        for jobs in (1, 2):
            d = tmp_path / f"j{jobs}"
            d.mkdir()
            out = run(_study(d, sampling=sampling), jobs=jobs)
            results.append([{k: v for k, v in r.items() if k not in timing} for r in out])
        assert results[0] == results[1]


class TestDefinition:
    def test_hash_is_canonical(self):
        assert variant_hash({"a": 90, "b": 0.1}) == variant_hash({"b": 0.1, "a": 90.0})
        assert variant_hash({"a": 90}) != variant_hash({"a": 90.5})
        assert variant_hash({"a": np.float64(0.1)}) == variant_hash({"a": 0.1})
        assert canonical({"x": [1.0, 2.5]}) == {"x": [1, 2.5]}

    def test_lhs_is_seeded_and_stratified(self, tmp_path):
        lhs = {"lhs": {"ranges": {"radius": [0.2, 0.4], "angle": [30, 90]}, "n": 8, "seed": 3}}
        a = variants(_study(tmp_path, sampling=lhs))
        b = variants(_study(tmp_path, sampling=lhs))
        assert a == b and len(a) == 8
        strata = sorted(int((r["radius"] - 0.2) / 0.2 * 8) for r in a)
        assert strata == list(range(8))

    def test_csv_table_and_fixed_parameters(self, tmp_path):
        (tmp_path / "rows.csv").write_text("radius,angle,label\n0.2,90,a\n0.3,45.5,b\n")
        study = _study(tmp_path, sampling={"table": {"csv": "rows.csv"}},
                       parameters={"n": 4, "radius": 9})
        assert variants(study) == [{"n": 4, "radius": 0.2, "angle": 90, "label": "a"},
                                   {"n": 4, "radius": 0.3, "angle": 45.5, "label": "b"}]

    @pytest.mark.parametrize("body, message", [
        ({"template": {"python": "bends:build"}, "jobz": 2}, "unknown study key"),
        ({"template": {"yaml": "x"}}, "template must be"),
        ({"template": {"python": "bends:build"}, "format": "vtk"}, "format must be"),
        ({"template": {"python": "bends:build"}, "budget": {"cells": 1}}, "unknown budget"),
    ])
    def test_bad_study_files(self, tmp_path, body, message):
        (tmp_path / "s.json").write_text(json.dumps(body))
        with pytest.raises(StudyError, match=message):
            load_study(tmp_path / "s.json")

    def test_duplicate_variants_rejected(self, tmp_path):
        study = _study(tmp_path, sampling={"table": {"rows": [{"radius": 0.2, "angle": 90},
                                                              {"angle": 90.0, "radius": 0.2}]}})
        with pytest.raises(StudyError, match="same parameters"):
            preflight(study)


class TestCli:
    def test_run_status_export(self, tmp_path, capsys):
        _study(tmp_path, sampling={"table": {"rows": [{"radius": 0.2, "angle": 90}]}},
               format="openfoam")
        path = str(tmp_path / "study.json")
        assert main(["run", path, "--stage", "preflight"]) == 0
        assert main(["status", path]) == 0
        assert "checked: 1" in capsys.readouterr().out
        assert main(["run", path]) == 0
        h = variant_hash({"radius": 0.2, "angle": 90})
        assert (tmp_path / "out/variants" / h / "mesh.roles.json").exists()
        assert main(["export", path]) == 0
        assert ".npz" in capsys.readouterr().out

    def test_preflight_failure_exit_code(self, tmp_path, capsys):
        _study(tmp_path, sampling={"table": {"rows": [{"radius": 0.04, "angle": 90}]}})
        assert main(["run", str(tmp_path / "study.json")]) == 2
        assert "fitting #1 Bend" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Case and run stages (task 0043)
# ---------------------------------------------------------------------------

PIPE = '''
from hexmesh import Assembly, PipeSpec, Straight

def build(p):
    spec = PipeSpec(nang=4).core("fluid", radius=0.01, nrad=2)
    asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.2, n_layers=p.get("n", 20)))
    return asm
'''

POST = '''
import numpy as np
from hexmesh.study import openfoam as of

def dp(case, params):
    """Mean p of the first axial cell layer minus that of the last."""
    mesh = case / "constant/polyMesh"
    pts, faces = of.read_points(mesh / "points"), of.read_faces(mesh / "faces")
    owner, neigh = of.read_labels(mesh / "owner"), of.read_labels(mesh / "neighbour")
    p = of.read_internal(of.latest_time(case) / "p", 1)
    fc, sf = of.face_geometry(pts, faces)
    cc, vol = of.cell_geometry(fc, sf, owner, neigh, len(p))
    x = cc[:, 0]
    first, last = x < x.min() + 1e-9, x > x.max() - 1e-9
    mean = lambda m: float((p[m] * vol[m]).sum() / vol[m].sum())
    return {"dp": mean(first) - mean(last), "dx": float(x.max() - x.min())}
'''


def _template(root, header):
    """A laminar simpleFoam case with $U and $nu placeholders, no mesh."""
    files = {
        "system/controlDict": header("dictionary", "controlDict", "system") + (
            "application simpleFoam; startFrom startTime; startTime 0; stopAt endTime;\n"
            "endTime 3000; deltaT 1; writeControl timeStep; writeInterval 3000;\n"
            "writeFormat ascii; writePrecision 12; writeCompression off;\n"
            "timeFormat general; runTimeModifiable false;\n"),
        "system/fvSchemes": header("dictionary", "fvSchemes", "system") + (
            "ddtSchemes { default steadyState; }\ngradSchemes { default Gauss linear; }\n"
            "divSchemes { default none; div(phi,U) bounded Gauss linear;\n"
            "  div((nuEff*dev2(T(grad(U))))) Gauss linear; }\n"
            "laplacianSchemes { default Gauss linear corrected; }\n"
            "interpolationSchemes { default linear; }\nsnGradSchemes { default corrected; }\n"),
        "system/fvSolution": header("dictionary", "fvSolution", "system") + (
            "solvers { p { solver GAMG; smoother GaussSeidel; tolerance 1e-9; relTol 0.05; }\n"
            "  U { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-10; relTol 0.1; } }\n"
            "SIMPLE { nNonOrthogonalCorrectors 0; residualControl { p 1e-6; U 1e-7; } }\n"
            "relaxationFactors { fields { p 0.3; } equations { U 0.7; } }\n"),
        "constant/transportProperties": header("dictionary", "transportProperties", "constant")
        + "transportModel Newtonian;\nnu $nu;\n",
        "constant/turbulenceProperties": header("dictionary", "turbulenceProperties",
                                                "constant") + "simulationType laminar;\n",
        "0/U": header("volVectorField", "U", "0") + (
            "dimensions [0 1 -1 0 0 0 0];\ninternalField uniform (0 0 0);\n"
            "inletValue uniform ($U 0 0);\n"
            "boundaryField {\n fluid_inlet { type fixedValue; value $inletValue; }\n"
            " fluid_outlet { type zeroGradient; }\n fluid_wall { type noSlip; } }\n"),
        "0/p": header("volScalarField", "p", "0") + (
            "dimensions [0 2 -2 0 0 0 0];\ninternalField uniform 0;\n"
            "boundaryField {\n fluid_inlet { type zeroGradient; }\n"
            " fluid_outlet { type fixedValue; value uniform 0; }\n"
            " fluid_wall { type zeroGradient; } }\n"),
    }
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)


def _pipe_study(tmp_path, rows, **fields):
    from hexmesh.study.openfoam import header
    (tmp_path / "pipe.py").write_text(PIPE)
    (tmp_path / "post.py").write_text(POST)
    _template(tmp_path / "case", header)
    body = {"template": {"python": "pipe:build"}, "output": "out", "format": "openfoam",
            "sampling": {"table": {"rows": rows}},
            "case": {"template": "case"},
            "run": {"command": "simpleFoam > log.simpleFoam 2>&1", "post": "post:dp",
                    "cores_per_job": 1}}
    body.update(fields)
    (tmp_path / "study.json").write_text(json.dumps(body))
    return load_study(tmp_path / "study.json")


class TestCaseTemplates:
    def test_substitution_rules(self, tmp_path):
        from hexmesh.study.openfoam import substitute_case
        (tmp_path / "0").mkdir()
        (tmp_path / "0/U").write_text(
            "inletValue uniform ($U 0 0);\nin { value $inletValue; }\n"
            "a $Umax; cost $$5; path $FOAM_CASE;\n")
        with pytest.raises(ValueError, match=r"0/U: unknown placeholder\(s\) \$Umax"):
            substitute_case(tmp_path, {"U": 0.5})
        assert substitute_case(tmp_path, {"U": 0.5, "Umax": 2}) == ["0/U"]
        assert (tmp_path / "0/U").read_text() == (
            "inletValue uniform (0.5 0 0);\nin { value $inletValue; }\n"
            "a 2; cost $5; path $FOAM_CASE;\n")

    def test_unknown_placeholder_fails_the_case_naming_the_file(self, tmp_path):
        study = _pipe_study(tmp_path, [{"U": 0.005}], run=None)   # $nu missing
        rows = run(study, "case")
        assert rows[0]["status"] == "case_failed"
        assert "constant/transportProperties: unknown placeholder(s) $nu" in rows[0]["error"]

    @pytest.mark.parametrize("fields, message", [
        ({"format": "msh"}, 'a case stage needs "format": "openfoam"'),
        ({"case": None}, "a run stage needs a case stage"),
        ({"run": {"command": "x", "cores": 2}}, "unknown run key"),
        ({"run": {"command": "x", "cores_per_job": 0}}, "cores_per_job must be"),
    ])
    def test_bad_blocks(self, tmp_path, fields, message):
        with pytest.raises(StudyError, match=message):
            _pipe_study(tmp_path, [{"U": 1, "nu": 1}], **fields)

    def test_jobs_times_cores_within_the_machine(self, tmp_path):
        import os
        from hexmesh.study import run_stage
        study = _pipe_study(tmp_path, [{"U": 1, "nu": 1}])
        study.run["cores_per_job"] = (os.cpu_count() or 1) + 1
        rows = [{"hash": "x", "status": "case_ready", "params": {}, "network": {}}]
        with pytest.raises(StudyError, match="exceeds the"):
            run_stage(study, rows, jobs=1, force=True)


def test_other_runs_sees_a_detached_process():
    """A process that isn't ours (reparented) and looks like pytest."""
    import os
    import signal
    import subprocess
    import sys
    from hexmesh.study import other_runs
    out = subprocess.run(
        ["bash", "-c", f"{sys.executable} -c 'import time; time.sleep(30)' "
                       f"pytest-marker-0043 >/dev/null 2>&1 & echo $!"],
        capture_output=True, text=True)
    pid = int(out.stdout.strip())
    try:
        for _ in range(50):
            if any("pytest-marker-0043" in line for line in other_runs()):
                break
            time.sleep(0.05)
        assert any(line.startswith(f"{pid}:") for line in other_runs())
        assert not any(line.startswith(f"{os.getpid()}:") for line in other_runs())
    finally:
        os.kill(pid, signal.SIGTERM)


@pytest.mark.openfoam
def test_pipe_study_case_and_run(tmp_path):
    """Two laminar pipes and a broken one through case and run: Δp from the
    post-processing function, failures recorded, re-run skips."""
    from hexmesh.study.openfoam import have_openfoam
    if not have_openfoam():
        pytest.skip("OpenFOAM not available")
    nu = 1e-6
    # Re 10 and 20: the entrance length (≈ 0.06 Re D ≈ 1 cm) is short
    rows = [{"U": 0.0005, "nu": nu}, {"U": 0.001, "nu": nu}, {"U": 0.001, "nu": "broken"}]
    study = _pipe_study(tmp_path, rows, jobs=2)
    out = run(study, force=True)
    assert [r["status"] for r in out] == ["done", "done", "run_failed"]
    for r in out[:2]:
        U = r["params"]["U"]
        exact = 32 * nu * U * r["result"]["dx"] / 0.02 ** 2
        assert r["result"]["dp"] == pytest.approx(exact, rel=0.1)
        assert r["run_exit"] == 0 and r["run_time"] > 0
    assert out[1]["result"]["dp"] == pytest.approx(2 * out[0]["result"]["dp"], rel=0.02)
    assert out[2]["run_exit"] != 0
    with open(study.output / "study.csv") as f:
        table = list(csv.DictReader(f))
    assert float(table[0]["result.dp"]) == pytest.approx(out[0]["result"]["dp"])
    logs = [(variant_dir(study, r["hash"]) / "run.json").stat().st_mtime_ns for r in out]
    again = run(study, force=True)
    assert [r["status"] for r in again] == ["done", "done", "run_failed"]
    assert [(variant_dir(study, r["hash"]) / "run.json").stat().st_mtime_ns
            for r in again] == logs
