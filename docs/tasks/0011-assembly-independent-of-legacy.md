# 0011 — Assembly independent of legacy code

- **Status:** done
- **Decision:** [0004 — Retire the legacy API](../decisions/0004-retire-legacy-api.md)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `hexmesh/assembly` cannot survive deleting legacy code (task
0017), because it still imports from it.

**Where.**
- `assembly/corners.py:24` imports
  `connectors.fittings._connect_layer_aligned`, which uses `_extract_geom`
  and `_curve_endpoints` (`fittings.py:325`, `:375`, `:741`).
- `assembly/assembler.py:33` imports `network.QualityReport` and
  `RegionQuality`.
- `assembly/interface.py:26` imports `core.cursor.Cursor` and
  `_perpendicular`; `Interface.cursor` is unused by the assembly.
- `assembly/fittings.py:24` imports `core.cursor._rodrigues`.

**Do.**
1. Move `_connect_layer_aligned` and the helpers it needs into
   `assembly/corners.py`.  Use `corners.curve_endpoints` there, not the
   legacy `_curve_endpoints` (task 0000).
2. Move `QualityReport` and `RegionQuality` into a new
   `assembly/quality.py`.  Keep `hexmesh.network` working by re-exporting
   them from there until task 0017.
3. Move `_rodrigues` and `_perpendicular` into `assembly/interface.py`.
   Drop `Interface.cursor`.
4. Legacy code may import the moved pieces back from `assembly`.
   `assembly` must not import `connectors`, `network` or `model`.

**Accept.**
- `grep -rnE "^from \.\.(connectors|network|model)|core\.cursor|connectors\." hexmesh/assembly`
  finds nothing.  (Refined: the original pattern also matched
  `gmsh.model`.)
- New test: with `hexmesh.connectors`, `hexmesh.network` and
  `hexmesh.model` blocked in `sys.modules`, importing `hexmesh.assembly`
  and meshing a `Straight` still work.
- No new failures.

## Agent notes

- `_connect_layer_aligned` needs only gmsh and `CircleShape`, not
  `_extract_geom` or `_curve_endpoints` (correspondence is passed in).  It
  moved unchanged as `corners.connect_aligned`.  Legacy
  `fittings._connect_layer` imports it back lazily, inside the function,
  to avoid an import cycle through `hexmesh.assembly`.
- `rotate` and `perpendicular` are public in `assembly/interface.py`.  The
  new-code tests (`test_blocks`, `test_corners`, the kit) use `rotate`.
  `core/cursor.py` keeps its own copies for legacy.
- **Found by the new test:** `hexmesh/core/__init__.py` imported
  `core.cursor` eagerly, so any `hexmesh.core` import loaded the legacy
  cursor.  `Cursor`/`Plane` are now loaded lazily (module `__getattr__`);
  `from hexmesh.core import Cursor` still works for legacy.
- `core/region.py` is not legacy: `PipeSpec` uses `MaterialGraph`.

## Questions for design

## Outcome

- **Files:**
  - `assembly/corners.py` (`connect_aligned`);
  - `assembly/quality.py` (new);
  - `assembly/interface.py` (`rotate`, `perpendicular`; `Frame.cursor`
    removed);
  - `assembly/fittings.py`, `assembly/assembler.py`;
  - `core/__init__.py` (lazy legacy export);
  - legacy re-imports in `connectors/fittings.py` and `network.py`;
  - `tests/test_assembly_standalone.py` (new): runs in a subprocess with
    `hexmesh.connectors`, `hexmesh.network`, `hexmesh.model` and
    `hexmesh.core.cursor` blocked, and meshes a `Straight`;
  - test imports switched to `rotate`.
- **Tests:** 457 passed, 10 failed (the known `TestYJunctionQuality`
  failures), 4 xfailed.
- **Follow-up:** none.  `core/cursor.py` goes in 0017.
