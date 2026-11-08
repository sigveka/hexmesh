# 0114 — A committed PCF sample, and insulation from the `hexmesh` commands

- **Status:** done
- **Decision:** [0032 — Network interchange](../decisions/0032-network-interchange.md) (the PCF reader); [0040 — Agents for users](../decisions/0040-user-agents-network-design-and-resolution.md) (the CLI)
- **Depends on:** 0098, 0102 (done).  Before the launch post.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The README's new "From plant data (PCF)" section (design,
2026-11-08) shows `read_pcf("line.pcf").to_assembly(pipe,
insulation=True)`, but the repository holds no PCF file a reader can run
it on.  And the `hexmesh` commands read a PCF with `--spec`, but can't
ask for the file's insulation: only Python's `insulation=True` can, so an
agent using the commands gets bare pipes.

Design checked on a scratch line (2026-11-08): a 100 mm header with a
reducing tee to a 50 mm branch, an elbow, nang 8, a 4 mm steel shell:
19 072 cells bare; with insulation (50 mm) and a 0.25 m branch stub,
22 848 cells, one quality warning at the tee (SJ 0.258, r/R 0.5).  With
a 0.1 m stub the insulated tee is rejected (`branch_length must exceed
the turning station's height 0.1435`).  With an equal tee,
`equal_tee_unsupported`, naming `line.pcf:11`.

**Where.**  `hexmesh/examples/plant/` (or `applications/`: say which and
why) for the sample and its example module; `hexmesh/agent/_commands.py`
and `cli.py`; the manifest; `tests/test_readme.py`;
`docs/GALLERY.md` (through `docs/gallery/build.py`); `API.md`,
`docs/GUIDE.md`'s plant-data section; `CHANGELOG.md`.

**Do.**
1. **The sample:** a small, realistic PCF line, written for hexmesh (no
   vendor file): one pipeline, insulated, with a reducing tee, an elbow,
   a concentric reducer, a bare valve or flange (so `insulation_end`
   appears), and an equipment nozzle end.  Shipped as package data, so
   `pip install` users have it.
   - An example module that reads it and writes the mesh, in the
     gallery like the others (image, numbers).
2. **The README:** the PCF section's code reads the shipped sample by a
   path a user can type (e.g. through the example's own `main`, or
   `hexmesh.examples.plant.SAMPLE`), so it runs as written.  Keep the
   section's prose; change only the code and its file name.
   - `tests/test_readme.py`: the section's code runs (no gmsh: it stops
     before `write_openfoam`, or patches it), and its cell count matches
     the example's.
   - The quoted `equal_tee_unsupported` error stays true: a test feeds an
     equal-tee variant of the sample and checks the code and the
     `file:line` form the README shows.
3. **`--insulation`** on every `hexmesh` command that reads a network,
   for PCF input: the same meaning as `to_assembly(insulation=True)`.
   - On a JSON description it's an input error (`cli_input_unreadable`
     or a new code), with a hint: insulation is part of the description.
   - The manifest lists it (from the parser, as today).
4. **Docs:** API.md's CLI table and the GUIDE's plant-data section name
   the sample and `--insulation`.

**Accept.**
- `python3 -m hexmesh.examples.plant.<name>` writes the mesh; the
  gallery shows it.
- The README's PCF code runs as written, checked by a test.
- `hexmesh estimate <sample> --spec … --insulation` gives the insulated
  count, equal to Python's; without the flag, the bare count.
- Full suite: no new failures (check memory first).

**Out of scope.**  Equal tees (planned through the wye-family layout),
crosses, and angled tees in networks (task 0103).

## Agent notes

- **Where:** `hexmesh/examples/applications/`.  The line starts at an
  equipment nozzle, beside `drum_nozzle`, and the category's docstring
  calls applications "the examples closest to a real model".  A new
  `plant` category would hold one example.
