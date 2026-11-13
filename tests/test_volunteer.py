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
Volunteer runs (decision 0044; task 0119): the runners, the cards and
VOLUNTEERS.md, the mesh hash, the job script, and ``check`` accepting a
good contribution and rejecting tampered ones.  No OpenFOAM: the check's
mesh hash is given, not meshed.
"""

import copy
import importlib.util
import json
import os
import pathlib
import re
import shutil
import shlex
import subprocess
import sys

import pytest

from hexmesh.study import openfoam as of

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vol = _load("volunteer", "validation/volunteer.py")


@pytest.fixture
def restore_runner():
    before = of.runner()
    yield
    of.set_runner(before)


# --- runners ----------------------------------------------------------------------

def test_path_runner_runs_the_command_as_it_is(restore_runner):
    of.set_runner("path")
    assert of._argv("checkMesh", pathlib.Path("/tmp")) == ["bash", "-c", "checkMesh"]


def test_apptainer_runner_mounts_as_docker_does(restore_runner, tmp_path):
    of.set_runner("apptainer:docker://opencfd/openfoam-default:2406")
    case, mesh = tmp_path / "case", tmp_path / "mesh"
    argv = of._argv(f"gmshToFoam {mesh / 'x.msh'}", case, mounts=[mesh])
    assert argv[:3] == ["apptainer", "exec", "--cleanenv"]
    binds = [argv[i + 1] for i, a in enumerate(argv) if a == "--bind"]
    assert binds == [f"{case}:/work/0", f"{mesh}:/work/1"]
    assert argv[argv.index("--pwd") + 1] == "/work/0"
    assert "docker://opencfd/openfoam-default:2406" in argv
    assert argv[-1].endswith("gmshToFoam /work/1/x.msh") and "bashrc" in argv[-1]


def test_only_docker_names_containers(restore_runner, tmp_path, monkeypatch):
    """``foam`` stops a named Docker container on interrupt; other
    runners' commands are its children."""
    seen = []
    monkeypatch.setattr(of, "_argv", lambda cmd, cwd, mounts=(), name=None:
                        seen.append(name) or ["true"])
    for spec in ("path", "apptainer:x.sif", of.V2406):
        of.set_runner(spec)
        of.foam("true", tmp_path, "log.x")
    assert seen[0] is None and seen[1] is None and seen[2].startswith("hexmesh-")


@pytest.mark.parametrize("bad", ["apptainer:", "path:x", "singularity:x", "Docker:x"])
def test_bad_new_runners_rejected(restore_runner, bad):
    with pytest.raises(ValueError, match="apptainer:<image>"):
        of.set_runner(bad)


def test_native_bashrc_is_configurable(tmp_path):
    rc = tmp_path / "bashrc"
    out = subprocess.run(
        [sys.executable, "-c", "from hexmesh.study import openfoam as of; print(of.OPENFOAM_RC)"],
        capture_output=True, text=True, cwd=ROOT,
        env={**os.environ, "HEXMESH_OPENFOAM_RC": str(rc), "PYTHONPATH": str(ROOT)})
    assert out.stdout.strip() == str(rc)


@pytest.mark.parametrize("got, ok", [("v2406", True), ("2406", True), ("v2312", False),
                                     ("", False)])
def test_require_version(monkeypatch, got, ok):
    monkeypatch.setattr(of, "openfoam_version", lambda: got)
    if ok:
        assert of.require_version("v2406") == got
    else:
        with pytest.raises(ValueError, match="needs OpenFOAM v2406") as e:
            of.require_version("v2406")
        assert e.value.code == "openfoam_version_mismatch"
    assert of.require_version("v2406", allow_other=True) == got


# --- cards and VOLUNTEERS.md ------------------------------------------------------------

def test_every_requirement_says_where_it_comes_from():
    cards = vol.cards()
    assert "helical_pipe" in cards
    for case, card in cards.items():
        drv = vol.driver(case)
        for name, level in card["levels"].items():
            drv._parse(name)                                   # a level the driver knows
            assert {"cores", "wall_time", "peak_memory", "peak_disk"} <= set(level["requirements"])
            for key, req in level["requirements"].items():
                assert req["basis"] in vol.BASES, (case, name, key)
                assert isinstance(req["value"], (int, float)) and req["value"] > 0, (case, key)
                assert req["how"] and "MEASURE" not in req["how"], (case, key)


