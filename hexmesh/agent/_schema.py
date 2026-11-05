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
"""JSON Schema of the saved ``hexmesh.assembly`` description (task 0095).

``schema()`` builds it at call time from the registries, so it never
goes stale and is never hand-edited:
- the fitting types, ``intent.FITTING_TYPES``, and their dataclass
  fields' metadata (``hexmesh.core.params``);
- ``PipeSpec.PARAMS``, ``CORE_PARAMS`` and ``SHELL_PARAMS``;
- the outline shapes, ``shape.SHAPES``;
- the equipment, ``Drum`` and its nozzles;
- ``limits.LIMITS``, under ``x-limits``.

Every field has its type, ``x-unit``, ``description`` (the one-line doc,
then its docstring entry: the rules that aren't ranges), range and
default.  A field checked against a registered limit names it in
``x-limit``.  Adding a registry later (the network document's part
classes, decision 0032) is one more entry in :func:`_defs`.

``python3 -m hexmesh.agent.schema`` prints it (``schema.py``, the command;
the package imports this module, so running it with ``-m`` would load it
twice).
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import re

from hexmesh import Drum, Nozzle, OnHead, OnShell, PipeSpec
from hexmesh.assembly import intent, limits
from hexmesh.core.params import RANGES
from hexmesh.core.shape import SHAPES

DIALECT = "https://json-schema.org/draft/2020-12/schema"

_NUMBER = {"type": "number"}
_VECTOR = {"type": "array", "prefixItems": [_NUMBER] * 3, "minItems": 3, "maxItems": 3,
           "items": False}

#: field name → value schema, for fields a Python annotation can't
#: describe (tuples and nested registries); the rest follow their type
_VALUES = {
    "points": {"type": "array", "items": {"$ref": "#/$defs/Vector3"}, "minItems": 2},
    "toward": {"$ref": "#/$defs/Vector3"},
    "end_tangent": {"$ref": "#/$defs/Vector3"},
    "position": {"$ref": "#/$defs/Vector3"},
    "axis": {"$ref": "#/$defs/Vector3"},
    "up": {"$ref": "#/$defs/Vector3"},
    "stack_changes": {"type": "array", "items": {
        "type": "array", "prefixItems": [{"type": "integer"}, {"$ref": "#/$defs/PipeSpec"}],
        "minItems": 2, "maxItems": 2, "items": False}},
    "profile": {"anyOf": [
        {"type": "array", "prefixItems": [{"const": "cosine"}, _NUMBER],
         "minItems": 2, "maxItems": 2, "items": False},
        {"type": "array", "prefixItems": [{"const": "venturi"}, _NUMBER, _NUMBER],
         "minItems": 2, "maxItems": 3, "items": False},
        {"type": "array", "minItems": 2, "items": {
            "type": "array", "prefixItems": [_NUMBER, _NUMBER], "minItems": 2,
            "maxItems": 2, "items": False}}]},
    "nozzles": {"type": "array", "items": {"$ref": "#/$defs/Nozzle"}},
    "wall_bump": {"type": "array", "prefixItems": [_NUMBER, _NUMBER], "minItems": 2,
                  "maxItems": 2, "items": False},
}
#: annotation word → value schema
_TYPES = {
    "float": _NUMBER, "int": {"type": "integer"}, "str": {"type": "string"},
    "bool": {"type": "boolean"},
    "PipeSpec": {"$ref": "#/$defs/PipeSpec"},
    "CircleShape": {"$ref": "#/$defs/Shape"}, "RectShape": {"$ref": "#/$defs/Shape"},
    "Shape": {"$ref": "#/$defs/Shape"},
    "OnShell": {"$ref": "#/$defs/Location"}, "OnHead": {"$ref": "#/$defs/Location"},
}


def _doc_entries(obj) -> dict[str, str]:
    """name → text of each entry in *obj*'s numpy-style ``Parameters``
    section (``a, b : type`` entries give both names the text)."""
    doc = inspect.getdoc(obj) or ""
    m = re.search(r"^Parameters\n-+\n(.*?)(?=^\S[^\n]*\n-+\n|\Z)", doc, re.M | re.S)
    out: dict[str, str] = {}
    if not m:
        return out
    for head, body in re.findall(r"^(\S[^\n]*?) : [^\n]*\n((?:[ \t]+[^\n]*\n?|\n)*)",
                                 m.group(1), re.M):
        text = " ".join(body.split())
        for name in head.split(","):
            out[name.strip()] = text
    return out


def _summary(obj) -> str:
    """*obj*'s docstring up to its ``Parameters`` section, whitespace folded
    within paragraphs."""
    doc = (inspect.getdoc(obj) or "").split("\nParameters\n")[0]
    return "\n\n".join(" ".join(p.split()) for p in doc.split("\n\n") if p.strip())


def _plain(v):
    if isinstance(v, tuple):
        return [_plain(x) for x in v]
    return v


def _value(name: str, annotation: str | None, nullable: bool) -> dict:
    if name in _VALUES:
        s = dict(_VALUES[name])
    else:
        words = [w.strip() for w in (annotation or "").split("|") if w.strip() != "None"]
        alts = list({json.dumps(_TYPES[w], sort_keys=True): _TYPES[w] for w in words}.values())
        s = dict(alts[0]) if len(alts) == 1 else {"anyOf": alts}
    if nullable:
        s = {"anyOf": [s, {"type": "null"}]}
    return s


def _field(name: str, meta: dict, annotation: str | None, *, nullable: bool = False,
           default=dataclasses.MISSING, docs: dict | None = None) -> dict:
    """The schema of one field from its :mod:`hexmesh.core.params` metadata."""
    s = _value(name, annotation, nullable or "None" in (annotation or ""))
    text = meta["doc"]
    if docs and docs.get(name):
        text += ".\n\n" + docs[name]
    if meta.get("input"):
        text += "\n\nAn input: left out of the description while unset."
    s["description"] = text
    s["x-unit"] = meta["unit"]
    for k in RANGES:
        if k in meta:
            s[k] = meta[k]
    if "limit" in meta:
        s["x-limit"] = _plain(meta["limit"])
    if default is not dataclasses.MISSING:
        s["default"] = _plain(default)
    return s


def _dataclass(cls, *, tag: tuple[str, str] | None = None, title: str | None = None) -> dict:
    """An object schema of dataclass *cls*: one property per public field;
    required are those without a default.  *tag* is ``(key, value)`` of a
    type tag the saved form carries (``{"type": "Bend"}``)."""
    docs = _doc_entries(cls)
    props, required = {}, []
    if tag:
        props[tag[0]] = {"const": tag[1]}
        required.append(tag[0])
    for f in dataclasses.fields(cls):
        if f.name.startswith("_"):
            continue
        has = f.default is not dataclasses.MISSING or f.default_factory is not dataclasses.MISSING
        props[f.name] = _field(f.name, dict(f.metadata), f.type, docs=docs,
                               default=f.default if f.default is not dataclasses.MISSING
                               else dataclasses.MISSING)
        if not has:
            required.append(f.name)
    return {"type": "object", "title": title or cls.__name__, "description": _summary(cls),
            "properties": props, "required": required, "additionalProperties": False}


def _table(table: dict, keys, *, required=(), nullable=(), extra=None, title: str,
           description: str, docs: dict | None = None) -> dict:
    """An object schema from a method's parameter table (``PipeSpec.CORE_PARAMS``):
    the saved *keys* only."""
    props = dict(extra or {})
    for k in keys:
        props[k] = _field(k, table[k], _ANNOTATIONS.get(k), nullable=k in nullable, docs=docs)
    return {"type": "object", "title": title, "description": description,
            "properties": props, "required": list(required), "additionalProperties": False}


#: value types of the PipeSpec tables' saved keys
_ANNOTATIONS = {"nang": "int", "nang_w": "int", "nang_h": "int", "mbmp": "float",
                "rot": "float", "n_outer": "int", "name": "str", "shape": "Shape",
                "nrad": "int", "mprg": "float", "layout": "str", "dR": "float",
                "outer": "Shape"}


def _spec_defs() -> dict:
    init, core, shell = (_doc_entries(m) for m in (PipeSpec, PipeSpec.core, PipeSpec.shell))
    spec = _table(PipeSpec.PARAMS, ("nang", "nang_w", "nang_h", "mbmp", "rot", "n_outer"),
                  required=("core", "shells"), nullable=("nang", "nang_w", "nang_h"),
                  title="PipeSpec", description=_summary(PipeSpec), docs=init,
                  extra=None)
    spec["properties"]["core"] = {"$ref": "#/$defs/Core"}
    spec["properties"]["shells"] = {"type": "array", "items": {"$ref": "#/$defs/Shell"}}
    core_d = _table(PipeSpec.CORE_PARAMS, ("name", "shape", "layout", "nrad", "mprg",
                                          "wall_bump"),
                    required=("name", "shape", "nrad"), nullable=("mprg",), docs=core,
                    title="Core", description=_summary(PipeSpec.core))
    shell_props = {"type": {"enum": ["shell", "square_shell"],
                            "description": "the layer kind; square_shell is the form saved "
                                           "before decision 0026, read as a rect outer"}}
    shell_d = _table(PipeSpec.SHELL_PARAMS, ("name", "dR", "nrad", "mprg", "outer"),
                     required=("type", "name", "nrad"), nullable=("dR", "mprg"), docs=shell,
                     extra=shell_props, title="Shell", description=_summary(PipeSpec.shell))
    # square_shell (before decision 0026) saved its rectangle flat
    for k in ("half_w", "half_h"):
        shell_d["properties"][k] = {"type": "number", "x-unit": "length", "exclusiveMinimum": 0,
                                    "description": f"square_shell only: the outline's {k}"}
    shell_d["oneOf"] = [{"required": ["dR"]}, {"required": ["outer"]},
                        {"required": ["half_w", "half_h"],
                         "properties": {"type": {"const": "square_shell"}}}]
    shapes = {cls.__name__: _dataclass(cls, tag=("type", tag)) for tag, cls in SHAPES.items()}
    return {"PipeSpec": spec, "Core": core_d, "Shell": shell_d, **shapes,
            "Shape": {"oneOf": [{"$ref": f"#/$defs/{n}"} for n in sorted(shapes)]}}


def _fitting_defs() -> dict:
    defs = {n: _dataclass(c, tag=("type", n)) for n, c in intent.FITTING_TYPES.items()}
    defs["Fitting"] = {"oneOf": [{"$ref": f"#/$defs/{n}"} for n in sorted(intent.FITTING_TYPES)]}
    return defs


def _equipment_defs() -> dict:
    return {
        "Drum": _dataclass(Drum),
        "Nozzle": _dataclass(Nozzle),
        "OnShell": _dataclass(OnShell, tag=("type", "shell")),
        "OnHead": _dataclass(OnHead, tag=("type", "head")),
        "Location": {"oneOf": [{"$ref": "#/$defs/OnShell"}, {"$ref": "#/$defs/OnHead"}]},
    }


def _assembly_defs() -> dict:
    index = {"type": "integer", "minimum": 0}
    frame = {"type": "object", "title": "Frame", "description": "an interface's pose",
             "properties": {k: {"$ref": "#/$defs/Vector3", "x-unit": u, "description": d}
                            for k, u, d in (("position", "length", "centre of the face"),
                                            ("normal", "1", "unit normal, along the flow"),
                                            ("up", "1", "unit up, across the face"))},
             "required": ["position", "normal", "up"], "additionalProperties": False}
    inlet = {"type": "object", "title": "Inlet",
             "description": "the first interface: its frame and spec, and the drum nozzle it "
                            "starts from, if any",
             "properties": {**frame["properties"], "spec": {"$ref": "#/$defs/PipeSpec"},
                            "nozzle": {"type": "object", "properties": {
                                "drum": {"$ref": "#/$defs/Drum"}, "name": {"type": "string"}},
                                "required": ["drum", "name"], "additionalProperties": False}},
             "required": ["position", "normal", "up", "spec"], "additionalProperties": False}
    edge = {"type": "object", "title": "Edge",
            "description": "one add, close or prepend, in order: the fitting and where it "
                           "attaches (interfaces are numbered in creation order)",
            "properties": {
                "fitting": {"$ref": "#/$defs/Fitting"},
                "label": {"type": "string", "description": "the fitting's name"},
                "source": {**index, "description": "add: the interface it starts from"},
                "close": {"type": "array", "prefixItems": [index, index], "minItems": 2,
                          "maxItems": 2, "items": False,
                          "description": "close: the two interfaces it joins"},
                "prepend": {"const": True, "description": "prepend: before the inlet"},
                "frames": {"type": "object", "additionalProperties": {"$ref": "#/$defs/Frame"},
                           "description": "outlet frames that differ from the fitting's "
                                          "own placement, by port number"}},
            "required": ["fitting"], "additionalProperties": False,
            "oneOf": [{"required": ["source"]}, {"required": ["close"]},
                      {"required": ["prepend"]}]}
    assembly = {
        "type": "object", "title": "Assembly", "description": _summary(intent),
        "properties": {
            "format": {"const": intent.FORMAT},
            "version": {"const": intent.VERSION,
                        "description": "the description's version; older ones load through "
                                       "intent.upgrade()"},
            "inlet": {"$ref": "#/$defs/Inlet"},
            "edges": {"type": "array", "items": {"$ref": "#/$defs/Edge"}},
            "names": {"type": "object", "additionalProperties": {"type": "string"},
                      "description": "interface names, by interface number"},
            "tail": {"anyOf": [index, {"type": "null"}],
                     "description": "the interface the next add continues from"},
            "equipment": {"type": "array", "items": index,
                          "description": "interfaces that are equipment faces"},
            "lc": {"type": "number", "exclusiveMinimum": 0, "x-unit": "length",
                   "description": "characteristic length for GMSH"},
            "axial_cell": {"type": "number", "exclusiveMinimum": 0, "x-unit": "length",
                           "description": "axial cell size that n_layers=None resolves from"}},
        "required": ["format", "version", "inlet", "edges"], "additionalProperties": False}
    return {"Vector3": _VECTOR, "Frame": frame, "Inlet": inlet, "Edge": edge,
            "Assembly": assembly}


def _defs() -> dict:
    """Every ``$defs`` entry: one builder per registry."""
    defs: dict = {}
    for build in (_spec_defs, _fitting_defs, _equipment_defs, _assembly_defs):
        defs.update(build())
    return defs


def schema() -> dict:
    """The JSON Schema (draft 2020-12) of an ``Assembly.to_dict()``
    description at the current ``intent.VERSION``.  ``$defs`` holds the
    spec, each fitting type, the shapes and the equipment, which validate
    on their own as ``{"$ref": "#/$defs/<name>"}`` inside this document;
    ``x-limits`` holds ``limits.LIMITS``."""
    return {
        "$schema": DIALECT,
        "$id": f"urn:hexmesh:{intent.FORMAT}:{intent.VERSION}",
        "title": f"{intent.FORMAT} description, version {intent.VERSION}",
        "x-version": intent.VERSION,
        "$ref": "#/$defs/Assembly",
        "$defs": _defs(),
        "x-limits": {n: {"value": _plain(l.value), "unit": l.unit, "kind": l.kind,
                         "doc": l.doc} for n, l in limits.LIMITS.items()},
    }


def dumps() -> str:
    """:func:`schema` as deterministic JSON text (sorted keys)."""
    return json.dumps(schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