- **The sample, `pcf_line.pcf`:** pipeline A-100, 100 mm, 50 mm
  insulation, millimetres.
  - It runs from V-101's nozzle N1 through a pipe, a reducing tee to a
    50 mm branch (0.5 m), a pipe, an elbow (R 300 mm), a 100 → 80 mm
    concentric reducer, a pipe, a bare flanged valve (`SKEY VVFL`, no
    `INSULATION ON`) and a pipe.
  - The pipeline is named A-100 so the README's prose (`A_100_end3`,
    `V_101_N1`) names the sample's own patches.
  - Package data: `"hexmesh.examples.applications" = ["*.pcf"]`.  A
    wheel built from the tree contains it (checked with `pip wheel`).
- **Insulation ends inside the valve.**  The valve's stack changes are
  at its layers 1 and 5 of 6, so the insulation stops one cell inside
  it from each side.  This is what the GUIDE says: "the neighbouring
  straight component" is the valve.
- **The README:**
  - The Python block imports `SAMPLE` and prints `# 35712`.  Its write
    is now `pcf_line.msh`.
  - The quoted error was out of date: it said `line.pcf:11` and
    `[1.15 0. 0.]`.  It's now exactly what the sample with an equal
    branch, saved as `line.pcf`, gives: `line.pcf:19`, `[1.1 0.  0. ]`
    (NumPy's spacing).  Its `where` is a subset of the real one, which
    also has `format` and `record_id`.
  - Prose unchanged.  The CLI sentence still names a user's own
    `line.pcf` and `sizes.json`.
- **`--insulation` on a description** raises the existing
  `cli_input_unreadable`, `where: {field: "insulation"}`, with a hint,
  rather than a new code.  It matches how a missing `--spec` is reported.
- **Gallery:** `--only` restamps the gallery-wide date and commit in
  `metrics.json` (entries have none of their own).  So a `pcf_line`-only
  run made the README's insulated_tee row claim 2026-11-08.  I re-ran
  insulated_tee in the same run so that claim holds.  Its numbers are
  unchanged except the build time, 7.2 → 8.0 s at load 1.5.
- **The first example read from a file** reached
  `test_describe_every_example_without_gmsh`'s check that
  `describe(asm)` equals `describe(asm.to_dict())`.
  - It failed: the live tee warning names `pcf_line.pcf:19`, the saved
    copy's doesn't.
  - That's by design.  Task 0096's answer says `origin` is diagnostic
    only, never saved, and `from_dict` assemblies have none.
  - The test now asserts the two differ when the example has origins,
    and match once the origins are cleared.  No code changed.

## Outcome

- **Files:**
  - new: `hexmesh/examples/applications/pcf_line.pcf`, `pcf_line.py`,
    `docs/gallery/img/pcf_line.png`, `pcf_line_section.png`;
  - `hexmesh/examples/__init__.py` (registered), `pyproject.toml`
    (package data);
  - `hexmesh/agent/_commands.py`, `cli.py` (`--insulation`);
  - `README.md` (the PCF code and quote; the gallery's metrics row),
    `docs/GALLERY.md`, `docs/gallery/metrics.json`, `API.md`,
    `docs/GUIDE.md`, `CHANGELOG.md`;
  - tests: `tests/test_readme.py` (+3), `tests/test_agent_advise.py`
    (+3), `tests/test_agent_manifest.py` (the argument set).
- **Measured** (nang 8, 4 mm steel):
  - 28 800 cells bare, 35 712 insulated; Python, `hexmesh estimate` and
    the example agree.
  - Mesh: min SICN 0.062, 9.1 s.
  - One quality warning, the tee's predicted SJ 0.258 (r/R 0.5), naming
    `pcf_line.pcf:19`.  It matches design's scratch line (0.258).
  - Patches: `*_V_101_N1`, `*_A_100_end2`, `*_A_100_end3`,
    `insulation_end`, the walls and the interfaces.
- **Tests:**
  - the full suite: 3747 passed, 1 failed, 15 skipped;
  - the failure is the describe check above.  After the test fix
    `tests/test_agent_describe.py` passes (66).  The full suite wasn't
    rerun for a one-test change.
  - `tests/test_agent_describe.py` also changed (the provenance case).
- **Proposed follow-up:** give `metrics.json` per-entry dates, or have
  `--only` keep the meta, so a partial gallery run can't restamp the
  README's numbers.
