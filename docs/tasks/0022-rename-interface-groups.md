# 0022 — Rename material-interface groups to `interface_<inner>_<outer>`

- **Status:** done
- **Decision:** [0013 — OpenFOAM output: group names and boundary roles](../decisions/0013-openfoam-group-names-and-boundary-roles.md)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  hexmesh's `<a>_to_<b>` interface group names collide with the
patch names `splitMeshRegions` creates, which silently corrupts CHT
splits (task 0005; `docs/integrations/openfoam.md`, Known quirks).
Decision 0013 renames them to hexmesh-owned names.

**Where.**
- `hexmesh/core/cross_section.py:179–187`: `interface_names()`.
- `hexmesh/assembly/blocks.py:420`: the tee's block layout builds
  `f"{m0}_to_{m1}"` itself.
- `hexmesh/core/region.py:18,78,82`: a default label `"{a}_to_{b}"`.
  Check whether anything still uses `region.py` after decision 0004.  If
  it is dead, say so under *Agent notes* rather than deleting it here.
- `hexmesh/assembly/assembler.py`: the `write_openfoam` docstring.
- `hexmesh/io/writers/openfoam.py:17`: its docstring says interface
  labels match `{regionA}_to_{regionB}`.
- `hexmesh/examples/insulated_pipe.py:7`; `API.md`, `README.md`.
- Tests: `tests/test_openfoam_output.py:70,90` (hexmesh group names) and
  `tests/test_assembly.py:212`.  **Not** lines 131–135: those assert
  `splitMeshRegions`' own `mappedWall` names, which stay.

**Do.**
1. One helper, e.g. `interface_group_name(inner, outer) -> str` →
   `f"interface_{inner}_{outer}"`, with materials in **inner → outer**
   order of the layer stack.  Use it in `interface_names()` and in
   `blocks.py`.  For the tee, check that `m0`/`m1` follow the same
   inner → outer order, so a material pair gets one name everywhere.
2. Validate material names so generated names stay within
   `[A-Za-z0-9_]`.  If `PipeSpec` already restricts layer names, note
   that.  Otherwise reject other characters in `PipeSpec` with a message
   naming the layer.
3. Update the docstrings and docs listed above.  `write_openfoam`'s
   docstring should say interfaces are left out by default because the
   split rebuilds them as `mappedWall`, not because of a name clash.
4. Make `interfaces=True` safe: the OpenFOAM test
   (`test_openfoam_cht_split`, which runs when OpenFOAM is present) gets
   a variant **with** interfaces kept.  It asserts that the split still
   gives correct `mappedWall` pairs (864 faces each on the insulated
   pipe), and that the `interface_*` faceZones exist.

**Accept.**
- No `_to_` group names are produced by hexmesh (a test greps the
  physical names of the kit cases with more than one layer).
- `test_openfoam_cht_split` passes with interfaces both omitted and
  kept.
- Full suite: no new failures.

**Out of scope.**  Boundary retyping (task 0023).  Changing
`splitMeshRegions`' names.

## Agent notes

- **Helper:** `hexmesh.core.cross_section.interface_group_name(inner,
  outer)` → `interface_<inner>_<outer>`.  Used by
  `LayeredCrossSection.interface_names()` (every sweep) and by
  `BlockLayout.realise`.
- **Tee order.**  `BlockLayout` is used only by the tee, and the tee is
  single-material, so `blocks.py` produces no interface groups today.
  Its pair came from block order, which is arbitrary, so `realise` now
  takes `layer_order` and sorts each pair inner → outer by it, and
  `Tee.fill` passes `spec.layer_names`.  A future multi-layer tee then
  names a pair the same way a sweep does.
- **`core/region.py` is dead.**  `MaterialGraph` is reachable only
  through `PipeSpec.graph` / `BundleSpec.graph`, and nothing calls
  either (legacy, decision 0004).  It is not deleted; its default label
  now uses the helper, so it can't drift.
- **Layer names were unrestricted.**  `PipeSpec.core`, `.shell` and
  `.square_shell` now reject names outside `[A-Za-z0-9_]`, with a
  `ValueError` naming the layer.
- **Docs and docstrings:** `write_openfoam` now says interfaces are left
  out because the split rebuilds them as `mappedWall`.  Also updated:
  `io/writers/openfoam.py`, `examples/insulated_pipe.py`, the README
  table and OpenFOAM paragraph, and the API naming list.
- **`interfaces=True` is now safe.**  `test_openfoam_cht_split` is
  parametrised on `interfaces`.  Both variants give `mappedWall` pairs
  of equal face counts on all four interface sides, and `insulation_wall`
  stays a `patch`.  With interfaces kept, the base mesh has both
  `interface_*` faceZones; without, it has none.  This test pipe has
  4 × 3 × 4 = 48 faces per cylindrical surface, so the 864 in the task
  (the insulated-pipe example) does not apply; the test asserts equality
  across the sides instead.
- **Shared machine.**  Task 0024's working-tree `pyproject.toml` makes
  plain `pytest` run `-n auto -m 'not openfoam'`, so the OpenFOAM tests
  need an explicit `-m openfoam` run (done; both pass).  My task-0009
  commit `086f294` included 0024's `@pytest.mark.openfoam` line on
  `test_openfoam_cht_split`, because it was already in that file; its
  registration is still in 0024's uncommitted `pyproject.toml`.

## Questions for design

_None._

## Outcome

- **Files:**
  - `core/cross_section.py`: `interface_group_name`;
  - `assembly/blocks.py`: `realise(layer_order)`;
  - `assembly/tee.py`;
  - `core/region.py`;
  - `core/spec.py`: `_check_layer_name`;
  - `assembly/assembler.py`, `io/writers/openfoam.py` and
    `examples/insulated_pipe.py` (docstrings);
  - docs: `README.md`, `API.md`;
  - tests: new `tests/test_group_names.py` (one test per multi-layer kit
    case, plus the helper and layer-name tests), `test_openfoam_output.py`
    (new names; CHT split ×2) and `test_assembly.py`.
- **Accept:**
  - no `_to_` group names in any multi-layer kit case;
  - the CHT split passes with interfaces both omitted and kept.
- **Breaking:** `<a>_to_<b>` group names are now
  `interface_<inner>_<outer>` (decision 0013 consequence; no changelog
  exists yet).
- **Tests:** 544 passed (default run, `-n auto`, OpenFOAM deselected) + 2 passed (`-m openfoam`), 0 failed.
