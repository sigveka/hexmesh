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
"""``hexmesh.agent.describe`` and ``preview``: what a network is, without
GMSH (task 0097)."""

import hashlib
import importlib
import json
import os
import textwrap
import time
import warnings

import gmsh
import numpy as np
import pytest

from hexmesh import PipeSpec, Session
from hexmesh.agent import describe
from hexmesh.core.shape import CircleShape
from hexmesh.examples import ALL
from hexmesh.io.readers import read_pcf

PCF_TEE = """\
ISOGEN-FILES ISOGEN.FLS
UNITS-BORE MM
UNITS-CO-ORDS MM
PIPELINE-REFERENCE L-1
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
TEE
    END-POINT 1000 0 0 100
    END-POINT 1200 0 0 100
    CENTRE-POINT 1100 0 0
    BRANCH1-POINT 1100 300 0 50
PIPE
    END-POINT 1200 0 0 100
    END-POINT 2000 0 0 100
PIPE
    END-POINT 1100 300 0 50
    END-POINT 1100 800 0 50
"""
PCF_ANGLED = """\
ISOGEN-FILES ISOGEN.FLS
UNITS-BORE MM
UNITS-CO-ORDS MM
PIPELINE-REFERENCE L-1
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
VALVE-ANGLE
    END-POINT 1000 0 0 100
    END-POINT 1150 150 0 100
    CENTRE-POINT 1150 0 0
PIPE
    END-POINT 1150 150 0 100
    END-POINT 1150 1000 0 100
"""


def _example(name):
    return importlib.import_module(f"hexmesh.examples.{name}").build()


def _pcf(tmp_path, text, name="plant.pcf"):
    path = tmp_path / name
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return read_pcf(path)


def _spec():
    return PipeSpec(nang=4).core("fluid", CircleShape(radius=0.05, nang=4), nrad=3)


# --- describe ---------------------------------------------------------------------

@pytest.mark.parametrize("name", ALL)
def test_describe_every_example_without_gmsh(name):
    """No GMSH session, valid JSON, byte-identical across runs and between
    the assembly and its saved description; cells equal cell_count().
    A file's provenance (``origin``, task 0096) is never saved, so an
    example read from a PCF (``pcf_line``) matches its description once
    its origins are cleared.  Before, it differs only where a message
    names the file (a warning's ``<file>:<line>``); an imported network
    with no such message (``subsea_pipeline``) matches already."""
    assert not gmsh.isInitialized()
    asm = _example(name)
    text = json.dumps(describe(asm), sort_keys=True, allow_nan=False)
    assert not gmsh.isInitialized()
    assert text == json.dumps(describe(asm), sort_keys=True, allow_nan=False)
    saved = json.dumps(describe(asm.to_dict()), sort_keys=True, allow_nan=False)
    if any(e.origin for e in asm.edges):
        files = {os.path.basename(str(e.origin.get("file"))) for e in asm.edges if e.origin}
        assert saved == text or any(f in text for f in files)   # only the file:line is lost
        for e in asm.edges:
            e.origin = None
        text = json.dumps(describe(asm), sort_keys=True, allow_nan=False)
    assert text == saved
    d = json.loads(text)
    assert d["error"] is None
    assert d["totals"]["cells"] == asm.cell_count()
    assert [f["cells"] for f in d["fittings"]] == [asm.cell_counts()[e.index] for e in asm.edges]
    box = d["totals"]["bounding_box"]
    lo, hi = np.array(box["min"]) - 1e-9, np.array(box["max"]) + 1e-9
    for f in d["fittings"]:
        for p in [f["inlet"]] + f["outlets"]:
            assert np.all(lo <= p["position"]) and np.all(np.array(p["position"]) <= hi)


def _built_ends(asm) -> dict:
    """Patch name → centroid of its nodes, from the real build: the
    ``open_end`` groups, ``<layer>_<patch>``, merged over the layers."""
    asm.mesh()
    layers = sorted({n for i in asm.interfaces for n in i.spec.layer_names}, key=len,
                    reverse=True)
    nodes: dict[str, list] = {}
    for dim, tag in gmsh.model.getPhysicalGroups(2):
        group = gmsh.model.getPhysicalName(dim, tag)
        if asm.group_roles().get(group) != "open_end":
            continue
        layer = next(n for n in layers if group.startswith(n + "_"))
        _, x = gmsh.model.mesh.getNodesForPhysicalGroup(dim, tag)
        nodes.setdefault(group[len(layer) + 1:], []).append(x.reshape(-1, 3))
    return {k: np.unique(np.vstack(v), axis=0).mean(axis=0) for k, v in nodes.items()}