def test_volunteers_md_is_current():
    assert vol.DOC.read_text(encoding="utf-8") == vol.render(), (
        "validation/VOLUNTEERS.md is stale: run python3 -m validation.volunteer docs")


def test_volunteer_text_has_no_task_numbers():
    assert not re.search(r"\b(task|decision) \d{4}\b", vol.render(), re.I)


@pytest.mark.posix_only
def test_job_script_is_bash_with_slurm_directives(tmp_path):
    req = vol.card("helical_pipe")["levels"]["re3000_n24"]["requirements"]
    text = vol.job_script("helical_pipe", "re3000_n24", tmp_path, req, 4)
    assert "#SBATCH --ntasks=4" in text and "#SBATCH --time=" in text and "#SBATCH --mem=" in text
    assert text.rstrip().endswith(f"validation.volunteer run {shlex.quote(str(tmp_path))}")
    path = tmp_path / "job.sh"
    path.write_text(text, encoding="utf-8", newline="\n")
    assert subprocess.run(["bash", "-n", str(path)]).returncode == 0



# --- the command line, for people (task 0160) ------------------------------------------

@pytest.fixture
def no_runner(monkeypatch):
    """A runner is never looked for: a name mistake is caught before it."""
    def touched(*a, **k):
        raise AssertionError("the runner was touched")
    monkeypatch.setattr(vol, "pick_runner", touched)
    monkeypatch.setattr(vol, "use_runner", touched)


def _cli(capsys, *argv) -> tuple[int, str]:
    code = vol.main([str(a) for a in argv])
    out = capsys.readouterr()
    return code, out.err.strip()


@pytest.mark.parametrize("argv, says", [
    (("prepare", "helical_pipe", "re3000", "--dir", "{tmp}/run"),
     "unknown level 're3000' for helical_pipe; did you mean 're3000_n24'? Levels: re3000_n24."),
    (("prepare", "helical", "re3000_n24", "--dir", "{tmp}/run"),
     "unknown case 'helical'; did you mean 'helical_pipe'?"),
    (("info", "helical_pipe", "re3000"), "did you mean 're3000_n24'?"),
    (("run", "helical_pipe", "re3000_n24"), "run takes the directory `prepare --dir` made"),
    (("collect", "helical_pipe"), "collect takes the directory `prepare --dir` made"),
    (("run", "{tmp}/nothere"), "isn't a prepared run directory"),
    (("check", "{tmp}/nothere.contrib.json"), "no file"),
])
def test_a_mistake_is_one_line_naming_the_fix(capsys, tmp_path, no_runner, argv, says):
    code, err = _cli(capsys, *(a.format(tmp=tmp_path) for a in argv))
    assert code == 2 and says in err, err
    assert len(err.splitlines()) == 1 and "Traceback" not in err
    assert not (tmp_path / "run").exists()


def test_a_runner_error_is_one_line(capsys, tmp_path, monkeypatch):
    """The names are right, OpenFOAM isn't: the StudyError is one line."""
    from hexmesh.study.definition import StudyError
    def wrong_version(*a, **k):
        raise StudyError("runner 'path' has no OpenFOAM; this needs OpenFOAM v2406",
                         code="openfoam_version_mismatch", hint="pick a runner with OpenFOAM v2406")
    monkeypatch.setattr(vol, "pick_runner", lambda c, given: "path")
    monkeypatch.setattr(vol, "use_runner", wrong_version)
    code, err = _cli(capsys, "prepare", "helical_pipe", "re3000_n24", "--dir", tmp_path / "run")
    assert code == 2 and len(err.splitlines()) == 1 and "Traceback" not in err
    assert "needs OpenFOAM v2406; pick a runner" in err


