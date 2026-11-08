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
The README and the guides (task 0078): the README's first code block
builds the network the gallery measures, with the cell count its metrics
table quotes; every relative link and image in ``README.md``,
``docs/WHY.md`` and ``docs/GUIDE.md`` resolves, anchors included;
``CITATION.cff`` carries ``pyproject.toml``'s version; and every number
the "With an agent" primer quotes is what the commands return for its
network (task 0110).
"""

import io
import json
import re
import sys
import tomllib
from collections import Counter
from pathlib import Path

import pytest

from hexmesh import _gmsh
from hexmesh.agent import cli
from hexmesh.assembly import AssemblyError
from hexmesh.examples.applications import pcf_line
from hexmesh.examples.sections import insulated_network, insulated_tee
from hexmesh.interchange import read_pcf

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DOCS = [README, ROOT / "docs" / "WHY.md", ROOT / "docs" / "GUIDE.md"]


def first_python_block(text: str) -> str:
    return re.search(r"^```python\n(.*?)^```", text, re.M | re.S).group(1)


def metrics_cells(text: str) -> int:
    """The cells the README's ``readme:metrics`` table quotes."""
    block = text.split("<!-- readme:metrics:start -->")[1].split("<!-- readme:metrics:end -->")[0]
    row = [l for l in block.splitlines() if re.match(r"^\| [\d\s ]+ = ", l)][0]
    predicted, meshed = (int(re.sub(r"\D", "", x)) for x in row.split("|")[1].split("="))
    assert predicted == meshed
    return predicted


def _run_block(tmp_path, monkeypatch, *, mesh: bool) -> dict:
    code = first_python_block(README.read_text(encoding="utf-8"))
    if not mesh:
        code = "\n".join(l for l in code.splitlines() if "asm.write" not in l)
    monkeypatch.chdir(tmp_path)
    ns: dict = {}
    exec(compile(code, "README.md", "exec"), ns)              # noqa: S102
    return ns


def _same_network(asm):
    ref = insulated_tee.build()
    assert asm.cell_count() == ref.cell_count()
    assert [type(e.fitting).__name__ for e in asm.edges] == \
        [type(e.fitting).__name__ for e in ref.edges]
    assert asm.cell_count() == metrics_cells(README.read_text(encoding="utf-8"))


def test_the_readme_block_builds_the_measured_network(tmp_path, monkeypatch):
    """Everything but the write, which meshes (see the slow test)."""
    _same_network(_run_block(tmp_path, monkeypatch, mesh=False)["asm"])


@pytest.mark.slow
def test_the_readme_block_runs_as_written(tmp_path, monkeypatch):
    ns = _run_block(tmp_path, monkeypatch, mesh=True)
    _same_network(ns["asm"])
    assert (tmp_path / "insulated_tee.msh").stat().st_size > 0


# --- links ---------------------------------------------------------------------

