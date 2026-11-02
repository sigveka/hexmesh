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
PCF reader robustness (task 0064): annotation records, inline components
the reader doesn't know, and files holding several unconnected pipelines.

The fixtures are hand-written (millimetres) and use only the keywords of the
PCF guide.  Optionally, ``HEXMESH_PCF_SAMPLES`` points at a local directory
of third-party sample files (never committed): each is read and built, and
the outcome printed.
"""

import os
import warnings
from pathlib import Path

import pytest

from hexmesh.assembly import AssemblyError, Reducer, Straight
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec
from hexmesh.io.readers.pcf import ANNOTATION_TYPES, read_pcf

HEADER = """\
ISOGEN-FILES ISOGEN.FLS
UNITS-BORE MM
UNITS-CO-ORDS MM
"""


def _spec(bore=0.1):
    return PipeSpec(nang=4).core("fluid", CircleShape(radius=bore / 2, nang=4), nrad=3)


def _read(tmp_path, text):
    p = tmp_path / "net.pcf"
    p.write_text(HEADER + text, encoding="utf-8")
    return read_pcf(p)


def _fittings(asm):
    return [type(e.fitting).__name__ for e in asm.edges]


ANNOTATED = """\
END-POSITION-OPEN
    CO-ORDS 0 0 0
PIPELINE-REFERENCE L-1
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
    MESSAGE
    TEXT A MESSAGE ON THE PIPE
MESSAGE-SQUARE
    CO-ORDS 500 0 0
    TEXT 7
WELD
    CO-ORDS 1000 0 0
SUPPORT
    CO-ORDS 400 0 0 0
    SKEY 01HG
FLOW-ARROW
    CO-ORDS 200 0 0
ISO-SPLIT-POINT
    CO-ORDS 1000 0 0
PIPE
    END-POINT 1000 0 0 100
    END-POINT 2000 0 0 100
TEXT
    CO-ORDS 1500 0 0
END-POSITION-CLOSED
    CO-ORDS 2000 0 0
"""


def test_annotations_ignored_quietly_and_counted(tmp_path):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        net = _read(tmp_path, ANNOTATED)
        asm = net.to_assembly(_spec())
    assert net.skipped == []
    assert [c.record_type for c in net.components] == ["PIPE", "PIPE"]
    counts = {"END-POSITION-OPEN": 1, "MESSAGE-SQUARE": 1, "WELD": 1, "SUPPORT": 1,
              "FLOW-ARROW": 1, "ISO-SPLIT-POINT": 1, "TEXT": 1, "END-POSITION-CLOSED": 1}
    assert net.report["ignored"] == counts           # kept through to_assembly
    assert "END-POSITION-OPEN" not in net.header     # not a header keyword
    assert _fittings(asm) == ["Straight", "Straight"]


def test_annotation_list_matches_the_guide():
    """The guide's information items (pcf.md lists them)."""
    assert {"MESSAGE", "MESSAGE-ELLIPSE", "TEXT", "REFERENCE-DIMENSION", "TML",
            "FLOW-ARROW", "ISO-SPLIT-POINT", "LOCATION-POINT", "PIPE-BREAK",
            "SPOOL-IDENTIFIER", "SYSTEM-SPLIT", "END-POSITION-NULL"} <= ANNOTATION_TYPES
    assert not ANNOTATION_TYPES & {"PIPE", "WELD", "SUPPORT", "VALVE"}


def test_weld_with_end_points_is_still_a_joint(tmp_path):
    net = _read(tmp_path, """\
PIPELINE-REFERENCE L-1
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
WELD
    END-POINT 1000 0 0 100
    END-POINT 1001 0 0 100
PIPE
    END-POINT 1001 0 0 100
    END-POINT 2000 0 0 100
""")
    assert [c.kind for c in net.components] == ["pipe", "joint", "pipe"]
    assert net.report["ignored"] == {}


INLINE = """\
PIPELINE-REFERENCE L-1
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
UNION
    END-POINT 1000 0 0 100
    END-POINT 1080 0 0 100
PIPE
    END-POINT 1080 0 0 100
    END-POINT 1500 0 0 100
UNION
    END-POINT 1500 0 0 100
    END-POINT 1580 0 0 100
MISC-COMPONENT
    END-POINT 1580 0 0 100
    END-POINT 1780 0 0 100
    CENTRE-POINT 1680 0 0
PIPE
    END-POINT 1780 0 0 100
    END-POINT 2500 0 0 100
"""


def test_unknown_inline_component_is_a_straight(tmp_path):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        net = _read(tmp_path, INLINE)
    msgs = [str(x.message) for x in w]
    assert sum("UNION treated as an inline straight" in m for m in msgs) == 1   # once per type
    assert sum("MISC-COMPONENT treated as an inline straight" in m for m in msgs) == 1
    assert not [m for m in msgs if "Unsupported" in m]
    assert [c.kind for c in net.components] == ["pipe", "fitting", "pipe", "fitting",
                                                "fitting", "pipe"]
    asm = net.to_assembly(_spec())
    assert all(isinstance(e.fitting, Straight) for e in asm.edges)
    assert asm.edges[-1].fitting.length == pytest.approx(0.72)