def test_a_level_the_driver_builds_but_the_card_does_not_offer_is_allowed(monkeypatch):
    """A stored level (re1800_n12) still prepares, with no requirements."""
    assert vol.offered_level("helical_pipe", "re1800_n12") is None
    assert vol.offered_level("helical_pipe", "re3000_n24")["requirements"]["cores"]["value"] == 4


def test_list_and_info_fit_a_terminal(capsys):
    for argv in (("list",), ("info", "helical_pipe")):
        assert vol.main(list(argv)) == 0
        out = capsys.readouterr().out
        assert out and max(map(len, out.splitlines())) <= vol.WIDTH, argv
        assert "|---" not in out and "$" not in out
    assert vol.main(["list"]) == 0
    out = capsys.readouterr().out
    assert ("python3 -m validation.volunteer prepare helical_pipe re3000_n24 --dir run/" in out
            and "git clone --branch volunteer-helical-" in out)


def test_help_shows_the_commands(capsys):
    with pytest.raises(SystemExit) as e:
        vol.main(["-h"])
    out = capsys.readouterr().out
    assert e.value.code == 0 and "prepare <case> <level> --dir run/" in out
    assert "sbatch run/job.sh" in out and "decision" not in out
    with pytest.raises(SystemExit):
        vol.main(["run", "-h"])
    assert "the directory `prepare --dir` made; job.sh calls this" in capsys.readouterr().out


def test_card_note_and_five_commands_say_the_same():
    """One instruction for the version: git clone --branch <tag> (task 0160)."""
    c = vol.card("helical_pipe")
    assert "git clone --branch" in c["hexmesh"]["note"] and "checkout" not in c["hexmesh"]["note"]
    assert "git clone --branch <tag>" in vol.render()

# --- the mesh hash -------------------------------------------------------------------

MSH = ("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n{comments}$PhysicalNames\n1\n3 1 \"fluid\"\n"
       "$EndPhysicalNames\n$Nodes\n2\n1 0 0 {z}\n2 0.1 -0 0\n$EndNodes\n$Elements\n1\n"
       "1 15 2 1 1 1\n$EndElements\n")
COMMENTS = "$Comments\ngenerated by hexmesh {v} (gmsh {g})\n$EndComments\n"


def test_mesh_hash_ignores_comments_line_endings_and_last_digits(tmp_path):
    """gmsh 4.15.2 writes a few coordinates one unit in the last place
    away from 4.12.1's: the same mesh."""
    a, b, c, d, e = (tmp_path / f"{x}.msh" for x in "abcde")
    a.write_text(MSH.format(comments=COMMENTS.format(v="0.5.0", g="4.12.1"), z="0.0612397775904346"),
                 encoding="utf-8", newline="\n")
    b.write_text(MSH.format(comments=COMMENTS.format(v="0.6.0", g="4.15.2"),
                            z="0.06123977759043459"), encoding="utf-8",
                 newline="\r\n")
    c.write_text(MSH.format(comments="", z="0.0612397775904346"), encoding="utf-8", newline="\n")
    d.write_text(MSH.format(comments="", z="0.0612397776"), encoding="utf-8", newline="\n")
    assert vol.mesh_hash(a) == vol.mesh_hash(b) == vol.mesh_hash(c) != vol.mesh_hash(d)
    e.write_text(a.read_text(encoding="utf-8").replace("1 15 2 1 1 1", "1 15 2 1 1 2"),
                 encoding="utf-8", newline="\n")
    assert vol.mesh_hash(e) != vol.mesh_hash(a)                   # elements count


# --- check ----------------------------------------------------------------------------

jsonschema = pytest.importorskip("jsonschema")
HASH = "ab" * 32
LEVEL = "re1800_n12"


@pytest.fixture
def stored_copy(tmp_path):
    path = tmp_path / "results.json"
    shutil.copy(ROOT / "validation/helical_pipe/results.json", path)
    return path