def _strip_code(text: str) -> str:
    text = re.sub(r"^```.*?^```", "", text, flags=re.M | re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def slugs(path: Path) -> set[str]:
    """GitHub's anchors for *path*'s headings, and explicit ids."""
    text = re.sub(r"^```.*?^```", "", path.read_text(encoding="utf-8"), flags=re.M | re.S)
    out, seen = set(), Counter()
    for h in re.findall(r"^#{1,6} +(.+?) *#*$", text, re.M):
        s = re.sub(r"[^\w\- ]", "", h.lower().replace("`", "")).replace(" ", "-")
        out.add(s if not seen[s] else f"{s}-{seen[s]}")
        seen[s] += 1
    out |= set(re.findall(r'<a (?:id|name)="([^"]+)"', text))
    return out


def links(path: Path) -> list[str]:
    text = _strip_code(path.read_text(encoding="utf-8"))
    found = re.findall(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", text)
    found += re.findall(r'<img[^>]*\bsrc="([^"]+)"', text)
    found += re.findall(r'<a[^>]*\bhref="([^"]+)"', text)
    return [u for u in found if not re.match(r"^[a-z]+:", u)]   # http:, mailto:, ...


def broken(path: Path) -> list[str]:
    bad = []
    for link in links(path):
        target, _, anchor = link.partition("#")
        dest = path if not target else (path.parent / target).resolve()
        if not dest.exists():
            bad.append(f"{link}: no such file")
        elif anchor and dest.suffix == ".md" and anchor not in slugs(dest):
            where = dest.relative_to(ROOT) if dest.is_relative_to(ROOT) else dest.name
            bad.append(f"{link}: no heading #{anchor} in {where}")
    return bad


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_relative_link_resolves(doc):
    assert links(doc), f"{doc.name}: no links found: is the pattern wrong?"
    assert broken(doc) == []


def test_a_planted_broken_link_and_anchor(tmp_path):
    (tmp_path / "a.md").write_text("# Top\n\n## Two words\n", encoding="utf-8")
    doc = tmp_path / "doc.md"
    doc.write_text("[ok](a.md#two-words) [self](#here) [gone](b.md) [bad](a.md#nope) "
                   '<img src="c.png"> `[code](x.md)` [web](https://example.com)\n\n'
                   "## Here\n", encoding="utf-8")
    assert sorted(broken(doc)) == ["a.md#nope: no heading #nope in a.md",
                                   "b.md: no such file", "c.png: no such file"]


# --- versions --------------------------------------------------------------------

def test_citation_version_is_the_package_s():
    citation = re.search(r"^version: *(\S+)", (ROOT / "CITATION.cff").read_text(
        encoding="utf-8"), re.M).group(1).strip("'\"")
    with open(ROOT / "pyproject.toml", "rb") as f:
        package = tomllib.load(f)["project"]["version"]
    assert citation == package, "bump CITATION.cff's version with pyproject.toml's"


# --- from plant data (task 0114) ----------------------------------------------

def pcf_section(text: str) -> str:
    return text.split("\n## From plant data (PCF)\n")[1].split("\n---\n")[0]


def test_the_pcf_block_counts_the_shipped_sample_s_cells(tmp_path, monkeypatch, capsys):
    """Everything but the write (which meshes): it prints the count its
    comment quotes, the example's."""
    code = first_python_block(pcf_section(README.read_text(encoding="utf-8")))
    quoted = int(re.search(r"^print\(asm\.cell_count\(\)\) +# (\d+)$", code, re.M).group(1))
    code = "\n".join(l for l in code.splitlines() if "asm.write" not in l)
    monkeypatch.chdir(tmp_path)
    exec(compile(code, "README.md", "exec"), {})              # noqa: S102
    assert int(capsys.readouterr().out) == quoted == pcf_line.build().cell_count()


def _subset(small, big) -> bool:
    if isinstance(small, dict):
        return isinstance(big, dict) and all(k in big and _subset(v, big[k])
                                             for k, v in small.items())
    return small == big


def test_the_pcf_section_s_error_is_what_an_equal_tee_gives(tmp_path, monkeypatch):
    """The quoted ``equal_tee_unsupported``: the sample with its branch at
    the run's 100 mm, saved as ``line.pcf``.  Code and message exact; the
    ``where`` shown is part of the real one."""
    quoted = json.loads(re.search(r"^  ```json\n(.*?)^  ```", pcf_section(
        README.read_text(encoding="utf-8")), re.M | re.S).group(1))
    text = pcf_line.SAMPLE.read_text(encoding="utf-8")
    equal = text.replace("1100 300 0 50", "1100 300 0 100").replace("1100 800 0 50",
                                                                    "1100 800 0 100")
    assert equal.count(" 100\n") - text.count(" 100\n") == 3      # the branch point and pipe
    monkeypatch.chdir(tmp_path)
    Path("line.pcf").write_text(equal, encoding="utf-8")
    with pytest.raises(AssemblyError) as e:
        read_pcf("line.pcf").to_assembly(pcf_line.pipe, insulation=True)
    got = e.value.to_dict()
    assert (got["code"], got["message"]) == (quoted["code"], quoted["message"])
    assert _subset(quoted["where"], got["where"]), got["where"]


def test_a_planted_wrong_where_is_not_a_subset():
    assert not _subset({"source": {"line": 11}}, {"source": {"line": 19, "file": "line.pcf"}})
    assert _subset({"source": {"line": 19}}, {"part": "1", "source": {"line": 19}})


# --- the agent primer (task 0110) ----------------------------------------------

def primer(text: str) -> str:
    """The "With an agent" section as one line: blockquote marks dropped,
    whitespace collapsed, so a regex can span the prose's line breaks."""
    section = text.split("\n## With an agent\n")[1].split("\n---\n")[0]
    return re.sub(r"\s+", " ", " ".join(re.sub(r"^> ?", "", l) for l in section.splitlines()))


N = r"(\d[\d ]*\d|\d)"                 # 641 680: digit groups split by spaces

#: What the primer says, as (what, regex): one group per value.
CLAIMS = {
    "the budget": r"stay under " + N + " cells",
    "the velocity, cm/s": r"water at " + N + " cm/s",
    "the accuracy asked": r"cm/s, (\w+) accuracy",
    "estimate's cells": r"`hexmesh estimate`: " + N + " cells",
    "the cells at the accuracy asked": r"(?:\w+) accuracy needs " + N + " cells",
    "the straights' axial aspect, before": r"axial aspect " + N + " →",
    "the straights' axial aspect, after": r"axial aspect \d+ → " + N + ",",
    "the cells with stretched straights": r"axial aspect \d+ → \d+, " + N + " cells",
    "the accuracy it fell back to": r"then fell back to (\w+):",
    "nang": r"`nang` " + N,
    "nrad": r"`nrad` " + N,
    "the cells advised": r"`nrad` \d+, " + N + " cells",
}


def said(text: str) -> dict:
    out = {}
    for what, rx in CLAIMS.items():
        m = re.search(rx, text)
        assert m, f"README primer: no longer says {what} (pattern {rx!r})"
        v = m.group(1)
        out[what] = int(v.replace(" ", "")) if v[0].isdigit() else v
    return out


class _Out:
    def __init__(self):
        self.buffer = io.BytesIO()

    def flush(self):
        pass


def _cli(*argv) -> dict:
    out, real = _Out(), sys.stdout
    sys.stdout = out
    try:
        cli.main([str(a) for a in argv])
    finally:
        sys.stdout = real
    payload = json.loads(out.buffer.getvalue())
    assert "result" in payload, f"hexmesh {argv[0]}: {payload['error']['message']}"
    return payload


@pytest.fixture(scope="module")
def got(tmp_path_factory):
    """The primer's session, run through the CLI on its network with the
    inputs its prose gives, with gmsh's loader made to fail: no command
    here may touch gmsh."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(_gmsh, "load", _no_gmsh)
        return _session(tmp_path_factory.mktemp("primer"))


def _no_gmsh():
    raise AssertionError("the primer's commands reached gmsh")


def _session(tmp: Path) -> dict:
    claims = said(primer(README.read_text(encoding="utf-8")))
    net, inputs, table = tmp / "header.json", tmp / "inputs.json", tmp / "table.json"
    asm = insulated_network.build()
    asm.save(net)
    inputs.write_text(json.dumps({"fluid": "water",
                                  "flow": {"velocity": claims["the velocity, cm/s"] / 100},
                                  "accuracy": claims["the accuracy asked"],
                                  "budget": claims["the budget"]}), encoding="utf-8")
    validated = _cli("validate", net)["result"]
    estimate = _cli("estimate", net)["result"]
    advice = _cli("advise", net, "--inputs", inputs)["result"]
    table.write_text(json.dumps(advice["table"]), encoding="utf-8")
    applied = tmp / "applied.json"
    applied.write_text(json.dumps(_cli("apply", net, "--table", table)["result"]),
                       encoding="utf-8")
    steps = advice["budget_steps"]
    aspect = re.fullmatch(r"straights' axial aspect (\d+) → (\d+)", steps[0]["step"])
    fallback = re.fullmatch(r"accuracy (\w+) → (\w+)", steps[-1]["step"])
    return {
        "claims": claims, "asm": asm,
        "validated": validated, "advice": advice,
        "revalidated": _cli("validate", applied)["result"],
        "values": {
            **{k: claims[k] for k in ("the budget", "the velocity, cm/s",
                                      "the accuracy asked")},
            "estimate's cells": estimate["cells"],
            "the cells at the accuracy asked": steps[0]["cells_before"],
            "the straights' axial aspect, before": int(aspect[1]),
            "the straights' axial aspect, after": int(aspect[2]),
            "the cells with stretched straights": steps[0]["cells_after"],
            "the accuracy it fell back to": advice["totals"]["accuracy"],
            "nang": advice["density"]["nang"],
            "nrad": advice["density"]["nrad"],
            "the cells advised": advice["totals"]["cells"],
        },
        "fell_from": fallback and fallback[1],
    }


def stale(claims: dict, values: dict) -> list[str]:
    return [f"README primer: {what} is {claims[what]}; the commands give {values[what]}"
            for what in CLAIMS if claims[what] != values[what]]


def test_the_primer_quotes_what_the_commands_return(got):
    assert stale(got["claims"], got["values"]) == []
    assert len(got["advice"]["budget_steps"]) == 2          # stretch, then one class down
    assert got["fell_from"] == got["claims"]["the accuracy asked"]
    assert got["advice"]["totals"]["within_budget"]


def test_the_primer_s_validations_and_note(got):
    text = primer(README.read_text(encoding="utf-8"))
    assert "`hexmesh validate` (no errors, no warnings)" in text
    assert got["validated"]["ok"] and got["validated"]["warnings"] == []
    assert "`validate` passes again" in text and got["revalidated"]["ok"]
    assert "calibrated on developed flow in straight runs" in text
    assert "advice_calibration_scope" in [n["code"] for n in got["advice"]["notes"]]


def test_a_planted_wrong_number_is_named(got):
    text = primer(README.read_text(encoding="utf-8")).replace("72 048 cells", "72 049 cells")
    assert stale(said(text), got["values"]) == \
        ["README primer: the cells advised is 72049; the commands give 72048"]


def test_the_primer_describes_its_network(got):
    """Each dimension the prose gives, against the example (in metres)."""
    text = primer(README.read_text(encoding="utf-8"))
    for phrase in ("200 mm bore, 6 mm steel, 25 mm insulation", "A 0.4 m straight;",
                   "a tee to a 120 mm branch, 0.3 m long, then 0.4 m more that goes bare "
                   "after its first cell", "0.4 m more header",
                   "a 60° wye with 0.15 m of run and two 0.4 m legs, each followed by 0.3 m"):
        assert phrase in text, phrase
    asm = got["asm"]
    spec = asm.edges[0].ports[0].spec.to_dict()
    assert spec["core"]["shape"]["radius"] * 2 == 0.2
    assert [(s["name"], s["dR"]) for s in spec["shells"]] == [("steel", 0.006),
                                                              ("insulation", 0.025)]
    kinds = [(type(e.fitting).__name__, e.fitting) for e in asm.edges]
    assert [k for k, _ in kinds] == ["Straight", "Tee", "Straight", "Straight", "Wye",
                                     "Straight", "Straight"]
    straight0, tee, tap, header, wye, left, right = (f for _, f in kinds)
    assert straight0.length == 0.4 and header.length == 0.4
    assert tee.branch_radius * 2 == 0.12 and tee.branch_length == 0.3 and tap.length == 0.4
    (at, bare), = tap.stack_changes
    assert at == 1 and bare.layer_names == ["fluid", "steel"]
    assert wye.angle == 60 and wye.run_length == 0.15 and wye.branch_length == 0.4
    assert left.length == right.length == 0.3