@pytest.mark.parametrize("source", ["applications.hvac_branched", "fittings.wye", "pcf"])
def test_open_ends_match_the_real_build(source, tmp_path):
    if source == "pcf":
        asm = _pcf(tmp_path, PCF_TEE).to_assembly(_spec())
    else:
        asm = _example(source)
    d = describe(asm)
    with Session(source):
        built = _built_ends(asm)
    ends = {e["name"]: np.array(e["position"]) for e in d["open_ends"]}
    assert set(ends) == set(built)
    scale = max(np.ptp(np.array([d["totals"]["bounding_box"]["min"],
                                 d["totals"]["bounding_box"]["max"]]), axis=0))
    for name, p in ends.items():
        np.testing.assert_allclose(built[name], p, atol=1e-6 * scale, err_msg=name)


def test_open_end_outward_and_junction_angles():
    d = describe(_example("fittings.wye"))
    ends = {e["name"]: e for e in d["open_ends"]}
    assert ends["inlet"]["outward"] == [-1.0, 0.0, 0.0]
    (wye,) = d["junctions"]
    assert wye["type"] == "Wye"
    assert [b["deflection"] for b in wye["branches"]] == [30.0, 30.0]
    assert wye["angles"] == [{"ports": [1, 2], "angle": 60.0}]
    assert d["units"]["angle"] == "deg"


def test_describe_reports_validation_problems():
    """A failing assembly is described, with the error's code, not raised."""
    from hexmesh import Assembly, Bend, Straight
    asm = Assembly(_spec())
    asm.add(Straight(0.3, n_layers=2))
    asm.add(Bend(0.04, 90, n_layers=4))            # tighter than the pipe
    d = describe(asm)
    assert d["error"]["code"] and "Bend" in d["error"]["message"]
    assert d["totals"]["cells"] is None


def test_describe_pcf_model_lists_rejected_parts(tmp_path):
    model = _pcf(tmp_path, PCF_ANGLED).to_model()
    d = describe(model)
    json.dumps(d, allow_nan=False)
    assert d["kind"] == "network_model" and d["units"]["length"] == "m"
    (rej,) = d["rejected"]
    assert rej["record"] == "VALVE-ANGLE" and "angle valves" in rej["reason"]
    assert rej["source"]["line"] == 8 and rej["source"]["record"] == "VALVE-ANGLE"
    assert d["totals"]["parts"] == len(model.parts)
    assert {c["origin"] for c in d["connections"]} <= {"inferred", "declared"}
    assert d["totals"]["inferred_connections"] == sum(
        c.origin == "inferred" for c in model.connections)
    assert json.dumps(d, sort_keys=True) == json.dumps(describe(model), sort_keys=True)


def test_describe_rejects_other_types():
    with pytest.raises(TypeError, match="describe"):
        describe(42)


# --- preview ----------------------------------------------------------------------

@pytest.mark.parametrize("name", ALL)
def test_preview_every_example(name, tmp_path):
    pytest.importorskip("matplotlib")
    from hexmesh.agent import preview
    asm = _example(name)
    t = time.perf_counter()
    a = preview(asm, tmp_path / "a.png")
    elapsed = time.perf_counter() - t
    b = preview(asm, tmp_path / "b.png")
    assert not gmsh.isInitialized()
    assert a.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert hashlib.sha1(a.read_bytes()).digest() == hashlib.sha1(b.read_bytes()).digest()
    assert b"Software" not in a.read_bytes() and b"Creation" not in a.read_bytes()
    assert elapsed < 2.0, f"{elapsed:.2f} s"


def test_preview_of_a_model(tmp_path):
    pytest.importorskip("matplotlib")
    from hexmesh.agent import preview
    out = preview(_pcf(tmp_path, PCF_ANGLED).to_model(), tmp_path / "m.png")
    assert out.stat().st_size > 0