def test_unknown_inline_component_with_two_bores_is_a_reducer(tmp_path):
    with pytest.warns(UserWarning, match="FROBNICATOR treated as a reducer"):
        net = _read(tmp_path, """\
PIPELINE-REFERENCE L-1
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
FROBNICATOR
    END-POINT 1000 0 0 100
    END-POINT 1150 0 0 80
PIPE
    END-POINT 1150 0 0 80
    END-POINT 2000 0 0 80
""")
    c = net.components[1]
    assert (c.kind, c.bore, c.end_bore) == ("reducer", pytest.approx(0.1), pytest.approx(0.08))
    asm = net.to_assembly(_spec())
    assert isinstance(asm.edges[1].fitting, Reducer)


ANGLED = """\
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


def test_angled_inline_component_rejected_by_name(tmp_path):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        net = _read(tmp_path, ANGLED)                 # read without a warning
    assert net.components[1].kind == "angled"
    for build in (net.to_assembly, net.to_assemblies):
        with pytest.raises(AssemblyError,
                           match=r"component 1 \(VALVE-ANGLE VALVE_ANGLE_1.*turn 90\.0°"
                                 r".*angle valves.*out of scope"):
            build(_spec())


def test_unknown_record_without_end_points_still_warns(tmp_path):
    with pytest.warns(UserWarning, match="Unsupported PCF component type 'GIZMO'"):
        net = _read(tmp_path, """\
PIPELINE-REFERENCE L-1
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
GIZMO
    CO-ORDS 500 0 0
""")
    assert [t for t, _ in net.skipped] == ["GIZMO"]


TWO_LINES = """\
PIPELINE-REFERENCE A-1
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
ELBOW
    END-POINT 1000 0 0 100
    END-POINT 1150 150 0 100
    CENTRE-POINT 1150 0 0
PIPE
    END-POINT 1150 150 0 100
    END-POINT 1150 800 0 100
PIPELINE-REFERENCE B-2
PIPE
    END-POINT 0 3000 0 100
    END-POINT 1200 3000 0 100
PIPE
    END-POINT 1200 3000 0 100
    END-POINT 2000 3000 0 100
END-CONNECTION-EQUIPMENT
    CO-ORDS 2000 3000 0
    CONNECTION-REFERENCE V-9/N1
"""


def test_several_pieces_to_assembly_lists_them(tmp_path):
    net = _read(tmp_path, TWO_LINES)
    with pytest.raises(AssemblyError, match=r"one connected piece.*2 unconnected pieces: "
                       r"pipeline A-1 \(components 0–2\); pipeline B-2 \(components 3–4\)"
                       r".*to_assemblies"):
        net.to_assembly(_spec())


def test_several_pieces_to_assemblies(tmp_path):
    net = _read(tmp_path, TWO_LINES)
    out = net.to_assemblies(_spec())
    assert list(out) == ["A_1", "B_2"]
    assert _fittings(out["A_1"]) == ["Straight", "Bend", "Straight"]
    assert _fittings(out["B_2"]) == ["Straight", "Straight"]
    assert set(net.report["pieces"]) == {"A_1", "B_2"}
    # the equipment connection belongs to B-2 alone, and names its end
    marked = {k: [i.name for i in a.open_interfaces() if i.equipment] for k, a in out.items()}
    assert marked == {"A_1": [], "B_2": ["V_9_N1"]}


def test_one_piece_to_assemblies_is_to_assembly(tmp_path):
    with pytest.warns(UserWarning, match="MISC-COMPONENT treated as an inline straight"):
        net = _read(tmp_path, INLINE.replace("UNION", "COUPLING"))
    one = net.to_assembly(_spec())
    (name, asm), = net.to_assemblies(_spec()).items()
    assert name == "L_1"
    assert asm.to_dict() == one.to_dict()


def test_equal_tee_message_says_planned(tmp_path):
    net = _read(tmp_path, """\
PIPELINE-REFERENCE L-1
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
TEE
    END-POINT 1000 0 0 100
    END-POINT 1200 0 0 100
    CENTRE-POINT 1100 0 0
    BRANCH1-POINT 1100 200 0 100
PIPE
    END-POINT 1200 0 0 100
    END-POINT 2000 0 0 100
PIPE
    END-POINT 1100 200 0 100
    END-POINT 1100 800 0 100
""")
    with pytest.raises(AssemblyError, match="equal tees .* planned through the wye-family "
                                            "layout; not available yet"):
        net.to_assembly(_spec())


@pytest.mark.skipif(not os.environ.get("HEXMESH_PCF_SAMPLES"),
                    reason="HEXMESH_PCF_SAMPLES (a local directory of sample PCFs) not set")
def test_local_sample_files():
    """Third-party samples (pcf.md, 'More sample files'): read and build
    each; the outcome is printed, not asserted (their licences keep them
    out of the repository)."""
    for path in sorted(Path(os.environ["HEXMESH_PCF_SAMPLES"]).glob("*.pcf")):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            net = read_pcf(path)
            try:
                out = net.to_assemblies(_spec(0.05))
                result = f"{len(out)} piece(s): " + ", ".join(
                    f"{k} {len(a.edges)} fittings" for k, a in out.items())
            except AssemblyError as e:
                result = f"AssemblyError: {e}"
        print(f"{path.name}: {len(net.components)} components, ignored "
              f"{net.report['ignored']}; {result}; warnings: "
              f"{sorted({str(x.message)[:70] for x in w})}")
