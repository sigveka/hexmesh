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
