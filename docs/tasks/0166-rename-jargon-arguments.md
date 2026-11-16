# 0166 — Rename the mesh-jargon names

- **Status:** ready (after 0164)
- **Decision:** [0053](../decisions/0053-api-hardening-before-freeze.md), amendment item 5 (the table of names)
- **Depends on:** 0164.
- **Blocks:** 0165, the 0.8.0 tag.

Ground rules for all tasks: [README](README.md#ground-rules).

**Do.**
1. **Rename by the decision's table**, with no aliases: `nang` →
   `n_arc`, `nang_w`/`nang_h` → `n_width`/`n_height`, `nrad` →
   `n_radial`, `mprg` → `radial_grading`, `mbmp` → `arc_bump`; remove
   `lc` (and its uses: it doesn't affect the mesh; check that no mesh
   changes).  Arguments, attributes and properties, the description's
   fields, the schema, limits' names, error-code `where` fields and
   messages, the CLI's JSON, the advisor's output, the manifest.
2. **Error codes containing an old name** are renamed; list each old →
   new in the CHANGELOG.
3. **Saved descriptions:** old field names migrate on load (a version
   bump with a migration test over one saved description per example).
4. **Internal names** may keep the old spelling where renaming isn't
   worth it; nothing public does.  An architecture test: none of the
   old names appears in `docs/api-1.0.json`, the schema, or a public
   docstring.
5. Docs (README, API.md, GUIDE, the gallery's text), examples
   (byte-identical meshes), `validation/` drivers, the inventory,
   CHANGELOG *Breaking*.  Tell the design session when it lands:
   CLAUDE.md and the decisions' future text use the new names.

**Accept.**  The architecture test; the migration test; examples
byte-identical; full suite and CI green.

## Agent notes

## Questions for design

## Outcome
