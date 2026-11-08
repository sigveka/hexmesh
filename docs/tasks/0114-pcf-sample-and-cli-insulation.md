# 0114 — A committed PCF sample, and insulation from the `hexmesh` commands

- **Status:** ready (after 0113)
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