def _contribution(results_path) -> dict:
    """A contribution carrying the stored level, as a volunteer's would."""
    level = next(lv for lv in json.loads(results_path.read_text(encoding="utf-8"))["levels"]
                 if lv["name"] == LEVEL)
    values = {k: v for k, v in level.items() if k not in ("name", "precision", "environment")}
    return {"format": vol.CONTRIB_FORMAT, "version": 1, "case": "helical_pipe", "level": LEVEL,
            "results": values, "extra": {},
            "environment": {**level["environment"], "date": "2026-11-10"},
            "mesh": {"sha256": HASH, "method": vol.HASH_METHOD,
                     "check": {"mesh_ok": True, "cells_foam": values["cells"]}},
            "run": {"cores": 4, "runs": 1, "wall_s": 600.0, "peak_memory_gb": 1.2,
                    "peak_memory_how": "test", "allow_version": False},
            "log_tail": ["End"], "contributor": {"name": "A. Volunteer"}}


def _check(tmp_path, contrib, results, **kw):
    path = tmp_path / "x.contrib.json"
    path.write_text(json.dumps(contrib), encoding="utf-8")
    return vol.check(path, results=results, hasher=lambda case, level: HASH, **kw)


def test_a_good_contribution_is_accepted_and_merged(tmp_path, stored_copy):
    contrib = _contribution(stored_copy)
    ok, lines = _check(tmp_path, contrib, stored_copy, merge=True)
    assert ok, lines
    assert "mesh hash matches" in "\n".join(lines) and lines[-1].startswith("merged into")
    merged = next(lv for lv in json.loads(stored_copy.read_text(encoding="utf-8"))["levels"]
                  if lv["name"] == LEVEL)
    assert merged["f"] == contrib["results"]["f"]
    assert merged["environment"]["contributed"]["name"] == "A. Volunteer"


def test_a_changed_number_is_rejected(tmp_path, stored_copy):
    contrib = _contribution(stored_copy)
    contrib["results"]["f"] *= 0.97                    # three per cent closer to Ito
    ok, lines = _check(tmp_path, contrib, stored_copy)
    assert not ok and any("results: f is" in x and "own numbers give" in x for x in lines)


def test_a_wrong_mesh_hash_is_rejected(tmp_path, stored_copy):
    contrib = _contribution(stored_copy)
    contrib["mesh"]["sha256"] = "cd" * 32
    ok, lines = _check(tmp_path, contrib, stored_copy)
    assert not ok and any("differs from the mesh made here" in x for x in lines)


@pytest.mark.parametrize("path", [("environment",), ("mesh", "sha256"), ("results", "steps")])
def test_a_missing_field_is_rejected(tmp_path, stored_copy, path):
    contrib = _contribution(stored_copy)
    parent = contrib
    for key in path[:-1]:
        parent = parent[key]
    del parent[path[-1]]
    ok, lines = _check(tmp_path, contrib, stored_copy)
    assert not ok and "contrib.schema.json" in lines[0]
    assert any(f"'{path[-1]}' is a required property" in x for x in lines)


def test_a_level_that_does_not_reproduce_the_stored_one_is_rejected(tmp_path, stored_copy):
    """Consistent in itself, but its f is not the stored level's."""
    contrib = _contribution(stored_copy)
    contrib["results"]["turn_mean_p"] = [p * 1.01 for p in contrib["results"]["turn_mean_p"]]
    drv = vol.driver("helical_pipe")
    contrib["results"].update(copy.deepcopy(drv.recompute(contrib["results"])))
    ok, lines = _check(tmp_path, contrib, stored_copy)
    assert not ok and any("doesn't reproduce the stored level" in x for x in lines)


def test_an_oversized_file_is_rejected(tmp_path, stored_copy):
    contrib = _contribution(stored_copy)
    contrib["log_tail"] = ["x" * 1999] * 200 + ["x" * 1999] * 400
    ok, lines = _check(tmp_path, contrib, stored_copy)
    assert not ok and "limit" in lines[0]


def test_raw_placeholders_are_caught():
    """GitHub hides ``<level>`` as an HTML tag; the generator refuses it
    outside code (task 0137)."""
    from validation.volunteer import _raw_placeholders
    assert _raw_placeholders("one file, helical_pipe-<level>.contrib.json") == ["<level>"]
    assert _raw_placeholders("one file, `x-<level>.json`; <!-- see <case> -->\n"
                             "```bash\nprepare <case>\n```") == []
