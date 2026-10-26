"""
Boundary roles for OpenFOAM cases (decision 0013, docs/tasks/0023).

``gmshToFoam`` writes every boundary patch as ``type patch;``.
``Assembly.write_openfoam`` therefore writes a role manifest next to the
``.msh``, and :func:`apply_boundary_roles` retypes the walls of the
converted case from it, in plain Python (no OpenFOAM process).

Manifest (``<stem>.roles.json``)::

    {"format": 1,
     "groups": {"fluid": "volume", "fluid_inlet": "open_end",
                "fluid_wall": "wall", "interface_fluid_steel": "interface"},
     "not_written": ["interface_fluid_steel"]}

Roles come from the assembly graph, never from group names.
``not_written`` lists groups that are in the manifest but were left out of
the ``.msh`` (material interfaces, by default).

A wall patch is written the way OpenFOAM's own tools write one (checked
against ``blockMesh`` v1912)::

    type            wall;
    inGroups        1(wall);
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import warnings
from pathlib import Path

FORMAT = 1
ROLES = ("volume", "open_end", "wall", "interface")


def roles_path(msh_path) -> Path:
    """``case/pipe.msh`` → ``case/pipe.roles.json``."""
    p = Path(msh_path)
    return p.with_name(p.stem + ".roles.json")


def write_roles(path, groups: dict[str, str], not_written=()) -> None:
    """Write a role manifest (indented JSON, sorted keys)."""
    bad = {g: r for g, r in groups.items() if r not in ROLES}
    if bad:
        raise ValueError(f"unknown roles {bad}; roles are {ROLES}")
    data = {"format": FORMAT, "groups": dict(groups),
            "not_written": sorted(not_written)}
    _atomic_write(Path(path), json.dumps(data, indent=2, sort_keys=True) + "\n")


def read_roles(path_or_dict) -> dict:
    """A manifest from a path or an already-loaded dict, checked."""
    if isinstance(path_or_dict, dict):
        data = path_or_dict
    else:
        data = json.loads(Path(path_or_dict).read_text(encoding="utf-8"))
    if data.get("format") != FORMAT:
        raise ValueError(f"unsupported role manifest format {data.get('format')!r}")
    return data


# ---------------------------------------------------------------------------
# constant/polyMesh/boundary
# ---------------------------------------------------------------------------

_TYPE = re.compile(r"^(?P<indent>[ \t]*)type(?P<gap>[ \t]+)(?P<value>\w+)[ \t]*;[ \t]*$", re.M)
_PHYS = re.compile(r"^(?P<lead>[ \t]*physicalType[ \t]+)\w+(?P<tail>[ \t]*;)", re.M)
_GROUPS = re.compile(r"^(?P<lead>[ \t]*inGroups[ \t]+)(?P<n>\d+)\((?P<items>[^)]*)\)", re.M)


def _skip(text: str, i: int) -> int:
    """Skip whitespace and comments."""
    while i < len(text):
        if text[i].isspace():
            i += 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = len(text) if j < 0 else j + 1
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = len(text) if j < 0 else j + 2
        else:
            return i
    return i


def _entries(text: str):
    """Yield ``(name, body_start, body_end)`` for each patch dictionary.

    The body is the text between the patch's ``{`` and its matching ``}``.
    """
    i = _skip(text, text.index("}", text.index("FoamFile")) + 1)
    m = re.compile(r"\d+").match(text, i)          # patch count
    if m:
        i = _skip(text, m.end())
    if not text.startswith("(", i):
        raise ValueError("boundary file: patch list '(' not found")
    i += 1
    while True:
        i = _skip(text, i)
        if text.startswith(")", i):
            return
        m = re.compile(r"[^\s{}()]+").match(text, i)
        if not m:
            raise ValueError(f"boundary file: patch name expected at offset {i}")
        name = m.group()
        i = _skip(text, m.end())
        if not text.startswith("{", i):
            raise ValueError(f"boundary file: '{{' expected after patch {name}")
        start, depth = i + 1, 1
        i += 1
        while depth:
            c = text[i]
            depth += (c == "{") - (c == "}")
            i += 1
        yield name, start, i - 1


def _as_wall(body: str) -> str:
    """Retype one patch body to a wall, touching only the typing lines."""
    m = _TYPE.search(body)
    if not m:
        raise ValueError("patch entry without a 'type' line")
    body = body[:m.start("value")] + "wall" + body[m.end("value"):]
    body = _PHYS.sub(lambda p: p.group("lead") + "wall" + p.group("tail"), body)
    g = _GROUPS.search(body)
    if g:
        items = g.group("items").split()
        if "wall" not in items:
            items.append("wall")
            body = (body[:g.start("n")] + f"{len(items)}({' '.join(items)})"
                    + body[g.end():])
    else:
        m = _TYPE.search(body)
        line_end = body.index("\n", m.end()) + 1 if "\n" in body[m.end():] else len(body)
        # keep the value column of the 'type' line (OpenFOAM pads keywords to 16)
        gap = " " * max(1, len("type") + len(m.group("gap")) - len("inGroups"))
        body = (body[:line_end] + f"{m.group('indent')}inGroups{gap}1(wall);\n"
                + body[line_end:])
    return body


def retype_boundary_text(text: str, roles: dict[str, str]) -> tuple[str, list, list]:
    """Retype the ``boundary`` file *text*.

    Returns ``(new_text, retyped, unknown)``.  Patches with role ``wall``
    become ``wall``; every other byte is kept.  ``mappedWall`` patches
    (made by ``splitMeshRegions``) are left alone and are not reported as
    unknown; other patches missing from *roles* are reported.
    """
    out, pos, retyped, unknown = [], 0, [], []
    for name, a, b in _entries(text):
        body = text[a:b]
        m = _TYPE.search(body)
        kind = m.group("value") if m else None
        role = roles.get(name)
        if kind == "mappedWall":
            continue
        if role is None:
            unknown.append(name)
        elif role == "wall" and kind != "wall":
            out.append(text[pos:a])
            out.append(_as_wall(body))
            pos = b
            retyped.append(name)
    out.append(text[pos:])
    return "".join(out), retyped, unknown


def apply_boundary_roles(case_dir, roles, region: str | None = None) -> list[str]:
    """Retype the walls of an OpenFOAM case from a role manifest.

    *roles* is a manifest dict or the path of a ``.roles.json``.  The file
    is ``constant/polyMesh/boundary``, or ``constant/<region>/polyMesh/
    boundary`` after ``splitMeshRegions``.  ``wall`` patches get ``type
    wall;`` and ``inGroups 1(wall);``; open ends stay ``patch``;
    ``mappedWall`` patches are untouched.  Patches missing from the
    manifest are left alone, with one warning naming them.  The file is
    rewritten atomically.  Returns the retyped patch names.
    """
    groups = read_roles(roles)["groups"]
    sub = Path("constant") / (region or "") / "polyMesh" / "boundary"
    path = Path(case_dir) / sub
    text = path.read_text(encoding="utf-8")
    new, retyped, unknown = retype_boundary_text(text, groups)
    if unknown:
        warnings.warn(f"{path}: patches not in the role manifest, left as they are: "
                      f"{', '.join(unknown)}", stacklevel=2)
    if new != text:
        _atomic_write(path, new)
    return retyped


def apply_boundary_roles_to_regions(case_dir, roles) -> dict[str, list[str]]:
    """:func:`apply_boundary_roles` for every region under ``constant/``.

    After ``splitMeshRegions`` that is each ``constant/<region>``; for an
    unsplit case, ``constant/polyMesh`` itself (key ``None``).
    """
    constant = Path(case_dir) / "constant"
    regions = sorted(d.name for d in constant.iterdir()
                     if d.is_dir() and (d / "polyMesh" / "boundary").exists())
    if not regions:
        return {None: apply_boundary_roles(case_dir, roles)}
    return {r: apply_boundary_roles(case_dir, roles, region=r) for r in regions}


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
