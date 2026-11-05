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
"""The JSON Schema of the saved description, and the field and limit
metadata it is generated from (task 0095)."""

import dataclasses
import importlib
import json
import re
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")

from hexmesh import Drum, Nozzle, OnHead, OnShell, PipeSpec, Session    # noqa: E402
from hexmesh.agent import dumps, schema                                   # noqa: E402
from hexmesh.assembly import intent, limits                               # noqa: E402
from hexmesh.core.params import UNITS, param                              # noqa: E402
from hexmesh.core.shape import SHAPES                                     # noqa: E402
from hexmesh.examples import ALL                                          # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).with_name("data")


@pytest.fixture(scope="module")
def validator():
    return jsonschema.Draft202012Validator(schema())


def _errors(validator, d) -> list[str]:
    return [f"{'/'.join(map(str, e.absolute_path))}: {e.message[:200]}"
            for e in validator.iter_errors(d)]


def test_schema_is_valid_draft_2020_12():
    s = schema()
    jsonschema.Draft202012Validator.check_schema(s)
    assert s["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert s["x-version"] == intent.VERSION
    assert set(intent.FITTING_TYPES) <= set(s["$defs"])
    assert {"PipeSpec", "Core", "Shell", "Drum", "Nozzle", "Assembly"} <= set(s["$defs"])


def test_schema_is_deterministic():
    assert dumps() == dumps()
    assert json.loads(dumps()) == schema()


@pytest.mark.parametrize("name", ALL)
def test_every_example_validates(name, validator):
    module = importlib.import_module(f"hexmesh.examples.{name}")
    with Session(name):
        d = json.loads(json.dumps(module.build().to_dict()))
    assert _errors(validator, d) == []


@pytest.mark.parametrize("path", sorted(DATA.glob("saved_before_*.json")), ids=lambda p: p.name)
def test_saved_fixtures_validate_after_upgrade(path, validator):
    d = intent.upgrade(json.loads(path.read_text(encoding="utf-8")))
    assert _errors(validator, d) == []


def test_bad_descriptions_are_rejected(validator):
    """The schema is not vacuous: a typo, a wrong type and an
    out-of-range value each fail."""
    with Session("bad"):
        d = json.loads(json.dumps(importlib.import_module(
            "hexmesh.examples.fittings.tee").build().to_dict()))
    tee = next(e["fitting"] for e in d["edges"] if e["fitting"]["type"] == "Tee")
    for change in ({"n_rnu": 3}, {"n_run": "3"}, {"n_run": 0}, {"type": "Teee"}):
        bad = json.loads(json.dumps(d))
        next(e["fitting"] for e in bad["edges"] if e["fitting"] == tee).update(change)
        assert _errors(validator, bad), change
    bad = {**d, "version": intent.VERSION + 1}
    assert _errors(validator, bad)


# --- field metadata -------------------------------------------------------------

def _described():
    """(owner, field, metadata) of every described field: the fittings,
    the shapes, the equipment and the PipeSpec tables."""
    classes = [*intent.FITTING_TYPES.values(), *SHAPES.values(), Drum, Nozzle, OnShell, OnHead]
    for cls in classes:
        for f in dataclasses.fields(cls):
            if not f.name.startswith("_"):
                yield cls.__name__, f.name, dict(f.metadata)
    for table in ("PARAMS", "CORE_PARAMS", "SHELL_PARAMS"):
        for name, meta in getattr(PipeSpec, table).items():
            yield f"PipeSpec.{table}", name, meta


def _missing(items) -> list:
    return [(owner, name) for owner, name, meta in items
            if meta.get("unit") not in UNITS or not meta.get("doc")]


def test_every_field_has_unit_and_doc():
    assert _missing(_described()) == []


def test_a_field_without_metadata_is_caught():
    """Planted case: a new fitting field without unit and doc fails."""
    @dataclasses.dataclass(frozen=True)
    class Planted:
        length: float = param("length", "axial length")
        n_new: int = 3
    items = [("Planted", f.name, dict(f.metadata)) for f in dataclasses.fields(Planted)]
    assert _missing(items) == [("Planted", "n_new")]


def test_spec_tables_match_the_signatures():
    import inspect
    for method, table in ((PipeSpec.__init__, PipeSpec.PARAMS),
                          (PipeSpec.core, PipeSpec.CORE_PARAMS),
                          (PipeSpec.shell, PipeSpec.SHELL_PARAMS)):
        args = set(inspect.signature(method).parameters) - {"self"}
        assert args == set(table), method.__name__


def test_field_limits_are_registered():
    def names(limit):
        if isinstance(limit, str):
            return [limit]
        if isinstance(limit, dict):
            return list(limit.values())
        return list(limit or ())
    unknown = [(o, n, x) for o, n, m in _described() for x in names(m.get("limit"))
               if x not in limits.LIMITS]
    assert unknown == []


# --- limits -----------------------------------------------------------------------

def test_every_limit_has_unit_kind_and_doc():
    for name, lim in limits.LIMITS.items():
        assert lim.unit and lim.kind in limits.KINDS and lim.doc, name
        assert getattr(limits, name) == lim.value, name


def _error_limit_names() -> set[str]:
    """Every name an error or warning passes as ``limit`` (a string, or the
    values of a mapping), when it is an upper-case constant name."""
    found = set()
    for p in (ROOT / "hexmesh").rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        found |= set(re.findall(r'limit="([A-Z][A-Z0-9_]+)"', text))
        for m in re.finditer(r"limit=\{([^}]*)\}", text):
            found |= set(re.findall(r'"([A-Z][A-Z0-9_]+)"', m.group(1)))
    return found


def test_every_error_limit_name_is_registered():
    names = _error_limit_names()
    assert names, "the scan found no names"
    assert sorted(names - set(limits.LIMITS)) == []


def test_api_limits_table_matches_the_registry():
    api = (ROOT / "API.md").read_text(encoding="utf-8")
    section = api.split("\n## Schema and limits")[1].split("\n## ")[0]
    rows = {}
    for line in section.splitlines():
        m = re.match(r"\| `([A-Z][A-Z0-9_]+)` \| (.*?) \| `(.*?)` \| (\w+) \| (.*) \|$", line)
        if m:
            rows[m.group(1)] = m.groups()[1:]
    assert set(rows) == set(limits.LIMITS)
    for name, (value, unit, kind, doc) in rows.items():
        lim = limits.LIMITS[name]
        assert (value, unit, kind, doc) == (_api_value(lim.value), lim.unit, lim.kind, lim.doc)


def _api_value(v) -> str:
    return f"`{v!r}`" if isinstance(v, tuple) else f"{v:g}"
